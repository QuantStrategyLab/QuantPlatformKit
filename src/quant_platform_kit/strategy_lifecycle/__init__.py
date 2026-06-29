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
]
