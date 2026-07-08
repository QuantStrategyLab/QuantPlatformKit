"""Risk management — unified risk engine, regime detection, and risk contracts.

Provides the consolidation point for risk logic previously scattered across
QuantStrategyPlugins (market_regime_control, crisis_response, macro_risk_governor),
quant_platform_kit.strategy_lifecycle.market_regime, and per-platform
runtime_execution_policy modules.
"""

from quant_platform_kit.risk.contracts import (
    RegimeContext,
    RegimeRoute,
    RiskAction,
    RiskAssessment,
    RiskSignal,
)
from quant_platform_kit.risk.engine import (
    RiskEngine,
    aggregate_risk_signals,
    build_risk_engine,
)
from quant_platform_kit.risk.gate import apply_risk_gate, enrich_decision_risk_diagnostics

__all__ = [
    "RegimeContext",
    "RegimeRoute",
    "RiskAction",
    "RiskAssessment",
    "RiskEngine",
    "RiskSignal",
    "aggregate_risk_signals",
    "apply_risk_gate",
    "enrich_decision_risk_diagnostics",
    "build_risk_engine",
]
