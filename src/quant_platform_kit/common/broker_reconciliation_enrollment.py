"""Fail-closed, broker-independent enrollment of a legacy live baseline.

This is deliberately *not* an execution authorisation mechanism.  It turns
two or more separated, read-only broker reconciliation receipts into a
redacted candidate that a private control plane may send for independent
review.  A later controller still has to verify the candidate's provenance,
bind any reviewer receipts to ``candidate_sha256``, and make an explicit
``RECONCILE_ONLY -> ACTIVE_LKG`` state change.

The first observation of a legacy deployment cannot safely establish its own
expected state: doing so could bless a stale or externally changed account.
Requiring multiple time-separated, identical observations makes that first
baseline enrolment observable and auditable without exposing positions,
balances, orders, fills, or account identifiers.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from .broker_reconciliation import BrokerReconciliationEvidence


BROKER_RECONCILIATION_BASELINE_CANDIDATE_SCHEMA_VERSION = (
    "broker_reconciliation_baseline_candidate.v1"
)
DEFAULT_BROKER_RECONCILIATION_ENROLLMENT_MAX_AGE = timedelta(minutes=30)
DEFAULT_BROKER_RECONCILIATION_ENROLLMENT_MIN_SEPARATION = timedelta(minutes=1)
DEFAULT_BROKER_RECONCILIATION_ENROLLMENT_MAX_SPAN = timedelta(minutes=15)
_SHA256_LENGTH = 64


class BrokerReconciliationEnrollmentFinding(str, Enum):
    """Redacted reasons a first legacy baseline cannot enter review."""

    EVIDENCE_INVALID = "broker_reconciliation_enrollment_evidence_invalid"
    EVIDENCE_COUNT_INSUFFICIENT = "broker_reconciliation_enrollment_evidence_count_insufficient"
    EVIDENCE_NOT_TIME_SEPARATED = "broker_reconciliation_enrollment_evidence_not_time_separated"
    EVIDENCE_WINDOW_EXCEEDED = "broker_reconciliation_enrollment_evidence_window_exceeded"
    EVIDENCE_STALE = "broker_reconciliation_enrollment_evidence_stale"
    BROKER_CONNECTION_FAILED = "broker_reconciliation_enrollment_broker_connection_failed"
    ACCOUNT_IDENTITY_MISMATCH = "broker_reconciliation_enrollment_account_identity_mismatch"
    BASELINE_TARGET_MISMATCH = "broker_reconciliation_enrollment_baseline_target_mismatch"
    OBSERVATION_MISMATCH = "broker_reconciliation_enrollment_observation_mismatch"


def _normalize_time(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("timestamp must be ISO-8601") from exc
    else:
        raise ValueError("timestamp must be a datetime or ISO-8601 string")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _iso(value: datetime | str) -> str:
    return _normalize_time(value).isoformat().replace("+00:00", "Z")


def _digest(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a SHA-256 digest")
    normalized = value.strip().lower().removeprefix("sha256:")
    if len(normalized) != _SHA256_LENGTH or any(char not in "0123456789abcdef" for char in normalized):
        raise ValueError(f"{field_name} must be a SHA-256 digest")
    return normalized


def _canonical_json(value: Mapping[str, object]) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("baseline candidate cannot be canonicalized") from exc


def _candidate_payload(value: Mapping[str, object]) -> dict[str, object]:
    required = {
        "schema_version",
        "platform_id",
        "strategy_profile",
        "account_scope_sha256",
        "baseline_id",
        "baseline_target_sha256",
        "source_evidence_sha256",
        "first_observed_at",
        "last_observed_at",
        "positions_sha256",
        "cash_sha256",
        "open_orders_sha256",
        "recent_executions_sha256",
        "local_execution_ledger_sha256",
        "candidate_sha256",
    }
    if set(value) != required:
        raise ValueError("baseline candidate has invalid fields")
    if value["schema_version"] != BROKER_RECONCILIATION_BASELINE_CANDIDATE_SCHEMA_VERSION:
        raise ValueError("unsupported baseline candidate schema version")
    source = value["source_evidence_sha256"]
    if not isinstance(source, (tuple, list)) or len(source) < 2:
        raise ValueError("source_evidence_sha256 must contain at least two receipts")
    normalized_source = tuple(sorted({_digest(item, field_name="source_evidence_sha256") for item in source}))
    if len(normalized_source) != len(source):
        raise ValueError("source_evidence_sha256 must be unique")
    first = _normalize_time(value["first_observed_at"])
    last = _normalize_time(value["last_observed_at"])
    if first > last:
        raise ValueError("first_observed_at must not be after last_observed_at")
    required_text = (
        "platform_id",
        "strategy_profile",
        "baseline_id",
    )
    normalized: dict[str, object] = {
        "schema_version": BROKER_RECONCILIATION_BASELINE_CANDIDATE_SCHEMA_VERSION,
        "source_evidence_sha256": normalized_source,
        "first_observed_at": _iso(first),
        "last_observed_at": _iso(last),
    }
    for field_name in required_text:
        text = value[field_name]
        if not isinstance(text, str) or text != text.strip() or not text or len(text) > 128:
            raise ValueError(f"{field_name} must be a non-empty bounded string")
        normalized[field_name] = text
    for field_name in (
        "account_scope_sha256",
        "baseline_target_sha256",
        "positions_sha256",
        "cash_sha256",
        "open_orders_sha256",
        "recent_executions_sha256",
        "local_execution_ledger_sha256",
    ):
        normalized[field_name] = _digest(value[field_name], field_name=field_name)
    return normalized


def canonical_broker_reconciliation_baseline_candidate_json(value: Mapping[str, object]) -> str:
    """Return canonical candidate JSON excluding its self-digest."""

    return _canonical_json(_candidate_payload(value))


def calculate_broker_reconciliation_baseline_candidate_sha256(value: Mapping[str, object]) -> str:
    """Return the content address of a redacted enrollment candidate."""

    return hashlib.sha256(
        canonical_broker_reconciliation_baseline_candidate_json(value).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class BrokerReconciliationBaselineCandidate:
    """A non-authorising, review-ready candidate built from matching samples."""

    platform_id: str
    strategy_profile: str
    account_scope_sha256: str
    baseline_id: str
    baseline_target_sha256: str
    source_evidence_sha256: tuple[str, ...]
    first_observed_at: datetime | str
    last_observed_at: datetime | str
    positions_sha256: str
    cash_sha256: str
    open_orders_sha256: str
    recent_executions_sha256: str
    local_execution_ledger_sha256: str
    candidate_sha256: str
    schema_version: str = BROKER_RECONCILIATION_BASELINE_CANDIDATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        payload = _candidate_payload(self.to_dict())
        for field_name, value in payload.items():
            if field_name in {"first_observed_at", "last_observed_at"}:
                object.__setattr__(self, field_name, _normalize_time(value))
            elif field_name != "schema_version":
                object.__setattr__(self, field_name, value)
        digest = _digest(self.candidate_sha256, field_name="candidate_sha256")
        object.__setattr__(self, "candidate_sha256", digest)
        if digest != calculate_broker_reconciliation_baseline_candidate_sha256(self.to_dict()):
            raise ValueError("baseline candidate_sha256 mismatch")

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["first_observed_at"] = _iso(payload["first_observed_at"])
        payload["last_observed_at"] = _iso(payload["last_observed_at"])
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "BrokerReconciliationBaselineCandidate":
        _candidate_payload(value)
        return cls(**dict(value))

    @property
    def expected_digests(self) -> dict[str, str]:
        """Exact broker-state digests a private controller must later verify."""

        return {
            "positions_sha256": self.positions_sha256,
            "cash_sha256": self.cash_sha256,
            "open_orders_sha256": self.open_orders_sha256,
            "recent_executions_sha256": self.recent_executions_sha256,
            "local_execution_ledger_sha256": self.local_execution_ledger_sha256,
        }


@dataclass(frozen=True)
class BrokerReconciliationEnrollmentEvaluation:
    """Fail-closed result of comparing independent read-only observations."""

    findings: tuple[BrokerReconciliationEnrollmentFinding, ...]
    candidate: BrokerReconciliationBaselineCandidate | None

    @property
    def ready_for_independent_review(self) -> bool:
        return not self.findings and self.candidate is not None


def _coerce_evidence(value: BrokerReconciliationEvidence | Mapping[str, object]) -> BrokerReconciliationEvidence:
    if isinstance(value, BrokerReconciliationEvidence):
        return value
    return BrokerReconciliationEvidence.from_dict(value)


def _same_observation(left: BrokerReconciliationEvidence, right: BrokerReconciliationEvidence) -> bool:
    fields = (
        "platform_id",
        "strategy_profile",
        "account_scope_sha256",
        "baseline_id",
        "baseline_target_sha256",
        "runtime_target_sha256",
        "positions_sha256",
        "cash_sha256",
        "open_orders_sha256",
        "recent_executions_sha256",
        "local_execution_ledger_sha256",
    )
    return all(getattr(left, field_name) == getattr(right, field_name) for field_name in fields)


def _build_candidate(samples: tuple[BrokerReconciliationEvidence, ...]) -> BrokerReconciliationBaselineCandidate:
    first, last = samples[0], samples[-1]
    draft: dict[str, object] = {
        "schema_version": BROKER_RECONCILIATION_BASELINE_CANDIDATE_SCHEMA_VERSION,
        "platform_id": first.platform_id,
        "strategy_profile": first.strategy_profile,
        "account_scope_sha256": first.account_scope_sha256,
        "baseline_id": first.baseline_id,
        "baseline_target_sha256": first.baseline_target_sha256,
        "source_evidence_sha256": tuple(sample.evidence_sha256 for sample in samples),
        "first_observed_at": first.observed_at,
        "last_observed_at": last.observed_at,
        "positions_sha256": first.positions_sha256,
        "cash_sha256": first.cash_sha256,
        "open_orders_sha256": first.open_orders_sha256,
        "recent_executions_sha256": first.recent_executions_sha256,
        "local_execution_ledger_sha256": first.local_execution_ledger_sha256,
        "candidate_sha256": "0" * _SHA256_LENGTH,
    }
    draft["candidate_sha256"] = calculate_broker_reconciliation_baseline_candidate_sha256(draft)
    return BrokerReconciliationBaselineCandidate.from_dict(draft)


def evaluate_broker_reconciliation_baseline_enrollment(
    evidences: Iterable[BrokerReconciliationEvidence | Mapping[str, object]],
    *,
    now: datetime | None = None,
    max_age: timedelta = DEFAULT_BROKER_RECONCILIATION_ENROLLMENT_MAX_AGE,
    min_separation: timedelta = DEFAULT_BROKER_RECONCILIATION_ENROLLMENT_MIN_SEPARATION,
    max_span: timedelta = DEFAULT_BROKER_RECONCILIATION_ENROLLMENT_MAX_SPAN,
) -> BrokerReconciliationEnrollmentEvaluation:
    """Evaluate matching samples before a legacy baseline can enter AI review.

    This function never writes state or decides an approval.  A candidate is
    emitted only when every sample is fresh, time-separated, readable, bound
    to the same baseline, and has identical state digests.
    """

    if max_age <= timedelta(0) or min_separation <= timedelta(0) or max_span <= timedelta(0):
        raise ValueError("enrollment timing limits must be positive")
    findings: list[BrokerReconciliationEnrollmentFinding] = []

    def add(finding: BrokerReconciliationEnrollmentFinding) -> None:
        if finding not in findings:
            findings.append(finding)

    try:
        samples = tuple(sorted((_coerce_evidence(item) for item in evidences), key=lambda item: item.observed_at))
    except (TypeError, ValueError):
        return BrokerReconciliationEnrollmentEvaluation(
            findings=(BrokerReconciliationEnrollmentFinding.EVIDENCE_INVALID,), candidate=None
        )
    if len(samples) < 2:
        add(BrokerReconciliationEnrollmentFinding.EVIDENCE_COUNT_INSUFFICIENT)
        return BrokerReconciliationEnrollmentEvaluation(findings=tuple(findings), candidate=None)
    if len({item.evidence_sha256 for item in samples}) != len(samples):
        add(BrokerReconciliationEnrollmentFinding.EVIDENCE_NOT_TIME_SEPARATED)
    reference_now = _normalize_time(now or datetime.now(timezone.utc))
    first, last = samples[0], samples[-1]
    if last.observed_at > reference_now or reference_now - last.observed_at > max_age:
        add(BrokerReconciliationEnrollmentFinding.EVIDENCE_STALE)
    if last.observed_at - first.observed_at < min_separation:
        add(BrokerReconciliationEnrollmentFinding.EVIDENCE_NOT_TIME_SEPARATED)
    if last.observed_at - first.observed_at > max_span:
        add(BrokerReconciliationEnrollmentFinding.EVIDENCE_WINDOW_EXCEEDED)
    for sample in samples:
        if not sample.broker_connected:
            add(BrokerReconciliationEnrollmentFinding.BROKER_CONNECTION_FAILED)
        if not sample.account_identity_match:
            add(BrokerReconciliationEnrollmentFinding.ACCOUNT_IDENTITY_MISMATCH)
        if sample.baseline_target_sha256 != sample.runtime_target_sha256:
            add(BrokerReconciliationEnrollmentFinding.BASELINE_TARGET_MISMATCH)
        if not _same_observation(first, sample):
            add(BrokerReconciliationEnrollmentFinding.OBSERVATION_MISMATCH)
    if findings:
        return BrokerReconciliationEnrollmentEvaluation(findings=tuple(findings), candidate=None)
    return BrokerReconciliationEnrollmentEvaluation(findings=(), candidate=_build_candidate(samples))


__all__ = [
    "BROKER_RECONCILIATION_BASELINE_CANDIDATE_SCHEMA_VERSION",
    "DEFAULT_BROKER_RECONCILIATION_ENROLLMENT_MAX_AGE",
    "DEFAULT_BROKER_RECONCILIATION_ENROLLMENT_MAX_SPAN",
    "DEFAULT_BROKER_RECONCILIATION_ENROLLMENT_MIN_SEPARATION",
    "BrokerReconciliationBaselineCandidate",
    "BrokerReconciliationEnrollmentEvaluation",
    "BrokerReconciliationEnrollmentFinding",
    "calculate_broker_reconciliation_baseline_candidate_sha256",
    "canonical_broker_reconciliation_baseline_candidate_json",
    "evaluate_broker_reconciliation_baseline_enrollment",
]
