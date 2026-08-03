"""Kelly criterion position sizing utilities."""

from __future__ import annotations

from dataclasses import dataclass
import math

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
_BOOTSTRAP_LOSS_BUDGET_CAP = 0.01
_BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP = 0.50
_BOOTSTRAP_NOMINAL_CAPS = {1: 0.50, 2: 0.25, 3: 0.15}


def risk_budgeted_target_weight(
    *,
    risk_mandate_id: str | None = None,
    account_equity: float | None = None,
    risk_fraction: float | None = None,
    stop_loss_distance: float | None = None,
    drawdown_scalar: float | None = None,
    available_account_exposure: float | None = None,
    product_leverage_factor: int | None = None,
    inputs_fresh: bool | None = None,
) -> float:
    """Return a fail-closed single-account target weight.

    ``bootstrap_small_account_v2`` permits one ETF position with its approved
    product cap. Without that mandate, the legacy 10% and unlevered fallback
    applies. This helper does not allocate across strategies.
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
    else:
        return 0.0

    risk_weight = risk_fraction * drawdown_scalar / stop_loss_distance
    if not math.isfinite(risk_weight):
        return 0.0

    return min(
        risk_weight,
        nominal_cap,
        available_account_exposure,
        _BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP / product_leverage_factor,
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
