"""Strategy Lifecycle Manager — continuous monitoring, drift detection, auto-optimization, and safe updates."""

from quant_platform_kit.strategy_lifecycle.contracts import (
    BacktestResult,
    DriftDimension,
    DriftResult,
    DriftStatus,
    OptimizationProposal,
    ParamDimension,
    ParamSearchSpace,
    StrategyHealthScore,
    StrategyPerformanceSnapshot,
    UpdateLogEntry,
    UpdateStage,
    WindowPerformance,
)
from quant_platform_kit.strategy_lifecycle.evidence_gate import (
    EvidenceGateResult,
    EvidencePackage,
    load_evidence_package,
    validate_evidence_package,
    validate_evidence_package_file,
)
from quant_platform_kit.strategy_lifecycle.live_candidate_notifications import (
    LiveCandidateNotificationEvent,
    build_live_candidate_notification,
)

__all__ = [
    "BacktestResult",
    "DriftDimension",
    "DriftResult",
    "DriftStatus",
    "OptimizationProposal",
    "ParamDimension",
    "ParamSearchSpace",
    "StrategyHealthScore",
    "StrategyPerformanceSnapshot",
    "UpdateLogEntry",
    "UpdateStage",
    "WindowPerformance",
    "EvidenceGateResult",
    "EvidencePackage",
    "LiveCandidateNotificationEvent",
    "load_evidence_package",
    "build_live_candidate_notification",
    "validate_evidence_package",
    "validate_evidence_package_file",
]
