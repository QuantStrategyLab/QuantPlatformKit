"""Kelly criterion position sizing utilities."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

_DEFAULT_MAX_POSITION_PCT = 0.10


@dataclass(frozen=True)
class KellyResult:
    win_rate: float
    avg_win: float
    avg_loss: float
    kelly_fraction: float
    half_kelly: float
    max_position_pct: float


_APPROVED_BOOTSTRAP_MANDATE = "bootstrap_small_account_v2"
_TQQQ_ETF_ONLY_RESEARCH_MANDATE = "tqqq_etf_only_research_v1"
_BOOTSTRAP_LOSS_BUDGET_CAP = 0.01
_BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP = 0.50
_BOOTSTRAP_NOMINAL_CAPS = {1: 0.50, 2: 0.25, 3: 0.15}
_TQQQ_ETF_ONLY_PRODUCTS = {
    "TQQQ": (3, 0.15, 0.45),
    "BOXX": (1, 0.50, 0.50),
}


def _weight_mapping(value: object, *, allow_empty: bool) -> dict[str, float] | None:
    if not isinstance(value, Mapping) or (not value and not allow_empty):
        return None
    normalized: dict[str, float] = {}
    for symbol, raw_weight in value.items():
        if (
            not isinstance(symbol, str)
            or not symbol
            or symbol != symbol.strip()
            or isinstance(raw_weight, bool)
            or not isinstance(raw_weight, (int, float))
        ):
            return None
        weight = float(raw_weight)
        if not math.isfinite(weight) or weight < 0.0:
            return None
        normalized[symbol] = weight
    return normalized


def risk_budgeted_target_weights(
    *,
    raw_target_weights: Mapping[str, float],
    risk_mandate_id: str | None,
    risk_fraction: float,
    stop_loss_distances: Mapping[str, float],
    drawdown_scalar: float,
    available_effective_exposure: float,
    product_leverage_factors: Mapping[str, int],
    inputs_fresh: bool,
) -> dict[str, float]:
    """Scale one mandate-bound multi-asset target vector proportionally.

    This is a pure sizing helper, not an allocator or an approval decision.
    Invalid, stale, unmandated or over-authority inputs return an empty vector.
    """
    raw_weights = _weight_mapping(raw_target_weights, allow_empty=False)
    if (
        inputs_fresh is not True
        or not isinstance(risk_mandate_id, str)
        or not risk_mandate_id
        or risk_mandate_id != risk_mandate_id.strip()
        or risk_mandate_id == _APPROVED_BOOTSTRAP_MANDATE
        or raw_weights is None
        or not isinstance(stop_loss_distances, Mapping)
        or not isinstance(product_leverage_factors, Mapping)
        or set(stop_loss_distances) != set(raw_weights)
        or set(product_leverage_factors) != set(raw_weights)
    ):
        return {}
    numeric_inputs = (risk_fraction, drawdown_scalar, available_effective_exposure)
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in numeric_inputs
    ):
        return {}
    risk_fraction, drawdown_scalar, available_effective_exposure = (
        float(value) for value in numeric_inputs
    )
    if (
        not all(math.isfinite(value) for value in numeric_inputs)
        or not 0.0 < risk_fraction <= _BOOTSTRAP_LOSS_BUDGET_CAP
        or not 0.0 < drawdown_scalar <= 1.0
        or not 0.0 < available_effective_exposure <= _BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP
    ):
        return {}

    stops: dict[str, float] = {}
    factors: dict[str, int] = {}
    for symbol in raw_weights:
        raw_stop = stop_loss_distances[symbol]
        factor = product_leverage_factors[symbol]
        if (
            isinstance(raw_stop, bool)
            or not isinstance(raw_stop, (int, float))
            or not math.isfinite(float(raw_stop))
            or not 0.0 < float(raw_stop) <= 1.0
            or isinstance(factor, bool)
            or not isinstance(factor, int)
            or factor not in _BOOTSTRAP_NOMINAL_CAPS
        ):
            return {}
        stops[symbol] = float(raw_stop)
        factors[symbol] = factor

    active = {symbol: weight for symbol, weight in raw_weights.items() if weight > 0.0}
    if not active:
        return {}
    modeled_loss = sum(active[symbol] * stops[symbol] for symbol in active)
    effective_exposure = sum(active[symbol] * factors[symbol] for symbol in active)
    if modeled_loss <= 0.0 or effective_exposure <= 0.0:
        return {}

    scales = [
        1.0,
        risk_fraction * drawdown_scalar / modeled_loss,
        available_effective_exposure / effective_exposure,
    ]
    scales.extend(
        _BOOTSTRAP_NOMINAL_CAPS[factors[symbol]] / weight
        for symbol, weight in active.items()
    )
    scale = min(scales)
    if not math.isfinite(scale) or scale <= 0.0:
        return {}
    return {symbol: weight * scale for symbol, weight in active.items()}


def validate_reduce_only_normalization(
    *,
    origin_weights: Mapping[str, float],
    target_weights: Mapping[str, float],
    product_leverage_factors: Mapping[str, int],
    effective_exposure_cap: float,
    observed_effective_exposure: float,
    cash_only: bool = False,
) -> bool:
    """Validate one explicit transition from an over-cap origin toward cash."""
    origin = _weight_mapping(origin_weights, allow_empty=False)
    target = _weight_mapping(target_weights, allow_empty=True)
    if (
        origin is None
        or target is None
        or not isinstance(product_leverage_factors, Mapping)
        or not (set(origin) | set(target)).issubset(product_leverage_factors)
        or isinstance(effective_exposure_cap, bool)
        or not isinstance(effective_exposure_cap, (int, float))
        or isinstance(observed_effective_exposure, bool)
        or not isinstance(observed_effective_exposure, (int, float))
        or not isinstance(cash_only, bool)
    ):
        return False
    cap = float(effective_exposure_cap)
    observed = float(observed_effective_exposure)
    if (
        not math.isfinite(cap)
        or not 0.0 <= cap <= _BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP
        or not math.isfinite(observed)
        or observed < 0.0
    ):
        return False

    factors: dict[str, int] = {}
    for symbol, factor in product_leverage_factors.items():
        if (
            isinstance(factor, bool)
            or not isinstance(factor, int)
            or factor not in _BOOTSTRAP_NOMINAL_CAPS
        ):
            return False
        factors[symbol] = factor
    origin_active = {symbol for symbol, weight in origin.items() if weight > 0.0}
    target_active = {symbol for symbol, weight in target.items() if weight > 0.0}
    if not origin_active or not target_active.issubset(origin_active):
        return False
    if cash_only and target_active:
        return False
    if any(target.get(symbol, 0.0) > origin[symbol] + 1e-9 for symbol in origin):
        return False
    if any(
        weight > _BOOTSTRAP_NOMINAL_CAPS[factors[symbol]] + 1e-9
        for symbol, weight in target.items()
    ):
        return False

    origin_effective = sum(weight * factors[symbol] for symbol, weight in origin.items())
    target_effective = sum(weight * factors[symbol] for symbol, weight in target.items())
    return (
        abs(origin_effective - observed) <= 1e-9
        and origin_effective > cap + 1e-9
        and target_effective < origin_effective - 1e-9
        and target_effective <= cap + 1e-9
    )


def risk_budgeted_target_weight(
    *,
    risk_mandate_id: str | None = None,
    product_symbol: str | None = None,
    account_equity: float | None = None,
    risk_fraction: float | None = None,
    stop_loss_distance: float | None = None,
    drawdown_scalar: float | None = None,
    available_account_exposure: float | None = None,
    product_leverage_factor: int | None = None,
    inputs_fresh: bool | None = None,
) -> float:
    """Return a fail-closed single-account target weight.

    Approved mandates permit one ETF position with their product caps. Without
    a mandate, the legacy 10% and unlevered fallback applies. This pure helper
    sizes a target; it does not authorize a product or execution.
    """
    numeric_inputs = (
        account_equity,
        risk_fraction,
        stop_loss_distance,
        drawdown_scalar,
        available_account_exposure,
    )
    if (
        inputs_fresh is not True
        or any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in numeric_inputs
        )
        or isinstance(product_leverage_factor, bool)
        or not isinstance(product_leverage_factor, int)
    ):
        return 0.0

    (
        account_equity,
        risk_fraction,
        stop_loss_distance,
        drawdown_scalar,
        available_account_exposure,
    ) = (float(value) for value in numeric_inputs)
    if (
        not all(math.isfinite(value) for value in numeric_inputs)
        or account_equity <= 0.0
        or not 0.0 < risk_fraction <= _BOOTSTRAP_LOSS_BUDGET_CAP
        or not 0.0 < stop_loss_distance <= 1.0
        or not 0.0 <= drawdown_scalar <= 1.0
        or not 0.0 <= available_account_exposure <= _BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP
    ):
        return 0.0

    if risk_mandate_id is None:
        if product_leverage_factor != 1:
            return 0.0
        nominal_cap = _DEFAULT_MAX_POSITION_PCT
    elif risk_mandate_id == _APPROVED_BOOTSTRAP_MANDATE:
        nominal_cap = _BOOTSTRAP_NOMINAL_CAPS.get(product_leverage_factor, 0.0)
        if nominal_cap == 0.0:
            return 0.0
    elif risk_mandate_id == _TQQQ_ETF_ONLY_RESEARCH_MANDATE:
        product = _TQQQ_ETF_ONLY_PRODUCTS.get(product_symbol or "")
        if (
            product is None
            or product_leverage_factor != product[0]
            or risk_fraction != _BOOTSTRAP_LOSS_BUDGET_CAP
            or stop_loss_distance != 0.05
            or drawdown_scalar not in {0.0, 0.5, 1.0}
        ):
            return 0.0
        nominal_cap = product[1]
        product_effective_cap = product[2]
    else:
        return 0.0

    risk_weight = risk_fraction * drawdown_scalar / stop_loss_distance
    if not math.isfinite(risk_weight):
        return 0.0

    effective_cap = (
        product_effective_cap
        if risk_mandate_id == _TQQQ_ETF_ONLY_RESEARCH_MANDATE
        else _BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP
    )
    return min(
        risk_weight,
        nominal_cap,
        available_account_exposure,
        effective_cap / product_leverage_factor,
    )


def estimate_kelly(returns: list[float]) -> KellyResult:
    """Estimate Kelly fraction from a list of per-trade returns."""
    if not returns:
        return KellyResult(
            win_rate=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            kelly_fraction=0.0,
            half_kelly=0.0,
            max_position_pct=0.0,
        )

    wins = [value for value in returns if value > 0]
    losses = [value for value in returns if value < 0]

    win_rate = len(wins) / len(returns)
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0

    if avg_win <= 0.0:
        kelly_fraction = 0.0
    elif avg_loss <= 0.0:
        kelly_fraction = min(win_rate, 1.0)
    else:
        payoff_ratio = avg_win / avg_loss
        kelly_fraction = (win_rate * payoff_ratio - (1.0 - win_rate)) / payoff_ratio
        kelly_fraction = max(0.0, min(kelly_fraction, 1.0))

    half_kelly = kelly_fraction / 2.0
    max_position_pct = min(half_kelly, _DEFAULT_MAX_POSITION_PCT)

    return KellyResult(
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        kelly_fraction=kelly_fraction,
        half_kelly=half_kelly,
        max_position_pct=max_position_pct,
    )
