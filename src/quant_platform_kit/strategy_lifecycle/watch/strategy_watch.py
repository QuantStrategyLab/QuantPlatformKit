"""Strategy optimization watcher for issue-only automation proposals."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from typing import Any, Final

from .automation_contracts import AutomationTask, EvidenceBundle, GateDecision, ProposedAction, TriggerRecord
from ..research_task import ResearchTaskError, build_strategy_diagnosis_task
from .strategy_automation_registry import LANE_RESEARCH_BACKLOG, summarize_strategy_registry_context
from .strategy_optimization_policy import evaluate_strategy_metrics

WATCHER_SCHEMA_VERSION = "strategy_optimization_watch.v1"
ISSUE_ONLY_ACTION = "open_issue"
PERFORMANCE_SCHEMA_VERSION = "strategy_performance.v2"
OPERATIONAL_SCHEMA_VERSION = "strategy_operational_metrics.v1"
METRICS_KIND_PERFORMANCE = "performance"
METRICS_KIND_OPERATIONAL = "operational_quality"
REQUIRED_PERFORMANCE_METRICS = ("sharpe", "cagr", "calmar", "win_rate", "max_dd")
MONITORING_SCHEMA_VERSION = "strategy_monitoring_evidence.v1"
METRICS_KIND_MONITORING = "monitoring_evidence"
MONITORING_FINDING_TYPE = "monitoring_trigger"
RESEARCH_INPUT_UNAVAILABLE_FINDING_TYPE = "research_input_unavailable"
RESEARCH_TASK_SOURCE_SCHEMA_VERSION = "qsl_research_task_source_snapshot.v1"
RESEARCH_TASK_SOURCE_ID = "aiaudit.strategy_optimization_watcher"
@dataclass(frozen=True)
class StrategyWatchRegistration:
    """Trusted source registration used by monitoring findings.

    Keep this registry data-only: adding a domain must not add a new
    execution path.  Unknown domains intentionally resolve to no repository
    so the watcher remains fail-closed.
    """

    domain: str
    repository: str


STRATEGY_WATCH_REGISTRY: Final[tuple[StrategyWatchRegistration, ...]] = (
    StrategyWatchRegistration("cn_equity", "QuantStrategyLab/CnEquityStrategies"),
    StrategyWatchRegistration("hk_equity", "QuantStrategyLab/HkEquityStrategies"),
    StrategyWatchRegistration("us_equity", "QuantStrategyLab/UsEquityStrategies"),
    StrategyWatchRegistration("crypto", "QuantStrategyLab/CryptoStrategies"),
)
# Compatibility view for callers that used the old mapping.  The tuple above
# remains the single source of truth.
STRATEGY_REPOSITORY_BY_DOMAIN: Final[dict[str, str]] = {
    item.domain: item.repository for item in STRATEGY_WATCH_REGISTRY
}


def resolve_strategy_watch_repository(domain: str) -> str:
    """Resolve a registered domain, returning ``""`` for unknown domains."""
    normalized = str(domain or "").strip()
    return next(
        (item.repository for item in STRATEGY_WATCH_REGISTRY if item.domain == normalized),
        "",
    )


def _dict_payload(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


COVERAGE_SCHEMA_VERSION = "strategy_performance.coverage_envelope.v1"
_COVERAGE_TIMESTAMP_FIELDS = (
    "source_segment_start_at", "source_segment_end_at", "available_return_start_at",
    "available_return_end_at", "return_start_at", "return_end_at", "requested_start_at", "requested_end_at",
)
_COVERAGE_FIELDS = frozenset(_COVERAGE_TIMESTAMP_FIELDS) | {
    "method", "timezone", "currency", "valuation_basis", "requested_window_complete", "coverage_status",
    "normalized_interval_count", "segment_interval_count", "return_count", "truncation_reasons",
}
_COVERAGE_REASONS = frozenset({
    "missing_interval", "overlapping_interval", "missing_interval_record", "null_interval",
    "invalid_interval", "interval_conflict", "same_end_different_start", "unlocated_invalid_interval",
    "mixed_account_scope", "observation_day_gap", "invalid_adjusted_return", "invalid_requested_window",
    "requested_checkpoint_unavailable",
})
_COMPARISON_FIELDS = frozenset({
    "comparable", "reason", "actual_start_date", "actual_end_date", "actual_observation_count", "calendar_id",
    "periods_per_year", "reference_coverage", "reference_start_date", "reference_end_date",
    "reference_observation_count", "reference_calendar_id", "reference_periods_per_year", "scope",
})
_COMPARISON_REASONS = frozenset({"", "interval_coverage_unavailable", "interval_comparison_window_or_method_mismatch",
    "interval_metric_window_not_fully_bound", "interval_performance_numbers_unavailable", "interval_annualization_not_comparable"})
_COVERAGE_CONTAINER_FIELDS = frozenset({"schema_version", "metrics_kind", "repo", "domain", "generated_at", "source", "snapshots"})
_COVERAGE_INNER_FIELDS = frozenset({
    "repo", "repository", "strategy_profile", "profile", "plugin", "strategy_plugin", "candidate_kind", "domain",
    "schema_version", "metrics_kind", "metric_set", "current_metrics", "current", "baseline_metrics", "baseline",
    "research_task_evidence", "source", "generated_at", "metadata",
})
_COVERAGE_METADATA_FIELDS = frozenset({
    "domain", "as_of", "window_days", "window_start", "window_end", "snapshot_computed_at", "backtest_computed_at",
    "snapshot_source_revision", "backtest_source_revision", "snapshot_cost_model", "backtest_cost_model",
    "provenance", "snapshot_data_timestamp", "backtest_data_timestamp", "interval_return_coverage", "interval_comparison",
})


def _coverage_protocol_present(payload: dict[str, Any]) -> bool:
    metadata = _dict_payload(payload.get("metadata"))
    return (str(payload.get("schema_version") or "").startswith("strategy_performance.coverage")
            or "payload" in payload or "coverage_context" in payload or "interval_return_coverage" in payload or "interval_comparison" in payload
            or "interval_return_coverage" in metadata or "interval_comparison" in metadata)


def _normalize_public_coverage(value: Any) -> dict[str, Any]:
    """Check the public 18-field projection without inventing private scope."""
    if not isinstance(value, dict) or set(value) != _COVERAGE_FIELDS:
        raise ValueError("invalid_public_coverage_fields")
    result = dict(value)
    for key, expected in {"method": "end_flow_checkpoint_daily_observations", "timezone": "UTC", "currency": "USDT",
                          "valuation_basis": "checkpoint_quantities_sampled_prices"}.items():
        if result[key] != expected:
            raise ValueError("unsupported_public_coverage_method")
    for key in ("normalized_interval_count", "segment_interval_count", "return_count"):
        if type(result[key]) is not int or result[key] < 0:
            raise ValueError("invalid_public_coverage_count")
    if result["segment_interval_count"] > result["normalized_interval_count"]:
        raise ValueError("invalid_public_coverage_count")
    reasons = result["truncation_reasons"]
    if (not isinstance(reasons, list) or len(reasons) > len(_COVERAGE_REASONS)
            or any(not isinstance(reason, str) or reason not in _COVERAGE_REASONS for reason in reasons)
            or len(set(reasons)) != len(reasons)):
        raise ValueError("invalid_public_coverage_reasons")
    timestamps: dict[str, datetime | None] = {}
    for key in _COVERAGE_TIMESTAMP_FIELDS:
        raw = result[key]
        parsed = None
        if raw is not None:
            if not isinstance(raw, str) or len(raw) > 64:
                raise ValueError("invalid_public_coverage_timestamp")
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if parsed.tzinfo is None or parsed.utcoffset() is None:
                    raise ValueError("invalid_public_coverage_timezone")
                parsed = parsed.astimezone(timezone.utc)
            except (ValueError, OverflowError) as exc:
                raise ValueError("invalid_public_coverage_timestamp") from exc
            result[key] = parsed.isoformat()
        timestamps[key] = parsed
    complete = result["requested_window_complete"]
    if complete is not None and type(complete) is not bool:
        raise ValueError("invalid_public_requested_window_complete")
    status = result["coverage_status"]
    if not isinstance(status, str) or status not in {"unavailable", "complete_segment", "truncated_segment", "complete_requested_window"}:
        raise ValueError("unknown_public_coverage_status")
    if status == "unavailable":
        if result["return_count"] or timestamps["return_start_at"] or timestamps["return_end_at"] or complete is True:
            raise ValueError("invalid_unavailable_public_coverage")
        return result
    if result["return_count"] < 1 or result["return_count"] >= result["segment_interval_count"]:
        raise ValueError("invalid_available_public_coverage")
    for start, end in (("source_segment_start_at", "source_segment_end_at"),
                       ("available_return_start_at", "available_return_end_at"), ("return_start_at", "return_end_at")):
        if timestamps[start] is None or timestamps[end] is None or timestamps[start] >= timestamps[end]:
            raise ValueError("invalid_public_coverage_window")
    if not (timestamps["source_segment_start_at"] <= timestamps["available_return_start_at"]
            <= timestamps["return_start_at"] < timestamps["return_end_at"]
            <= timestamps["available_return_end_at"] <= timestamps["source_segment_end_at"]):
        raise ValueError("invalid_public_coverage_containment")
    if result["return_count"] != (timestamps["return_end_at"].date() - timestamps["return_start_at"].date()).days:
        raise ValueError("invalid_public_coverage_count_window")
    if timestamps["requested_start_at"] is not None or timestamps["requested_end_at"] is not None:
        if (status != "complete_requested_window" or complete is not True
                or timestamps["requested_start_at"] != timestamps["return_start_at"]
                or timestamps["requested_end_at"] != timestamps["return_end_at"]):
            raise ValueError("incomplete_public_requested_window")
    elif complete is not None or status == "complete_requested_window":
        raise ValueError("invalid_public_requested_window_complete")
    if status == "complete_segment" and reasons:
        raise ValueError("invalid_complete_public_segment")
    if status == "truncated_segment" and not reasons:
        raise ValueError("missing_public_truncation_reason")
    return result


def _public_comparison_status(metadata: dict[str, Any], coverage: dict[str, Any], current: dict[str, Any], baseline: dict[str, Any]) -> str:
    comparison = metadata.get("interval_comparison")
    if not isinstance(comparison, dict) or set(comparison) != _COMPARISON_FIELDS:
        raise ValueError("invalid_public_comparison_fields")
    reason = comparison["reason"]
    if (type(comparison["comparable"]) is not bool or not isinstance(reason, str) or reason not in _COMPARISON_REASONS
            or comparison["comparable"] != (not bool(reason)) or comparison["scope"] != "supplied_checkpoint_window"):
        raise ValueError("invalid_public_comparison_claim")
    for key, expected in (("calendar_id", "CRYPTO_NATURAL_DAY"), ("periods_per_year", 365.25)):
        if isinstance(comparison[key], bool) or comparison[key] != expected:
            raise ValueError("public_annualization_not_comparable")
    if coverage["coverage_status"] != "unavailable":
        start = (datetime.fromisoformat(coverage["return_start_at"]).date() + timedelta(days=1)).isoformat()
        end = datetime.fromisoformat(coverage["return_end_at"]).date().isoformat()
        count = comparison["actual_observation_count"]
        if (comparison["actual_start_date"] != start or comparison["actual_end_date"] != end
                or type(count) is not int or count != coverage["return_count"]
                or type(current.get("observation_count")) is not int or current["observation_count"] != count):
            raise ValueError("public_metric_window_not_fully_bound")
        for key in REQUIRED_PERFORMANCE_METRICS:
            number = current.get(key)
            if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
                raise ValueError("public_performance_numbers_unavailable")
    if metadata.get("window_start", comparison["actual_start_date"]) != comparison["actual_start_date"] or metadata.get("window_end", comparison["actual_end_date"]) != comparison["actual_end_date"]:
        raise ValueError("public_metric_window_not_fully_bound")
    reference = comparison["reference_coverage"]
    if reference is None:
        if comparison["comparable"] or reason != "interval_coverage_unavailable":
            raise ValueError("public_comparison_reference_unavailable")
        return "unknown"
    reference = _normalize_public_coverage(reference)
    if coverage["coverage_status"] == "unavailable" or reference["coverage_status"] == "unavailable":
        if comparison["comparable"]:
            raise ValueError("invalid_public_comparison_claim")
        return "unknown"
    mismatch = any(coverage[key] != reference[key] for key in (
        "method", "timezone", "currency", "valuation_basis", "return_start_at", "return_end_at", "return_count"))
    for cov, metrics, prefix in ((coverage, current, "actual"), (reference, baseline, "reference")):
        expected_start = (datetime.fromisoformat(cov["return_start_at"]).date() + timedelta(days=1)).isoformat()
        expected_end = datetime.fromisoformat(cov["return_end_at"]).date().isoformat()
        count = comparison[f"{prefix}_observation_count"]
        if (comparison[f"{prefix}_start_date"] != expected_start or comparison[f"{prefix}_end_date"] != expected_end
                or type(count) is not int or count != cov["return_count"]
                or type(metrics.get("observation_count")) is not int or metrics["observation_count"] != count):
            raise ValueError("public_metric_window_not_fully_bound")
        for key in REQUIRED_PERFORMANCE_METRICS:
            number = metrics.get(key)
            if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
                raise ValueError("public_performance_numbers_unavailable")
    for key in ("calendar_id", "reference_calendar_id"):
        if comparison[key] != "CRYPTO_NATURAL_DAY":
            raise ValueError("public_annualization_not_comparable")
    for key in ("periods_per_year", "reference_periods_per_year"):
        number = comparison[key]
        if isinstance(number, bool) or not isinstance(number, (int, float)) or number != 365.25:
            raise ValueError("public_annualization_not_comparable")
    if comparison["comparable"] and mismatch:
        raise ValueError("invalid_public_comparison_claim")
    return "mismatch" if mismatch or reason else "consistent"


def _coverage_context(metadata: Any, current: dict[str, Any], baseline: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    """Expose only bounded, validated status; source metadata is never forwarded."""
    context: dict[str, Any] = {
        "read_status": "invalid" if errors else "valid", "public_comparison_status": "unknown",
        "comparison_status": "unknown", "optimization_status": "unavailable",
        "reason": "interval_scope_binding_unavailable",
        "explanation": "Public checkpoint windows can be internally consistent; trusted original account-scope binding is unavailable, so optimization is unavailable. Do not relabel as legacy v2 or P3 evidence.",
        "errors": list(errors),
    }
    try:
        if not isinstance(metadata, dict) or not set(metadata).issubset(_COVERAGE_METADATA_FIELDS):
            raise ValueError("invalid_public_coverage_metadata_fields")
        provenance = metadata.get("provenance", {})
        if not isinstance(provenance, dict) or not set(provenance).issubset({"snapshot", "backtest"}):
            raise ValueError("invalid_public_coverage_provenance_fields")
        for key, value in metadata.items():
            if key in {"interval_return_coverage", "interval_comparison", "provenance"}:
                continue
            if key == "window_days":
                if type(value) is not int or value < 1:
                    raise ValueError("invalid_public_coverage_metadata_value")
            elif not isinstance(value, str):
                raise ValueError("invalid_public_coverage_metadata_value")
        for item in provenance.values():
            if (not isinstance(item, dict) or not set(item).issubset({"source_revision", "cost_model", "data_timestamp", "status"})
                    or any(not isinstance(value, str) for value in item.values())):
                raise ValueError("invalid_public_coverage_provenance_fields")
        coverage = _normalize_public_coverage(metadata.get("interval_return_coverage"))
        comparison_status = _public_comparison_status(metadata, coverage, current, baseline)
        if not errors:
            context.update(public_comparison_status=comparison_status, coverage_status=coverage["coverage_status"],
                effective_window={"start_at": coverage["return_start_at"], "end_at": coverage["return_end_at"], "return_count": coverage["return_count"]},
                requested_window={"start_at": coverage["requested_start_at"], "end_at": coverage["requested_end_at"], "complete": coverage["requested_window_complete"]})
    except (ValueError, TypeError, OverflowError) as exc:
        # Only our fixed error codes escape; never echo malformed source values.
        context["errors"].append(str(exc) if isinstance(exc, ValueError) else "invalid_public_coverage_structure")
    if context["errors"]:
        context.update(read_status="invalid", reason="interval_coverage_contract_invalid")
        context["errors"] = sorted(set(context["errors"]))
    return context


@dataclass(frozen=True)
class StrategyWatchSnapshot:
    repo: str
    profile: str
    plugin: str = ""
    candidate_kind: str = "individual"
    domain: str = ""
    schema_version: str = ""
    metrics_kind: str = ""
    current_metrics: dict[str, Any] = field(default_factory=dict)
    baseline_metrics: dict[str, Any] = field(default_factory=dict)
    research_task_evidence: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    generated_at: str = ""
    coverage_context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
        *,
        default_repo: str = "",
        default_schema_version: str = "",
        default_metrics_kind: str = "",
        envelope_errors: tuple[str, ...] = (),
    ) -> "StrategyWatchSnapshot":
        errors = list(envelope_errors)
        wrapper_schema = str(payload.get("schema_version") or "")
        wrapped = "payload" in payload or wrapper_schema.startswith("strategy_performance.coverage")
        if wrapped:
            if (set(payload) != {"schema_version", "metrics_kind", "payload"}
                    or wrapper_schema != COVERAGE_SCHEMA_VERSION or payload.get("metrics_kind") != METRICS_KIND_PERFORMANCE):
                errors.append("invalid_coverage_item_envelope")
            inner = payload.get("payload")
            if not isinstance(inner, dict):
                errors.append("invalid_coverage_inner_payload")
                inner = {}
            if ("payload" in inner or "snapshots" in inner or inner.get("schema_version") != PERFORMANCE_SCHEMA_VERSION
                    or inner.get("metrics_kind") != METRICS_KIND_PERFORMANCE):
                errors.append("invalid_coverage_inner_contract")
            if not set(inner).issubset(_COVERAGE_INNER_FIELDS):
                errors.append("invalid_coverage_inner_fields")
            payload = inner
        metadata = _dict_payload(payload.get("metadata"))
        if wrapped or _coverage_protocol_present(payload):
            repos = {str(value).strip() for value in (default_repo, payload.get("repo"), payload.get("repository")) if value}
            domains = {str(value).strip() for value in (payload.get("domain"), metadata.get("domain")) if value}
            if len(repos) > 1 or len(domains) > 1:
                errors.append("coverage_source_identity_mismatch")
        coverage_present = _coverage_protocol_present(payload)
        if coverage_present and not wrapped:
            errors.append("coverage_envelope_required")
        current = _dict_payload(payload.get("current_metrics") or payload.get("current"))
        baseline = _dict_payload(payload.get("baseline_metrics") or payload.get("baseline"))
        context = _coverage_context(payload.get("metadata"), current, baseline, errors) if coverage_present or errors else {}
        profile = str(payload.get("strategy_profile") or payload.get("profile") or "").strip()
        return cls(
            repo=str(payload.get("repo") or payload.get("repository") or default_repo).strip(),
            profile=profile,
            plugin=str(payload.get("plugin") or payload.get("strategy_plugin") or "").strip(),
            candidate_kind=str(payload.get("candidate_kind") or "individual").strip(),
            domain=str(payload.get("domain") or "").strip(),
            schema_version=COVERAGE_SCHEMA_VERSION if wrapped and context else str(payload.get("schema_version") or default_schema_version).strip(),
            metrics_kind=str(payload.get("metrics_kind") or payload.get("metric_set") or default_metrics_kind).strip(),
            current_metrics=current,
            baseline_metrics=baseline,
            research_task_evidence=_dict_payload(payload.get("research_task_evidence")),
            source=str(payload.get("source") or "").strip(),
            generated_at=str(payload.get("generated_at") or "").strip(),
            coverage_context=context,
        )

    def subject(self) -> str:
        parts = [self.repo, self.profile or self.plugin]
        return ":".join(part for part in parts if part)

    def to_dict(self) -> dict[str, Any]:
        if self.coverage_context:
            return {"schema_version": self.schema_version, "metrics_kind": self.metrics_kind,
                    "coverage_context": dict(self.coverage_context)}
        return {
            "repo": self.repo,
            "profile": self.profile,
            "plugin": self.plugin,
            "candidate_kind": self.candidate_kind,
            "domain": self.domain,
            "schema_version": self.schema_version,
            "metrics_kind": self.metrics_kind,
            "current_metrics": self.current_metrics,
            "baseline_metrics": self.baseline_metrics,
            "research_task_evidence": self.research_task_evidence,
            "source": self.source,
            "generated_at": self.generated_at,
        }


@dataclass(frozen=True)
class StrategyWatchFinding:
    snapshot: StrategyWatchSnapshot
    severity: str
    signals: list[dict[str, Any]]
    finding_type: str = "metric_degradation"
    registry_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": WATCHER_SCHEMA_VERSION,
            "snapshot": self.snapshot.to_dict(),
            "severity": self.severity,
            "signals": self.signals,
            "finding_type": self.finding_type,
            "registry_context": self.registry_context,
        }


def build_strategy_monitoring_finding(
    *,
    domain: str,
    profile: str,
    severity: str,
    metrics: dict[str, Any],
    signals: list[dict[str, Any]],
    source: str,
    generated_at: str = "",
    repo: str = "",
) -> StrategyWatchFinding:
    """Build a pre-classified, issue-only finding from trusted monitor evidence."""
    normalized_domain = str(domain or "").strip()
    normalized_profile = str(profile or "").strip()
    resolved_repo = str(repo or resolve_strategy_watch_repository(normalized_domain) or "").strip()
    if not normalized_domain or not normalized_profile:
        raise ValueError("strategy monitoring finding requires domain and profile")
    if not resolved_repo:
        raise ValueError(f"no strategy repository is configured for domain={normalized_domain!r}")
    return StrategyWatchFinding(
        snapshot=StrategyWatchSnapshot(
            repo=resolved_repo,
            profile=normalized_profile,
            schema_version=MONITORING_SCHEMA_VERSION,
            metrics_kind=METRICS_KIND_MONITORING,
            current_metrics=dict(metrics),
            source=str(source or "").strip(),
            generated_at=str(generated_at or "").strip(),
        ),
        severity="high" if str(severity).strip().lower() == "high" else "medium",
        signals=[dict(signal) for signal in signals],
        finding_type=MONITORING_FINDING_TYPE,
    )


def build_research_input_unavailable_finding(
    *,
    repo: str,
    profile: str,
    status: str,
    reason_code: str,
    candidate_id: str = "",
    date_cutoff: str = "",
    source: str = "",
) -> StrategyWatchFinding:
    """Build a high-severity issue-only finding for a deferred research input.

    A deferred P1 source has not produced an observation.  It must be visible
    to operators, but it must never be treated as performance degradation or
    allowed to produce a strategy-change task.
    """
    normalized_repo = str(repo or "").strip()
    normalized_profile = str(profile or candidate_id or "").strip()
    normalized_status = str(status or "").strip().upper()
    normalized_reason = str(reason_code or "").strip()
    if not normalized_repo or not normalized_profile:
        raise ValueError("research input finding requires repository and profile")
    if normalized_status != "DEFERRED" or not normalized_reason:
        raise ValueError("research input finding requires a deferred status and reason code")
    metrics = {
        "p1_status": normalized_status,
        "reason_code": normalized_reason,
        "candidate_id": str(candidate_id or "").strip(),
        "date_cutoff": str(date_cutoff or "").strip(),
    }
    return StrategyWatchFinding(
        snapshot=StrategyWatchSnapshot(
            repo=normalized_repo,
            profile=normalized_profile,
            schema_version="research_input_terminal.v1",
            metrics_kind="research_input_terminal",
            current_metrics=metrics,
            source=str(source or "").strip(),
        ),
        severity="high",
        signals=[
            {
                "metric": "p1_status",
                "reason": (
                    f"P1 research input is deferred: {normalized_reason}; "
                    "no comparable performance observation was published"
                ),
            }
        ],
        finding_type=RESEARCH_INPUT_UNAVAILABLE_FINDING_TYPE,
    )


def _snapshots_from_payload(payload: dict[str, Any]) -> list[StrategyWatchSnapshot]:
    default_repo = str(payload.get("repo") or payload.get("repository") or "").strip()
    default_schema_version = str(payload.get("schema_version") or "").strip()
    default_metrics_kind = str(payload.get("metrics_kind") or payload.get("metric_set") or "").strip()
    raw_snapshots = payload.get("snapshots")
    if not isinstance(raw_snapshots, list):
        raw_snapshots = [payload]
    elif not raw_snapshots and default_schema_version.startswith("strategy_performance.coverage"):
        raw_snapshots = [{}]
    snapshots: list[StrategyWatchSnapshot] = []
    coverage_container = default_schema_version.startswith("strategy_performance.coverage")
    for item in raw_snapshots:
        errors: list[str] = []
        if coverage_container:
            if (default_schema_version != COVERAGE_SCHEMA_VERSION or default_metrics_kind != METRICS_KIND_PERFORMANCE
                    or (isinstance(payload.get("snapshots"), list) and set(payload) != _COVERAGE_CONTAINER_FIELDS)):
                errors.append("invalid_coverage_container_contract")
            if not isinstance(item, dict) or "payload" not in item:
                errors.append("coverage_item_envelope_required")
        elif isinstance(payload.get("snapshots"), list) and isinstance(item, dict) and "payload" in item:
            errors.append("coverage_container_envelope_required")
        if isinstance(payload.get("snapshots"), list) and _coverage_protocol_present(payload) and not coverage_container:
            errors.append("coverage_container_envelope_required")
        if isinstance(item, dict):
            inner = item.get("payload") if isinstance(item.get("payload"), dict) else item
            if coverage_container or _coverage_protocol_present(inner):
                metadata = _dict_payload(inner.get("metadata"))
                domains = {str(value).strip() for value in (payload.get("domain"), inner.get("domain"), metadata.get("domain")) if value}
                if len(domains) > 1:
                    errors.append("coverage_source_identity_mismatch")
            snapshots.append(
                StrategyWatchSnapshot.from_dict(
                    item,
                    default_repo=default_repo,
                    default_schema_version=default_schema_version,
                    default_metrics_kind=default_metrics_kind,
                    envelope_errors=tuple(errors),
                )
            )
        else:
            snapshots.append(
                StrategyWatchSnapshot(
                    repo=default_repo,
                    profile="",
                    schema_version=default_schema_version,
                    metrics_kind=default_metrics_kind,
                    coverage_context=_coverage_context(None, {}, {}, errors) if errors else {},
                )
            )
    return snapshots


def strategy_watch_coverage_status(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Read-only coverage status, separate from optimization findings."""
    return [dict(snapshot.coverage_context) for snapshot in _snapshots_from_payload(payload) if snapshot.coverage_context]


def _data_quality_signal(reason: str, *, metric: str = "data_quality") -> dict[str, Any]:
    return {"metric": metric, "reason": reason}


def _metric_value_issues(metrics: dict[str, Any], *, label: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for metric in REQUIRED_PERFORMANCE_METRICS:
        if metric not in metrics:
            continue
        value = metrics[metric]
        if isinstance(value, bool):
            valid = False
        else:
            try:
                valid = math.isfinite(float(value))
            except (TypeError, ValueError):
                valid = False
        if not valid:
            issues.append(_data_quality_signal(f"{label}.{metric} must be a finite numeric value", metric=metric))
    return issues


def _validate_snapshot_contract(snapshot: StrategyWatchSnapshot) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    schema_version = snapshot.schema_version
    metrics_kind = snapshot.metrics_kind

    if not schema_version and not metrics_kind:
        legacy_metrics = set(snapshot.current_metrics).intersection(snapshot.baseline_metrics, REQUIRED_PERFORMANCE_METRICS)
        if legacy_metrics:
            return _metric_value_issues(snapshot.current_metrics, label="current_metrics") + _metric_value_issues(
                snapshot.baseline_metrics, label="baseline_metrics"
            )
        return [_data_quality_signal("missing versioned performance metrics; no comparable legacy metrics found")]

    if schema_version == PERFORMANCE_SCHEMA_VERSION and not metrics_kind:
        metrics_kind = METRICS_KIND_PERFORMANCE
    elif metrics_kind == METRICS_KIND_PERFORMANCE and not schema_version:
        schema_version = PERFORMANCE_SCHEMA_VERSION

    if not schema_version:
        issues.append(_data_quality_signal("missing schema_version; expected strategy_performance.v2 payload"))
    if not metrics_kind:
        issues.append(_data_quality_signal("missing metrics_kind; expected performance payload"))

    if schema_version == OPERATIONAL_SCHEMA_VERSION or metrics_kind == METRICS_KIND_OPERATIONAL:
        issues.append(
            _data_quality_signal(
                "operational metrics payload is incompatible with optimization watcher; publish strategy_performance.v2 instead"
            )
        )
        return issues

    if schema_version and schema_version != PERFORMANCE_SCHEMA_VERSION:
        issues.append(
            _data_quality_signal(
                f"unsupported schema_version={schema_version!r}; expected {PERFORMANCE_SCHEMA_VERSION}"
            )
        )
    if metrics_kind and metrics_kind != METRICS_KIND_PERFORMANCE:
        issues.append(
            _data_quality_signal(
                f"unsupported metrics_kind={metrics_kind!r}; expected {METRICS_KIND_PERFORMANCE!r}"
            )
        )
    if issues:
        return issues

    missing_current = [metric for metric in REQUIRED_PERFORMANCE_METRICS if metric not in snapshot.current_metrics]
    missing_baseline = [metric for metric in REQUIRED_PERFORMANCE_METRICS if metric not in snapshot.baseline_metrics]
    if missing_current:
        issues.append(
            _data_quality_signal(
                f"current_metrics missing required performance metrics: {', '.join(missing_current)}"
            )
        )
    if missing_baseline:
        issues.append(
            _data_quality_signal(
                f"baseline_metrics missing required performance metrics: {', '.join(missing_baseline)}"
            )
        )
    issues.extend(_metric_value_issues(snapshot.current_metrics, label="current_metrics"))
    issues.extend(_metric_value_issues(snapshot.baseline_metrics, label="baseline_metrics"))
    return issues


def evaluate_strategy_watch(payload: dict[str, Any]) -> list[StrategyWatchFinding]:
    """Evaluate metrics payload and return issue-worthy findings only."""
    registry_payload = payload.get("automation_registry") or payload.get("registry") or {}
    findings: list[StrategyWatchFinding] = []
    for snapshot in _snapshots_from_payload(payload):
        if snapshot.coverage_context:
            continue
        validation_issues = _validate_snapshot_contract(snapshot)
        context = summarize_strategy_registry_context(registry_payload, snapshot.profile) if snapshot.profile else {}
        if validation_issues:
            findings.append(
                StrategyWatchFinding(
                    snapshot=snapshot,
                    severity="medium",
                    signals=validation_issues,
                    finding_type="data_quality",
                    registry_context=context,
                )
            )
            continue
        decision = evaluate_strategy_metrics(snapshot.current_metrics, snapshot.baseline_metrics)
        if not decision["should_open_issue"]:
            continue
        findings.append(
            StrategyWatchFinding(
                snapshot=snapshot,
                severity=str(decision["severity"]),
                signals=list(decision["signals"]),
                finding_type="metric_degradation",
                registry_context=context,
            )
        )
    return findings


def finding_event_key(finding: StrategyWatchFinding) -> str:
    payload = {
        "snapshot": finding.snapshot.to_dict(),
        "severity": finding.severity,
        "signals": finding.signals,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def finding_to_automation_task(finding: StrategyWatchFinding) -> AutomationTask:
    """Convert a deterministic finding into an issue-only automation task."""
    if finding.snapshot.coverage_context or finding.snapshot.schema_version.startswith("strategy_performance.coverage"):
        raise ValueError("coverage observations cannot authorize optimization issues")
    lane = str(finding.registry_context.get("automation_lane") or LANE_RESEARCH_BACKLOG)
    event_key = finding_event_key(finding)
    signal_reasons = [str(signal.get("reason") or signal.get("metric") or "metric degraded") for signal in finding.signals]
    finding_type = str(finding.finding_type or "metric_degradation")
    if finding_type == "data_quality":
        trigger_kind = "strategy_metrics_contract_invalid"
        evidence_summary = "Strategy metrics payload failed watcher contract validation."
        rationale = (
            "Open a data-quality issue so the source repo publishes "
            "strategy_performance.v2 before optimization automation runs again."
        )
    elif finding_type == RESEARCH_INPUT_UNAVAILABLE_FINDING_TYPE:
        trigger_kind = "strategy_research_input_unavailable"
        evidence_summary = "A trusted P1 terminal record deferred the research input."
        rationale = (
            "Restore the trusted research-data input before optimization automation "
            "or any strategy-change proposal resumes."
        )
    elif finding_type == MONITORING_FINDING_TYPE:
        trigger_kind = "strategy_monitoring_trigger"
        evidence_summary = "Strategy monitoring evidence crossed a research-review threshold."
        rationale = "Open a research optimization issue for AI diagnosis and bounded, no-order experiment planning."
    else:
        trigger_kind = "strategy_metric_degradation"
        evidence_summary = "Deterministic strategy metrics crossed degradation thresholds."
        rationale = "Open a research optimization issue for AI diagnosis and sandbox experiment planning."
    trigger = TriggerRecord(
        source="strategy_optimization_watcher",
        kind=trigger_kind,
        severity=finding.severity,
        reason="; ".join(signal_reasons) or (
            "strategy metrics contract invalid"
            if finding_type == "data_quality"
            else "research input unavailable"
            if finding_type == RESEARCH_INPUT_UNAVAILABLE_FINDING_TYPE
            else "strategy metrics degraded"
        ),
        subject=finding.snapshot.subject(),
        metrics=finding.snapshot.current_metrics,
        evidence=signal_reasons,
    )
    evidence = EvidenceBundle(
        summary=evidence_summary,
        artifacts=[finding.snapshot.source] if finding.snapshot.source else [],
        metrics={
            "current": finding.snapshot.current_metrics,
            "baseline": finding.snapshot.baseline_metrics,
        },
        risks=[
            "issue-only: no strategy code, live parameters, broker/order paths, or deployment are changed",
            "sandbox backtest evidence is required before any PR can be proposed",
        ],
    )
    proposed = ProposedAction(
        action=ISSUE_ONLY_ACTION,
        lane=lane,
        target=finding.snapshot.repo,
        rationale=rationale,
        requires_human_review=False,
        metadata={"profile": finding.snapshot.profile, "plugin": finding.snapshot.plugin, "event_key": event_key, "finding_type": finding_type},
    )
    gate = GateDecision(
        allowed=True,
        reason="Issue-only proposal is allowed; it may only lead to a separately validated, inactive research task.",
        required_checks=[
            "qsl.research_task.v1 validation before any experiment",
            "offline no-order sandbox backtest evidence before any candidate PR",
            "inactive candidate registry/authority gate before P4-P6 impact",
        ],
        human_review_required=False,
        metadata={"issue_only": True, "live_impact_allowed": False},
    )
    return AutomationTask(
        trigger=trigger,
        evidence=evidence,
        proposed_action=proposed,
        gate_decision=gate,
        metadata={"event_key": event_key, "finding_type": finding_type},
    )


def finding_to_research_task(finding: StrategyWatchFinding, *, parameter_bounds_sha256: str | None = None) -> dict[str, Any] | None:
    """Build a task only when a verified P3 comparison binds every input.

    Existing legacy/operational watcher lanes remain issue-only.  They must not
    be promoted into a research task merely because they emitted a finding.
    """
    snapshot = finding.snapshot
    if snapshot.coverage_context or snapshot.schema_version.startswith("strategy_performance.coverage"):
        return None
    if finding.finding_type != "metric_degradation" or snapshot.metrics_kind != METRICS_KIND_PERFORMANCE:
        return None
    strategy_repository = STRATEGY_REPOSITORY_BY_DOMAIN.get(snapshot.domain)
    if not strategy_repository:
        return None
    try:
        return build_strategy_diagnosis_task(
            event_key=finding_event_key(finding),
            created_at=snapshot.generated_at,
            candidate_id=snapshot.profile,
            candidate_kind=snapshot.candidate_kind,
            domain=snapshot.domain,
            strategy_repository=strategy_repository,
            evidence=snapshot.research_task_evidence,
            parameter_bounds_sha256=parameter_bounds_sha256,
        )
    except ResearchTaskError:
        return None


def research_task_context_available(payload: dict[str, Any]) -> bool:
    """Whether the watcher payload carries the bounded P3 bindings a task needs."""
    snapshots = (_snapshots_from_payload(payload) if payload.get("schema_version") == COVERAGE_SCHEMA_VERSION
                 and isinstance(payload.get("snapshots"), list) else [StrategyWatchSnapshot.from_dict(payload)])
    return any(
        not snapshot.coverage_context
        and snapshot.metrics_kind == METRICS_KIND_PERFORMANCE
        and snapshot.candidate_kind in {"individual", "portfolio", "plugin"}
        and snapshot.domain in STRATEGY_REPOSITORY_BY_DOMAIN
        and bool(snapshot.profile)
        and set(snapshot.research_task_evidence) == {"p1_input_digest", "p2_config_digest", "p3_evidence_id", "strategy_revision", "producer_revision"}
        for snapshot in snapshots
    )


def research_task_source_snapshot(
    findings: list[StrategyWatchFinding],
    *,
    context_available: bool,
    computed_at: str,
    task_builder=finding_to_research_task,
) -> dict[str, Any]:
    """Project only verified tasks into the separate, source-owned queue index."""
    tasks: list[dict[str, Any]] = []
    errors: list[str] = []
    if not context_available:
        errors.append("research_task_context_unavailable")
    else:
        for finding in findings:
            task = task_builder(finding)
            if task is None:
                errors.append("research_task_contract_unavailable")
            else:
                tasks.append(task)
    generated_values = [finding.snapshot.generated_at for finding in findings if finding.snapshot.generated_at]
    generated_at = max(generated_values) if generated_values else computed_at
    return {
        "schema_version": RESEARCH_TASK_SOURCE_SCHEMA_VERSION,
        "source_id": RESEARCH_TASK_SOURCE_ID,
        "generated_at": generated_at,
        "computed_at": computed_at,
        "data_status": "unavailable" if errors else "ready",
        "tasks": [] if errors else tasks,
        "errors": sorted(set(errors)),
    }


def watcher_issue_key(task: AutomationTask) -> str:
    payload = task.to_dict()
    trigger = payload.get("trigger") if isinstance(payload.get("trigger"), dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    subject = str(trigger.get("subject") or "")
    key_payload: dict[str, Any] = {"subject": subject}
    finding_type = str(metadata.get("finding_type") or "metric_degradation")
    if finding_type != "metric_degradation":
        key_payload["finding_type"] = finding_type
        key_payload["trigger_kind"] = str(trigger.get("kind") or "")
    raw = json.dumps(key_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def issue_for_task(task: AutomationTask) -> dict[str, str]:
    """Build a GitHub issue title/body for a strategy optimization task."""
    payload = task.to_dict()
    trigger = payload["trigger"]
    evidence = payload["evidence"]
    action = payload["proposed_action"]
    event_key = str(payload.get("metadata", {}).get("event_key") or "")
    issue_key = watcher_issue_key(task)
    title = f"AI strategy optimization proposal: {trigger.get('subject') or action.get('target') or 'strategy profile'}"
    signals = "\n".join(f"- {item}" for item in trigger.get("evidence", [])) or "- Strategy metrics degraded."
    checks = "\n".join(f"- [ ] {item}" for item in payload["gate_decision"].get("required_checks", []))
    risks = "\n".join(f"- {item}" for item in evidence.get("risks", []))
    body = "\n".join(
        [
            f"<!-- strategy-optimization-watcher:{issue_key} -->",
            "## Summary",
            str(evidence.get("summary") or "Strategy optimization watcher opened this issue."),
            "",
            "## Trigger",
            f"- Severity: `{trigger.get('severity')}`",
            f"- Subject: `{trigger.get('subject')}`",
            f"- Event key: `{event_key}`",
            "",
            "## Signals",
            signals,
            "",
            "## Safety boundary",
            risks,
            "",
            "## Required gates before candidate or live impact",
            checks,
            "",
            "This watcher only opens an issue. It does not modify strategy code, tune active parameters, submit orders, merge PRs, or deploy.",
        ]
    )
    return {"title": title[:240], "body": body}
