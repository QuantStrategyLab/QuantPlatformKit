"""Shared data models for the strategy lifecycle management system."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping


# ── Window Performance ──────────────────────────────────────────────


@dataclass(frozen=True)
class WindowPerformance:
    """Rolling-window performance metrics for a single strategy."""

    window_name: str
    window_days: int
    start_date: date
    end_date: date
    observation_count: int

    # Return metrics
    total_return: float
    cagr: float
    volatility: float

    # Risk-adjusted metrics
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float

    # Risk metrics
    max_drawdown: float
    win_rate: float
    profit_factor: float | None = None

    # Benchmark comparison
    benchmark_symbol: str = ""
    benchmark_return: float | None = None
    benchmark_cagr: float | None = None
    benchmark_max_drawdown: float | None = None
    excess_cagr: float | None = None
    alpha: float | None = None
    information_ratio: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "window_name": self.window_name,
            "window_days": self.window_days,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "observation_count": self.observation_count,
            "total_return": self.total_return,
            "cagr": self.cagr,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "benchmark_symbol": self.benchmark_symbol,
            "benchmark_return": self.benchmark_return,
            "benchmark_cagr": self.benchmark_cagr,
            "benchmark_max_drawdown": self.benchmark_max_drawdown,
            "excess_cagr": self.excess_cagr,
            "alpha": self.alpha,
            "information_ratio": self.information_ratio,
        }


# ── Strategy Performance Snapshot ───────────────────────────────────


@dataclass(frozen=True)
class StrategyPerformanceSnapshot:
    """Daily snapshot of rolling performance for one strategy."""

    strategy_profile: str
    domain: str
    platform: str
    as_of: date

    # Rolling windows (keyed by window_days: 63, 126, 252, 756)
    windows: Mapping[int, WindowPerformance] = field(default_factory=dict)

    # Latest single-period return
    latest_return: float | None = None

    # Benchmark reference
    benchmark_symbol: str = ""

    # Drift summary (populated by drift detector in a later pass)
    drift_score: float | None = None
    drift_status: str | None = None

    # Metadata
    data_freshness_days: int = 0
    source_artifact_path: str = ""
    computed_at: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_profile": self.strategy_profile,
            "domain": self.domain,
            "platform": self.platform,
            "as_of": self.as_of.isoformat(),
            "windows": {str(k): v.to_dict() for k, v in self.windows.items()},
            "latest_return": self.latest_return,
            "benchmark_symbol": self.benchmark_symbol,
            "drift_score": self.drift_score,
            "drift_status": self.drift_status,
            "data_freshness_days": self.data_freshness_days,
            "source_artifact_path": self.source_artifact_path,
            "computed_at": self.computed_at,
        }


# ── Drift Detection ─────────────────────────────────────────────────


class DriftStatus(str, enum.Enum):
    """Escalation levels for strategy drift."""

    HEALTHY = "healthy"
    WATCH = "watch"
    REVIEW = "review"
    CRITICAL = "critical"

    @classmethod
    def from_score(cls, score: float) -> "DriftStatus":
        if score < 0.25:
            return cls.HEALTHY
        if score < 0.50:
            return cls.WATCH
        if score < 0.75:
            return cls.REVIEW
        return cls.CRITICAL

    @property
    def severity_order(self) -> int:
        _order = {DriftStatus.HEALTHY: 0, DriftStatus.WATCH: 1, DriftStatus.REVIEW: 2, DriftStatus.CRITICAL: 3}
        return _order[self]


@dataclass(frozen=True)
class DriftDimension:
    """A single dimension of drift between actual and expected performance."""

    metric_name: str
    actual: float
    expected: float
    deviation: float
    deviation_pct: float
    threshold: float
    breached: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "metric_name": self.metric_name,
            "actual": self.actual,
            "expected": self.expected,
            "deviation": self.deviation,
            "deviation_pct": self.deviation_pct,
            "threshold": self.threshold,
            "breached": self.breached,
        }


@dataclass(frozen=True)
class DriftResult:
    """Complete drift analysis for one strategy snapshot."""

    strategy_profile: str
    domain: str
    as_of: date
    drift_score: float
    status: DriftStatus
    dimensions: Mapping[str, DriftDimension] = field(default_factory=dict)
    previous_status: DriftStatus | None = None
    escalated: bool = False
    cooldown_active: bool = False
    alert_suppressed: bool = False
    baseline_param_set_id: str | None = None
    baseline_available: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_profile": self.strategy_profile,
            "domain": self.domain,
            "as_of": self.as_of.isoformat(),
            "drift_score": self.drift_score,
            "status": self.status.value,
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
            "previous_status": self.previous_status.value if self.previous_status else None,
            "baseline_param_set_id": self.baseline_param_set_id,
            "baseline_available": self.baseline_available,
            "escalated": self.escalated,
            "cooldown_active": self.cooldown_active,
            "alert_suppressed": self.alert_suppressed,
        }

    @property
    def breached_dimensions(self) -> tuple[DriftDimension, ...]:
        return tuple(d for d in self.dimensions.values() if d.breached)


# ── Backtest & Optimization ─────────────────────────────────────────


@dataclass(frozen=True)
class BacktestResult:
    """Standardized result from a single backtest run."""

    strategy_profile: str
    domain: str
    param_set_id: str
    params: Mapping[str, Any]
    param_version: int = 1

    # Core metrics
    sharpe_ratio: float | None = None
    calmar_ratio: float | None = None
    sortino_ratio: float | None = None
    max_drawdown: float | None = None
    cagr: float | None = None
    volatility: float | None = None
    win_rate: float | None = None
    total_return: float | None = None

    # Time window
    start_date: date | None = None
    end_date: date | None = None
    observation_count: int = 0

    # Benchmark comparison
    benchmark_symbol: str = ""
    benchmark_cagr: float | None = None
    benchmark_max_drawdown: float | None = None
    excess_cagr: float | None = None

    # Out-of-sample validation
    oos_sharpe: float | None = None
    oos_calmar: float | None = None
    oos_max_drawdown: float | None = None
    walk_forward_stability: float | None = None

    # Metadata
    run_id: str = ""
    run_duration_seconds: float = 0.0
    source_script: str = ""
    computed_at: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_profile": self.strategy_profile,
            "domain": self.domain,
            "param_set_id": self.param_set_id,
            "params": dict(self.params),
            "param_version": self.param_version,
            "sharpe_ratio": self.sharpe_ratio,
            "calmar_ratio": self.calmar_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown": self.max_drawdown,
            "cagr": self.cagr,
            "volatility": self.volatility,
            "win_rate": self.win_rate,
            "total_return": self.total_return,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "observation_count": self.observation_count,
            "benchmark_symbol": self.benchmark_symbol,
            "benchmark_cagr": self.benchmark_cagr,
            "benchmark_max_drawdown": self.benchmark_max_drawdown,
            "excess_cagr": self.excess_cagr,
            "oos_sharpe": self.oos_sharpe,
            "oos_calmar": self.oos_calmar,
            "oos_max_drawdown": self.oos_max_drawdown,
            "walk_forward_stability": self.walk_forward_stability,
            "run_id": self.run_id,
            "run_duration_seconds": self.run_duration_seconds,
            "source_script": self.source_script,
            "computed_at": self.computed_at,
        }


@dataclass(frozen=True)
class SensitivityReport:
    """Results from a parameter-grid sensitivity sweep."""

    strategy_profile: str
    domain: str
    base_params: Mapping[str, Any]
    results: tuple[BacktestResult, ...] = ()
    combination_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_profile": self.strategy_profile,
            "domain": self.domain,
            "base_params": dict(self.base_params),
            "combination_count": self.combination_count,
            "results": [r.to_dict() for r in self.results],
        }


@dataclass(frozen=True)
class ParamSearchSpace:
    """Definition of the search space for one strategy's parameters."""

    strategy_profile: str
    domain: str
    dimensions: Mapping[str, ParamDimension] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_profile": self.strategy_profile,
            "domain": self.domain,
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
        }


@dataclass(frozen=True)
class ParamDimension:
    """A single parameter dimension in the search space."""

    name: str
    param_type: str  # "int", "float", "choice"
    bounds: tuple[float, float] | None = None
    choices: tuple[str, ...] | None = None
    step: float | None = None
    current_value: object = None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "param_type": self.param_type,
            "bounds": list(self.bounds) if self.bounds else None,
            "choices": list(self.choices) if self.choices else None,
            "step": self.step,
            "current_value": self.current_value,
        }


@dataclass(frozen=True)
class OptimizationProposal:
    """A parameter optimization proposal comparing current vs proposed params."""

    strategy_profile: str
    domain: str

    # Current state
    current_params: Mapping[str, Any] = field(default_factory=dict)
    current_metrics: BacktestResult | None = None

    # Proposed state
    proposed_params: Mapping[str, Any] = field(default_factory=dict)
    proposed_metrics: BacktestResult | None = None

    # Comparison
    improvement_score: float = 0.0
    confidence: float = 0.0
    winning_dimensions: tuple[str, ...] = ()
    regressing_dimensions: tuple[str, ...] = ()
    recommendation: str = ""  # "promote", "reject", "needs_review"

    # Walk-forward validation
    walk_forward_passed: bool = False

    # Metadata
    optimization_method: str = ""
    search_iterations: int = 0
    computed_at: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_profile": self.strategy_profile,
            "domain": self.domain,
            "current_params": dict(self.current_params),
            "current_metrics": self.current_metrics.to_dict() if self.current_metrics else None,
            "proposed_params": dict(self.proposed_params),
            "proposed_metrics": self.proposed_metrics.to_dict() if self.proposed_metrics else None,
            "improvement_score": self.improvement_score,
            "confidence": self.confidence,
            "winning_dimensions": list(self.winning_dimensions),
            "regressing_dimensions": list(self.regressing_dimensions),
            "recommendation": self.recommendation,
            "walk_forward_passed": self.walk_forward_passed,
            "optimization_method": self.optimization_method,
            "search_iterations": self.search_iterations,
            "computed_at": self.computed_at,
        }


# ── Safe Update ─────────────────────────────────────────────────────


class UpdateStage(str, enum.Enum):
    """Stages in the parameter update lifecycle."""

    OPTIMIZED = "optimized"
    SHADOW_VALIDATING = "shadow_validating"
    SHADOW_PASSED = "shadow_passed"
    SHADOW_REJECTED = "shadow_rejected"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PATCH_CREATED = "patch_created"
    DENIED = "denied"
    DEPLOYED = "deployed"
    RUNTIME_CONFIRMED = "runtime_confirmed"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True)
class UpdateLogEntry:
    """Immutable audit log entry for a parameter update."""

    strategy_profile: str
    domain: str
    entry_id: str
    stage: UpdateStage
    timestamp: str  # ISO-8601
    operator: str  # "auto_optimizer" or "human:{user_id}"

    # Before/after context
    param_version_from: int | None = None
    param_version_to: int | None = None
    params_before: Mapping[str, Any] = field(default_factory=dict)
    params_after: Mapping[str, Any] = field(default_factory=dict)

    # Decision details
    reason: str = ""
    approval_source: str = ""  # "auto" | "telegram" | "manual"
    improvement_score: float | None = None
    shadow_days: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_profile": self.strategy_profile,
            "domain": self.domain,
            "entry_id": self.entry_id,
            "stage": self.stage.value,
            "timestamp": self.timestamp,
            "operator": self.operator,
            "param_version_from": self.param_version_from,
            "param_version_to": self.param_version_to,
            "params_before": dict(self.params_before),
            "params_after": dict(self.params_after),
            "reason": self.reason,
            "approval_source": self.approval_source,
            "improvement_score": self.improvement_score,
            "shadow_days": self.shadow_days,
        }


# ── Health Score ────────────────────────────────────────────────────


@dataclass(frozen=True)
class StrategyHealthScore:
    """Composite health score (0-100) for a single strategy."""

    strategy_profile: str
    domain: str
    as_of: date
    overall_score: float

    # Sub-scores
    performance_score: float  # 35%
    risk_score: float  # 25%
    decay_score: float  # 20%
    stability_score: float  # 10%
    operational_score: float  # 10%

    # Status
    status: str = ""  # healthy, watch, review, critical

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_profile": self.strategy_profile,
            "domain": self.domain,
            "as_of": self.as_of.isoformat(),
            "overall_score": self.overall_score,
            "performance_score": self.performance_score,
            "risk_score": self.risk_score,
            "decay_score": self.decay_score,
            "stability_score": self.stability_score,
            "operational_score": self.operational_score,
            "status": self.status,
        }


# ── Drift Detection Context ──────────────────────────────────────────


@dataclass(frozen=True)
class DriftDetectionContext:
    """Bundled context for drift detection — reduces parameter sprawl."""

    snapshot: StrategyPerformanceSnapshot
    backtest: "BacktestResult | None" = None
    policy_drift: object = None  # DriftPolicy
    previous_status: object = None  # DriftStatus | None
    regime: object = None  # MarketRegimeResult | None

    @property
    def strategy_profile(self) -> str:
        return self.snapshot.strategy_profile

    @property
    def domain(self) -> str:
        return self.snapshot.domain
