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
from quant_platform_kit.strategy_spec import (
    OPTIMIZATION_SPEC_SCHEMA_VERSION,
    RESEARCH_SPEC_SCHEMA_VERSION,
    validate_optimization_spec,
    validate_research_spec,
    validate_strategy_spec,
    validate_strategy_spec_file,
)
from quant_platform_kit.strategy_lifecycle.evidence_gate import (
    EvidenceGateResult,
    EvidencePackage,
    load_evidence_package,
    validate_evidence_package,
    validate_evidence_package_file,
)
from quant_platform_kit.strategy_lifecycle.evidence_package_v2 import (
    STRATEGY_EVIDENCE_PACKAGE_SCHEMA_VERSION,
    canonical_evidence_package_v2_bytes,
    read_evidence_package_v2_json,
    validate_evidence_package_v2,
)
from quant_platform_kit.strategy_lifecycle.live_candidate_notifications import (
    LiveCandidateNotificationEvent,
    build_live_candidate_notification,
)
from quant_platform_kit.strategy_lifecycle.lifecycle_status import (
    CANONICAL_LIFECYCLE_STATES,
    LEGACY_CATALOG_STATUS_MAP,
    catalog_status_grants_execution_permission,
    normalize_catalog_lifecycle_status,
)

__all__ = [
    "BacktestResult",
    "DriftDimension",
    "DriftResult",
    "DriftStatus",
    "OptimizationProposal",
    "ParamDimension",
    "ParamSearchSpace",
    "RESEARCH_SPEC_SCHEMA_VERSION",
    "OPTIMIZATION_SPEC_SCHEMA_VERSION",
    "StrategyHealthScore",
    "STRATEGY_EVIDENCE_PACKAGE_SCHEMA_VERSION",
    "StrategyPerformanceSnapshot",
    "UpdateLogEntry",
    "UpdateStage",
    "WindowPerformance",
    "EvidenceGateResult",
    "EvidencePackage",
    "LiveCandidateNotificationEvent",
    "CANONICAL_LIFECYCLE_STATES",
    "LEGACY_CATALOG_STATUS_MAP",
    "load_evidence_package",
    "canonical_evidence_package_v2_bytes",
    "read_evidence_package_v2_json",
    "build_live_candidate_notification",
    "catalog_status_grants_execution_permission",
    "normalize_catalog_lifecycle_status",
    "validate_evidence_package",
    "validate_evidence_package_file",
    "validate_evidence_package_v2",
    "validate_optimization_spec",
    "validate_research_spec",
    "validate_strategy_spec",
    "validate_strategy_spec_file",
]
