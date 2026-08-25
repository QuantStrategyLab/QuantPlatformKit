"""Broker-account identity checks shared by platform execution runtimes.

The platform adapter collects read-only facts from the broker and this module
compares them with the reviewed runtime target. It deliberately accepts only
redacted identifiers: neither account numbers nor credentials are copied into
reports, logs, plugin payloads, or durable receipts.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .models import ExecutionReport, OrderIntent
from .ports import ExecutionPort


ACCOUNT_IDENTITY_RECEIPT_SCHEMA_VERSION = "account_identity_receipt.v1"


class AccountIdentityEnforcement(str, Enum):
    """Whether identity findings are recorded only or stop broker writes."""

    OBSERVE = "observe"
    ENFORCE = "enforce"


class AccountIdentityEvidenceSource(str, Enum):
    """Origin of account facts, ordered by what the broker exposes."""

    BROKER_API = "broker_api"
    BROKER_API_PARTIAL = "broker_api_partial"
    OPERATOR_ATTESTATION = "operator_attestation"


class AccountIdentityField(str, Enum):
    ACCOUNT_ID = "account_id"
    ACCOUNT_MODE = "account_mode"
    ACCOUNT_TYPE = "account_type"


class AccountIdentityFinding(str, Enum):
    """Stable, redacted findings suitable for runtime command gates."""

    ACCOUNT_IDENTITY_CONFIGURATION_INVALID = "account_identity_configuration_invalid"
    ACCOUNT_IDENTITY_EVIDENCE_UNAVAILABLE = "account_identity_evidence_unavailable"
    ACCOUNT_IDENTITY_ID_MISMATCH = "account_identity_id_mismatch"
    ACCOUNT_IDENTITY_MODE_MISMATCH = "account_identity_mode_mismatch"
    ACCOUNT_IDENTITY_PLATFORM_MISMATCH = "account_identity_platform_mismatch"
    ACCOUNT_IDENTITY_TYPE_MISMATCH = "account_identity_type_mismatch"


_SHA256_FINGERPRINT = re.compile(r"^sha256:[0-9a-f]{64}$")


def _normalized_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalized_values(values: Iterable[object] | object | None) -> tuple[str, ...]:
    if values is None:
        return ()
    candidates = (values,) if isinstance(values, str) else values
    normalized: list[str] = []
    for value in candidates:
        text = _normalized_text(value)
        if text is None:
            continue
        canonical = text.lower()
        if canonical not in normalized:
            normalized.append(canonical)
    return tuple(sorted(normalized))


def _normalized_fields(values: Iterable[object] | object | None) -> frozenset[AccountIdentityField]:
    if values is None:
        return frozenset()
    candidates = (values,) if isinstance(values, str) else values
    normalized: set[AccountIdentityField] = set()
    for value in candidates:
        try:
            normalized.add(
                AccountIdentityField(
                    str(value.value if isinstance(value, AccountIdentityField) else value or "")
                    .strip()
                    .lower()
                )
            )
        except ValueError as exc:
            supported = ", ".join(item.value for item in AccountIdentityField)
            raise ValueError(f"account identity required_fields must use: {supported}") from exc
    return frozenset(normalized)


def _normalized_enforcement(value: object) -> AccountIdentityEnforcement:
    if isinstance(value, AccountIdentityEnforcement):
        return value
    try:
        return AccountIdentityEnforcement(str(value or "observe").strip().lower() or "observe")
    except ValueError as exc:
        raise ValueError("account identity enforcement must be observe or enforce") from exc


@dataclass(frozen=True)
class AccountIdentityPolicy:
    """Reviewed expectation carried by one runtime target.

    ``expected_account_id_fingerprint`` must be an HMAC/SHA-256 style
    fingerprint generated outside the runtime. Raw account numbers are not
    accepted in this contract.
    """

    enforcement: AccountIdentityEnforcement = AccountIdentityEnforcement.OBSERVE
    required_fields: frozenset[AccountIdentityField] = frozenset()
    expected_account_types: tuple[str, ...] = ()
    expected_account_modes: tuple[str, ...] = ()
    expected_account_id_fingerprint: str | None = None

    def __post_init__(self) -> None:
        enforcement = _normalized_enforcement(self.enforcement)
        account_types = _normalized_values(self.expected_account_types)
        account_modes = _normalized_values(self.expected_account_modes)
        fingerprint = _normalized_text(self.expected_account_id_fingerprint)
        if fingerprint is not None:
            fingerprint = fingerprint.lower()
            if not _SHA256_FINGERPRINT.fullmatch(fingerprint):
                raise ValueError(
                    "expected_account_id_fingerprint must be a redacted sha256:<64 lowercase hex> value"
                )
        required = _normalized_fields(self.required_fields)
        if account_types:
            required = required | {AccountIdentityField.ACCOUNT_TYPE}
        if account_modes:
            required = required | {AccountIdentityField.ACCOUNT_MODE}
        if fingerprint is not None:
            required = required | {AccountIdentityField.ACCOUNT_ID}
        if enforcement is AccountIdentityEnforcement.ENFORCE and not required:
            raise ValueError("enforced account identity policy must require at least one field")
        object.__setattr__(self, "enforcement", enforcement)
        object.__setattr__(self, "required_fields", frozenset(required))
        object.__setattr__(self, "expected_account_types", account_types)
        object.__setattr__(self, "expected_account_modes", account_modes)
        object.__setattr__(self, "expected_account_id_fingerprint", fingerprint)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "AccountIdentityPolicy":
        payload = dict(value or {})
        supported_fields = {
            "enforcement",
            "required_fields",
            "expected_account_types",
            "expected_account_modes",
            "expected_account_id_fingerprint",
        }
        unknown_fields = sorted(set(payload) - supported_fields)
        if unknown_fields:
            raise ValueError(
                "unsupported account identity policy fields: " + ", ".join(unknown_fields)
            )
        return cls(
            enforcement=payload.get("enforcement", AccountIdentityEnforcement.OBSERVE.value),
            required_fields=payload.get("required_fields"),
            expected_account_types=payload.get("expected_account_types"),
            expected_account_modes=payload.get("expected_account_modes"),
            expected_account_id_fingerprint=payload.get("expected_account_id_fingerprint"),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.required_fields)

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "enforcement": self.enforcement.value,
            "required_fields": sorted(field.value for field in self.required_fields),
            "expected_account_types": list(self.expected_account_types),
            "expected_account_modes": list(self.expected_account_modes),
            "account_id_fingerprint_configured": self.expected_account_id_fingerprint is not None,
        }


@dataclass(frozen=True)
class BrokerAccountIdentity:
    """Read-only broker evidence with no raw identifier material."""

    platform_id: str
    evidence_source: AccountIdentityEvidenceSource = AccountIdentityEvidenceSource.BROKER_API
    account_types: tuple[str, ...] = ()
    account_modes: tuple[str, ...] = ()
    account_id_fingerprint: str | None = None

    def __post_init__(self) -> None:
        platform_id = _normalized_text(self.platform_id)
        if platform_id is None:
            raise ValueError("broker account identity platform_id is required")
        source = self.evidence_source
        if not isinstance(source, AccountIdentityEvidenceSource):
            try:
                source = AccountIdentityEvidenceSource(str(source or "").strip().lower())
            except ValueError as exc:
                supported = ", ".join(item.value for item in AccountIdentityEvidenceSource)
                raise ValueError(f"account identity evidence_source must use: {supported}") from exc
        fingerprint = _normalized_text(self.account_id_fingerprint)
        if fingerprint is not None:
            fingerprint = fingerprint.lower()
            if not _SHA256_FINGERPRINT.fullmatch(fingerprint):
                raise ValueError(
                    "account_id_fingerprint must be a redacted sha256:<64 lowercase hex> value"
                )
        object.__setattr__(self, "platform_id", platform_id.lower())
        object.__setattr__(self, "evidence_source", source)
        object.__setattr__(self, "account_types", _normalized_values(self.account_types))
        object.__setattr__(self, "account_modes", _normalized_values(self.account_modes))
        object.__setattr__(self, "account_id_fingerprint", fingerprint)

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "platform_id": self.platform_id,
            "evidence_source": self.evidence_source.value,
            "account_types": list(self.account_types),
            "account_modes": list(self.account_modes),
            "account_id_fingerprint_observed": self.account_id_fingerprint is not None,
        }


@dataclass(frozen=True)
class AccountIdentityDecision:
    """Redacted identity verdict immediately before broker execution."""

    policy: AccountIdentityPolicy
    observation: BrokerAccountIdentity | None
    findings: tuple[str, ...]

    @property
    def policy_allows(self) -> bool:
        return not self.findings

    @property
    def would_block(self) -> bool:
        return not self.policy_allows

    @property
    def broker_write_allowed(self) -> bool:
        return self.policy_allows or self.policy.enforcement is AccountIdentityEnforcement.OBSERVE

    def to_receipt(self) -> dict[str, object]:
        return {
            "schema_version": ACCOUNT_IDENTITY_RECEIPT_SCHEMA_VERSION,
            "configured": self.policy.is_configured,
            "policy": self.policy.to_safe_dict(),
            "observation": self.observation.to_safe_dict() if self.observation is not None else None,
            "findings": list(self.findings),
            "policy_allows": self.policy_allows,
            "would_block": self.would_block,
            "broker_write_allowed": self.broker_write_allowed,
        }


class AccountIdentityBlockedError(RuntimeError):
    """Raised before a broker adapter is invoked by an enforced identity gate."""


@dataclass(frozen=True)
class AccountIdentityGuardedExecutionPort(ExecutionPort):
    """Execution-port wrapper shared by every strategy and plugin path."""

    delegate: ExecutionPort
    decision: AccountIdentityDecision

    def submit_order(self, order: OrderIntent) -> ExecutionReport:
        if not self.decision.broker_write_allowed:
            findings = ", ".join(self.decision.findings) or "account_identity_blocked"
            raise AccountIdentityBlockedError(f"broker write blocked by account identity gate: {findings}")
        return self.delegate.submit_order(order)


def evaluate_account_identity(
    *,
    expected_platform_id: object,
    policy: AccountIdentityPolicy | Mapping[str, Any] | None,
    observation: BrokerAccountIdentity | None,
) -> AccountIdentityDecision:
    """Compare a runtime target's reviewed expectation with broker evidence.

    An unconfigured policy is a compatibility no-op. Once a field is required,
    missing evidence is a fail-closed finding. The selected enforcement controls
    whether that finding only emits a receipt or blocks the port wrapper.
    """

    expected_platform = _normalized_text(expected_platform_id)
    if expected_platform is None:
        raise ValueError("expected_platform_id is required")
    resolved_policy = (
        policy
        if isinstance(policy, AccountIdentityPolicy)
        else AccountIdentityPolicy.from_mapping(policy)
    )
    if not resolved_policy.is_configured:
        return AccountIdentityDecision(
            policy=resolved_policy,
            observation=observation,
            findings=(),
        )

    findings: list[str] = []
    if observation is None:
        findings.append(AccountIdentityFinding.ACCOUNT_IDENTITY_EVIDENCE_UNAVAILABLE.value)
    else:
        if observation.platform_id != expected_platform.lower():
            findings.append(AccountIdentityFinding.ACCOUNT_IDENTITY_PLATFORM_MISMATCH.value)
        _validate_identity_field(
            required=AccountIdentityField.ACCOUNT_TYPE in resolved_policy.required_fields,
            observed=observation.account_types,
            expected=resolved_policy.expected_account_types,
            missing_finding=AccountIdentityFinding.ACCOUNT_IDENTITY_EVIDENCE_UNAVAILABLE,
            mismatch_finding=AccountIdentityFinding.ACCOUNT_IDENTITY_TYPE_MISMATCH,
            findings=findings,
        )
        _validate_identity_field(
            required=AccountIdentityField.ACCOUNT_MODE in resolved_policy.required_fields,
            observed=observation.account_modes,
            expected=resolved_policy.expected_account_modes,
            missing_finding=AccountIdentityFinding.ACCOUNT_IDENTITY_EVIDENCE_UNAVAILABLE,
            mismatch_finding=AccountIdentityFinding.ACCOUNT_IDENTITY_MODE_MISMATCH,
            findings=findings,
        )
        _validate_identifier(
            required=AccountIdentityField.ACCOUNT_ID in resolved_policy.required_fields,
            observed=observation.account_id_fingerprint,
            expected=resolved_policy.expected_account_id_fingerprint,
            findings=findings,
        )
    return AccountIdentityDecision(
        policy=resolved_policy,
        observation=observation,
        findings=tuple(findings),
    )


def _validate_identity_field(
    *,
    required: bool,
    observed: tuple[str, ...],
    expected: tuple[str, ...],
    missing_finding: AccountIdentityFinding,
    mismatch_finding: AccountIdentityFinding,
    findings: list[str],
) -> None:
    if not required:
        return
    if not expected:
        findings.append(AccountIdentityFinding.ACCOUNT_IDENTITY_CONFIGURATION_INVALID.value)
        return
    if not observed:
        if missing_finding.value not in findings:
            findings.append(missing_finding.value)
        return
    if set(observed) != set(expected) and mismatch_finding.value not in findings:
        findings.append(mismatch_finding.value)


def _validate_identifier(
    *,
    required: bool,
    observed: str | None,
    expected: str | None,
    findings: list[str],
) -> None:
    if not required:
        return
    if expected is None:
        findings.append(AccountIdentityFinding.ACCOUNT_IDENTITY_CONFIGURATION_INVALID.value)
        return
    if observed is None:
        if AccountIdentityFinding.ACCOUNT_IDENTITY_EVIDENCE_UNAVAILABLE.value not in findings:
            findings.append(AccountIdentityFinding.ACCOUNT_IDENTITY_EVIDENCE_UNAVAILABLE.value)
        return
    if observed != expected:
        findings.append(AccountIdentityFinding.ACCOUNT_IDENTITY_ID_MISMATCH.value)


__all__ = [
    "ACCOUNT_IDENTITY_RECEIPT_SCHEMA_VERSION",
    "AccountIdentityBlockedError",
    "AccountIdentityDecision",
    "AccountIdentityEnforcement",
    "AccountIdentityEvidenceSource",
    "AccountIdentityField",
    "AccountIdentityFinding",
    "AccountIdentityGuardedExecutionPort",
    "AccountIdentityPolicy",
    "BrokerAccountIdentity",
    "evaluate_account_identity",
]
