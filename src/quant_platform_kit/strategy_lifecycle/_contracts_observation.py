"""Return observation, calendar readiness, and interval coverage contracts."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal, Mapping, TypedDict

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


class IntervalReturnCoverage(TypedDict):
    """Local checkpoint coverage, not proof of native archive completeness."""

    method: str
    timezone: str
    currency: str
    valuation_basis: str
    account_scope_sha256: str | None
    source_segment_start_at: str | None
    source_segment_end_at: str | None
    available_return_start_at: str | None
    available_return_end_at: str | None
    return_start_at: str | None
    return_end_at: str | None
    requested_start_at: str | None
    requested_end_at: str | None
    requested_window_complete: bool | None
    coverage_status: Literal[
        "unavailable", "complete_segment", "truncated_segment", "complete_requested_window"
    ]
    normalized_interval_count: int
    segment_interval_count: int
    return_count: int
    truncation_reasons: list[str]


INTERVAL_SNAPSHOT_SCHEMA_VERSION = "strategy_lifecycle.snapshot.coverage.v1"
_INTERVAL_COVERAGE_REASONS = frozenset({
    "missing_interval", "overlapping_interval", "missing_interval_record", "null_interval",
    "invalid_interval", "interval_conflict", "same_end_different_start", "unlocated_invalid_interval",
    "mixed_account_scope", "observation_day_gap", "invalid_adjusted_return", "invalid_requested_window",
    "requested_checkpoint_unavailable",
})


def normalize_interval_return_coverage(value: Any) -> IntervalReturnCoverage:
    """Validate supplied checkpoint coverage; never infer native archive qualification."""
    if not isinstance(value, Mapping) or set(value) != set(IntervalReturnCoverage.__annotations__):
        raise ValueError("invalid_interval_return_coverage_fields")
    result = dict(value)
    for key, expected in {"method": "end_flow_checkpoint_daily_observations", "timezone": "UTC",
                          "currency": "USDT", "valuation_basis": "checkpoint_quantities_sampled_prices"}.items():
        if result[key] != expected:
            raise ValueError("unsupported_interval_return_coverage_method")
    scope = result["account_scope_sha256"]
    if scope is not None and (not isinstance(scope, str) or not re.fullmatch(r"[0-9a-f]{64}", scope)):
        raise ValueError("invalid_interval_return_coverage_scope")
    for key in ("normalized_interval_count", "segment_interval_count", "return_count"):
        if type(result[key]) is not int or result[key] < 0:
            raise ValueError("invalid_interval_return_coverage_count")
    if result["segment_interval_count"] > result["normalized_interval_count"]:
        raise ValueError("invalid_interval_return_coverage_count")
    reasons = result["truncation_reasons"]
    if (not isinstance(reasons, list) or any(not isinstance(reason, str) or reason not in _INTERVAL_COVERAGE_REASONS
                                           for reason in reasons) or len(set(reasons)) != len(reasons)):
        raise ValueError("invalid_interval_return_coverage_reasons")
    result["truncation_reasons"] = sorted(reasons)
    timestamps: dict[str, datetime | None] = {}
    for key in ("source_segment_start_at", "source_segment_end_at", "available_return_start_at",
                "available_return_end_at", "return_start_at", "return_end_at", "requested_start_at", "requested_end_at"):
        raw = result[key]
        parsed = None
        if raw is not None:
            if not isinstance(raw, str):
                raise ValueError("invalid_interval_return_coverage_timestamp")
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("invalid_interval_return_coverage_timestamp") from exc
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError("invalid_interval_return_coverage_timezone")
            parsed = parsed.astimezone(timezone.utc)
            result[key] = parsed.isoformat()
        timestamps[key] = parsed
    complete = result["requested_window_complete"]
    if complete is not None and type(complete) is not bool:
        raise ValueError("invalid_interval_requested_window_complete")
    status = result["coverage_status"]
    if status not in {"unavailable", "complete_segment", "truncated_segment", "complete_requested_window"}:
        raise ValueError("unknown_interval_return_coverage_status")
    if status == "unavailable":
        if result["return_count"] or timestamps["return_start_at"] or timestamps["return_end_at"] or complete is True:
            raise ValueError("invalid_unavailable_interval_return_coverage")
        return result
    if not scope or result["return_count"] < 1 or result["return_count"] >= result["segment_interval_count"]:
        raise ValueError("invalid_available_interval_return_coverage")
    for start, end in (("source_segment_start_at", "source_segment_end_at"),
                       ("available_return_start_at", "available_return_end_at"), ("return_start_at", "return_end_at")):
        if timestamps[start] is None or timestamps[end] is None or timestamps[start] >= timestamps[end]:
            raise ValueError("invalid_interval_return_coverage_window")
    if not (timestamps["source_segment_start_at"] <= timestamps["available_return_start_at"]
            <= timestamps["return_start_at"] < timestamps["return_end_at"]
            <= timestamps["available_return_end_at"] <= timestamps["source_segment_end_at"]):
        raise ValueError("invalid_interval_return_coverage_containment")
    if result["return_count"] != (timestamps["return_end_at"].date() - timestamps["return_start_at"].date()).days:
        raise ValueError("invalid_interval_return_coverage_count_window")
    requested = timestamps["requested_start_at"] is not None or timestamps["requested_end_at"] is not None
    if requested:
        if (status != "complete_requested_window" or complete is not True
                or timestamps["requested_start_at"] != timestamps["return_start_at"]
                or timestamps["requested_end_at"] != timestamps["return_end_at"]):
            raise ValueError("incomplete_interval_requested_window")
    elif complete is not None or status == "complete_requested_window":
        raise ValueError("invalid_interval_requested_window_complete")
    if status == "complete_segment" and reasons:
        raise ValueError("invalid_complete_interval_segment")
    if status == "truncated_segment" and not reasons:
        raise ValueError("missing_interval_truncation_reason")
    return result


def interval_return_coverage_comparison_reason(
    current: Any, reference: Any, *, current_window: Any, reference_metrics: Any,
) -> str:
    """Empty means comparable supplied windows; date labels alone are insufficient."""
    try:
        left = normalize_interval_return_coverage(current)
        right = normalize_interval_return_coverage(reference)
    except (ValueError, TypeError):
        return "interval_coverage_unavailable"
    if left["coverage_status"] == "unavailable" or right["coverage_status"] == "unavailable":
        return "interval_coverage_unavailable"
    for key in ("method", "timezone", "currency", "valuation_basis", "account_scope_sha256",
                "return_start_at", "return_end_at", "return_count"):
        if left[key] != right[key]:
            return "interval_comparison_window_or_method_mismatch"
    for cov, metrics in ((left, current_window), (right, reference_metrics)):
        start = datetime.fromisoformat(cov["return_start_at"]).date() + timedelta(days=1)
        end = datetime.fromisoformat(cov["return_end_at"]).date()
        if (metrics is None or getattr(metrics, "start_date", None) != start
                or getattr(metrics, "end_date", None) != end
                or type(getattr(metrics, "observation_count", None)) is not int
                or getattr(metrics, "observation_count", None) != cov["return_count"]):
            return "interval_metric_window_not_fully_bound"
        for name in ("sharpe_ratio", "cagr", "calmar_ratio", "win_rate", "max_drawdown"):
            value = getattr(metrics, name, None)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                return "interval_performance_numbers_unavailable"
    calendar = getattr(current_window, "calendar_id", "")
    periods = getattr(current_window, "periods_per_year", None)
    if (not calendar or calendar != getattr(reference_metrics, "calendar_id", "")
            or isinstance(periods, bool) or periods not in VALID_PERIODS_PER_YEAR
            or periods != getattr(reference_metrics, "periods_per_year", None)):
        return "interval_annualization_not_comparable"
    return ""


@dataclass(frozen=True)
class LiveReturnSeriesResult:
    """Derivation outcome; incomplete calendars never look like a successful short series."""

    series: Any  # pd.Series; typed loosely to avoid importing pandas in contracts
    status: str
    detail: str = ""
    coverage: IntervalReturnCoverage | None = None


@dataclass(frozen=True)
class LiveReturnCollectionResult:
    """Collector outcome with explicit incomplete profiles."""

    series_by_profile: Mapping[str, Any]
    incomplete_by_profile: Mapping[str, str]
    coverage_by_profile: Mapping[str, IntervalReturnCoverage] = field(default_factory=dict)


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


