"""Fail-closed evidence contract for resuming a frozen live baseline.

``RECONCILE_ONLY`` intentionally prevents ordinary orders after a runtime is
frozen.  A successful health probe is not enough to remove that protection:
the platform must also show that its broker state and its durable local
execution ledger still agree with the frozen baseline.

This module is deliberately broker- and cloud-independent.  Adapters collect
their own read-only observations, canonicalise them locally, and expose only
their SHA-256 digests and boolean comparisons through this contract.  It is
therefore safe to persist the resulting receipt in a private control-plane
artifact without publishing account identifiers, balances, positions, order
details, or fill details.

The contract authorises neither a broker call nor a state transition by
itself.  A trusted control-plane consumer must verify the receipt and perform
the explicit ``RECONCILE_ONLY -> ACTIVE_LKG`` update.  Any missing, stale, or
mismatched evidence remains fail-closed.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any


BROKER_RECONCILIATION_EVIDENCE_SCHEMA_VERSION = "broker_reconciliation_evidence.v1"
DEFAULT_BROKER_RECONCILIATION_MAX_AGE = timedelta(minutes=30)

_PROFILE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_PLATFORM_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_BASELINE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class BrokerReconciliationFinding(str, Enum):
    """Stable, redacted reasons a frozen live baseline must remain blocked."""

    EVIDENCE_STALE = "broker_reconciliation_evidence_stale"
    BASELINE_TARGET_MISMATCH = "broker_reconciliation_baseline_target_mismatch"
    BROKER_CONNECTION_FAILED = "broker_reconciliation_broker_connection_failed"
    ACCOUNT_IDENTITY_MISMATCH = "broker_reconciliation_account_identity_mismatch"
    POSITIONS_MISMATCH = "broker_reconciliation_positions_mismatch"
    CASH_MISMATCH = "broker_reconciliation_cash_mismatch"
    OPEN_ORDERS_MISMATCH = "broker_reconciliation_open_orders_mismatch"
    RECENT_EXECUTIONS_MISMATCH = "broker_reconciliation_recent_executions_mismatch"
    LOCAL_EXECUTION_LEDGER_MISMATCH = "broker_reconciliation_local_execution_ledger_mismatch"


def _required_text(value: object, *, field_name: str, maximum_length: int = 256) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    if value != value.strip() or not value:
        raise ValueError(f"{field_name} must be a non-empty, trimmed string")
    if len(value) > maximum_length or any(ord(character) < 32 for character in value):
        raise ValueError(f"{field_name} is not a safe bounded string")
    return value


def _normalize_identifier(value: object, *, field_name: str, pattern: re.Pattern[str]) -> str:
    normalized = _required_text(value, field_name=field_name, maximum_length=128)
    if not pattern.fullmatch(normalized):
        raise ValueError(f"{field_name} has invalid characters")
    return normalized


def _normalize_sha256(value: object, *, field_name: str) -> str:
    digest = _required_text(value, field_name=field_name, maximum_length=64).lower()
    if digest.startswith("sha256:"):
        digest = digest.removeprefix("sha256:")
    if not _SHA256_PATTERN.fullmatch(digest):
        raise ValueError(f"{field_name} must be a SHA-256 digest")
    return digest


def _normalize_observed_at(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        observed_at = value
    elif isinstance(value, str):
        try:
            observed_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("observed_at must be an ISO-8601 timestamp") from exc
    else:
        raise ValueError("observed_at must be a datetime or ISO-8601 timestamp")
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must include a timezone")
    return observed_at.astimezone(timezone.utc).replace(microsecond=0)


def _normalize_bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def canonical_broker_observation_json(value: object) -> str:
    """Return a deterministic local representation before it is hashed.

    Callers must pass their normalised, read-only observations.  The returned
    string is intentionally not included in an evidence receipt and must not
    be emitted to logs, because it may contain sensitive broker data.
    """

    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("broker observation cannot be canonicalized") from exc


def calculate_broker_observation_sha256(value: object) -> str:
    """Hash a local broker observation without exposing its contents."""

    return hashlib.sha256(canonical_broker_observation_json(value).encode("utf-8")).hexdigest()


def _evidence_payload(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("broker reconciliation evidence must be an object")
    required_fields = {
        "schema_version",
        "platform_id",
        "strategy_profile",
        "account_scope_sha256",
        "baseline_id",
        "baseline_target_sha256",
        "runtime_target_sha256",
        "observed_at",
        "broker_connected",
        "account_identity_match",
        "positions_match",
        "cash_match",
        "open_orders_match",
        "recent_executions_match",
        "local_execution_ledger_match",
        "positions_sha256",
        "cash_sha256",
        "open_orders_sha256",
        "recent_executions_sha256",
        "local_execution_ledger_sha256",
        "evidence_sha256",
    }
    actual_fields = set(value)
    if actual_fields != required_fields:
        missing = sorted(required_fields - actual_fields)
        unexpected = sorted(actual_fields - required_fields)
        detail = []
        if missing:
            detail.append("missing: " + ", ".join(missing))
        if unexpected:
            detail.append("unexpected: " + ", ".join(unexpected))
        raise ValueError("broker reconciliation evidence has invalid fields (" + "; ".join(detail) + ")")
    if value["schema_version"] != BROKER_RECONCILIATION_EVIDENCE_SCHEMA_VERSION:
        raise ValueError("unsupported broker reconciliation evidence schema version")
    observed_at = _normalize_observed_at(value["observed_at"])
    return {
        "schema_version": BROKER_RECONCILIATION_EVIDENCE_SCHEMA_VERSION,
        "platform_id": _normalize_identifier(
            value["platform_id"], field_name="platform_id", pattern=_PLATFORM_PATTERN
        ),
        "strategy_profile": _normalize_identifier(
            value["strategy_profile"], field_name="strategy_profile", pattern=_PROFILE_PATTERN
        ),
        "account_scope_sha256": _normalize_sha256(
            value["account_scope_sha256"], field_name="account_scope_sha256"
        ),
        "baseline_id": _normalize_identifier(
            value["baseline_id"], field_name="baseline_id", pattern=_BASELINE_ID_PATTERN
        ),
        "baseline_target_sha256": _normalize_sha256(
            value["baseline_target_sha256"], field_name="baseline_target_sha256"
        ),
        "runtime_target_sha256": _normalize_sha256(
            value["runtime_target_sha256"], field_name="runtime_target_sha256"
        ),
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "broker_connected": _normalize_bool(value["broker_connected"], field_name="broker_connected"),
        "account_identity_match": _normalize_bool(
            value["account_identity_match"], field_name="account_identity_match"
        ),
        "positions_match": _normalize_bool(value["positions_match"], field_name="positions_match"),
        "cash_match": _normalize_bool(value["cash_match"], field_name="cash_match"),
        "open_orders_match": _normalize_bool(value["open_orders_match"], field_name="open_orders_match"),
        "recent_executions_match": _normalize_bool(
            value["recent_executions_match"], field_name="recent_executions_match"
        ),
        "local_execution_ledger_match": _normalize_bool(
            value["local_execution_ledger_match"], field_name="local_execution_ledger_match"
        ),
        "positions_sha256": _normalize_sha256(value["positions_sha256"], field_name="positions_sha256"),
        "cash_sha256": _normalize_sha256(value["cash_sha256"], field_name="cash_sha256"),
        "open_orders_sha256": _normalize_sha256(
            value["open_orders_sha256"], field_name="open_orders_sha256"
        ),
        "recent_executions_sha256": _normalize_sha256(
            value["recent_executions_sha256"], field_name="recent_executions_sha256"
        ),
        "local_execution_ledger_sha256": _normalize_sha256(
            value["local_execution_ledger_sha256"], field_name="local_execution_ledger_sha256"
        ),
    }


def canonical_broker_reconciliation_evidence_json(value: Mapping[str, object]) -> str:
    """Return canonical public-safe evidence JSON excluding its self-digest."""

    payload = _evidence_payload(value)
    try:
        return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("broker reconciliation evidence cannot be canonicalized") from exc


def calculate_broker_reconciliation_evidence_sha256(value: Mapping[str, object]) -> str:
    """Calculate the receipt digest over all required evidence except itself."""

    return hashlib.sha256(canonical_broker_reconciliation_evidence_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BrokerReconciliationEvidence:
    """Content-addressed proof required before a frozen baseline can resume."""

    platform_id: str
    strategy_profile: str
    account_scope_sha256: str
    baseline_id: str
    baseline_target_sha256: str
    runtime_target_sha256: str
    observed_at: datetime | str
    broker_connected: bool
    account_identity_match: bool
    positions_match: bool
    cash_match: bool
    open_orders_match: bool
    recent_executions_match: bool
    local_execution_ledger_match: bool
    positions_sha256: str
    cash_sha256: str
    open_orders_sha256: str
    recent_executions_sha256: str
    local_execution_ledger_sha256: str
    evidence_sha256: str
    schema_version: str = BROKER_RECONCILIATION_EVIDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        payload = _evidence_payload(self.to_dict())
        object.__setattr__(self, "platform_id", payload["platform_id"])
        object.__setattr__(self, "strategy_profile", payload["strategy_profile"])
        object.__setattr__(self, "account_scope_sha256", payload["account_scope_sha256"])
        object.__setattr__(self, "baseline_id", payload["baseline_id"])
        object.__setattr__(self, "baseline_target_sha256", payload["baseline_target_sha256"])
        object.__setattr__(self, "runtime_target_sha256", payload["runtime_target_sha256"])
        object.__setattr__(self, "observed_at", _normalize_observed_at(self.observed_at))
        for field_name in (
            "broker_connected",
            "account_identity_match",
            "positions_match",
            "cash_match",
            "open_orders_match",
            "recent_executions_match",
            "local_execution_ledger_match",
        ):
            object.__setattr__(self, field_name, payload[field_name])
        for field_name in (
            "positions_sha256",
            "cash_sha256",
            "open_orders_sha256",
            "recent_executions_sha256",
            "local_execution_ledger_sha256",
        ):
            object.__setattr__(self, field_name, payload[field_name])
        if self.schema_version != BROKER_RECONCILIATION_EVIDENCE_SCHEMA_VERSION:
            raise ValueError("unsupported broker reconciliation evidence schema version")
        digest = _normalize_sha256(self.evidence_sha256, field_name="evidence_sha256")
        object.__setattr__(self, "evidence_sha256", digest)
        if digest != calculate_broker_reconciliation_evidence_sha256(self.to_dict()):
            raise ValueError("broker reconciliation evidence_sha256 mismatch")

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        observed_at = payload["observed_at"]
        if isinstance(observed_at, datetime):
            payload["observed_at"] = observed_at.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
                "+00:00", "Z"
            )
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "BrokerReconciliationEvidence":
        _evidence_payload(value)
        return cls(**dict(value))


def build_broker_reconciliation_evidence(
    *,
    platform_id: object,
    strategy_profile: object,
    account_scope_sha256: object,
    baseline_id: object,
    baseline_target_sha256: object,
    runtime_target_sha256: object,
    observed_at: datetime | str,
    broker_connected: bool,
    account_identity_match: bool,
    positions_match: bool,
    cash_match: bool,
    open_orders_match: bool,
    recent_executions_match: bool,
    local_execution_ledger_match: bool,
    positions_sha256: object,
    cash_sha256: object,
    open_orders_sha256: object,
    recent_executions_sha256: object,
    local_execution_ledger_sha256: object,
) -> BrokerReconciliationEvidence:
    """Build an immutable, redacted recovery receipt from adapter comparisons."""

    draft: dict[str, object] = {
        "schema_version": BROKER_RECONCILIATION_EVIDENCE_SCHEMA_VERSION,
        "platform_id": platform_id,
        "strategy_profile": strategy_profile,
        "account_scope_sha256": account_scope_sha256,
        "baseline_id": baseline_id,
        "baseline_target_sha256": baseline_target_sha256,
        "runtime_target_sha256": runtime_target_sha256,
        "observed_at": observed_at,
        "broker_connected": broker_connected,
        "account_identity_match": account_identity_match,
        "positions_match": positions_match,
        "cash_match": cash_match,
        "open_orders_match": open_orders_match,
        "recent_executions_match": recent_executions_match,
        "local_execution_ledger_match": local_execution_ledger_match,
        "positions_sha256": positions_sha256,
        "cash_sha256": cash_sha256,
        "open_orders_sha256": open_orders_sha256,
        "recent_executions_sha256": recent_executions_sha256,
        "local_execution_ledger_sha256": local_execution_ledger_sha256,
        "evidence_sha256": "0" * 64,
    }
    draft["evidence_sha256"] = calculate_broker_reconciliation_evidence_sha256(draft)
    return BrokerReconciliationEvidence.from_dict(draft)


def evaluate_broker_reconciliation_recovery(
    evidence: BrokerReconciliationEvidence | Mapping[str, object] | None,
    *,
    now: datetime | None = None,
    max_age: timedelta = DEFAULT_BROKER_RECONCILIATION_MAX_AGE,
    expected_platform_id: str | None = None,
    expected_strategy_profile: str | None = None,
    expected_account_scope_sha256: str | None = None,
    expected_baseline_id: str | None = None,
    expected_runtime_target_sha256: str | None = None,
    expected_positions_sha256: str | None = None,
    expected_cash_sha256: str | None = None,
    expected_open_orders_sha256: str | None = None,
    expected_recent_executions_sha256: str | None = None,
    expected_local_execution_ledger_sha256: str | None = None,
) -> tuple[BrokerReconciliationFinding, ...]:
    """Return every blocking finding; an empty tuple is required for recovery.

    This is a policy-free validation of one fresh receipt.  A control plane may
    add stronger checks (trusted producer, durable storage generation, dual
    approval) but may not treat a non-empty result as recoverable.
    """

    if max_age <= timedelta(0):
        raise ValueError("max_age must be positive")
    if evidence is None:
        return (BrokerReconciliationFinding.BROKER_CONNECTION_FAILED,)
    try:
        normalized = (
            evidence
            if isinstance(evidence, BrokerReconciliationEvidence)
            else BrokerReconciliationEvidence.from_dict(evidence)
        )
    except (TypeError, ValueError):
        return (BrokerReconciliationFinding.BROKER_CONNECTION_FAILED,)

    findings: list[BrokerReconciliationFinding] = []

    def append(finding: BrokerReconciliationFinding) -> None:
        if finding not in findings:
            findings.append(finding)

    reference_now = _normalize_observed_at(now or datetime.now(timezone.utc))
    if normalized.observed_at > reference_now or reference_now - normalized.observed_at > max_age:
        append(BrokerReconciliationFinding.EVIDENCE_STALE)
    if normalized.baseline_target_sha256 != normalized.runtime_target_sha256:
        append(BrokerReconciliationFinding.BASELINE_TARGET_MISMATCH)
    if expected_runtime_target_sha256 is not None:
        try:
            expected_digest = _normalize_sha256(
                expected_runtime_target_sha256, field_name="expected_runtime_target_sha256"
            )
        except ValueError:
            append(BrokerReconciliationFinding.BASELINE_TARGET_MISMATCH)
        else:
            if normalized.runtime_target_sha256 != expected_digest:
                append(BrokerReconciliationFinding.BASELINE_TARGET_MISMATCH)
    for actual, expected in (
        (normalized.platform_id, expected_platform_id),
        (normalized.strategy_profile, expected_strategy_profile),
        (normalized.account_scope_sha256, expected_account_scope_sha256),
        (normalized.baseline_id, expected_baseline_id),
    ):
        if expected is not None and actual != expected:
            append(BrokerReconciliationFinding.ACCOUNT_IDENTITY_MISMATCH)

    for actual, expected, finding, field_name in (
        (
            normalized.positions_sha256,
            expected_positions_sha256,
            BrokerReconciliationFinding.POSITIONS_MISMATCH,
            "expected_positions_sha256",
        ),
        (
            normalized.cash_sha256,
            expected_cash_sha256,
            BrokerReconciliationFinding.CASH_MISMATCH,
            "expected_cash_sha256",
        ),
        (
            normalized.open_orders_sha256,
            expected_open_orders_sha256,
            BrokerReconciliationFinding.OPEN_ORDERS_MISMATCH,
            "expected_open_orders_sha256",
        ),
        (
            normalized.recent_executions_sha256,
            expected_recent_executions_sha256,
            BrokerReconciliationFinding.RECENT_EXECUTIONS_MISMATCH,
            "expected_recent_executions_sha256",
        ),
        (
            normalized.local_execution_ledger_sha256,
            expected_local_execution_ledger_sha256,
            BrokerReconciliationFinding.LOCAL_EXECUTION_LEDGER_MISMATCH,
            "expected_local_execution_ledger_sha256",
        ),
    ):
        if expected is None:
            continue
        try:
            expected_digest = _normalize_sha256(expected, field_name=field_name)
        except ValueError:
            append(finding)
        else:
            if actual != expected_digest:
                append(finding)

    for matched, finding in (
        (normalized.broker_connected, BrokerReconciliationFinding.BROKER_CONNECTION_FAILED),
        (normalized.account_identity_match, BrokerReconciliationFinding.ACCOUNT_IDENTITY_MISMATCH),
        (normalized.positions_match, BrokerReconciliationFinding.POSITIONS_MISMATCH),
        (normalized.cash_match, BrokerReconciliationFinding.CASH_MISMATCH),
        (normalized.open_orders_match, BrokerReconciliationFinding.OPEN_ORDERS_MISMATCH),
        (normalized.recent_executions_match, BrokerReconciliationFinding.RECENT_EXECUTIONS_MISMATCH),
        (
            normalized.local_execution_ledger_match,
            BrokerReconciliationFinding.LOCAL_EXECUTION_LEDGER_MISMATCH,
        ),
    ):
        if not matched:
            append(finding)
    return tuple(findings)


__all__ = [
    "BROKER_RECONCILIATION_EVIDENCE_SCHEMA_VERSION",
    "DEFAULT_BROKER_RECONCILIATION_MAX_AGE",
    "BrokerReconciliationEvidence",
    "BrokerReconciliationFinding",
    "build_broker_reconciliation_evidence",
    "calculate_broker_observation_sha256",
    "calculate_broker_reconciliation_evidence_sha256",
    "canonical_broker_observation_json",
    "canonical_broker_reconciliation_evidence_json",
    "evaluate_broker_reconciliation_recovery",
]
