"""Fail-closed contracts for recovering an existing reconciled live baseline.

The shared layer is deliberately pure: it has no HTTP, broker, cloud-store,
or state-write implementation.  A platform-owned private controller must
recheck the broker after an operator confirmation, then atomically compare and
set one exact target from ``RECONCILE_ONLY`` to ``ACTIVE_LKG``.  The plan
returned here is never an order or execution authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Protocol, runtime_checkable

from .broker_reconciliation import BrokerReconciliationEvidence, evaluate_broker_reconciliation_recovery
from .broker_reconciliation_enrollment import (
    BROKER_RECONCILIATION_BASELINE_CANDIDATE_V2_SCHEMA_VERSION,
    BrokerReconciliationBaselineCandidate,
)


RECONCILIATION_RECOVERY_SOURCE_SNAPSHOT_SCHEMA_VERSION = "qsl_reconciliation_recovery_source_snapshot.v1"
RECONCILIATION_RECOVERY_CONFIRMATION_SCHEMA_VERSION = "qsl_reconciliation_recovery_confirmation.v1"
RECONCILIATION_RECOVERY_TRANSITION_PLAN_SCHEMA_VERSION = "broker_reconciliation_recovery_transition_plan.v1"
DEFAULT_RECONCILIATION_RECOVERY_MAX_AGE = timedelta(minutes=30)
DEFAULT_RECONCILIATION_RECOVERY_MIN_SAMPLE_SEPARATION = timedelta(minutes=1)
DEFAULT_RECONCILIATION_RECOVERY_MAX_SAMPLE_WINDOW = timedelta(minutes=15)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
_PROFILE = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_LOGIN = re.compile(r"^[A-Za-z0-9-]{1,39}$")


def _time(value: datetime | str, field_name: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field_name} must be ISO-8601") from exc
    else:
        raise ValueError(f"{field_name} must be a datetime or ISO-8601 string")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _iso(value: datetime | str, field_name: str) -> str:
    return _time(value, field_name).isoformat().replace("+00:00", "Z")


def _digest(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a SHA-256 digest")
    normalized = value.strip().lower().removeprefix("sha256:")
    if not _SHA256.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a SHA-256 digest")
    return normalized


def _identifier(value: object, field_name: str, *, profile: bool = False) -> str:
    pattern = _PROFILE if profile else _IDENTIFIER
    if not isinstance(value, str) or value != value.strip() or not pattern.fullmatch(value):
        raise ValueError(f"{field_name} has invalid characters")
    return value


def _confirmation_digest(value: Mapping[str, object]) -> str:
    material = dict(value)
    material.pop("confirmation_sha256", None)
    try:
        body = json.dumps(material, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("confirmation cannot be canonicalized") from exc
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReconciliationRecoveryDualReview:
    """Redacted advisory review result; never an execution or recovery authority."""

    outcome: str
    reviewer_count: int
    evidence_binding_sha256: str

    def __post_init__(self) -> None:
        outcome = str(self.outcome or "").strip().lower()
        if outcome not in {"approved", "rejected", "unavailable"}:
            raise ValueError("dual_review.outcome is unsupported")
        if isinstance(self.reviewer_count, bool) or not isinstance(self.reviewer_count, int) or not 0 <= self.reviewer_count <= 10:
            raise ValueError("dual_review.reviewer_count must be a bounded integer")
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "evidence_binding_sha256", _digest(self.evidence_binding_sha256, "dual_review.evidence_binding_sha256"))

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ReconciliationRecoveryRecord:
    """One redacted recovery row accepted by the QSL console ingress."""

    recovery_id: str
    console_platform: str
    candidate: BrokerReconciliationBaselineCandidate
    dual_review: ReconciliationRecoveryDualReview
    readiness: str
    blocker_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "recovery_id", _identifier(self.recovery_id, "recovery_id"))
        object.__setattr__(self, "console_platform", _identifier(self.console_platform, "console_platform", profile=True))
        if not isinstance(self.candidate, BrokerReconciliationBaselineCandidate):
            raise TypeError("candidate must be BrokerReconciliationBaselineCandidate")
        if not isinstance(self.dual_review, ReconciliationRecoveryDualReview):
            raise TypeError("dual_review must be ReconciliationRecoveryDualReview")
        readiness = str(self.readiness or "").strip()
        if readiness not in {"blocked", "awaiting_human_confirmation"}:
            raise ValueError("readiness is unsupported")
        blockers = tuple(str(item).strip() for item in self.blocker_codes)
        if len(blockers) > 20 or any(not item or len(item) > 160 for item in blockers) or len(set(blockers)) != len(blockers):
            raise ValueError("blocker_codes must be unique bounded values")
        if readiness == "blocked" and not blockers:
            raise ValueError("blocked recovery record requires blocker_codes")
        if readiness == "awaiting_human_confirmation" and blockers:
            raise ValueError("awaiting recovery record cannot contain blockers")
        object.__setattr__(self, "readiness", readiness)
        object.__setattr__(self, "blocker_codes", blockers)

    def to_console_dict(self) -> dict[str, object]:
        candidate = self.candidate
        return {
            "recovery_id": self.recovery_id,
            "platform": self.console_platform,
            "strategy_profile": candidate.strategy_profile,
            "environment": "live",
            "reconciliation_state": "RECONCILE_ONLY",
            "readiness": self.readiness,
            "candidate_sha256": candidate.candidate_sha256,
            "evidence_sample_count": len(candidate.source_evidence_sha256),
            "first_observed_at": _iso(candidate.first_observed_at, "candidate.first_observed_at"),
            "last_observed_at": _iso(candidate.last_observed_at, "candidate.last_observed_at"),
            "dual_review": self.dual_review.to_dict(),
            "blocker_codes": list(self.blocker_codes),
        }


@dataclass(frozen=True)
class ReconciliationRecoverySourceSnapshot:
    """Exact, redacted source snapshot for ``/sync-reconciliation-recovery-source``."""

    source_id: str
    generated_at: datetime | str
    computed_at: datetime | str
    records: tuple[ReconciliationRecoveryRecord, ...]
    errors: tuple[str, ...] = ()
    schema_version: str = RECONCILIATION_RECOVERY_SOURCE_SNAPSHOT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != RECONCILIATION_RECOVERY_SOURCE_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("unsupported reconciliation recovery source schema")
        object.__setattr__(self, "source_id", _identifier(self.source_id, "source_id"))
        records = tuple(self.records)
        if len(records) > 100 or any(not isinstance(item, ReconciliationRecoveryRecord) for item in records):
            raise ValueError("records must contain at most 100 recovery records")
        if len({item.recovery_id for item in records}) != len(records):
            raise ValueError("records must not repeat recovery_id")
        errors = tuple(str(item).strip() for item in self.errors)
        if len(errors) > 100 or any(not item or len(item) > 160 for item in errors) or len(set(errors)) != len(errors):
            raise ValueError("errors must contain unique bounded values")
        object.__setattr__(self, "generated_at", _time(self.generated_at, "generated_at"))
        object.__setattr__(self, "computed_at", _time(self.computed_at, "computed_at"))
        object.__setattr__(self, "records", records)
        object.__setattr__(self, "errors", errors)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "generated_at": _iso(self.generated_at, "generated_at"),
            "computed_at": _iso(self.computed_at, "computed_at"),
            "data_status": "ready",
            "recoveries": [record.to_console_dict() for record in self.records],
            "errors": list(self.errors),
        }


def build_reconciliation_recovery_record(
    *,
    recovery_id: str,
    console_platform: str,
    candidate: BrokerReconciliationBaselineCandidate,
    dual_review: ReconciliationRecoveryDualReview | None = None,
    now: datetime | None = None,
    max_age: timedelta = DEFAULT_RECONCILIATION_RECOVERY_MAX_AGE,
    min_separation: timedelta = DEFAULT_RECONCILIATION_RECOVERY_MIN_SAMPLE_SEPARATION,
    max_sample_window: timedelta = DEFAULT_RECONCILIATION_RECOVERY_MAX_SAMPLE_WINDOW,
) -> ReconciliationRecoveryRecord:
    """Build a non-authorising row from a platform-verified source-bound candidate.

    The source root binds content, not trust or completeness. The platform must
    verify the underlying receipts before calling. ``min_separation`` remains
    a compatibility argument; optional model review is advisory only.
    """

    if max_age <= timedelta(0) or max_sample_window <= timedelta(0):
        raise ValueError("recovery timing limits must be positive")
    candidate = BrokerReconciliationBaselineCandidate.from_dict(candidate.to_dict())
    reference_now = _time(now or datetime.now(timezone.utc), "now")
    window = candidate.last_observed_at - candidate.first_observed_at
    blockers: list[str] = []
    if candidate.schema_version != BROKER_RECONCILIATION_BASELINE_CANDIDATE_V2_SCHEMA_VERSION:
        blockers.append("reconciliation_recovery_source_binding_missing")
    if window > max_sample_window:
        blockers.append("reconciliation_recovery_sample_window_invalid")
    if candidate.last_observed_at > reference_now or reference_now - candidate.last_observed_at > max_age:
        blockers.append("reconciliation_recovery_candidate_stale")
    if dual_review is None:
        dual_review = ReconciliationRecoveryDualReview("unavailable", 0, candidate.candidate_sha256)
    if dual_review.evidence_binding_sha256 != candidate.candidate_sha256:
        blockers.append("reconciliation_recovery_dual_review_binding_mismatch")
    return ReconciliationRecoveryRecord(
        recovery_id=recovery_id,
        console_platform=console_platform,
        candidate=candidate,
        dual_review=dual_review,
        readiness="awaiting_human_confirmation" if not blockers else "blocked",
        blocker_codes=tuple(blockers),
    )


@dataclass(frozen=True)
class ReconciliationRecoveryConfirmation:
    """Current immutable console receipt.  It remains explicitly non-executable."""

    recovery_id: str
    candidate_sha256: str
    dual_review_binding_sha256: str
    confirmed_at: datetime | str
    confirmed_by: str
    no_order: bool
    execution_authority_granted: bool
    confirmation_sha256: str
    schema_version: str = RECONCILIATION_RECOVERY_CONFIRMATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != RECONCILIATION_RECOVERY_CONFIRMATION_SCHEMA_VERSION:
            raise ValueError("unsupported reconciliation recovery confirmation schema")
        if self.no_order is not True or self.execution_authority_granted is not False:
            raise ValueError("confirmation must remain non-executable")
        confirmed_by = str(self.confirmed_by or "").strip()
        if not _LOGIN.fullmatch(confirmed_by):
            raise ValueError("confirmed_by has invalid characters")
        object.__setattr__(self, "recovery_id", _identifier(self.recovery_id, "recovery_id"))
        object.__setattr__(self, "candidate_sha256", _digest(self.candidate_sha256, "candidate_sha256"))
        object.__setattr__(self, "dual_review_binding_sha256", _digest(self.dual_review_binding_sha256, "dual_review_binding_sha256"))
        object.__setattr__(self, "confirmed_at", _time(self.confirmed_at, "confirmed_at"))
        object.__setattr__(self, "confirmed_by", confirmed_by)
        digest = _digest(self.confirmation_sha256, "confirmation_sha256")
        object.__setattr__(self, "confirmation_sha256", digest)
        if digest != calculate_reconciliation_recovery_confirmation_sha256(self.to_dict()):
            raise ValueError("confirmation_sha256 mismatch")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "recovery_id": self.recovery_id,
            "candidate_sha256": self.candidate_sha256,
            "dual_review_binding_sha256": self.dual_review_binding_sha256,
            "confirmed_at": _iso(self.confirmed_at, "confirmed_at"),
            "confirmed_by": self.confirmed_by,
            "no_order": True,
            "execution_authority_granted": False,
            "confirmation_sha256": self.confirmation_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ReconciliationRecoveryConfirmation":
        required = {
            "schema_version", "recovery_id", "candidate_sha256", "dual_review_binding_sha256", "confirmed_at",
            "confirmed_by", "no_order", "execution_authority_granted", "confirmation_sha256",
        }
        if set(value) != required:
            raise ValueError("reconciliation recovery confirmation has invalid fields")
        return cls(**dict(value))


def calculate_reconciliation_recovery_confirmation_sha256(value: Mapping[str, object]) -> str:
    """Return the QRS-compatible content digest for a confirmation receipt."""

    return _confirmation_digest(value)


class ReconciliationRecoveryActivationFinding(str, Enum):
    CURRENT_STATE_NOT_RECONCILE_ONLY = "reconciliation_recovery_current_state_not_reconcile_only"
    CONFIRMATION_INVALID = "reconciliation_recovery_confirmation_invalid"
    CONFIRMATION_CANDIDATE_MISMATCH = "reconciliation_recovery_confirmation_candidate_mismatch"
    CONFIRMATION_DUAL_REVIEW_MISMATCH = "reconciliation_recovery_confirmation_dual_review_mismatch"
    CONFIRMATION_STALE = "reconciliation_recovery_confirmation_stale"
    EVIDENCE_NOT_REOBSERVED_AFTER_CONFIRMATION = "reconciliation_recovery_evidence_not_reobserved_after_confirmation"
    SOURCE_BINDING_MISSING = "reconciliation_recovery_source_binding_missing"
    DUAL_REVIEW_NOT_REVERIFIED = "reconciliation_recovery_dual_review_not_reverified"


@dataclass(frozen=True)
class ReconciliationRecoveryTransitionPlan:
    """Proposed exact CAS transition; a platform port must apply it atomically."""

    recovery_id: str
    candidate_sha256: str
    confirmation_sha256: str
    baseline_id: str
    baseline_target_sha256: str
    expected_digests: Mapping[str, str]
    verified_at: datetime | str
    expected_live_continuity_state: str = "RECONCILE_ONLY"
    next_live_continuity_state: str = "ACTIVE_LKG"
    no_order: bool = True
    execution_authority_granted: bool = False
    requires_atomic_compare_and_set: bool = True
    schema_version: str = RECONCILIATION_RECOVERY_TRANSITION_PLAN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != RECONCILIATION_RECOVERY_TRANSITION_PLAN_SCHEMA_VERSION:
            raise ValueError("unsupported reconciliation recovery transition plan schema")
        if self.expected_live_continuity_state != "RECONCILE_ONLY" or self.next_live_continuity_state != "ACTIVE_LKG":
            raise ValueError("only RECONCILE_ONLY -> ACTIVE_LKG is supported")
        if self.no_order is not True or self.execution_authority_granted is not False or self.requires_atomic_compare_and_set is not True:
            raise ValueError("transition plan must remain non-executable and atomic")
        expected = {str(key): _digest(value, f"expected_digests.{key}") for key, value in self.expected_digests.items()}
        required = {"positions_sha256", "cash_sha256", "open_orders_sha256", "recent_executions_sha256", "local_execution_ledger_sha256"}
        if set(expected) != required:
            raise ValueError("transition plan requires exactly five state digests")
        object.__setattr__(self, "recovery_id", _identifier(self.recovery_id, "recovery_id"))
        object.__setattr__(self, "candidate_sha256", _digest(self.candidate_sha256, "candidate_sha256"))
        object.__setattr__(self, "confirmation_sha256", _digest(self.confirmation_sha256, "confirmation_sha256"))
        object.__setattr__(self, "baseline_id", _identifier(self.baseline_id, "baseline_id"))
        object.__setattr__(self, "baseline_target_sha256", _digest(self.baseline_target_sha256, "baseline_target_sha256"))
        object.__setattr__(self, "expected_digests", expected)
        object.__setattr__(self, "verified_at", _time(self.verified_at, "verified_at"))

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["verified_at"] = _iso(self.verified_at, "verified_at")
        payload["expected_digests"] = dict(self.expected_digests)
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ReconciliationRecoveryTransitionPlan":
        """Decode one complete, non-executable recovery transition plan.

        State-transition adapters consume plans across a persistence boundary,
        so accepting a partial mapping here would let an omitted guard silently
        fall back to a dataclass default.  Keep the wire representation exact
        and let ``__post_init__`` validate every value.
        """

        required = {
            "schema_version",
            "recovery_id",
            "candidate_sha256",
            "confirmation_sha256",
            "baseline_id",
            "baseline_target_sha256",
            "expected_digests",
            "verified_at",
            "expected_live_continuity_state",
            "next_live_continuity_state",
            "no_order",
            "execution_authority_granted",
            "requires_atomic_compare_and_set",
        }
        if not isinstance(value, Mapping) or set(value) != required:
            raise ValueError("reconciliation recovery transition plan has invalid fields")
        return cls(**dict(value))


@dataclass(frozen=True)
class ReconciliationRecoveryActivationEvaluation:
    findings: tuple[str, ...]
    transition_plan: ReconciliationRecoveryTransitionPlan | None

    @property
    def ready_for_atomic_state_transition(self) -> bool:
        return not self.findings and self.transition_plan is not None


def evaluate_reconciliation_recovery_activation(
    *,
    recovery_id: str,
    candidate: BrokerReconciliationBaselineCandidate,
    confirmation: ReconciliationRecoveryConfirmation | Mapping[str, object] | None,
    current_evidence: BrokerReconciliationEvidence | Mapping[str, object] | None,
    current_live_continuity_state: str,
    dual_review_binding_reverified: bool = False,
    now: datetime | None = None,
    max_age: timedelta = DEFAULT_RECONCILIATION_RECOVERY_MAX_AGE,
) -> ReconciliationRecoveryActivationEvaluation:
    """Recheck confirmation/current evidence and return a non-executable plan.

    The platform must independently validate source provenance/completeness.
    ``dual_review_binding_reverified`` is deprecated and grants no authority.
    """

    if max_age <= timedelta(0):
        raise ValueError("max_age must be positive")
    findings: list[str] = []

    def add(value: str) -> None:
        if value not in findings:
            findings.append(value)

    try:
        recovery_id = _identifier(recovery_id, "recovery_id")
        candidate = BrokerReconciliationBaselineCandidate.from_dict(candidate.to_dict())
    except (AttributeError, TypeError, ValueError):
        return ReconciliationRecoveryActivationEvaluation((ReconciliationRecoveryActivationFinding.CONFIRMATION_INVALID.value,), None)
    reference_now = _time(now or datetime.now(timezone.utc), "now")
    if str(current_live_continuity_state or "").strip().upper() != "RECONCILE_ONLY":
        add(ReconciliationRecoveryActivationFinding.CURRENT_STATE_NOT_RECONCILE_ONLY.value)
    try:
        normalized_confirmation = confirmation if isinstance(confirmation, ReconciliationRecoveryConfirmation) else ReconciliationRecoveryConfirmation.from_dict(confirmation or {})
    except (TypeError, ValueError):
        normalized_confirmation = None
        add(ReconciliationRecoveryActivationFinding.CONFIRMATION_INVALID.value)
    if normalized_confirmation is not None:
        if normalized_confirmation.recovery_id != recovery_id or normalized_confirmation.candidate_sha256 != candidate.candidate_sha256:
            add(ReconciliationRecoveryActivationFinding.CONFIRMATION_CANDIDATE_MISMATCH.value)
        if normalized_confirmation.dual_review_binding_sha256 != candidate.candidate_sha256:
            add(ReconciliationRecoveryActivationFinding.CONFIRMATION_DUAL_REVIEW_MISMATCH.value)
        if normalized_confirmation.confirmed_at > reference_now or reference_now - normalized_confirmation.confirmed_at > max_age:
            add(ReconciliationRecoveryActivationFinding.CONFIRMATION_STALE.value)
    if candidate.schema_version != BROKER_RECONCILIATION_BASELINE_CANDIDATE_V2_SCHEMA_VERSION:
        add(ReconciliationRecoveryActivationFinding.SOURCE_BINDING_MISSING.value)
    try:
        normalized_evidence = current_evidence if isinstance(current_evidence, BrokerReconciliationEvidence) else BrokerReconciliationEvidence.from_dict(current_evidence or {})
    except (TypeError, ValueError):
        normalized_evidence = None
    # The second-level controller must prove a *new* read after the operator
    # confirmed the intent. Equal-second timestamps cannot establish ordering,
    # so they remain fail-closed too.
    if normalized_confirmation is not None and normalized_evidence is not None and normalized_evidence.observed_at <= normalized_confirmation.confirmed_at:
        add(ReconciliationRecoveryActivationFinding.EVIDENCE_NOT_REOBSERVED_AFTER_CONFIRMATION.value)
    for finding in evaluate_broker_reconciliation_recovery(
        normalized_evidence,
        now=reference_now,
        max_age=max_age,
        expected_platform_id=candidate.platform_id,
        expected_strategy_profile=candidate.strategy_profile,
        expected_account_scope_sha256=candidate.account_scope_sha256,
        expected_baseline_id=candidate.baseline_id,
        expected_runtime_target_sha256=candidate.baseline_target_sha256,
        expected_positions_sha256=candidate.expected_digests["positions_sha256"],
        expected_cash_sha256=candidate.expected_digests["cash_sha256"],
        expected_open_orders_sha256=candidate.expected_digests["open_orders_sha256"],
        expected_recent_executions_sha256=candidate.expected_digests["recent_executions_sha256"],
        expected_local_execution_ledger_sha256=candidate.expected_digests["local_execution_ledger_sha256"],
    ):
        add(finding.value)
    if findings or normalized_confirmation is None:
        return ReconciliationRecoveryActivationEvaluation(tuple(findings), None)
    return ReconciliationRecoveryActivationEvaluation(
        (),
        ReconciliationRecoveryTransitionPlan(
            recovery_id=recovery_id,
            candidate_sha256=candidate.candidate_sha256,
            confirmation_sha256=normalized_confirmation.confirmation_sha256,
            baseline_id=candidate.baseline_id,
            baseline_target_sha256=candidate.baseline_target_sha256,
            expected_digests=candidate.expected_digests,
            verified_at=reference_now,
        ),
    )


@runtime_checkable
class ReconciliationRecoverySourcePublisher(Protocol):
    def publish_reconciliation_recovery_source(self, snapshot: ReconciliationRecoverySourceSnapshot) -> None:
        """Publish a redacted source snapshot; implementations own transport/auth."""


@runtime_checkable
class ReconciliationRecoveryConfirmationReader(Protocol):
    def read_reconciliation_recovery_confirmation(self, recovery_id: str) -> ReconciliationRecoveryConfirmation | Mapping[str, object] | None:
        """Read one current confirmation via a private, least-privilege channel."""


@runtime_checkable
class ReconciliationRecoveryDualReviewVerifier(Protocol):
    def verify_reconciliation_recovery_dual_review(self, candidate_sha256: str) -> bool:
        """Return true only after validating independent reviewer receipts."""


@runtime_checkable
class ReconciliationRecoveryStateTransitionPort(Protocol):
    def compare_and_set_reconciliation_recovery_transition(self, plan: ReconciliationRecoveryTransitionPlan) -> bool:
        """Atomically apply the exact plan or return false without mutation."""


__all__ = [
    "DEFAULT_RECONCILIATION_RECOVERY_MAX_AGE",
    "DEFAULT_RECONCILIATION_RECOVERY_MAX_SAMPLE_WINDOW",
    "DEFAULT_RECONCILIATION_RECOVERY_MIN_SAMPLE_SEPARATION",
    "RECONCILIATION_RECOVERY_CONFIRMATION_SCHEMA_VERSION",
    "RECONCILIATION_RECOVERY_SOURCE_SNAPSHOT_SCHEMA_VERSION",
    "RECONCILIATION_RECOVERY_TRANSITION_PLAN_SCHEMA_VERSION",
    "ReconciliationRecoveryActivationEvaluation",
    "ReconciliationRecoveryActivationFinding",
    "ReconciliationRecoveryConfirmation",
    "ReconciliationRecoveryConfirmationReader",
    "ReconciliationRecoveryDualReview",
    "ReconciliationRecoveryDualReviewVerifier",
    "ReconciliationRecoveryRecord",
    "ReconciliationRecoverySourcePublisher",
    "ReconciliationRecoverySourceSnapshot",
    "ReconciliationRecoveryStateTransitionPort",
    "ReconciliationRecoveryTransitionPlan",
    "build_reconciliation_recovery_record",
    "calculate_reconciliation_recovery_confirmation_sha256",
    "evaluate_reconciliation_recovery_activation",
]
