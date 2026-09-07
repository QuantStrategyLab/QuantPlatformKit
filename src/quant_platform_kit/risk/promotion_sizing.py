"""Promotion sizing chain: target × risk-profile scale × plugin scalar → RiskEngine.

Pure helper for the **new-promotion / material-change HITL confirmation path** only.
Do **not** use this module to recompute or rescale an already-live book.

Dual-scale warning (do not conflate):
- Composer unlevered-benchmark MDD ceilings: 1.00 / 1.25 / 1.50
- This module's position scales: 0.50 / 0.75 / 1.00 (never above 1.00)

Does not grant live authority. Plugin scalars may only shrink exposure (≤ 1).
Does not replace or weaken RiskEngine final veto.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

from quant_platform_kit.common.strategy_contracts import PositionTarget, StrategyDecision
from quant_platform_kit.risk.engine import RiskEngine
from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import (
    RISK_PROFILE_IDS,
)

# Position scales for promotion HITL only (≠ Composer MDD ceilings 1.00/1.25/1.50).
DEFAULT_RISK_PROFILE_SCALES: dict[str, float] = {
    "CAPITAL_PRESERVATION": 0.50,
    "BALANCED_COMPOUNDING": 0.75,
    "GROWTH_COMPOUNDING": 1.00,
}


@dataclass(frozen=True)
class PromotionSizingResult:
    """Sized target after profile/plugin scales and RiskEngine final veto."""

    target_weight: float
    risk_profile: str
    risk_profile_scale: float
    plugin_scalar: float
    sized_weight: float
    risk_action: str
    risk_reason: str
    final_weight: float
    decision: StrategyDecision
    live_authority_granted: bool = False


def normalize_plugin_scalar(value: Any) -> float:
    """Clamp plugin exposure scalar to [0, 1]. Invalid input fails closed to 0."""
    if value is None:
        return 1.0
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    scalar = float(value)
    if not math.isfinite(scalar) or scalar < 0.0:
        return 0.0
    if scalar > 1.0:
        return 1.0
    return scalar


def resolve_risk_profile_scale(
    risk_profile: str,
    *,
    scale_bps: int | None = None,
) -> float:
    """Resolve a risk-profile envelope scale (fraction of strategy target)."""
    profile = str(risk_profile or "").strip().upper()
    if profile not in RISK_PROFILE_IDS:
        raise ValueError(
            "risk_profile must be CAPITAL_PRESERVATION, "
            "BALANCED_COMPOUNDING, or GROWTH_COMPOUNDING"
        )
    if scale_bps is not None:
        if isinstance(scale_bps, bool) or not isinstance(scale_bps, int):
            raise ValueError("scale_bps must be an int in [0, 10000]")
        if not 0 <= scale_bps <= 10_000:
            raise ValueError("scale_bps must be an int in [0, 10000]")
        return scale_bps / 10_000.0
    return DEFAULT_RISK_PROFILE_SCALES[profile]


def size_target_weight(
    target_weight: float,
    *,
    risk_profile: str,
    plugin_scalar: Any = None,
    scale_bps: int | None = None,
) -> float:
    """Return target_weight × risk_profile_scale × plugin_scalar (fail-closed)."""
    if (
        isinstance(target_weight, bool)
        or not isinstance(target_weight, (int, float))
        or not math.isfinite(float(target_weight))
        or float(target_weight) < 0.0
    ):
        return 0.0
    profile_scale = resolve_risk_profile_scale(risk_profile, scale_bps=scale_bps)
    plugin = normalize_plugin_scalar(plugin_scalar)
    sized = float(target_weight) * profile_scale * plugin
    if not math.isfinite(sized) or sized < 0.0:
        return 0.0
    return sized


def assess_promotion_sized_target(
    *,
    target_weight: float,
    risk_profile: str,
    plugin_scalar: Any = None,
    scale_bps: int | None = None,
    symbol: str = "SPY",
    portfolio_snapshot: Any = None,
    engine: RiskEngine | None = None,
    market_data: Mapping[str, Any] | None = None,
) -> PromotionSizingResult:
    """Size a target then run RiskEngine.assess; reject forces final_weight to 0.

    Intended only for new promotion or material-change confirmation.
    Accept/approve never grants live authority and must not rescale existing live.
    """
    profile = str(risk_profile or "").strip().upper()
    profile_scale = resolve_risk_profile_scale(profile, scale_bps=scale_bps)
    plugin = normalize_plugin_scalar(plugin_scalar)
    sized = size_target_weight(
        target_weight,
        risk_profile=profile,
        plugin_scalar=plugin,
        scale_bps=scale_bps,
    )
    decision = StrategyDecision(
        positions=(PositionTarget(symbol=str(symbol), target_weight=sized),),
        diagnostics={
            "promotion_sizing": {
                "target_weight": float(target_weight)
                if isinstance(target_weight, (int, float))
                and not isinstance(target_weight, bool)
                else None,
                "risk_profile": profile,
                "risk_profile_scale": profile_scale,
                "plugin_scalar": plugin,
                "sized_weight": sized,
            }
        },
    )
    risk_engine = engine if engine is not None else RiskEngine()
    action = risk_engine.assess(decision, portfolio_snapshot, market_data=market_data)
    if action.action == "approve":
        engine_scale = min(
            float(action.budget_scalar),
            float(action.leverage_scalar),
            float(action.risk_asset_scalar),
        )
        if not math.isfinite(engine_scale) or engine_scale < 0.0:
            engine_scale = 0.0
        final_weight = sized * min(engine_scale, 1.0)
    else:
        final_weight = 0.0
    return PromotionSizingResult(
        target_weight=float(target_weight)
        if isinstance(target_weight, (int, float)) and not isinstance(target_weight, bool)
        else 0.0,
        risk_profile=profile,
        risk_profile_scale=profile_scale,
        plugin_scalar=plugin,
        sized_weight=sized,
        risk_action=str(action.action),
        risk_reason=str(action.reason),
        final_weight=final_weight,
        decision=decision,
        live_authority_granted=False,
    )


__all__ = [
    "DEFAULT_RISK_PROFILE_SCALES",
    "PromotionSizingResult",
    "assess_promotion_sized_target",
    "normalize_plugin_scalar",
    "resolve_risk_profile_scale",
    "size_target_weight",
]
