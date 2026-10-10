"""Stationary block bootstrap confidence intervals (research-only).

Politis, D. N. and Romano, J. P. (1994), "The Stationary Bootstrap", JASA
89(428). Each resampled path is built from blocks with geometric lengths of
mean ``mean_block_length``; indices wrap around the sample end. This keeps
short-range serial dependence that an i.i.d. bootstrap would destroy, but it
is **not** a guarantee about future risk and does not correct for multiple
testing.

Requires numpy from the optional ``research`` extra; numpy is imported lazily
so that importing ``quant_platform_kit.research_stats`` never needs it.

The seed is mandatory: the same inputs, seed, block length and resample count
always reproduce the same interval.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from quant_platform_kit.research_stats._validation import (
    ResearchInputError,
    finite_float,
    positive_int,
    simple_returns,
)
from quant_platform_kit.research_stats.sharpe_inference import (
    STATUS_COMPUTED,
    STATUS_UNCOMPUTABLE,
)

METHOD = "stationary_bootstrap"
SUPPORTED_STATISTICS = ("log_growth", "sharpe", "max_drawdown")
_MIN_OBSERVATIONS = 2
_MIN_RESAMPLES = 100


def _numpy() -> Any:
    try:
        import numpy as np  # noqa: PLC0415 - optional research extra
    except ImportError as exc:  # pragma: no cover - exercised via subprocess test
        raise ImportError(
            "stationary_bootstrap_ci requires numpy; install 'quant-platform-kit[research]'"
        ) from exc
    return np


@dataclass(frozen=True)
class BootstrapInterval:
    statistic: str
    status: str
    estimate: float | None
    lower: float | None
    upper: float | None
    reason_code: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "statistic": self.statistic,
            "status": self.status,
            "estimate": self.estimate,
            "lower": self.lower,
            "upper": self.upper,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True)
class BootstrapResult:
    status: str
    method: str
    observations: int
    mean_block_length: float | None
    n_resamples: int | None
    seed: int | None
    confidence: float | None
    intervals: Mapping[str, BootstrapInterval] = field(default_factory=dict)
    reason_code: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "method": self.method,
            "observations": self.observations,
            "mean_block_length": self.mean_block_length,
            "n_resamples": self.n_resamples,
            "seed": self.seed,
            "confidence": self.confidence,
            "intervals": {k: v.to_dict() for k, v in self.intervals.items()},
            "reason_code": self.reason_code,
        }


def _stationary_indices(np: Any, rng: Any, n: int, n_resamples: int, mean_block_length: float) -> Any:
    p_new_block = 1.0 / mean_block_length
    starts = rng.integers(0, n, size=(n_resamples, n))
    new_block = rng.random((n_resamples, n)) < p_new_block
    new_block[:, 0] = True
    idx = np.empty((n_resamples, n), dtype=np.int64)
    idx[:, 0] = starts[:, 0]
    for t in range(1, n):
        idx[:, t] = np.where(new_block[:, t], starts[:, t], (idx[:, t - 1] + 1) % n)
    return idx


def _statistics(np: Any, paths: Any) -> dict[str, Any]:
    """Row-wise statistics; returns NaN where a statistic is undefined."""
    log_growth = np.log1p(paths).mean(axis=1)
    if paths.shape[1] >= 2:
        std = paths.std(axis=1, ddof=1)
        mean = paths.mean(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            sharpe = np.where(std > 0.0, mean / np.where(std > 0.0, std, 1.0), np.nan)
    else:
        sharpe = np.full(paths.shape[0], np.nan)
    equity = np.cumprod(1.0 + paths, axis=1)
    peak = np.maximum.accumulate(np.maximum(equity, 1.0), axis=1)
    max_drawdown = np.minimum((equity / peak - 1.0).min(axis=1), 0.0)
    return {"log_growth": log_growth, "sharpe": sharpe, "max_drawdown": max_drawdown}


def _failed(reason: str, observations: int = 0) -> BootstrapResult:
    return BootstrapResult(
        status=STATUS_UNCOMPUTABLE,
        method=METHOD,
        observations=observations,
        mean_block_length=None,
        n_resamples=None,
        seed=None,
        confidence=None,
        reason_code=reason,
    )


def stationary_bootstrap_ci(
    returns: Iterable[object],
    *,
    seed: int,
    mean_block_length: object,
    n_resamples: int = 1000,
    confidence: object = 0.95,
    statistics: Iterable[str] = SUPPORTED_STATISTICS,
) -> BootstrapResult:
    """Percentile CIs for per-period log growth, per-period Sharpe and MDD.

    - ``log_growth``: mean of ``log(1 + r)`` per period (not annualized).
    - ``sharpe``: mean / sample std (ddof=1) per period; rf/MAR removed by caller.
    - ``max_drawdown``: most negative drawdown including initial equity 1.

    A statistic whose point estimate or any resample is undefined (for example
    zero variance for Sharpe) is ``UNCOMPUTABLE`` for that statistic only.
    """
    try:
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ResearchInputError("seed must be an explicit non-negative integer")
        series = simple_returns(returns)
        block = finite_float(mean_block_length, "mean_block_length")
        if block < 1.0:
            raise ResearchInputError("mean_block_length must be >= 1")
        resamples = positive_int(n_resamples, "n_resamples", minimum=_MIN_RESAMPLES)
        level = finite_float(confidence, "confidence")
        if not 0.0 < level < 1.0:
            raise ResearchInputError("confidence must be in (0, 1)")
        requested = tuple(statistics)
        unknown = [s for s in requested if s not in SUPPORTED_STATISTICS]
        if unknown or not requested:
            raise ResearchInputError(f"unsupported statistics: {unknown or 'none'}")
    except ResearchInputError:
        return _failed("invalid_input")
    n = len(series)
    if n < _MIN_OBSERVATIONS:
        return _failed("insufficient_observations", n)
    if block > n:
        return _failed("block_longer_than_sample", n)

    np = _numpy()
    rng = np.random.default_rng(seed)
    data = np.asarray(series, dtype=np.float64)
    idx = _stationary_indices(np, rng, n, resamples, block)
    resampled = _statistics(np, data[idx])
    point = _statistics(np, data[np.newaxis, :])
    alpha = (1.0 - level) / 2.0

    intervals: dict[str, BootstrapInterval] = {}
    for name in requested:
        estimate = float(point[name][0])
        draws = resampled[name]
        if not math.isfinite(estimate):
            intervals[name] = BootstrapInterval(name, STATUS_UNCOMPUTABLE, None, None, None, "undefined_point_estimate")
            continue
        if not bool(np.all(np.isfinite(draws))):
            intervals[name] = BootstrapInterval(name, STATUS_UNCOMPUTABLE, estimate, None, None, "degenerate_resample")
            continue
        lower, upper = np.quantile(draws, [alpha, 1.0 - alpha])
        intervals[name] = BootstrapInterval(name, STATUS_COMPUTED, estimate, float(lower), float(upper))

    return BootstrapResult(
        status=STATUS_COMPUTED,
        method=METHOD,
        observations=n,
        mean_block_length=block,
        n_resamples=resamples,
        seed=seed,
        confidence=level,
        intervals=intervals,
    )
