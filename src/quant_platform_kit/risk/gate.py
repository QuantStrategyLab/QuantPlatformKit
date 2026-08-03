"""Unified risk gate — hard checks before any StrategyDecision is returned.

Consolidates the lightweight gate from CnEquityStrategies entrypoints with
optional RiskEngine integration and circuit-breaker diagnostics (task 8 prep).
"""

from __future__ import annotations

import logging
import math
from typing import Any, Mapping

from quant_platform_kit.risk.engine import build_risk_engine
from quant_platform_kit.strategy_contracts import StrategyDecision

logger = logging.getLogger(__name__)

_STOP_LOSS_THRESHOLD = -0.20
_MAX_CONSECUTIVE_LOSSES = 5
_DEFAULT_MAX_SINGLE_WEIGHT = 0.10
_APPROVED_BOOTSTRAP_MANDATE = "bootstrap_small_account_v2"
_BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP = 0.50
_BOOTSTRAP_NOMINAL_CAPS = {1: 0.50, 2: 0.25, 3: 0.15}


def enrich_decision_risk_diagnostics(
    decision: StrategyDecision,
    *,
    unrealized_pnl_pct: float | None = None,
    consecutive_losses: int | None = None,
) -> StrategyDecision:
    """Attach stop-loss / circuit-breaker diagnostics used by apply_risk_gate.

    Platforms should call this after computing portfolio PnL / trade streak,
    before ``apply_risk_gate``. Missing values are left unset (gate skips those
    checks).
    """
    diagnostics = dict(decision.diagnostics or {})
    if unrealized_pnl_pct is not None:
        diagnostics["unrealized_pnl_pct"] = float(unrealized_pnl_pct)
    if consecutive_losses is not None:
        diagnostics["consecutive_losses"] = int(consecutive_losses)
    if diagnostics == dict(decision.diagnostics or {}):
        return decision
    return StrategyDecision(
        positions=decision.positions,
        budgets=decision.budgets,
        risk_flags=decision.risk_flags,
        diagnostics=diagnostics,
    )


def apply_risk_gate(
    decision: StrategyDecision,
    *,
    risk_mandate_id: str | None = None,
    product_leverage_factors: Mapping[str, int] | None = None,
    available_account_exposure: float | None = None,
    max_single_weight: float = _DEFAULT_MAX_SINGLE_WEIGHT,
    max_positions: int = 20,
    max_total_exposure: float = 1.0,
    portfolio_snapshot: Any | None = None,
    market_data: Mapping[str, Any] | None = None,
) -> StrategyDecision:
    """Apply hard risk checks to a strategy decision.

    Checks (in order):
    1. Circuit breaker from diagnostics (unrealized_pnl_pct, consecutive_losses)
    2. Mandate-specific single-account and leverage classification limits
    3. Legacy caller-supplied concentration limits when no mandate is supplied
    4. Legacy position-count and total-exposure limits
    5. RiskEngine.assess() when portfolio_snapshot is provided

    Returns an empty-position StrategyDecision on REJECT.
    """
    diagnostics = dict(decision.diagnostics or {})

    pnl_pct = diagnostics.get("unrealized_pnl_pct")
    if pnl_pct is not None and float(pnl_pct) < _STOP_LOSS_THRESHOLD:
        logger.warning(
            "risk_gate REJECT stop_loss: unrealized_pnl_pct=%.2f%%",
            float(pnl_pct) * 100,
        )
        return _reject(
            decision,
            flag="rejected:stop_loss",
            reason=f"未实现亏损 {float(pnl_pct):.1%} < {_STOP_LOSS_THRESHOLD:.0%} 止损线",
        )

    consecutive_losses = diagnostics.get("consecutive_losses")
    if (
        consecutive_losses is not None
        and int(consecutive_losses) > _MAX_CONSECUTIVE_LOSSES
    ):
        logger.warning(
            "risk_gate REJECT circuit_breaker: consecutive_losses=%d",
            int(consecutive_losses),
        )
        return _reject(
            decision,
            flag="rejected:circuit_breaker",
            reason=f"连续亏损 {int(consecutive_losses)} 笔 > {_MAX_CONSECUTIVE_LOSSES} 熔断",
        )

    positions = decision.positions or ()
    if not positions:
        return decision

    weights: list[tuple[Any, float]] = []
    for position in positions:
        raw_weight = position.target_weight
        if raw_weight is None:
            weight = 0.0
        elif isinstance(raw_weight, bool) or not isinstance(raw_weight, (int, float)):
            return _reject(
                decision,
                flag="rejected:invalid_weight",
                reason=f"{position.symbol} 目标仓位无效",
            )
        else:
            weight = abs(float(raw_weight))
            if not math.isfinite(weight):
                return _reject(
                    decision,
                    flag="rejected:invalid_weight",
                    reason=f"{position.symbol} 目标仓位无效",
                )
        if weight > 0.0:
            weights.append((position, weight))

    if risk_mandate_id == _APPROVED_BOOTSTRAP_MANDATE:
        if len(weights) > 1:
            return _reject(
                decision,
                flag="rejected:too_many_positions",
                reason="bootstrap_small_account_v2 仅允许一个非零持仓",
            )
        if available_account_exposure is None or (
            isinstance(available_account_exposure, bool)
            or not isinstance(available_account_exposure, (int, float))
            or not math.isfinite(float(available_account_exposure))
            or not 0.0
            <= float(available_account_exposure)
            <= _BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP
        ):
            return _reject(
                decision,
                flag="rejected:overexposed",
                reason="可用账户仓位容量无效",
            )
        if weights:
            active_symbols = {position.symbol for position, _ in weights}
            if (
                product_leverage_factors is None
                or set(product_leverage_factors) != active_symbols
            ):
                return _reject(
                    decision,
                    flag="rejected:leverage_classification",
                    reason="缺少或不一致的产品杠杆分类",
                )
            position, weight = weights[0]
            leverage_factor = product_leverage_factors[position.symbol]
            if (
                isinstance(leverage_factor, bool)
                or not isinstance(leverage_factor, int)
                or leverage_factor not in _BOOTSTRAP_NOMINAL_CAPS
            ):
                return _reject(
                    decision,
                    flag="rejected:leverage_classification",
                    reason="产品杠杆分类无效",
                )
            nominal_cap = _BOOTSTRAP_NOMINAL_CAPS[leverage_factor]
            if weight > nominal_cap:
                return _reject(
                    decision,
                    flag="rejected:concentration",
                    reason=f"{position.symbol} {weight:.1%} > {nominal_cap:.0%} 上限",
                )
            effective_exposure = weight * leverage_factor
            if effective_exposure > _BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP + 1e-9:
                return _reject(
                    decision,
                    flag="rejected:overexposed",
                    reason=f"有效敞口 {effective_exposure:.1%} > 50%",
                )
            if weight > float(available_account_exposure) + 1e-9:
                return _reject(
                    decision,
                    flag="rejected:overexposed",
                    reason=f"名义仓位 {weight:.1%} > 可用账户容量",
                )
    else:
        if risk_mandate_id is not None:
            return _reject(
                decision,
                flag="rejected:unknown_risk_mandate",
                reason="风险授权未获批准",
            )
        effective_single_weight = (
            float(max_single_weight)
            if isinstance(max_single_weight, (int, float))
            and not isinstance(max_single_weight, bool)
            and math.isfinite(float(max_single_weight))
            and 0.0 <= float(max_single_weight) <= 1.0
            else _DEFAULT_MAX_SINGLE_WEIGHT
        )
        for position, weight in weights:
            if weight > effective_single_weight:
                logger.warning(
                    "risk_gate REJECT concentration: symbol=%s weight=%.2f%% limit=%.0f%%",
                    position.symbol,
                    weight * 100,
                    effective_single_weight * 100,
                )
                return _reject(
                    decision,
                    flag="rejected:concentration",
                    reason=f"{position.symbol} {weight:.1%} > {effective_single_weight:.0%} 上限",
                )

        if len(positions) > max_positions:
            logger.warning(
                "risk_gate REJECT position_count: %d > %d",
                len(positions),
                max_positions,
            )
            return _reject(
                decision,
                flag="rejected:too_many_positions",
                reason=f"{len(positions)} 个持仓 > {max_positions} 上限",
            )

        total_weight = sum(weight for _, weight in weights)
        if total_weight > max_total_exposure + 1e-9:
            logger.warning(
                "risk_gate REJECT total_exposure: %.2f%% > %.0f%%",
                total_weight * 100,
                max_total_exposure * 100,
            )
            return _reject(
                decision,
                flag="rejected:overexposed",
                reason=f"总仓位 {total_weight:.1%} > {max_total_exposure:.0%}",
            )

    if portfolio_snapshot is not None:
        engine = build_risk_engine()
        assessment = engine.assess(
            decision,
            portfolio_snapshot,
            market_data=market_data,
        )
        if assessment.action == "reject":
            logger.warning("risk_gate REJECT risk_engine: %s", assessment.reason)
            return _reject(
                decision,
                flag="rejected:risk_engine",
                reason=assessment.reason,
            )

    risk_flags = list(decision.risk_flags or ())
    risk_flags.append("risk_gate:passed")
    return StrategyDecision(
        positions=decision.positions,
        budgets=decision.budgets,
        risk_flags=tuple(risk_flags),
        diagnostics={**diagnostics, "risk_gate": "APPROVE"},
    )


def _reject(
    decision: StrategyDecision,
    *,
    flag: str,
    reason: str,
) -> StrategyDecision:
    return StrategyDecision(
        positions=(),
        budgets=decision.budgets,
        risk_flags=(flag,),
        diagnostics={
            **(decision.diagnostics or {}),
            "risk_gate": "REJECT",
            "reason": reason,
        },
    )
