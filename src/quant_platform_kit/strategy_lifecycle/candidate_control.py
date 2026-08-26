"""Immutable, non-execution contracts for research candidates and approvals.

This module deliberately models evidence and a bounded human decision without
introducing another lifecycle.  Its artifacts are useful to research tooling,
but they never authorize broker execution or a ``live_enabled`` transition.
"""

from __future__ import annotations

import enum
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


SOURCE_RECEIPT_SCHEMA_VERSION = "source_receipt.v1"
STRATEGY_CANDIDATE_SCHEMA_VERSION = "strategy_candidate.v1"
PROMOTION_DECISION_SCHEMA_VERSION = "promotion_decision.v1"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RFC3339_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


class CandidateKind(str, enum.Enum):
    """The bounded change type proposed by a research candidate."""

    PARAMETER_CHANGE = "parameter_change"
    STRATEGY_REVISION = "strategy_revision"
    NEW_STRATEGY = "new_strategy"
    PLUGIN_REVISION = "plugin_revision"


class ResearchCandidateStatus(str, enum.Enum):
    """Research-local progress, intentionally separate from lifecycle status."""

    DRAFT = "draft"
    RESEARCHING = "researching"
    BACKTEST_COMPLETE = "backtest_complete"
    SHADOW_READY = "shadow_ready"
    SHADOW_OBSERVING = "shadow_observing"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class PromotionScope(str, enum.Enum):
    """The only non-live scopes a human decision may cover."""

    RESEARCH = "research"
    SHADOW = "shadow"
    PAPER = "paper"


class PromotionOutcome(str, enum.Enum):
    """A human decision can approve a bounded non-live scope or reject it."""

    APPROVED = "approved"
    REJECTED = "rejected"


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _require_identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty canonical string")


def _require_sha256(value: str, name: str) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _parse_rfc3339(value: str, name: str) -> datetime:
    if not isinstance(value, str) or not _RFC3339_DATETIME.fullmatch(value):
        raise ValueError(f"{name} must be an RFC 3339 date-time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an RFC 3339 date-time") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a UTC offset")
    return parsed


@dataclass(frozen=True)
class SourceReceipt:
    """A content-addressed record of untrusted network research material.

    A receipt preserves provenance, license information, and the exact content
    digest.  It makes no claim that the source is accurate, safe, or approved.
    """

    receipt_id: str
    source_uri: str
    retrieved_at: str
    content_sha256: str
    license: str
    receipt_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("receipt_id", "source_uri", "license"):
            _require_identifier(getattr(self, name), name)
        _parse_rfc3339(self.retrieved_at, "retrieved_at")
        _require_sha256(self.content_sha256, "content_sha256")
        object.__setattr__(self, "receipt_sha256", _sha256(self._payload()))

    @property
    def content_trust(self) -> str:
        """Network material is always untrusted at this boundary."""

        return "untrusted"

    @property
    def grants_execution_authority(self) -> bool:
        """A source receipt is evidence only, never an authorization."""

        return False

    def _payload(self) -> dict[str, object]:
        return {
            "schema_version": SOURCE_RECEIPT_SCHEMA_VERSION,
            "receipt_id": self.receipt_id,
            "source_uri": self.source_uri,
            "retrieved_at": self.retrieved_at,
            "content_sha256": self.content_sha256,
            "license": self.license,
            "content_trust": self.content_trust,
            "grants_execution_authority": False,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True)
class CandidateIdentityBinding:
    """Digests that bind a candidate to frozen risk and research evidence.

    ``candidate_risk_identity_sha256`` must be the digest computed by the
    existing :class:`~quant_platform_kit.risk.contracts.CandidateRiskIdentity`.
    The remaining digests bind the candidate to the exact research artifacts
    that were reviewed.  This class does not inspect or authorize any of them.
    """

    candidate_risk_identity_sha256: str
    research_spec_sha256: str
    source_receipt_sha256s: tuple[str, ...] = ()
    optimization_spec_sha256: str | None = None

    def __post_init__(self) -> None:
        _require_sha256(
            self.candidate_risk_identity_sha256,
            "candidate_risk_identity_sha256",
        )
        _require_sha256(self.research_spec_sha256, "research_spec_sha256")
        if self.optimization_spec_sha256 is not None:
            _require_sha256(self.optimization_spec_sha256, "optimization_spec_sha256")
        digests = tuple(self.source_receipt_sha256s)
        for digest in digests:
            _require_sha256(digest, "source_receipt_sha256s item")
        if tuple(sorted(digests)) != digests or len(set(digests)) != len(digests):
            raise ValueError(
                "source_receipt_sha256s must be unique and sorted for canonical binding"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_risk_identity_sha256": self.candidate_risk_identity_sha256,
            "research_spec_sha256": self.research_spec_sha256,
            "optimization_spec_sha256": self.optimization_spec_sha256,
            "source_receipt_sha256s": list(self.source_receipt_sha256s),
        }


@dataclass(frozen=True)
class StrategyCandidate:
    """One immutable research candidate, bound to evidence instead of power."""

    candidate_id: str
    candidate_kind: CandidateKind
    research_status: ResearchCandidateStatus
    strategy_profile: str
    domain: str
    created_at: str
    identity_binding: CandidateIdentityBinding
    source_receipts: tuple[SourceReceipt, ...] = ()
    candidate_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("candidate_id", "strategy_profile", "domain"):
            _require_identifier(getattr(self, name), name)
        if not isinstance(self.candidate_kind, CandidateKind):
            raise TypeError("candidate_kind must be a CandidateKind")
        if not isinstance(self.research_status, ResearchCandidateStatus):
            raise TypeError("research_status must be a ResearchCandidateStatus")
        _parse_rfc3339(self.created_at, "created_at")
        if not isinstance(self.identity_binding, CandidateIdentityBinding):
            raise TypeError("identity_binding must be a CandidateIdentityBinding")
        if self.candidate_kind is CandidateKind.PARAMETER_CHANGE and (
            self.identity_binding.optimization_spec_sha256 is None
        ):
            raise ValueError("parameter_change candidates require optimization_spec_sha256")
        if any(type(receipt) is not SourceReceipt for receipt in self.source_receipts):
            raise TypeError("source_receipts must contain SourceReceipt values")
        receipt_digests = tuple(receipt.receipt_sha256 for receipt in self.source_receipts)
        if tuple(sorted(receipt_digests)) != receipt_digests:
            raise ValueError("source_receipts must be ordered by receipt_sha256")
        if self.identity_binding.source_receipt_sha256s != receipt_digests:
            raise ValueError("identity_binding must exactly bind source_receipts")
        object.__setattr__(self, "candidate_sha256", _sha256(self._payload()))

    @property
    def grants_execution_authority(self) -> bool:
        """Candidates are research evidence and cannot authorize execution."""

        return False

    def _payload(self) -> dict[str, object]:
        return {
            "schema_version": STRATEGY_CANDIDATE_SCHEMA_VERSION,
            "candidate_id": self.candidate_id,
            "candidate_kind": self.candidate_kind.value,
            "research_status": self.research_status.value,
            "strategy_profile": self.strategy_profile,
            "domain": self.domain,
            "created_at": self.created_at,
            "identity_binding": self.identity_binding.to_dict(),
            "source_receipts": [receipt.to_dict() for receipt in self.source_receipts],
            "grants_execution_authority": False,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "candidate_sha256": self.candidate_sha256}


@dataclass(frozen=True)
class PromotionDecision:
    """An expiring human decision limited to a non-live candidate scope.

    This is intentionally not a deployment authorization.  A valid decision
    can make a candidate eligible for the named non-live scope only; platform
    and broker authorization remain independent controls.
    """

    decision_id: str
    candidate_sha256: str
    outcome: PromotionOutcome
    scope: PromotionScope
    reviewed_by: str
    reviewed_at: str
    expires_at: str
    decision_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("decision_id", "reviewed_by"):
            _require_identifier(getattr(self, name), name)
        _require_sha256(self.candidate_sha256, "candidate_sha256")
        if not isinstance(self.outcome, PromotionOutcome):
            raise TypeError("outcome must be a PromotionOutcome")
        if not isinstance(self.scope, PromotionScope):
            raise TypeError("scope must be a PromotionScope")
        reviewed_at = _parse_rfc3339(self.reviewed_at, "reviewed_at")
        expires_at = _parse_rfc3339(self.expires_at, "expires_at")
        if expires_at <= reviewed_at:
            raise ValueError("expires_at must be after reviewed_at")
        object.__setattr__(self, "decision_sha256", _sha256(self._payload()))

    @property
    def grants_live(self) -> bool:
        """No value or scope of this contract can grant live access."""

        return False

    @property
    def grants_execution_authority(self) -> bool:
        """Execution remains solely under independent platform controls."""

        return False

    def is_current(self, *, at: datetime | None = None) -> bool:
        """Return whether an approved non-live decision remains in its window."""

        instant = at or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            raise ValueError("at must include a UTC offset")
        return (
            self.outcome is PromotionOutcome.APPROVED
            and instant < _parse_rfc3339(self.expires_at, "expires_at")
        )

    def _payload(self) -> dict[str, object]:
        return {
            "schema_version": PROMOTION_DECISION_SCHEMA_VERSION,
            "decision_id": self.decision_id,
            "candidate_sha256": self.candidate_sha256,
            "outcome": self.outcome.value,
            "scope": self.scope.value,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
            "expires_at": self.expires_at,
            "approval_actor_type": "human",
            "grants_live": False,
            "grants_execution_authority": False,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "decision_sha256": self.decision_sha256}


def validate_source_receipt(payload: Any) -> list[str]:
    """Validate a serialized ``source_receipt.v1`` artifact without I/O."""

    issues = _validate_mapping(payload, SOURCE_RECEIPT_SCHEMA_VERSION, (
        "receipt_id", "source_uri", "retrieved_at", "content_sha256", "license",
        "content_trust", "grants_execution_authority", "receipt_sha256",
    ))
    if not isinstance(payload, Mapping):
        return issues
    for key in ("receipt_id", "source_uri", "license"):
        _validate_identifier(payload.get(key), key, issues)
    _validate_datetime(payload.get("retrieved_at"), "retrieved_at", issues)
    _validate_sha(payload.get("content_sha256"), "content_sha256", issues)
    if payload.get("content_trust") != "untrusted":
        issues.append("content_trust must be 'untrusted'")
    if payload.get("grants_execution_authority") is not False:
        issues.append("grants_execution_authority must be False")
    _validate_reported_digest(payload, "receipt_sha256", issues)
    return issues


def validate_strategy_candidate(payload: Any) -> list[str]:
    """Validate a serialized immutable candidate and all bound source receipts."""

    issues = _validate_mapping(payload, STRATEGY_CANDIDATE_SCHEMA_VERSION, (
        "candidate_id", "candidate_kind", "research_status", "strategy_profile",
        "domain", "created_at", "identity_binding", "source_receipts",
        "grants_execution_authority", "candidate_sha256",
    ))
    if not isinstance(payload, Mapping):
        return issues
    for key in ("candidate_id", "strategy_profile", "domain"):
        _validate_identifier(payload.get(key), key, issues)
    if payload.get("candidate_kind") not in {kind.value for kind in CandidateKind}:
        issues.append("candidate_kind must be parameter_change, strategy_revision, new_strategy, or plugin_revision")
    if payload.get("research_status") not in {status.value for status in ResearchCandidateStatus}:
        issues.append("research_status must be a supported research candidate status")
    _validate_datetime(payload.get("created_at"), "created_at", issues)
    if payload.get("grants_execution_authority") is not False:
        issues.append("grants_execution_authority must be False")

    binding = payload.get("identity_binding")
    _validate_identity_binding(binding, payload.get("candidate_kind"), issues)
    source_receipts = payload.get("source_receipts")
    receipt_digests: list[str] = []
    if not isinstance(source_receipts, list):
        issues.append("source_receipts must be an array")
    else:
        for index, receipt in enumerate(source_receipts):
            receipt_issues = validate_source_receipt(receipt)
            issues.extend(f"source_receipts[{index}].{issue}" for issue in receipt_issues)
            if isinstance(receipt, Mapping) and isinstance(receipt.get("receipt_sha256"), str):
                receipt_digests.append(receipt["receipt_sha256"])
        if receipt_digests != sorted(receipt_digests):
            issues.append("source_receipts must be ordered by receipt_sha256")
        if len(set(receipt_digests)) != len(receipt_digests):
            issues.append("source_receipts must not contain duplicate receipt_sha256 values")
        if isinstance(binding, Mapping) and binding.get("source_receipt_sha256s") != receipt_digests:
            issues.append("identity_binding.source_receipt_sha256s must exactly bind source_receipts")

    _validate_reported_digest(payload, "candidate_sha256", issues)
    return issues


def validate_promotion_decision(payload: Any) -> list[str]:
    """Validate a human-only, expiring, non-live decision artifact."""

    issues = _validate_mapping(payload, PROMOTION_DECISION_SCHEMA_VERSION, (
        "decision_id", "candidate_sha256", "outcome", "scope", "reviewed_by",
        "reviewed_at", "expires_at", "approval_actor_type", "grants_live",
        "grants_execution_authority", "decision_sha256",
    ))
    if not isinstance(payload, Mapping):
        return issues
    for key in ("decision_id", "reviewed_by"):
        _validate_identifier(payload.get(key), key, issues)
    _validate_sha(payload.get("candidate_sha256"), "candidate_sha256", issues)
    if payload.get("outcome") not in {outcome.value for outcome in PromotionOutcome}:
        issues.append("outcome must be approved or rejected")
    if payload.get("scope") not in {scope.value for scope in PromotionScope}:
        issues.append("scope must be research, shadow, or paper; live is never allowed")
    if payload.get("approval_actor_type") != "human":
        issues.append("approval_actor_type must be 'human'")
    if payload.get("grants_live") is not False:
        issues.append("grants_live must be False")
    if payload.get("grants_execution_authority") is not False:
        issues.append("grants_execution_authority must be False")
    reviewed_at = _validate_datetime(payload.get("reviewed_at"), "reviewed_at", issues)
    expires_at = _validate_datetime(payload.get("expires_at"), "expires_at", issues)
    if reviewed_at is not None and expires_at is not None and expires_at <= reviewed_at:
        issues.append("expires_at must be after reviewed_at")
    _validate_reported_digest(payload, "decision_sha256", issues)
    return issues


def _validate_mapping(payload: Any, schema_version: str, required: tuple[str, ...]) -> list[str]:
    if not isinstance(payload, Mapping):
        return ["top-level JSON must be an object"]
    issues = [f"missing required field: {key}" for key in ("schema_version", *required) if key not in payload]
    if payload.get("schema_version") != schema_version:
        issues.append(f"schema_version must be {schema_version!r}")
    return issues


def _validate_identifier(value: Any, name: str, issues: list[str]) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        issues.append(f"{name} must be a non-empty canonical string")


def _validate_sha(value: Any, name: str, issues: list[str]) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        issues.append(f"{name} must be a lowercase SHA-256 digest")


def _validate_datetime(value: Any, name: str, issues: list[str]) -> datetime | None:
    try:
        return _parse_rfc3339(value, name)
    except ValueError:
        issues.append(f"{name} must be an RFC 3339 date-time")
        return None


def _validate_identity_binding(binding: Any, candidate_kind: Any, issues: list[str]) -> None:
    if not isinstance(binding, Mapping):
        issues.append("identity_binding must be an object")
        return
    for key in ("candidate_risk_identity_sha256", "research_spec_sha256"):
        _validate_sha(binding.get(key), f"identity_binding.{key}", issues)
    optimization = binding.get("optimization_spec_sha256")
    if candidate_kind == CandidateKind.PARAMETER_CHANGE.value and optimization is None:
        issues.append("parameter_change candidates require identity_binding.optimization_spec_sha256")
    if optimization is not None:
        _validate_sha(optimization, "identity_binding.optimization_spec_sha256", issues)
    sources = binding.get("source_receipt_sha256s")
    if not isinstance(sources, list):
        issues.append("identity_binding.source_receipt_sha256s must be an array")
        return
    for digest in sources:
        _validate_sha(digest, "identity_binding.source_receipt_sha256s item", issues)
    if sources != sorted(sources) or len(set(sources)) != len(sources):
        issues.append("identity_binding.source_receipt_sha256s must be unique and sorted")


def _validate_reported_digest(payload: Mapping[str, Any], key: str, issues: list[str]) -> None:
    reported = payload.get(key)
    _validate_sha(reported, key, issues)
    if not isinstance(reported, str):
        return
    unsigned = {name: value for name, value in payload.items() if name != key}
    try:
        expected = _sha256(unsigned)
    except (TypeError, ValueError):
        issues.append(f"{key} cannot be calculated from canonical JSON")
        return
    if reported != expected:
        issues.append(f"{key} does not match canonical artifact content")
