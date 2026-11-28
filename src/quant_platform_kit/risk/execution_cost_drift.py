"""Pure-offline execution cost & slippage drift monitor (Roadmap P1 #1).

Compares observed fill prices and commissions against model assumptions without
broker, cloud, or network I/O. Breaching configured slippage or commission-ratio
bounds signals ``pause_promotion=True`` once ``min_sample_count`` fills exist.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
import math

_VALID_SIDES = frozenset({"BUY", "SELL"})


def _is_finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    pos = q * (len(sorted_values) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_values[lo])
    frac = pos - lo
    return float(sorted_values[lo]) * (1.0 - frac) + float(sorted_values[hi]) * frac


@dataclass(frozen=True)
class FillCostObservation:
    """One observed fill compared against the model execution assumption."""

    session_date: date
    symbol: str
    side: str
    filled_qty: float
    model_price: float
    fill_price: float
    model_commission_usd: float
    actual_commission_usd: float


@dataclass(frozen=True)
class ExecutionCostDriftConfig:
    """Fail-closed drift bounds that pause capital promotion when breached."""

    max_median_slippage_bps: float = 15.0
    max_p95_slippage_bps: float = 40.0
    max_commission_ratio: float = 1.5
    min_sample_count: int = 5


@dataclass(frozen=True)
class ExecutionCostDriftReport:
    """Summary of observed vs model slippage and commission drift."""

    sample_count: int
    sufficient_samples: bool
    mean_slippage_bps: float
    median_slippage_bps: float
    p95_slippage_bps: float
    total_model_commission_usd: float
    total_actual_commission_usd: float
    commission_ratio: float | None
    pause_promotion: bool
    breach_reasons: tuple[str, ...] = ()


def compute_adverse_slippage_bps(observation: FillCostObservation) -> float:
    """Return signed adverse slippage in bps (positive = worse than model).

    For ``BUY`` fills, paying above ``model_price`` is adverse; for ``SELL``
    fills, receiving below ``model_price`` is adverse.
    """
    if not isinstance(observation.session_date, date):
        raise ValueError("INVALID_SESSION_DATE")
    if not isinstance(observation.symbol, str) or not observation.symbol.strip():
        raise ValueError("INVALID_SYMBOL")
    side = observation.side.strip().upper() if isinstance(observation.side, str) else ""
    if side not in _VALID_SIDES:
        raise ValueError("INVALID_SIDE")
    if not _is_finite(observation.filled_qty) or float(observation.filled_qty) <= 0.0:
        raise ValueError("INVALID_FILLED_QTY")
    if not _is_finite(observation.model_price) or float(observation.model_price) <= 0.0:
        raise ValueError("INVALID_MODEL_PRICE")
    if not _is_finite(observation.fill_price) or float(observation.fill_price) <= 0.0:
        raise ValueError("INVALID_FILL_PRICE")
    if not _is_finite(observation.model_commission_usd) or float(observation.model_commission_usd) < 0.0:
        raise ValueError("INVALID_MODEL_COMMISSION")
    if not _is_finite(observation.actual_commission_usd) or float(observation.actual_commission_usd) < 0.0:
        raise ValueError("INVALID_ACTUAL_COMMISSION")

    model_px = float(observation.model_price)
    fill_px = float(observation.fill_price)
    signed_diff = (fill_px - model_px) if side == "BUY" else (model_px - fill_px)
    return (signed_diff / model_px) * 10_000.0


def evaluate_execution_cost_drift(
    observations: Iterable[FillCostObservation],
    config: ExecutionCostDriftConfig | None = None,
) -> ExecutionCostDriftReport:
    """Evaluate observed fills against model slippage/commission drift bounds."""
    cfg = config or ExecutionCostDriftConfig()
    if (
        not _is_finite(cfg.max_median_slippage_bps)
        or float(cfg.max_median_slippage_bps) < 0.0
        or not _is_finite(cfg.max_p95_slippage_bps)
        or float(cfg.max_p95_slippage_bps) < 0.0
        or not _is_finite(cfg.max_commission_ratio)
        or float(cfg.max_commission_ratio) <= 0.0
        or not isinstance(cfg.min_sample_count, int)
        or isinstance(cfg.min_sample_count, bool)
        or cfg.min_sample_count < 1
    ):
        raise ValueError("INVALID_COST_DRIFT_CONFIG")

    obs_list = list(observations)
    if not obs_list:
        return ExecutionCostDriftReport(
            sample_count=0,
            sufficient_samples=False,
            mean_slippage_bps=0.0,
            median_slippage_bps=0.0,
            p95_slippage_bps=0.0,
            total_model_commission_usd=0.0,
            total_actual_commission_usd=0.0,
            commission_ratio=None,
            pause_promotion=False,
            breach_reasons=(),
        )

    slippages = sorted(compute_adverse_slippage_bps(obs) for obs in obs_list)
    total_model_comm = sum(float(obs.model_commission_usd) for obs in obs_list)
    total_actual_comm = sum(float(obs.actual_commission_usd) for obs in obs_list)

    mean_slip = sum(slippages) / len(slippages)
    median_slip = _percentile(slippages, 0.50)
    p95_slip = _percentile(slippages, 0.95)

    if total_model_comm > 0.0:
        comm_ratio: float | None = total_actual_comm / total_model_comm
    elif total_actual_comm == 0.0:
        comm_ratio = 1.0
    else:
        comm_ratio = math.inf

    sufficient = len(obs_list) >= cfg.min_sample_count
    breaches: list[str] = []
    if sufficient:
        if median_slip > float(cfg.max_median_slippage_bps):
            breaches.append("MEDIAN_SLIPPAGE_DRIFT_EXCEEDED")
        if p95_slip > float(cfg.max_p95_slippage_bps):
            breaches.append("P95_SLIPPAGE_DRIFT_EXCEEDED")
        if comm_ratio is None or comm_ratio > float(cfg.max_commission_ratio):
            breaches.append("COMMISSION_RATIO_DRIFT_EXCEEDED")

    return ExecutionCostDriftReport(
        sample_count=len(obs_list),
        sufficient_samples=sufficient,
        mean_slippage_bps=mean_slip,
        median_slippage_bps=median_slip,
        p95_slippage_bps=p95_slip,
        total_model_commission_usd=total_model_comm,
        total_actual_commission_usd=total_actual_comm,
        commission_ratio=comm_ratio,
        pause_promotion=bool(breaches),
        breach_reasons=tuple(breaches),
    )


__all__ = [
    "ExecutionCostDriftConfig",
    "ExecutionCostDriftReport",
    "FillCostObservation",
    "compute_adverse_slippage_bps",
    "evaluate_execution_cost_drift",
]
