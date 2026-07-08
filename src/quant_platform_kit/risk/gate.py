"""Unified risk gate — hard checks before any StrategyDecision is returned.

Consolidates the lightweight gate from CnEquityStrategies entrypoints with
optional RiskEngine integration and circuit-breaker diagnostics (task 8 prep).
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from quant_platform_kit.risk.engine import build_risk_engine
from quant_platform_kit.strategy_contracts import StrategyDecision

logger = logging.getLogger(__name__)

_STOP_LOSS_THRESHOLD = -0.20
_MAX_CONSECUTIVE_LOSSES = 5



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
    max_single_weight: float = 1.0,
    max_positions: int = 20,
    max_total_exposure: float = 1.0,
    portfolio_snapshot: Any | None = None,
    market_data: Mapping[str, Any] | None = None,
) -> StrategyDecision:
    """Apply hard risk checks to a strategy decision.

    Checks (in order):
    1. Circuit breaker from diagnostics (unrealized_pnl_pct, consecutive_losses)
    2. Single-name concentration (when max_single_weight < 1.0)
    3. Position count limit
    4. Total exposure limit
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
    if consecutive_losses is not None and int(consecutive_losses) > _MAX_CONSECUTIVE_LOSSES:
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

    if max_single_weight < 1.0:
        for position in positions:
            weight = abs(float(position.target_weight or 0.0))
            if weight > max_single_weight:
                logger.warning(
                    "risk_gate REJECT concentration: symbol=%s weight=%.2f%% limit=%.0f%%",
                    position.symbol,
                    weight * 100,
                    max_single_weight * 100,
                )
                return _reject(
                    decision,
                    flag="rejected:concentration",
                    reason=f"{position.symbol} {weight:.1%} > {max_single_weight:.0%} 上限",
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

    total_weight = sum(abs(float(p.target_weight or 0.0)) for p in positions)
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
