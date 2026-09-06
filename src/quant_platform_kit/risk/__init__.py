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
    RiskGateAssessment,
    RiskGateResult,
    RiskSignal,
)
from quant_platform_kit.risk.engine import (
    RiskEngine,
    aggregate_risk_signals,
    build_risk_engine,
)
from quant_platform_kit.risk.gate import (
    assess_with_evidence,
    apply_risk_gate,
    enrich_decision_risk_diagnostics,
)
from quant_platform_kit.risk.portfolio_diagnostics import (
    compute_unrealized_pnl_pct,
    extract_portfolio_risk_diagnostics,
)
from quant_platform_kit.risk.snapshot import RiskSnapshot, build_risk_snapshot
from quant_platform_kit.risk.cross_asset_snapshot import build_cross_asset_snapshot
from quant_platform_kit.risk.research_consumer import (
    DEFAULT_RESEARCH_STRATEGIES,
    ResearchRiskObservation,
    consume_research_risk,
    consume_research_risk_batch,
)
from quant_platform_kit.risk.account_new_risk_gate import (
    AccountNewRiskGateError,
    InjectedReconciliationSnapshot,
    NewRiskAdmissionResult,
    NewRiskDisposition,
    evaluate_new_risk_admission,
    evaluate_new_risk_from_reader,
    validate_injected_snapshot,
)
from quant_platform_kit.risk.promotion_sizing import (
    DEFAULT_RISK_PROFILE_SCALES,
    PromotionSizingResult,
    assess_promotion_sized_target,
    normalize_plugin_scalar,
    resolve_risk_profile_scale,
    size_target_weight,
)

__all__ = [
    "RegimeContext",
    "RegimeRoute",
    "RiskAction",
    "RiskAssessment",
    "RiskGateAssessment",
    "RiskGateResult",
    "RiskEngine",
    "RiskSignal",
    "aggregate_risk_signals",
    "assess_with_evidence",
    "apply_risk_gate",
    "compute_unrealized_pnl_pct",
    "enrich_decision_risk_diagnostics",
    "extract_portfolio_risk_diagnostics",
    "build_risk_engine",
    "RiskSnapshot",
    "build_risk_snapshot",
    "build_cross_asset_snapshot",
    "DEFAULT_RESEARCH_STRATEGIES",
    "ResearchRiskObservation",
    "consume_research_risk",
    "consume_research_risk_batch",
    "AccountNewRiskGateError",
    "InjectedReconciliationSnapshot",
    "NewRiskAdmissionResult",
    "NewRiskDisposition",
    "evaluate_new_risk_admission",
    "evaluate_new_risk_from_reader",
    "validate_injected_snapshot",
    "DEFAULT_RISK_PROFILE_SCALES",
    "PromotionSizingResult",
    "assess_promotion_sized_target",
    "normalize_plugin_scalar",
    "resolve_risk_profile_scale",
    "size_target_weight",
]
