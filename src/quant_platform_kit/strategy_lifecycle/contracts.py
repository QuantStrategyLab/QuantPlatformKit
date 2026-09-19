"""Shared data models for the strategy lifecycle management system."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping

from quant_platform_kit.common.exchange_full_day_closures_2026 import (
    XHKG_FULL_DAY_CLOSURES_2026,
    XHKG_HOLIDAY_COVERAGE_2026,
    XHKG_HOLIDAY_SOURCE_2026,
    XNYS_FULL_DAY_CLOSURES_2026,
    XNYS_HOLIDAY_COVERAGE_2026,
    XNYS_HOLIDAY_SOURCE_2026,
)

# ── Return observation / annualization contract ─────────────────────


# Limited valid annualization bases. Equity session metrics use 252;
# crypto natural-day metrics use 365.25. Other values are rejected.
VALID_PERIODS_PER_YEAR: frozenset[float] = frozenset({252.0, 365.25})

_EQUITY_PERIODS_PER_YEAR: float = 252.0
_CRYPTO_PERIODS_PER_YEAR: float = 365.25


@dataclass(frozen=True)
class ReturnObservationContract:
    """Explicit calendar + annualization basis for daily return evidence.

    ``calendar_id`` names the intended session calendar. Domain defaults for
    ``XNYS`` / ``XHKG`` attach the published 2026 full-day closure tables with
    explicit source URLs and coverage ``[2026-01-01, 2026-12-31]``. Spans
    outside that coverage remain ``incomplete_calendar``. Synthetic sources are
    never treated as real exchange evidence. Caller-supplied contracts and
    coverage overlays are not replaced by defaults when explicitly provided.
    """

    calendar_id: str
    periods_per_year: float
    domain: str = ""
    session_holidays: frozenset[str] = field(default_factory=frozenset)
    holiday_source: str = ""
    holiday_coverage_start: date | None = None
    holiday_coverage_end: date | None = None

    def __post_init__(self) -> None:
        calendar_id = str(self.calendar_id or "").strip()
        if not calendar_id:
            raise ValueError("calendar_id is required")
        periods = float(self.periods_per_year)
        if periods not in VALID_PERIODS_PER_YEAR:
            allowed = ", ".join(str(value) for value in sorted(VALID_PERIODS_PER_YEAR))
            raise ValueError(f"periods_per_year must be one of: {allowed}")
        holidays = frozenset(str(day).strip() for day in self.session_holidays if str(day).strip())
        start = self.holiday_coverage_start
        end = self.holiday_coverage_end
        if (start is None) ^ (end is None):
            raise ValueError("holiday_coverage_start and holiday_coverage_end must be set together")
        if start is not None and end is not None and end < start:
            raise ValueError("holiday_coverage_end must be on or after holiday_coverage_start")
        object.__setattr__(self, "calendar_id", calendar_id)
        object.__setattr__(self, "periods_per_year", periods)
        object.__setattr__(self, "domain", str(self.domain or "").strip())
        object.__setattr__(self, "session_holidays", holidays)
        object.__setattr__(self, "holiday_source", str(self.holiday_source or "").strip())
        object.__setattr__(self, "holiday_coverage_start", start)
        object.__setattr__(self, "holiday_coverage_end", end)


_SYNTHETIC_HOLIDAY_SOURCES: frozenset[str] = frozenset(
    {
        "synthetic",
        "synthetic_fixture_only",
        "fixture",
        "test",
        "test_only",
    }
)

_PUBLISHED_EXCHANGE_HOLIDAY_SOURCES_2026: frozenset[str] = frozenset(
    {
        XNYS_HOLIDAY_SOURCE_2026,
        XHKG_HOLIDAY_SOURCE_2026,
    }
)


def is_synthetic_holiday_source(holiday_source: str) -> bool:
    """Return True when the source must not be treated as real exchange evidence."""
    text = str(holiday_source or "").strip().lower()
    return (not text) or text in _SYNTHETIC_HOLIDAY_SOURCES


def exchange_holiday_calendar_readiness(
    contract: ReturnObservationContract,
    *,
    span_start: date,
    span_end: date,
) -> tuple[bool, str]:
    """Whether exchange-holiday semantics are computable for ``[span_start, span_end]``."""
    if span_end < span_start:
        return False, "invalid_observation_span"
    calendar_id = contract.calendar_id
    if calendar_id == "CRYPTO_NATURAL_DAY":
        return True, "natural_day"
    if calendar_id == "XSHG":
        coverage = (date(2023, 1, 1), date(2026, 12, 31))
        if span_start < coverage[0] or span_end > coverage[1]:
            return False, "cn_equity_holiday_coverage_exceeded"
        source = str(contract.holiday_source or "").strip()
        if is_synthetic_holiday_source(source) and source:
            return False, "synthetic_holiday_source_not_accepted"
        if source and source != "quant_platform_kit.common.cn_equity_calendar":
            return False, "unsupported_cn_holiday_source"
        return True, "cn_equity_calendar"
    if calendar_id in {"XNYS", "XHKG"}:
        if is_synthetic_holiday_source(contract.holiday_source):
            return False, "exchange_holiday_source_missing_or_synthetic"
        if contract.holiday_coverage_start is None or contract.holiday_coverage_end is None:
            return False, "exchange_holiday_coverage_missing"
        if span_start < contract.holiday_coverage_start or span_end > contract.holiday_coverage_end:
            return False, "exchange_holiday_coverage_exceeded"
        source = str(contract.holiday_source or "").strip()
        if source in _PUBLISHED_EXCHANGE_HOLIDAY_SOURCES_2026:
            return True, "published_exchange_closures_2026"
        # Non-synthetic caller-attested overlays remain allowed inside their coverage.
        return True, "caller_supplied_exchange_holidays"
    return False, f"unsupported_calendar_id:{calendar_id}"


@dataclass(frozen=True)
class LiveReturnSeriesResult:
    """Derivation outcome; incomplete calendars never look like a successful short series."""

    series: Any  # pd.Series; typed loosely to avoid importing pandas in contracts
    status: str
    detail: str = ""


@dataclass(frozen=True)
class LiveReturnCollectionResult:
    """Collector outcome with explicit incomplete profiles."""

    series_by_profile: Mapping[str, Any]
    incomplete_by_profile: Mapping[str, str]


_DOMAIN_RETURN_OBSERVATION_CONTRACTS: Mapping[str, ReturnObservationContract] = {
    "us_equity": ReturnObservationContract(
        calendar_id="XNYS",
        periods_per_year=_EQUITY_PERIODS_PER_YEAR,
        domain="us_equity",
        session_holidays=XNYS_FULL_DAY_CLOSURES_2026,
        holiday_source=XNYS_HOLIDAY_SOURCE_2026,
        holiday_coverage_start=XNYS_HOLIDAY_COVERAGE_2026[0],
        holiday_coverage_end=XNYS_HOLIDAY_COVERAGE_2026[1],
    ),
    "cn_equity": ReturnObservationContract(
        calendar_id="XSHG",
        periods_per_year=_EQUITY_PERIODS_PER_YEAR,
        domain="cn_equity",
        holiday_source="quant_platform_kit.common.cn_equity_calendar",
        holiday_coverage_start=date(2023, 1, 1),
        holiday_coverage_end=date(2026, 12, 31),
    ),
    "hk_equity": ReturnObservationContract(
        calendar_id="XHKG",
        periods_per_year=_EQUITY_PERIODS_PER_YEAR,
        domain="hk_equity",
        session_holidays=XHKG_FULL_DAY_CLOSURES_2026,
        holiday_source=XHKG_HOLIDAY_SOURCE_2026,
        holiday_coverage_start=XHKG_HOLIDAY_COVERAGE_2026[0],
        holiday_coverage_end=XHKG_HOLIDAY_COVERAGE_2026[1],
    ),
    "crypto": ReturnObservationContract(
        calendar_id="CRYPTO_NATURAL_DAY",
        periods_per_year=_CRYPTO_PERIODS_PER_YEAR,
        domain="crypto",
    ),
}


def resolve_return_observation_contract(domain: str) -> ReturnObservationContract:
    """Resolve the frozen return-frequency contract for a lifecycle domain.

    US/HK defaults include published 2026 full-day closures only. Spans outside
    that coverage stay incomplete until a non-synthetic overlay covers them.
    """
    key = str(domain or "").strip()
    contract = _DOMAIN_RETURN_OBSERVATION_CONTRACTS.get(key)
    if contract is None:
        raise ValueError(
            f"unsupported return observation domain={domain!r}; "
            f"expected one of: {', '.join(sorted(_DOMAIN_RETURN_OBSERVATION_CONTRACTS))}"
        )
    return contract


def merge_return_observation_contract(
    base: ReturnObservationContract,
    *,
    session_holidays: frozenset[str] | None = None,
    holiday_source: str | None = None,
    holiday_coverage_start: date | None = None,
    holiday_coverage_end: date | None = None,
) -> ReturnObservationContract:
    """Overlay caller-supplied holiday evidence onto a domain base contract.

    Explicit overlay values replace the corresponding base fields; omitted
    overlays keep the base (including published 2026 defaults).
    """
    return ReturnObservationContract(
        calendar_id=base.calendar_id,
        periods_per_year=base.periods_per_year,
        domain=base.domain,
        session_holidays=base.session_holidays if session_holidays is None else session_holidays,
        holiday_source=base.holiday_source if holiday_source is None else holiday_source,
        holiday_coverage_start=(
            base.holiday_coverage_start if holiday_coverage_start is None else holiday_coverage_start
        ),
        holiday_coverage_end=(
            base.holiday_coverage_end if holiday_coverage_end is None else holiday_coverage_end
        ),
    )

def validate_periods_per_year(periods_per_year: float) -> float:
    """Accept only the frozen annualization bases."""
    periods = float(periods_per_year)
    if periods not in VALID_PERIODS_PER_YEAR:
        allowed = ", ".join(str(value) for value in sorted(VALID_PERIODS_PER_YEAR))
        raise ValueError(f"periods_per_year must be one of: {allowed}")
    return periods


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

    # Explicit frequency / annualization metadata (defaults preserve equity 252)
    calendar_id: str = ""
    periods_per_year: float = _EQUITY_PERIODS_PER_YEAR

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
            "calendar_id": self.calendar_id,
            "periods_per_year": self.periods_per_year,
        }


# ── Strategy Performance Snapshot ───────────────────────────────────


@dataclass(frozen=True)
class StrategyPerformanceSnapshot:
    """Daily snapshot of rolling performance for one strategy."""

    strategy_profile: str
    domain: str
    platform: str
    as_of: date | None

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
    source_revision: str = ""
    cost_model: str = ""
    # Live/CSV return completeness: "ok", "truncated_after_observation_gap", ...
    observation_status: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_profile": self.strategy_profile,
            "domain": self.domain,
            "platform": self.platform,
            "as_of": self.as_of.isoformat() if self.as_of is not None else None,
            "windows": {str(k): v.to_dict() for k, v in self.windows.items()},
            "latest_return": self.latest_return,
            "benchmark_symbol": self.benchmark_symbol,
            "drift_score": self.drift_score,
            "drift_status": self.drift_status,
            "data_freshness_days": self.data_freshness_days,
            "source_artifact_path": self.source_artifact_path,
            "computed_at": self.computed_at,
            "source_revision": self.source_revision,
            "cost_model": self.cost_model,
            "observation_status": self.observation_status,
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
        _order = {
            DriftStatus.HEALTHY: 0,
            DriftStatus.WATCH: 1,
            DriftStatus.REVIEW: 2,
            DriftStatus.CRITICAL: 3,
        }
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
    as_of: date | None
    drift_score: float
    status: DriftStatus
    dimensions: Mapping[str, DriftDimension] = field(default_factory=dict)
    previous_status: DriftStatus | None = None
    escalated: bool = False
    cooldown_active: bool = False
    alert_suppressed: bool = False
    baseline_param_set_id: str | None = None
    baseline_available: bool = True
    baseline_param_version: int | None = None
    baseline_artifact_id: str | None = None
    source_revision: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_profile": self.strategy_profile,
            "domain": self.domain,
            "as_of": self.as_of.isoformat() if self.as_of is not None else None,
            "source_revision": self.source_revision,
            "drift_score": self.drift_score,
            "status": self.status.value,
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
            "previous_status": self.previous_status.value
            if self.previous_status
            else None,
            "baseline_param_set_id": self.baseline_param_set_id,
            "baseline_available": self.baseline_available,
            "baseline_param_version": self.baseline_param_version,
            "baseline_artifact_id": self.baseline_artifact_id,
            "escalated": self.escalated,
            "cooldown_active": self.cooldown_active,
            "alert_suppressed": self.alert_suppressed,
        }

    @property
    def breached_dimensions(self) -> tuple[DriftDimension, ...]:
        return tuple(d for d in self.dimensions.values() if d.breached)


# ── Backtest & Optimization ─────────────────────────────────────────


@dataclass(frozen=True)
class PurgedWalkForwardFold:
    """Explicit train/test boundaries for one promotion-grade fold."""

    train_start: date
    train_end: date
    test_start: date
    test_end: date

    def to_dict(self) -> dict[str, str]:
        return {
            "train_start": self.train_start.isoformat(),
            "train_end": self.train_end.isoformat(),
            "test_start": self.test_start.isoformat(),
            "test_end": self.test_end.isoformat(),
        }


@dataclass(frozen=True)
class PromotionCostModel:
    """Finite cost inputs required by promotion-grade orchestration."""

    model_id: str
    commission_bps: float
    slippage_bps: float
    market_impact_bps: float = 0.0

    def to_dict(self) -> dict[str, str | float]:
        return {
            "model_id": self.model_id,
            "commission_bps": self.commission_bps,
            "slippage_bps": self.slippage_bps,
            "market_impact_bps": self.market_impact_bps,
        }


@dataclass(frozen=True)
class BacktestValidationIdentity:
    """Orchestrator-computed timing identity; never a caller promotion flag."""

    protocol: str
    fold_id: str
    fold_role: str
    train_start: date | None
    train_end: date | None
    test_start: date
    test_end: date
    locked_oos_start: date
    locked_oos_end: date
    purge_days: int
    embargo_days: int

    def to_dict(self) -> dict[str, object]:
        return {
            "protocol": self.protocol,
            "fold_id": self.fold_id,
            "fold_role": self.fold_role,
            "train_start": self.train_start.isoformat() if self.train_start else None,
            "train_end": self.train_end.isoformat() if self.train_end else None,
            "test_start": self.test_start.isoformat(),
            "test_end": self.test_end.isoformat(),
            "locked_oos_start": self.locked_oos_start.isoformat(),
            "locked_oos_end": self.locked_oos_end.isoformat(),
            "purge_days": self.purge_days,
            "embargo_days": self.embargo_days,
        }


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
    source_revision: str = ""
    cost_model: str = ""

    # Appended to preserve the positional order of every legacy field above.
    validation_identity: BacktestValidationIdentity | None = None
    cost_inputs: Mapping[str, float] = field(default_factory=dict)
    # None means legacy evidence without an explicit annualization basis.
    periods_per_year: float | None = None
    calendar_id: str = ""

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
            "source_revision": self.source_revision,
            "cost_model": self.cost_model,
            "validation_identity": (
                self.validation_identity.to_dict() if self.validation_identity is not None else None
            ),
            "cost_inputs": dict(self.cost_inputs),
            "periods_per_year": self.periods_per_year,
            "calendar_id": self.calendar_id,
        }


@dataclass(frozen=True)
class PromotionBacktestRun:
    """Validated output produced only by the strict promotion orchestration path."""

    strategy_profile: str
    domain: str
    fold_results: tuple[BacktestResult, ...]
    locked_oos_result: BacktestResult
    folds: tuple[PurgedWalkForwardFold, ...]
    locked_oos_start: date
    locked_oos_end: date
    purge_days: int
    embargo_days: int
    source_revision: str
    cost_model: PromotionCostModel

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_profile": self.strategy_profile,
            "domain": self.domain,
            "folds": [fold.to_dict() for fold in self.folds],
            "fold_results": [result.to_dict() for result in self.fold_results],
            "locked_oos_result": self.locked_oos_result.to_dict(),
            "locked_oos_start": self.locked_oos_start.isoformat(),
            "locked_oos_end": self.locked_oos_end.isoformat(),
            "purge_days": self.purge_days,
            "embargo_days": self.embargo_days,
            "source_revision": self.source_revision,
            "cost_model": self.cost_model.to_dict(),
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
    recommendation: str = ""  # "research_candidate", "promote", "reject", "needs_review"

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
            "current_metrics": self.current_metrics.to_dict()
            if self.current_metrics
            else None,
            "proposed_params": dict(self.proposed_params),
            "proposed_metrics": self.proposed_metrics.to_dict()
            if self.proposed_metrics
            else None,
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
    ROLLBACK_PROPOSED = "rollback_proposed"
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
    as_of: date | None
    overall_score: float | None

    # Sub-scores
    performance_score: float | None  # 35%
    risk_score: float | None  # 25%
    decay_score: float | None  # 20%
    stability_score: float | None  # 10%
    operational_score: float | None  # 10%

    # Status
    status: str = ""  # healthy, watch, review, critical

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_profile": self.strategy_profile,
            "domain": self.domain,
            "as_of": self.as_of.isoformat() if self.as_of is not None else None,
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
