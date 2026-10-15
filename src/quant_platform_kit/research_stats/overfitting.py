"""Probability of Backtest Overfitting via CSCV (research-only, stdlib only).

Bailey, D. H., Borwein, J. M., López de Prado, M. and Zhu, Q. J. (2017),
"The Probability of Backtest Overfitting", Journal of Computational Finance
20(4). Combinatorially Symmetric Cross-Validation (CSCV):

1. Arrange the per-period returns of **all N trials** on the **same dates**
   as a T × N matrix and split the rows into S contiguous, equal blocks
   (S even). Leading rows that do not fill a block are dropped and reported.
2. For each of the C(S, S/2) ways to choose S/2 blocks as in-sample (IS),
   the remaining blocks are out-of-sample (OOS).
3. Select the IS-best trial n* by the performance metric; compute its
   relative OOS rank ω = rank / (N + 1) (average ranks for ties) and the
   logit λ = ln(ω / (1 − ω)).
4. PBO = share of combinations with λ ≤ 0 (the IS winner is at or below the
   OOS median).

Performance metric: ``sharpe`` (per-period mean / sample std, ddof=1) or
``mean_log_growth`` (mean of log(1 + r)). IS-best ties pick the first trial in
input order and are counted in ``details["is_best_ties"]``.

Fail-closed: fewer than two trials, ragged/misaligned columns, odd or too few
blocks, blocks shorter than ``min_rows_per_block``, or any undefined block
metric (e.g. zero variance) return ``UNCOMPUTABLE`` with ``value=None``.
"""

from __future__ import annotations

import itertools
import math
from typing import Mapping, Sequence

from quant_platform_kit.research_stats._validation import (
    ResearchInputError,
    positive_int,
    simple_returns,
)
from quant_platform_kit.research_stats.sharpe_inference import (
    STATUS_COMPUTED,
    StatResult,
    _uncomputable,
)

PBO_METRICS = ("sharpe", "mean_log_growth")
MAX_SPLITS = 16  # C(16, 8) = 12,870 combinations bounds runtime.
_MIN_TRIALS = 2


def _block_sums(column: Sequence[float], rows: int, n_splits: int) -> list[tuple[float, float, float]]:
    """(sum, sum of squares, sum of log1p) per block."""
    out = []
    for b in range(n_splits):
        chunk = column[b * rows:(b + 1) * rows]
        out.append((math.fsum(chunk), math.fsum(x * x for x in chunk), math.fsum(math.log1p(x) for x in chunk)))
    return out


def _performance(stats: Sequence[tuple[float, float, float]], count: int, metric: str) -> float | None:
    total = math.fsum(s[0] for s in stats)
    if metric == "mean_log_growth":
        return math.fsum(s[2] for s in stats) / count
    squares = math.fsum(s[1] for s in stats)
    mean = total / count
    variance = (squares - count * mean * mean) / (count - 1)
    # Guard against round-off: treat relatively tiny variance as zero.
    if not math.isfinite(variance) or variance <= 1e-15 * max(1.0, squares / count):
        return None
    return mean / math.sqrt(variance)


def _average_rank(values: Sequence[float], index: int) -> float:
    """1-based ascending rank of values[index], averaging ties."""
    target = values[index]
    below = sum(1 for v in values if v < target)
    equal = sum(1 for v in values if v == target)
    return below + (equal + 1) / 2.0


def probability_of_backtest_overfitting(
    returns_by_trial: Mapping[str, Sequence[object]] | Sequence[Sequence[object]],
    *,
    n_splits: int = 16,
    metric: str = "sharpe",
    min_rows_per_block: int = 2,
) -> StatResult:
    """CSCV PBO over aligned per-period trial returns (all trials, incl. losers)."""
    name = "probability_of_backtest_overfitting"
    try:
        if metric not in PBO_METRICS:
            raise ResearchInputError(f"metric must be one of {PBO_METRICS}")
        splits = positive_int(n_splits, "n_splits", minimum=2)
        if splits % 2 or splits > MAX_SPLITS:
            raise ResearchInputError(f"n_splits must be even and <= {MAX_SPLITS}")
        min_rows = positive_int(min_rows_per_block, "min_rows_per_block", minimum=2)
        if isinstance(returns_by_trial, Mapping):
            labels = [str(k) for k in returns_by_trial.keys()]
            raw = list(returns_by_trial.values())
        elif isinstance(returns_by_trial, (str, bytes)):
            raise ResearchInputError("returns_by_trial must be a mapping or sequence of sequences")
        else:
            raw = list(returns_by_trial)
            labels = [str(i) for i in range(len(raw))]
        columns = [simple_returns(col, f"returns_by_trial[{labels[i]}]") for i, col in enumerate(raw)]
    except (ResearchInputError, TypeError) as exc:
        return _uncomputable(name, "invalid_input", message=str(exc))

    n_trials = len(columns)
    if n_trials < _MIN_TRIALS:
        return _uncomputable(name, "insufficient_trials", n_trials=n_trials, min_trials=_MIN_TRIALS)
    lengths = {len(c) for c in columns}
    if len(lengths) != 1:
        return _uncomputable(name, "trial_returns_not_aligned", lengths=sorted(lengths))
    total_rows = lengths.pop()
    rows = total_rows // splits
    if rows < min_rows:
        return _uncomputable(
            name, "insufficient_observations", observations=total_rows, n_splits=splits,
            min_rows_per_block=min_rows,
        )
    dropped = total_rows - rows * splits
    trimmed = [c[dropped:] for c in columns]  # drop oldest leading rows only
    blocks = [_block_sums(c, rows, splits) for c in trimmed]

    # Every single block must have a defined metric; otherwise some
    # combination could silently select from undefined values.
    for t, per_block in enumerate(blocks):
        for b in range(splits):
            if _performance([per_block[b]], rows, metric) is None:
                return _uncomputable(name, "undefined_performance", trial=labels[t], block=b)

    half = splits // 2
    lambdas: list[float] = []
    is_best_ties = 0
    for train in itertools.combinations(range(splits), half):
        test = [b for b in range(splits) if b not in train]
        is_perf: list[float] = []
        oos_perf: list[float] = []
        for per_block in blocks:
            p_is = _performance([per_block[b] for b in train], rows * half, metric)
            p_oos = _performance([per_block[b] for b in test], rows * half, metric)
            if p_is is None or p_oos is None:
                return _uncomputable(name, "undefined_performance", combination=list(train))
            is_perf.append(p_is)
            oos_perf.append(p_oos)
        best_value = max(is_perf)
        best = is_perf.index(best_value)
        if is_perf.count(best_value) > 1:
            is_best_ties += 1
        omega = _average_rank(oos_perf, best) / (n_trials + 1)
        lambdas.append(math.log(omega / (1.0 - omega)))

    overfit = sum(1 for lam in lambdas if lam <= 0.0)
    ordered = sorted(lambdas)
    mid = len(ordered) // 2
    median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0
    return StatResult(
        name=name,
        status=STATUS_COMPUTED,
        value=overfit / len(lambdas),
        details={
            "method": "cscv",
            "metric": metric,
            "n_trials": n_trials,
            "n_splits": splits,
            "rows_per_block": rows,
            "rows_dropped_leading": dropped,
            "n_combinations": len(lambdas),
            "logit_median": median,
            "is_best_ties": is_best_ties,
            "trial_labels": labels,
        },
    )
