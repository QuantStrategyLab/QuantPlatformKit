"""Pure, fail-closed admission contract for durable paper execution commands.

The deterministic risk gate lives outside this package.  It produces a small,
content-addressed receipt which is embedded in the immutable execution-command
intent.  This module verifies that receipt and its binding to the command and
the promoted release without importing a broker, a control plane, or any cloud
SDK.  Platform adapters can then pass ``integrity_findings`` to the existing
runtime command gate immediately before their paper simulation or broker call.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from .execution_commands import (
    ExecutionCommand,
    validate_execution_command_release_binding,
)
from .strategy_release import (
    StrategyReleaseIdentity,
    build_strategy_release_identity,
)


PAPER_RISK_ADMISSION_RECEIPT_SCHEMA_VERSION = "paper_risk_admission_receipt.v1"
PAPER_RISK_ADMISSION_RECEIPT_INTENT_FIELD = "paper_risk_admission_receipt"


class PaperRiskAdmissionDisposition(str, Enum):
    """The only risk permissions a deterministic paper receipt may grant."""

    ALLOW_NEW_RISK = "allow_new_risk"
    REDUCING_ONLY = "reducing_only"
    HALTED = "halted"


class PaperExecutionAdmissionFinding(str, Enum):
    """Stable, redacted findings consumable by the runtime command gate."""

    COMMAND_MODE_INVALID = "paper_execution_mode_invalid"
    COMMAND_IMMUTABILITY_INVALID = "command_digest_mismatch"
    RECEIPT_MISSING = "paper_risk_admission_receipt_missing"
    RECEIPT_INVALID = "paper_risk_admission_receipt_invalid"
    COMMAND_BINDING_MISMATCH = "paper_risk_admission_command_mismatch"
    RELEASE_BINDING_MISMATCH = "paper_risk_admission_release_mismatch"
    RISK_POLICY_MISMATCH = "paper_risk_admission_policy_mismatch"
    REDUCING_ONLY = "paper_risk_admission_reducing_only"
    HALTED = "paper_risk_admission_halted"


_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "strategy_profile",
        "release_id",
        "risk_policy_sha256",
        "decision_digest",
        "effective_session",
        "disposition",
        "reason_codes",
        "receipt_sha256",
    }
)
_PROFILE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_RELEASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_REASON_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*$")


def _required_text(value: object, *, field_name: str, maximum_length: int = 256) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    if value != value.strip() or not value:
        raise ValueError(f"{field_name} must be a non-empty, trimmed string")
    if len(value) > maximum_length or any(ord(character) < 32 for character in value):
        raise ValueError(f"{field_name} is not a safe bounded string")
    return value


def _normalize_profile(value: object) -> str:
    profile = _required_text(value, field_name="strategy_profile", maximum_length=128)
    if not _PROFILE_PATTERN.fullmatch(profile):
        raise ValueError("strategy_profile must be a lowercase scoped identifier")
    return profile


def _normalize_release_id(value: object) -> str:
    release_id = _required_text(value, field_name="release_id", maximum_length=128)
    if not _RELEASE_ID_PATTERN.fullmatch(release_id):
        raise ValueError("release_id has invalid characters")
    return release_id


def _normalize_sha256(value: object, *, field_name: str) -> str:
    digest = _required_text(value, field_name=field_name, maximum_length=64)
    if not _SHA256_PATTERN.fullmatch(digest):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
    return digest


def _normalize_effective_session(value: object) -> str:
    session = _required_text(value, field_name="effective_session", maximum_length=10)
    try:
        return date.fromisoformat(session).isoformat()
    except ValueError as exc:
        raise ValueError("effective_session must be an ISO-8601 date") from exc


def _normalize_reason_codes(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("reason_codes must be a list or tuple")
    normalized = tuple(
        _required_text(item, field_name="reason_codes[]", maximum_length=128)
        for item in value
    )
    if any(not _REASON_CODE_PATTERN.fullmatch(item) for item in normalized):
        raise ValueError("reason_codes must contain stable UPPER_SNAKE_CASE values")
    if len(set(normalized)) != len(normalized):
        raise ValueError("reason_codes must not contain duplicates")
    return normalized


def _normalize_disposition(value: object) -> PaperRiskAdmissionDisposition:
    try:
        return PaperRiskAdmissionDisposition(_required_text(value, field_name="disposition", maximum_length=32))
    except ValueError as exc:
        allowed = ", ".join(item.value for item in PaperRiskAdmissionDisposition)
        raise ValueError(f"disposition must be one of: {allowed}") from exc


def _validate_disposition_semantics(
    disposition: PaperRiskAdmissionDisposition,
    reason_codes: tuple[str, ...],
) -> None:
    if disposition is PaperRiskAdmissionDisposition.ALLOW_NEW_RISK and reason_codes:
        raise ValueError("allow_new_risk receipt must not contain reason_codes")
    if disposition is not PaperRiskAdmissionDisposition.ALLOW_NEW_RISK and not reason_codes:
        raise ValueError("non-allow receipt must contain reason_codes")


def _canonical_receipt_payload(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("paper risk admission receipt must be an object")
    actual_fields = set(value)
    if actual_fields != _RECEIPT_FIELDS:
        missing = sorted(_RECEIPT_FIELDS - actual_fields)
        unexpected = sorted(actual_fields - _RECEIPT_FIELDS)
        detail = []
        if missing:
            detail.append(f"missing: {', '.join(missing)}")
        if unexpected:
            detail.append(f"unexpected: {', '.join(unexpected)}")
        raise ValueError(f"paper risk admission receipt has invalid fields ({'; '.join(detail)})")
    if value["schema_version"] != PAPER_RISK_ADMISSION_RECEIPT_SCHEMA_VERSION:
        raise ValueError("unsupported paper risk admission receipt schema version")
    disposition = _normalize_disposition(value["disposition"])
    reason_codes = _normalize_reason_codes(value["reason_codes"])
    _validate_disposition_semantics(disposition, reason_codes)
    return {
        "schema_version": PAPER_RISK_ADMISSION_RECEIPT_SCHEMA_VERSION,
        "strategy_profile": _normalize_profile(value["strategy_profile"]),
        "release_id": _normalize_release_id(value["release_id"]),
        "risk_policy_sha256": _normalize_sha256(value["risk_policy_sha256"], field_name="risk_policy_sha256"),
        "decision_digest": _normalize_sha256(value["decision_digest"], field_name="decision_digest"),
        "effective_session": _normalize_effective_session(value["effective_session"]),
        "disposition": disposition.value,
        "reason_codes": list(reason_codes),
    }


def canonical_paper_risk_admission_receipt_json(value: Mapping[str, object]) -> str:
    """Return canonical receipt JSON excluding its content-addressed digest."""

    payload = _canonical_receipt_payload(value)
    try:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("paper risk admission receipt cannot be canonicalized") from exc


def calculate_paper_risk_admission_receipt_sha256(value: Mapping[str, object]) -> str:
    """Calculate the SHA-256 digest over the exact approved receipt fields."""

    return hashlib.sha256(canonical_paper_risk_admission_receipt_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PaperRiskAdmissionReceipt:
    """A content-addressed, deterministic risk result bound to one command."""

    strategy_profile: str
    release_id: str
    risk_policy_sha256: str
    decision_digest: str
    effective_session: str
    disposition: PaperRiskAdmissionDisposition | str
    reason_codes: tuple[str, ...] | list[str]
    receipt_sha256: str
    schema_version: str = PAPER_RISK_ADMISSION_RECEIPT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "strategy_profile", _normalize_profile(self.strategy_profile))
        object.__setattr__(self, "release_id", _normalize_release_id(self.release_id))
        object.__setattr__(
            self,
            "risk_policy_sha256",
            _normalize_sha256(self.risk_policy_sha256, field_name="risk_policy_sha256"),
        )
        object.__setattr__(
            self,
            "decision_digest",
            _normalize_sha256(self.decision_digest, field_name="decision_digest"),
        )
        object.__setattr__(self, "effective_session", _normalize_effective_session(self.effective_session))
        disposition = _normalize_disposition(self.disposition)
        reasons = _normalize_reason_codes(self.reason_codes)
        _validate_disposition_semantics(disposition, reasons)
        object.__setattr__(self, "disposition", disposition)
        object.__setattr__(self, "reason_codes", reasons)
        if self.schema_version != PAPER_RISK_ADMISSION_RECEIPT_SCHEMA_VERSION:
            raise ValueError("unsupported paper risk admission receipt schema version")
        normalized_digest = _normalize_sha256(self.receipt_sha256, field_name="receipt_sha256")
        object.__setattr__(self, "receipt_sha256", normalized_digest)
        if normalized_digest != calculate_paper_risk_admission_receipt_sha256(self.to_dict()):
            raise ValueError("paper risk admission receipt_sha256 mismatch")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "strategy_profile": self.strategy_profile,
            "release_id": self.release_id,
            "risk_policy_sha256": self.risk_policy_sha256,
            "decision_digest": self.decision_digest,
            "effective_session": self.effective_session,
            "disposition": self.disposition.value,
            "reason_codes": list(self.reason_codes),
            "receipt_sha256": self.receipt_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "PaperRiskAdmissionReceipt":
        _canonical_receipt_payload(value)
        return cls(
            schema_version=value["schema_version"],
            strategy_profile=value["strategy_profile"],
            release_id=value["release_id"],
            risk_policy_sha256=value["risk_policy_sha256"],
            decision_digest=value["decision_digest"],
            effective_session=value["effective_session"],
            disposition=value["disposition"],
            reason_codes=value["reason_codes"],
            receipt_sha256=value["receipt_sha256"],
        )


def build_paper_risk_admission_receipt(
    *,
    strategy_profile: object,
    release_id: object,
    risk_policy_sha256: object,
    decision_digest: object,
    effective_session: object,
    disposition: PaperRiskAdmissionDisposition | str,
    reason_codes: Sequence[object],
) -> PaperRiskAdmissionReceipt:
    """Build a strict receipt for an already-evaluated deterministic policy.

    This helper has no risk-engine authority: it only serializes the reviewed
    decision supplied by a control plane or a test fixture.
    """

    draft = {
        "schema_version": PAPER_RISK_ADMISSION_RECEIPT_SCHEMA_VERSION,
        "strategy_profile": strategy_profile,
        "release_id": release_id,
        "risk_policy_sha256": risk_policy_sha256,
        "decision_digest": decision_digest,
        "effective_session": effective_session,
        "disposition": disposition.value if isinstance(disposition, Enum) else disposition,
        "reason_codes": list(reason_codes),
        "receipt_sha256": "0" * 64,
    }
    draft["receipt_sha256"] = calculate_paper_risk_admission_receipt_sha256(draft)
    return PaperRiskAdmissionReceipt.from_dict(draft)


@dataclass(frozen=True)
class PaperExecutionAdmissionDecision:
    """The composed command/release/risk result for one paper command."""

    command_id: str | None
    disposition: PaperRiskAdmissionDisposition
    integrity_findings: tuple[str, ...]
    receipt_sha256: str | None = None

    @property
    def allows_new_risk(self) -> bool:
        return self.disposition is PaperRiskAdmissionDisposition.ALLOW_NEW_RISK

    @property
    def requires_exposure_reduction(self) -> bool:
        return self.disposition is PaperRiskAdmissionDisposition.REDUCING_ONLY


def _append_finding(findings: list[str], finding: str) -> None:
    if finding not in findings:
        findings.append(finding)


def _validate_command_immutability(command: ExecutionCommand) -> bool:
    try:
        reconstructed = ExecutionCommand.from_dict(command.to_dict())
    except (TypeError, ValueError):
        return False
    return reconstructed == command


def _halted(
    command: ExecutionCommand | None,
    findings: list[str],
    *,
    receipt_sha256: str | None = None,
) -> PaperExecutionAdmissionDecision:
    return PaperExecutionAdmissionDecision(
        command_id=command.command_id if command is not None else None,
        disposition=PaperRiskAdmissionDisposition.HALTED,
        integrity_findings=tuple(findings),
        receipt_sha256=receipt_sha256,
    )


def evaluate_paper_execution_admission(
    *,
    command: ExecutionCommand | None,
    expected_strategy_release: StrategyReleaseIdentity | Mapping[str, object] | None,
) -> PaperExecutionAdmissionDecision:
    """Fail closed unless a receipt is immutable and exactly release-bound.

    The receipt must be embedded in ``command.intent`` before the command ID is
    calculated.  Reconstructing the command verifies that neither receipt nor
    intent was altered after durable storage.  The returned stable findings are
    deliberately suitable for ``evaluate_runtime_command_gate``.
    """

    findings: list[str] = []
    if command is None:
        return _halted(command, [PaperExecutionAdmissionFinding.COMMAND_IMMUTABILITY_INVALID.value])
    if not _validate_command_immutability(command):
        return _halted(command, [PaperExecutionAdmissionFinding.COMMAND_IMMUTABILITY_INVALID.value])
    if command.execution_mode != "paper":
        return _halted(command, [PaperExecutionAdmissionFinding.COMMAND_MODE_INVALID.value])

    try:
        expected_release = build_strategy_release_identity(expected_strategy_release)
    except ValueError:
        return _halted(command, ["release_identity_invalid"])

    for finding in validate_execution_command_release_binding(
        command,
        expected_strategy_release=expected_release,
    ).findings:
        _append_finding(findings, finding)
    if findings:
        return _halted(command, findings)

    raw_receipt = command.intent.get(PAPER_RISK_ADMISSION_RECEIPT_INTENT_FIELD)
    if raw_receipt is None:
        return _halted(command, [PaperExecutionAdmissionFinding.RECEIPT_MISSING.value])
    if not isinstance(raw_receipt, Mapping):
        return _halted(command, [PaperExecutionAdmissionFinding.RECEIPT_INVALID.value])
    try:
        receipt = PaperRiskAdmissionReceipt.from_dict(raw_receipt)
    except (TypeError, ValueError):
        return _halted(command, [PaperExecutionAdmissionFinding.RECEIPT_INVALID.value])

    # ``decision_digest`` is the producer's immutable strategy-decision
    # digest, calculated before the admission receipt is added to the command
    # intent.  The command ID then content-addresses the complete intent,
    # including this receipt, so both directions are bound without a digest
    # self-reference.
    if receipt.decision_digest != command.decision_digest:
        _append_finding(findings, PaperExecutionAdmissionFinding.COMMAND_BINDING_MISMATCH.value)
    if receipt.strategy_profile != command.strategy_profile:
        _append_finding(findings, PaperExecutionAdmissionFinding.COMMAND_BINDING_MISMATCH.value)
    if receipt.effective_session != command.effective_date:
        _append_finding(findings, PaperExecutionAdmissionFinding.COMMAND_BINDING_MISMATCH.value)
    if receipt.release_id != expected_release.release_id:
        _append_finding(findings, PaperExecutionAdmissionFinding.RELEASE_BINDING_MISMATCH.value)
    if receipt.risk_policy_sha256 != expected_release.risk_policy_sha256:
        _append_finding(findings, PaperExecutionAdmissionFinding.RISK_POLICY_MISMATCH.value)
    if findings:
        return _halted(command, findings, receipt_sha256=receipt.receipt_sha256)

    if receipt.disposition is PaperRiskAdmissionDisposition.ALLOW_NEW_RISK:
        return PaperExecutionAdmissionDecision(
            command_id=command.command_id,
            disposition=receipt.disposition,
            integrity_findings=(),
            receipt_sha256=receipt.receipt_sha256,
        )
    if receipt.disposition is PaperRiskAdmissionDisposition.REDUCING_ONLY:
        return PaperExecutionAdmissionDecision(
            command_id=command.command_id,
            disposition=receipt.disposition,
            integrity_findings=(PaperExecutionAdmissionFinding.REDUCING_ONLY.value,),
            receipt_sha256=receipt.receipt_sha256,
        )
    return _halted(
        command,
        [PaperExecutionAdmissionFinding.HALTED.value],
        receipt_sha256=receipt.receipt_sha256,
    )


__all__ = [
    "PAPER_RISK_ADMISSION_RECEIPT_INTENT_FIELD",
    "PAPER_RISK_ADMISSION_RECEIPT_SCHEMA_VERSION",
    "PaperExecutionAdmissionDecision",
    "PaperExecutionAdmissionFinding",
    "PaperRiskAdmissionDisposition",
    "PaperRiskAdmissionReceipt",
    "build_paper_risk_admission_receipt",
    "calculate_paper_risk_admission_receipt_sha256",
    "canonical_paper_risk_admission_receipt_json",
    "evaluate_paper_execution_admission",
]
