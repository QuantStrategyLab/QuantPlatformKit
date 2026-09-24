"""Shared data models for the strategy lifecycle management system."""

from __future__ import annotations

import enum
import json
import math
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
    # Explicit unevaluable / incomplete-evidence reason; empty when scored normally.
    reason: str = ""

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
            "reason": self.reason,
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


# ── Research trial ledger ───────────────────────────────────────────
# Independent of BacktestResult / promotion. Synthetic storage is not a grant.


_IDENTITY_PLACEHOLDERS = frozenset({"unknown", "default", "none", "null", "na", "n/a"})
_RESEARCH_NON_SUCCESS = frozenset({"failed", "rejected", "aborted"})


class ResearchTrialStatus(str, enum.Enum):
    """Lifecycle of one research attempt. Terminal states do not promote."""

    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    ABORTED = "aborted"


def _reject_identity_placeholder(value: str) -> None:
    if value.casefold() in _IDENTITY_PLACEHOLDERS:
        raise ValueError("identity_placeholder")


def _label(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("identity")
    if len(value) > 200 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("identity")
    _reject_identity_placeholder(value)
    return value


def _raw_identity(value: object) -> str:
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        raise ValueError("identity")
    if len(value) > 500 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("identity")
    _reject_identity_placeholder(value)
    return value


def _run_identity(value: object) -> str:
    """Backtest run ids may contain internal spaces; they are not reason text."""

    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("identity")
    if len(value) > 500 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("identity")
    if any(char.isspace() and char != " " for char in value):
        raise ValueError("identity")
    _reject_identity_placeholder(value)
    return value


def _require_date(value: object) -> date:
    if type(value) is not date:
        raise ValueError("window")
    return value


def _finite_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("invalid_number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("invalid_number")
    return number


def _reason_code(value: object, *, allow_empty: bool) -> str:
    if not isinstance(value, str):
        raise ValueError("reason_code")
    if value == "" and allow_empty:
        return ""
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789_"
    if (
        not value
        or len(value) > 64
        or value[0] not in "abcdefghijklmnopqrstuvwxyz"
        or any(char not in alphabet for char in value)
    ):
        raise ValueError("reason_code")
    return value


def _cost_inputs(value: object, *, allow_empty: bool) -> dict[str, float]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Mapping):
        raise ValueError("cost_inputs")
    parsed: dict[str, float] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or any(char.isspace() for char in key):
            raise ValueError("cost_inputs")
        number = _finite_number(item)
        if number < 0:
            raise ValueError("cost_inputs")
        parsed[key] = number
    if not parsed and not allow_empty:
        raise ValueError("cost_inputs")
    return parsed


def _symbol(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 32:
        raise ValueError("position_mark")
    if any(not (char.isalnum() or char in "._-") for char in value):
        raise ValueError("position_mark")
    return value


@dataclass(frozen=True)
class ResearchPositionMark:
    """One position's quantity and marked value. Zero quantity has zero value."""

    symbol: str
    quantity: float
    valuation: float

    def __post_init__(self) -> None:
        symbol = _symbol(self.symbol)
        quantity = _finite_number(self.quantity)
        valuation = _finite_number(self.valuation)
        if (quantity == 0.0) != (valuation == 0.0):
            raise ValueError("position_mark")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(self, "valuation", valuation)

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "valuation": self.valuation,
        }


def _position_marks(value: object) -> tuple[ResearchPositionMark, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise ValueError("position_mark")
    marks: list[ResearchPositionMark] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, ResearchPositionMark):
            raise ValueError("position_mark")
        if item.symbol in seen:
            raise ValueError("position_mark")
        seen.add(item.symbol)
        marks.append(item)
    return tuple(marks)


@dataclass(frozen=True)
class ResearchLedgerDay:
    """End-of-session cash, marks, flows, fees, NAV, and that session's return."""

    session_date: date
    cash: float
    positions: tuple[ResearchPositionMark, ...]
    trade_net_cashflow: float
    fees: float
    nav: float
    daily_return: float

    def __post_init__(self) -> None:
        session_date = _require_date(self.session_date)
        cash = _finite_number(self.cash)
        positions = _position_marks(self.positions)
        trade_net_cashflow = _finite_number(self.trade_net_cashflow)
        fees = _finite_number(self.fees)
        if fees < 0:
            raise ValueError("ledger_fee")
        nav = _finite_number(self.nav)
        if nav <= 0:
            raise ValueError("ledger_nav")
        daily_return = _finite_number(self.daily_return)
        expected_nav = cash + sum(mark.valuation for mark in positions)
        if not math.isclose(nav, expected_nav, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("ledger_nav")
        object.__setattr__(self, "session_date", session_date)
        object.__setattr__(self, "cash", cash)
        object.__setattr__(self, "positions", positions)
        object.__setattr__(self, "trade_net_cashflow", trade_net_cashflow)
        object.__setattr__(self, "fees", fees)
        object.__setattr__(self, "nav", nav)
        object.__setattr__(self, "daily_return", daily_return)

    def to_dict(self) -> dict[str, object]:
        return {
            "session_date": self.session_date.isoformat(),
            "cash": self.cash,
            "positions": [mark.to_dict() for mark in self.positions],
            "trade_net_cashflow": self.trade_net_cashflow,
            "fees": self.fees,
            "nav": self.nav,
            "daily_return": self.daily_return,
        }


@dataclass(frozen=True)
class ResearchDailyLedger:
    """Complete daily book for one research trial.

    ``initial_session_date`` is the first marked session. Its cash, positions,
    and NAV are not a return observation. ``days`` are strictly later sessions
    and each carries that session's return. ``window_start`` is the initial
    session; ``observation_count`` counts only those later return days.
    """

    trial_id: str
    domain: str
    strategy_profile: str
    run_id: str
    param_version: int
    input_id: str
    calendar_id: str
    periods_per_year: float
    cost_source: str
    cost_inputs: Mapping[str, float]
    initial_session_date: date
    initial_nav: float
    initial_cash: float
    initial_positions: tuple[ResearchPositionMark, ...]
    days: tuple[ResearchLedgerDay, ...]
    synthetic: bool

    def __post_init__(self) -> None:
        trial_id = _raw_identity(self.trial_id)
        domain = _label(self.domain)
        strategy_profile = _label(self.strategy_profile)
        run_id = _run_identity(self.run_id)
        if type(self.param_version) is not int or self.param_version <= 0:
            raise ValueError("param_version")
        input_id = _raw_identity(self.input_id)
        calendar_id = _label(self.calendar_id)
        number = _finite_number(self.periods_per_year)
        try:
            periods = validate_periods_per_year(number)
        except ValueError as exc:
            raise ValueError("periods_per_year") from exc
        cost_source = _raw_identity(self.cost_source)
        cost_inputs = _cost_inputs(self.cost_inputs, allow_empty=False)
        initial_session_date = _require_date(self.initial_session_date)
        initial_nav = _finite_number(self.initial_nav)
        initial_cash = _finite_number(self.initial_cash)
        initial_positions = _position_marks(self.initial_positions)
        if initial_nav <= 0:
            raise ValueError("ledger_nav")
        expected_initial = initial_cash + sum(mark.valuation for mark in initial_positions)
        if not math.isclose(initial_nav, expected_initial, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("ledger_nav")
        if isinstance(self.days, (str, bytes)) or not isinstance(self.days, (tuple, list)) or not self.days:
            raise ValueError("ledger_dates")
        days = tuple(self.days)
        previous_date = initial_session_date
        for day in days:
            if not isinstance(day, ResearchLedgerDay):
                raise ValueError("ledger_dates")
            if day.session_date <= previous_date:
                raise ValueError("ledger_dates")
            previous_date = day.session_date
        if type(self.synthetic) is not bool:
            raise ValueError("synthetic")
        previous_cash = initial_cash
        previous_nav = initial_nav
        for day in days:
            expected_cash = previous_cash + day.trade_net_cashflow - day.fees
            if not math.isclose(day.cash, expected_cash, rel_tol=0.0, abs_tol=1e-9):
                raise ValueError("ledger_cash")
            expected_return = day.nav / previous_nav - 1.0
            if day.daily_return != expected_return:
                raise ValueError("ledger_return")
            previous_cash = day.cash
            previous_nav = day.nav
        object.__setattr__(self, "trial_id", trial_id)
        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "strategy_profile", strategy_profile)
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "input_id", input_id)
        object.__setattr__(self, "calendar_id", calendar_id)
        object.__setattr__(self, "periods_per_year", periods)
        object.__setattr__(self, "cost_source", cost_source)
        object.__setattr__(self, "cost_inputs", cost_inputs)
        object.__setattr__(self, "initial_session_date", initial_session_date)
        object.__setattr__(self, "initial_nav", initial_nav)
        object.__setattr__(self, "initial_cash", initial_cash)
        object.__setattr__(self, "initial_positions", initial_positions)
        object.__setattr__(self, "days", days)

    @property
    def window_start(self) -> date:
        return self.initial_session_date

    @property
    def window_end(self) -> date:
        return self.days[-1].session_date

    @property
    def observation_count(self) -> int:
        return len(self.days)

    @property
    def total_return(self) -> float:
        return self.days[-1].nav / self.initial_nav - 1.0

    @property
    def total_fees(self) -> float:
        return float(sum(day.fees for day in self.days))

    def to_dict(self) -> dict[str, object]:
        return {
            "trial_id": self.trial_id,
            "domain": self.domain,
            "strategy_profile": self.strategy_profile,
            "run_id": self.run_id,
            "param_version": self.param_version,
            "input_id": self.input_id,
            "calendar_id": self.calendar_id,
            "periods_per_year": self.periods_per_year,
            "cost_source": self.cost_source,
            "cost_inputs": dict(self.cost_inputs),
            "initial_session_date": self.initial_session_date.isoformat(),
            "initial_nav": self.initial_nav,
            "initial_cash": self.initial_cash,
            "initial_positions": [mark.to_dict() for mark in self.initial_positions],
            "days": [day.to_dict() for day in self.days],
            "synthetic": self.synthetic,
        }


def _actual_params(value: object, *, required: bool) -> dict[str, Any] | None:
    if value is None:
        if required:
            raise ValueError("actual_config_unknown")
        return None
    if type(value) is not dict:
        raise ValueError("actual_params")
    try:
        parsed = json.loads(json.dumps(value, sort_keys=True, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError("actual_params") from exc
    if type(parsed) is not dict or any(type(key) is not str or not key for key in parsed):
        raise ValueError("actual_params")
    return parsed


def _optional_identity(value: object, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise ValueError("identity")
        return None
    return _raw_identity(value)


@dataclass(frozen=True)
class ResearchTrialRecord:
    """One research attempt. Unknown actual params stay null, never a filler.

    Failed, rejected, and aborted trials store no run or return metric. They
    may keep known cost inputs. Succeeded points at one stored result and ledger.
    """

    trial_id: str
    domain: str
    strategy_profile: str
    status: ResearchTrialStatus
    candidate_config_id: str
    actual_params: Mapping[str, Any] | None
    param_set_id: str | None
    source_revision: str | None
    input_id: str
    window_start: date
    window_end: date
    calendar_id: str
    periods_per_year: float
    cost_source: str | None
    cost_inputs: Mapping[str, float]
    reason_code: str
    synthetic: bool
    run_id: str | None
    param_version: int | None

    def __post_init__(self) -> None:
        status = self.status
        if isinstance(status, str) and not isinstance(status, ResearchTrialStatus):
            try:
                status = ResearchTrialStatus(status)
            except ValueError as exc:
                raise ValueError("status") from exc
        if not isinstance(status, ResearchTrialStatus):
            raise ValueError("status")
        succeeded = status is ResearchTrialStatus.SUCCEEDED
        trial_id = _raw_identity(self.trial_id)
        domain = _label(self.domain)
        strategy_profile = _label(self.strategy_profile)
        candidate_config_id = _raw_identity(self.candidate_config_id)
        actual_params = _actual_params(self.actual_params, required=succeeded)
        param_set_id = _optional_identity(self.param_set_id, required=succeeded)
        source_revision = _optional_identity(self.source_revision, required=succeeded)
        input_id = _raw_identity(self.input_id)
        window_start = _require_date(self.window_start)
        window_end = _require_date(self.window_end)
        if window_end < window_start:
            raise ValueError("window")
        calendar_id = _label(self.calendar_id)
        try:
            periods = validate_periods_per_year(_finite_number(self.periods_per_year))
        except ValueError as exc:
            raise ValueError("periods_per_year") from exc
        cost_source = _optional_identity(self.cost_source, required=succeeded)
        if type(self.synthetic) is not bool:
            raise ValueError("synthetic")
        cost_inputs = _cost_inputs(self.cost_inputs, allow_empty=not succeeded)
        if succeeded:
            if not isinstance(self.run_id, str):
                raise ValueError("research_trial_result_link")
            run_id: str | None = _run_identity(self.run_id)
            if type(self.param_version) is not int or self.param_version <= 0:
                raise ValueError("param_version")
            param_version: int | None = self.param_version
            reason_code = _reason_code(self.reason_code, allow_empty=True)
            if reason_code != "":
                raise ValueError("reason_code")
        else:
            if self.run_id is not None or self.param_version is not None:
                raise ValueError("research_trial_result_link")
            run_id = None
            param_version = None
            if status is ResearchTrialStatus.STARTED:
                reason_code = _reason_code(self.reason_code, allow_empty=True)
                if reason_code != "":
                    raise ValueError("reason_code")
            elif status.value not in _RESEARCH_NON_SUCCESS:
                raise ValueError("status")
            else:
                reason_code = _reason_code(self.reason_code, allow_empty=False)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "trial_id", trial_id)
        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "strategy_profile", strategy_profile)
        object.__setattr__(self, "candidate_config_id", candidate_config_id)
        object.__setattr__(self, "actual_params", actual_params)
        object.__setattr__(self, "param_set_id", param_set_id)
        object.__setattr__(self, "source_revision", source_revision)
        object.__setattr__(self, "input_id", input_id)
        object.__setattr__(self, "window_start", window_start)
        object.__setattr__(self, "window_end", window_end)
        object.__setattr__(self, "calendar_id", calendar_id)
        object.__setattr__(self, "periods_per_year", periods)
        object.__setattr__(self, "cost_source", cost_source)
        object.__setattr__(self, "cost_inputs", cost_inputs)
        object.__setattr__(self, "reason_code", reason_code)
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "param_version", param_version)

    def to_dict(self) -> dict[str, object]:
        return {
            "trial_id": self.trial_id,
            "domain": self.domain,
            "strategy_profile": self.strategy_profile,
            "status": self.status.value,
            "candidate_config_id": self.candidate_config_id,
            "actual_params": None if self.actual_params is None else dict(self.actual_params),
            "param_set_id": self.param_set_id,
            "source_revision": self.source_revision,
            "input_id": self.input_id,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "calendar_id": self.calendar_id,
            "periods_per_year": self.periods_per_year,
            "cost_source": self.cost_source,
            "cost_inputs": dict(self.cost_inputs),
            "reason_code": self.reason_code,
            "synthetic": self.synthetic,
            "run_id": self.run_id,
            "param_version": self.param_version,
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
