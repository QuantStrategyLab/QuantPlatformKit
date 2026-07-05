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
    "load_evidence_package",
    "validate_evidence_package",
    "validate_evidence_package_file",
]
