"""Kelly criterion position sizing utilities."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

_DEFAULT_MAX_POSITION_PCT = 0.10
KELLY_BET_LOSS_RISK_SHARE_VERSION = "kelly.bet_loss_risk_share.v1"
KELLY_CAPITAL_EXPOSURE_VERSION = "kelly.capital_exposure.v1"
UNIT_BET_LOSS_RISK_SHARE = "bet_loss_risk_share"
UNIT_CAPITAL_EXPOSURE = "capital_exposure"


@dataclass(frozen=True)
class KellyResult:
    """Binary Kelly helper in bet-loss risk-share units.

    ``kelly_fraction`` / ``half_kelly`` are the stake fractions of a bet that
    is fully lost on a loss.  Legacy ``max_position_pct`` is
    ``min(half_kelly, 0.10)`` in the same risk-share unit; it is not capital
    exposure of an asset whose loss is only a fraction of notional.
    """

    win_rate: float
    avg_win: float
    avg_loss: float
    kelly_fraction: float
    half_kelly: float
    max_position_pct: float
    contract_version: str = KELLY_BET_LOSS_RISK_SHARE_VERSION
    unit: str = UNIT_BET_LOSS_RISK_SHARE


@dataclass(frozen=True)
class ConstrainedKellyResult:
    """Research-only Kelly recommendation bounded by an existing risk budget.

    ``recommended_position_pct`` is an upper bound in bet-loss risk-share units
    for downstream research sizing, not an execution instruction, capital
    exposure, or an approval decision.  A ``PARKED`` result always recommends
    zero.
    """

    status: str
    sample_count: int
    win_count: int
    loss_count: int
    raw_kelly_fraction: float
    fractional_kelly_fraction: float
    recommended_position_pct: float
    reason_codes: tuple[str, ...]
    contract_version: str = KELLY_BET_LOSS_RISK_SHARE_VERSION
    unit: str = UNIT_BET_LOSS_RISK_SHARE


@dataclass(frozen=True)
class CapitalExposureKellyResult:
    """Research-only capital-exposure Kelly bound with an explicit loss fraction.

    Converts a bet-loss risk share through ``loss_fraction_per_unit`` once,
    applies fractional Kelly once, then clips to risk/position caps.  Never
    authorizes orders and never invents a loss fraction from average loss.
    """

    status: str
    sample_count: int
    win_count: int
    loss_count: int
    bet_loss_risk_share: float
    loss_fraction_per_unit: float
    theoretical_capital_exposure: float
    fractional_capital_exposure: float
    recommended_capital_exposure: float
    reason_codes: tuple[str, ...]
    contract_version: str = KELLY_CAPITAL_EXPOSURE_VERSION
    unit: str = UNIT_CAPITAL_EXPOSURE


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


def _empty_kelly_result() -> KellyResult:
    return KellyResult(
        win_rate=0.0,
        avg_win=0.0,
        avg_loss=0.0,
        kelly_fraction=0.0,
        half_kelly=0.0,
        max_position_pct=0.0,
    )


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (OverflowError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _stable_mean(values: list[float]) -> float:
    """Average finite values without overflowing an intermediate sum."""
    scale = max(abs(value) for value in values)
    if scale == 0.0:
        return 0.0
    return scale * (sum(value / scale for value in values) / len(values))


def estimate_kelly(returns: list[float]) -> KellyResult:
    """Estimate Kelly bet-loss risk share from per-trade returns.

    Zero returns are ignored for win/loss probability and averages; they do not
    change the binary Kelly solution.  Invalid or non-finite inputs fail closed
    to a zero recommendation.
    """
    if not isinstance(returns, list):
        return _empty_kelly_result()
    if not returns:
        return _empty_kelly_result()
    if any(_finite_number(value) is None for value in returns):
        return _empty_kelly_result()

    values = [float(value) for value in returns]
    wins = [value for value in values if value > 0.0]
    losses = [value for value in values if value < 0.0]
    decisive = len(wins) + len(losses)
    if decisive == 0:
        return _empty_kelly_result()

    win_rate = len(wins) / decisive
    avg_win = _stable_mean(wins) if wins else 0.0
    avg_loss = abs(_stable_mean(losses)) if losses else 0.0

    if avg_win <= 0.0:
        kelly_fraction = 0.0
    elif avg_loss <= 0.0:
        kelly_fraction = min(win_rate, 1.0)
    else:
        kelly_fraction = win_rate - (1.0 - win_rate) * (avg_loss / avg_win)
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


def constrained_kelly_recommendation(
    returns: list[float],
    *,
    risk_budget_cap: float,
    position_cap: float = _DEFAULT_MAX_POSITION_PCT,
    fractional_kelly: float = 0.25,
    min_samples: int = 30,
    observed_max_drawdown: float | None = None,
    max_drawdown_limit: float = 0.25,
) -> ConstrainedKellyResult:
    """Return a fail-closed, research-only Kelly risk-budget recommendation.

    The recommendation is capped by ``risk_budget_cap`` (the authoritative
    portfolio risk budget), ``position_cap`` and fractional Kelly.  Values are
    bet-loss risk shares, not capital exposure.  It never allocates, submits
    orders, or increases a risk budget.  Insufficient samples, missing
    win/loss sides, invalid inputs, or excessive/illegal drawdown are parked
    instead of extrapolating from fragile estimates.
    """

    def parked(reason_codes: tuple[str, ...], *, sample_count: int = 0,
               win_count: int = 0, loss_count: int = 0) -> ConstrainedKellyResult:
        return ConstrainedKellyResult(
            status="PARKED",
            sample_count=sample_count,
            win_count=win_count,
            loss_count=loss_count,
            raw_kelly_fraction=0.0,
            fractional_kelly_fraction=0.0,
            recommended_position_pct=0.0,
            reason_codes=reason_codes,
        )

    if not isinstance(returns, list):
        return parked(("invalid_returns",))
    sample_count = len(returns)
    if any(_finite_number(value) is None for value in returns):
        return parked(("invalid_returns",), sample_count=sample_count)
    wins = sum(value > 0.0 for value in returns)
    losses = sum(value < 0.0 for value in returns)
    numeric = (risk_budget_cap, position_cap, fractional_kelly, max_drawdown_limit)
    if (any(_finite_number(value) is None for value in numeric)
            or not isinstance(min_samples, int) or isinstance(min_samples, bool)
            or min_samples < 2):
        return parked(("invalid_constraints",), sample_count=sample_count,
                      win_count=wins, loss_count=losses)
    caps = tuple(float(value) for value in numeric)
    if (any(value <= 0.0 for value in caps)
            or caps[2] >= 1.0 or caps[3] > 1.0):
        return parked(("invalid_constraints",), sample_count=sample_count,
                      win_count=wins, loss_count=losses)
    if sample_count < min_samples:
        return parked(("insufficient_samples",), sample_count=sample_count,
                      win_count=wins, loss_count=losses)
    if not wins or not losses:
        return parked(("insufficient_win_loss_observations",),
                      sample_count=sample_count, win_count=wins, loss_count=losses)
    if observed_max_drawdown is None:
        return parked(("missing_drawdown",), sample_count=sample_count,
                      win_count=wins, loss_count=losses)
    drawdown = _finite_number(observed_max_drawdown)
    if drawdown is None or drawdown < 0.0:
        return parked(("invalid_drawdown",), sample_count=sample_count,
                      win_count=wins, loss_count=losses)
    if drawdown > caps[3]:
        return parked(("drawdown_limit_exceeded",), sample_count=sample_count,
                      win_count=wins, loss_count=losses)

    result = estimate_kelly([float(value) for value in returns])
    fractional = result.kelly_fraction * caps[2]
    recommendation = min(fractional, caps[0], caps[1])
    if not math.isfinite(recommendation) or recommendation <= 0.0:
        return parked(("non_positive_edge",), sample_count=sample_count,
                      win_count=wins, loss_count=losses)
    return ConstrainedKellyResult(
        status="KELLY_READY",
        sample_count=sample_count,
        win_count=wins,
        loss_count=losses,
        raw_kelly_fraction=result.kelly_fraction,
        fractional_kelly_fraction=fractional,
        recommended_position_pct=recommendation,
        reason_codes=(),
    )


def research_capital_exposure_kelly(
    returns: list[float],
    *,
    loss_fraction_per_unit: float | None,
    risk_budget_cap: float,
    position_cap: float = _DEFAULT_MAX_POSITION_PCT,
    fractional_kelly: float = 0.5,
    observed_max_drawdown: float | None = None,
) -> CapitalExposureKellyResult:
    """Convert bet-loss risk share into research-only capital exposure.

    Requires an explicit trusted ``loss_fraction_per_unit``.  Fractional Kelly
    is applied once to the theoretical exposure; residual weight is cash and
    must not be renormalized back to a full book. The constrained Kelly sample,
    two-sided-return, and drawdown gates also apply. Full Kelly is rejected.
    """

    def parked(
        reason_codes: tuple[str, ...],
        *,
        sample_count: int = 0,
        win_count: int = 0,
        loss_count: int = 0,
        loss_fraction: float = 0.0,
    ) -> CapitalExposureKellyResult:
        return CapitalExposureKellyResult(
            status="PARKED",
            sample_count=sample_count,
            win_count=win_count,
            loss_count=loss_count,
            bet_loss_risk_share=0.0,
            loss_fraction_per_unit=loss_fraction,
            theoretical_capital_exposure=0.0,
            fractional_capital_exposure=0.0,
            recommended_capital_exposure=0.0,
            reason_codes=reason_codes,
        )

    if not isinstance(returns, list) or any(_finite_number(value) is None for value in returns):
        return parked(("invalid_returns",), sample_count=len(returns) if isinstance(returns, list) else 0)
    sample_count = len(returns)
    wins = sum(float(value) > 0.0 for value in returns)
    losses = sum(float(value) < 0.0 for value in returns)
    loss_fraction = _finite_number(loss_fraction_per_unit)
    if loss_fraction is None or loss_fraction <= 0.0 or loss_fraction > 1.0:
        return parked(
            ("missing_or_invalid_loss_fraction_per_unit",),
            sample_count=sample_count,
            win_count=wins,
            loss_count=losses,
        )
    numeric = (risk_budget_cap, position_cap, fractional_kelly)
    if any(_finite_number(value) is None for value in numeric):
        return parked(
            ("invalid_constraints",),
            sample_count=sample_count,
            win_count=wins,
            loss_count=losses,
            loss_fraction=loss_fraction,
        )
    risk_cap, pos_cap, fractional = (float(value) for value in numeric)
    if (
        risk_cap <= 0.0
        or pos_cap <= 0.0
        or risk_cap > 1.0
        or pos_cap > 1.0
        or fractional <= 0.0
    ):
        return parked(
            ("invalid_constraints",),
            sample_count=sample_count,
            win_count=wins,
            loss_count=losses,
            loss_fraction=loss_fraction,
        )
    if fractional >= 1.0:
        return parked(
            ("full_kelly_not_allowed",),
            sample_count=sample_count,
            win_count=wins,
            loss_count=losses,
            loss_fraction=loss_fraction,
        )

    constrained = constrained_kelly_recommendation(
        returns,
        risk_budget_cap=1.0,
        position_cap=1.0,
        fractional_kelly=fractional,
        min_samples=30,
        observed_max_drawdown=observed_max_drawdown,
        max_drawdown_limit=0.25,
    )
    if constrained.status != "KELLY_READY":
        return parked(
            constrained.reason_codes,
            sample_count=sample_count,
            win_count=wins,
            loss_count=losses,
            loss_fraction=loss_fraction,
        )
    risk_share = constrained.raw_kelly_fraction
    theoretical = risk_share / loss_fraction
    fractional_exposure = constrained.fractional_kelly_fraction / loss_fraction
    recommended = min(fractional_exposure, risk_cap, pos_cap)
    if (
        not all(
            math.isfinite(value)
            for value in (risk_share, theoretical, fractional_exposure, recommended)
        )
        or risk_share <= 0.0
        or recommended <= 0.0
    ):
        return parked(
            ("non_finite_or_non_positive_exposure",),
            sample_count=sample_count,
            win_count=wins,
            loss_count=losses,
            loss_fraction=loss_fraction,
        )
    return CapitalExposureKellyResult(
        status="KELLY_READY",
        sample_count=sample_count,
        win_count=wins,
        loss_count=losses,
        bet_loss_risk_share=risk_share,
        loss_fraction_per_unit=loss_fraction,
        theoretical_capital_exposure=theoretical,
        fractional_capital_exposure=fractional_exposure,
        recommended_capital_exposure=recommended,
        reason_codes=(),
    )
