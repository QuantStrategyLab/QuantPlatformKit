"""Lower-tail conditional correlation gate for Phase 11 BREADTH (research-only).

Evaluates whether a candidate sleeve's lower-tail conditional Pearson
correlation against a drawdown benchmark (such as ``QQQ`` or ``TQQQ``/``SOXL``)
clears a strict threshold on both its point estimate and its one-sided
stationary-bootstrap upper confidence bound.

Requires numpy from the optional ``research`` extra; numpy is imported lazily
via :func:`quant_platform_kit.research_stats.bootstrap._numpy` so importing
``quant_platform_kit.research_stats`` never requires it.

This module is research-only: it never reads accounts, calls brokers, places
orders, writes runtime risk policy, or grants paper/shadow/live authority.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

from quant_platform_kit.research_stats._validation import (
    ResearchInputError,
    finite_float,
    positive_int,
    simple_returns,
)
from quant_platform_kit.research_stats.bootstrap import (
    METHOD,
    _MIN_RESAMPLES,
    _numpy,
    _stationary_indices,
)
from quant_platform_kit.research_stats.sharpe_inference import (
    STATUS_COMPUTED,
    STATUS_UNCOMPUTABLE,
)


@dataclass(frozen=True)
class TailCorrelationResult:
    status: str
    method: str
    observations: int
    tail_observations: int
    tail_quantile: float | None
    confidence: float | None
    max_tail_correlation: float | None
    mean_block_length: float | None
    n_resamples: int | None
    seed: int | None
    estimate: float | None
    upper_confidence_bound: float | None
    passes_gate: bool
    reason_code: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "method": self.method,
            "observations": self.observations,
            "tail_observations": self.tail_observations,
            "tail_quantile": self.tail_quantile,
            "confidence": self.confidence,
            "max_tail_correlation": self.max_tail_correlation,
            "mean_block_length": self.mean_block_length,
            "n_resamples": self.n_resamples,
            "seed": self.seed,
            "estimate": self.estimate,
            "upper_confidence_bound": self.upper_confidence_bound,
            "passes_gate": self.passes_gate,
            "reason_code": self.reason_code,
        }


def _failed(
    reason: str,
    *,
    observations: int = 0,
    tail_observations: int = 0,
    tail_quantile: float | None = None,
    confidence: float | None = None,
    max_tail_correlation: float | None = None,
    mean_block_length: float | None = None,
    n_resamples: int | None = None,
    seed: int | None = None,
) -> TailCorrelationResult:
    return TailCorrelationResult(
        status=STATUS_UNCOMPUTABLE,
        method=METHOD,
        observations=observations,
        tail_observations=tail_observations,
        tail_quantile=tail_quantile,
        confidence=confidence,
        max_tail_correlation=max_tail_correlation,
        mean_block_length=mean_block_length,
        n_resamples=n_resamples,
        seed=seed,
        estimate=None,
        upper_confidence_bound=None,
        passes_gate=False,
        reason_code=reason,
    )


def _pearson_corr(np: Any, xs: Any, ys: Any) -> float | None:
    dx = xs - xs.mean()
    dy = ys - ys.mean()
    denom = float(math.sqrt(float(np.dot(dx, dx)) * float(np.dot(dy, dy))))
    if not math.isfinite(denom) or denom <= 0.0:
        return None
    corr = float(np.dot(dx, dy) / denom)
    if not math.isfinite(corr):
        return None
    return max(-1.0, min(1.0, corr))


def lower_tail_correlation_gate(
    candidate_returns: Iterable[object],
    benchmark_returns: Iterable[object],
    *,
    seed: int,
    mean_block_length: object = 5.0,
    n_resamples: int = 1000,
    tail_quantile: object = 0.10,
    confidence: object = 0.95,
    max_tail_correlation: object = 0.50,
    min_tail_observations: int = 10,
) -> TailCorrelationResult:
    """Evaluate point and stationary-bootstrap UCB lower-tail correlation.

    Lower-tail sessions are defined by ``benchmark_returns <= quantile(tail_quantile)``.
    The gate passes only when both the point correlation ``estimate`` and the
    one-sided stationary-bootstrap ``upper_confidence_bound`` are strictly less
    than ``max_tail_correlation``.
    """
    try:
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ResearchInputError("seed must be an explicit non-negative integer")
        cand = simple_returns(candidate_returns)
        bench = simple_returns(benchmark_returns)
        if len(cand) != len(bench):
            raise ResearchInputError("candidate_returns and benchmark_returns must have equal length")
        block = finite_float(mean_block_length, "mean_block_length")
        if block < 1.0:
            raise ResearchInputError("mean_block_length must be >= 1")
        resamples = positive_int(n_resamples, "n_resamples", minimum=_MIN_RESAMPLES)
        tail_q = finite_float(tail_quantile, "tail_quantile")
        if not 0.0 < tail_q < 1.0:
            raise ResearchInputError("tail_quantile must be in (0, 1)")
        level = finite_float(confidence, "confidence")
        if not 0.0 < level < 1.0:
            raise ResearchInputError("confidence must be in (0, 1)")
        max_corr = finite_float(max_tail_correlation, "max_tail_correlation")
        if not -1.0 < max_corr <= 1.0:
            raise ResearchInputError("max_tail_correlation must be in (-1, 1]")
        min_tail_obs = positive_int(min_tail_observations, "min_tail_observations", minimum=2)
    except ResearchInputError:
        return _failed("invalid_input")

    n = len(cand)
    np = _numpy()
    cand_arr = np.asarray(cand, dtype=np.float64)
    bench_arr = np.asarray(bench, dtype=np.float64)

    threshold = float(np.quantile(bench_arr, tail_q))
    tail_mask = bench_arr <= threshold
    tail_count = int(tail_mask.sum())
    common = {
        "observations": n,
        "tail_observations": tail_count,
        "tail_quantile": tail_q,
        "confidence": level,
        "max_tail_correlation": max_corr,
        "mean_block_length": block,
        "n_resamples": resamples,
        "seed": seed,
    }
    if tail_count < min_tail_obs:
        return _failed("insufficient_tail_observations", **common)

    estimate = _pearson_corr(np, cand_arr[tail_mask], bench_arr[tail_mask])
    if estimate is None:
        return _failed("zero_variance", **common)

    rng = np.random.default_rng(seed)
    idx = _stationary_indices(np, rng, n, resamples, block)
    cand_paths = cand_arr[idx]
    bench_paths = bench_arr[idx]

    boot_thresholds = np.quantile(bench_paths, tail_q, axis=1, keepdims=True)
    boot_masks = bench_paths <= boot_thresholds
    boot_counts = boot_masks.sum(axis=1)
    if int(boot_counts.min()) < 2:
        return _failed("undefined_resample_correlation", **common)

    weights = boot_masks.astype(np.float64)
    cand_means = (cand_paths * weights).sum(axis=1, keepdims=True) / boot_counts[:, None]
    bench_means = (bench_paths * weights).sum(axis=1, keepdims=True) / boot_counts[:, None]
    dc = np.where(boot_masks, cand_paths - cand_means, 0.0)
    db = np.where(boot_masks, bench_paths - bench_means, 0.0)
    denom = np.sqrt((dc * dc).sum(axis=1) * (db * db).sum(axis=1))
    if not bool(np.all(np.isfinite(denom) & (denom > 0.0))):
        return _failed("undefined_resample_correlation", **common)

    boot_corrs = np.clip((dc * db).sum(axis=1) / denom, -1.0, 1.0)
    if not bool(np.all(np.isfinite(boot_corrs))):
        return _failed("undefined_resample_correlation", **common)

    ucb = float(np.quantile(boot_corrs, level))
    passes_gate = bool(estimate < max_corr and ucb < max_corr)
    return TailCorrelationResult(
        status=STATUS_COMPUTED,
        method=METHOD,
        observations=n,
        tail_observations=tail_count,
        tail_quantile=tail_q,
        confidence=level,
        max_tail_correlation=max_corr,
        mean_block_length=block,
        n_resamples=resamples,
        seed=seed,
        estimate=estimate,
        upper_confidence_bound=ucb,
        passes_gate=passes_gate,
    )
