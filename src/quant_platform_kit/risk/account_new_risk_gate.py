"""Account-level NEW_RISK prohibition adapter (skeleton; not live-wired).

Module boundary
---------------
- Consumes an **injected**, already-redacted reconciliation snapshot projection.
- Decides only whether **new risk is prohibited**.
- Does **not** read brokers/accounts, deploy, enable/disable accounts, or reset
  circuit breakers. Callers that receive ``NEW_RISK_PROHIBITED`` must fail closed
  without auto-recovery.

Wiring status
-------------
Not attached to any real account read-back. Production gateways must inject a
verified snapshot and treat validation errors as ``NEW_RISK_PROHIBITED``.
This module does not grant live authority and does not weaken ``RiskEngine``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class NewRiskDisposition(str, Enum):
    """Only dispositions this adapter may emit."""

    ALLOW_NEW_RISK = "ALLOW_NEW_RISK"
    NEW_RISK_PROHIBITED = "NEW_RISK_PROHIBITED"


class AccountNewRiskGateError(ValueError):
    """Raised when an injected snapshot projection is structurally unsafe."""


@dataclass(frozen=True)
class InjectedReconciliationSnapshot:
    """Redacted, caller-injected projection of a reconciliation snapshot.

    Field values are closed enums. This is intentionally not an account DTO:
    no account ids, credentials, broker endpoints, or order payloads.
    """

    observation_status: str
    reconciliation_status: str
    circuit_breaker_state: str


class ReconciliationSnapshotReader(Protocol):
    """Injectable read-only source. Implementations must not mutate state."""

    def read_snapshot(self) -> InjectedReconciliationSnapshot:
        """Return one redacted snapshot projection or raise."""


_HEALTHY_OBSERVATION = "COMPLETE"
_HEALTHY_RECONCILIATION = "VERIFIED"
_HEALTHY_BREAKER = "CLOSED"

_ALLOWED_OBSERVATION = frozenset({"COMPLETE", "STALE", "UNAVAILABLE"})
_ALLOWED_RECONCILIATION = frozenset({"VERIFIED", "UNVERIFIED", "FAILED"})
_ALLOWED_BREAKER = frozenset({"CLOSED", "OPEN"})


@dataclass(frozen=True)
class NewRiskAdmissionResult:
    disposition: NewRiskDisposition
    reason_codes: tuple[str, ...]
    live_authority_granted: bool = False
    circuit_breaker_reset: bool = False
    account_enablement_changed: bool = False


def validate_injected_snapshot(
    snapshot: InjectedReconciliationSnapshot,
) -> InjectedReconciliationSnapshot:
    """Fail closed on unknown enum values; never invent a healthy default."""
    if not isinstance(snapshot, InjectedReconciliationSnapshot):
        raise AccountNewRiskGateError("snapshot must be InjectedReconciliationSnapshot")
    if snapshot.observation_status not in _ALLOWED_OBSERVATION:
        raise AccountNewRiskGateError("observation_status is not an allowed enum value")
    if snapshot.reconciliation_status not in _ALLOWED_RECONCILIATION:
        raise AccountNewRiskGateError("reconciliation_status is not an allowed enum value")
    if snapshot.circuit_breaker_state not in _ALLOWED_BREAKER:
        raise AccountNewRiskGateError("circuit_breaker_state is not an allowed enum value")
    return snapshot


def evaluate_new_risk_admission(
    snapshot: InjectedReconciliationSnapshot,
) -> NewRiskAdmissionResult:
    """Map unhealthy injected snapshots to ``NEW_RISK_PROHIBITED``.

    Healthy snapshots may return ``ALLOW_NEW_RISK`` for this skeleton's health
    axis only. That is **not** an order permission and never grants live.
    """
    validated = validate_injected_snapshot(snapshot)
    reasons: list[str] = []
    if validated.observation_status != _HEALTHY_OBSERVATION:
        reasons.append("OBSERVATION_NOT_COMPLETE")
    if validated.reconciliation_status != _HEALTHY_RECONCILIATION:
        reasons.append("RECONCILIATION_NOT_VERIFIED")
    if validated.circuit_breaker_state != _HEALTHY_BREAKER:
        reasons.append("CIRCUIT_BREAKER_OPEN")
    if reasons:
        return NewRiskAdmissionResult(
            disposition=NewRiskDisposition.NEW_RISK_PROHIBITED,
            reason_codes=tuple(reasons),
        )
    return NewRiskAdmissionResult(
        disposition=NewRiskDisposition.ALLOW_NEW_RISK,
        reason_codes=(),
    )


def evaluate_new_risk_from_reader(
    reader: ReconciliationSnapshotReader,
) -> NewRiskAdmissionResult:
    """Read via injected adapter; any reader/validation failure ⇒ prohibited."""
    try:
        snapshot = reader.read_snapshot()
    except AccountNewRiskGateError:
        raise
    except Exception as exc:  # noqa: BLE001 — fail closed at the boundary
        raise AccountNewRiskGateError(
            f"reconciliation snapshot reader failed: {type(exc).__name__}"
        ) from exc
    return evaluate_new_risk_admission(snapshot)


__all__ = [
    "AccountNewRiskGateError",
    "InjectedReconciliationSnapshot",
    "NewRiskAdmissionResult",
    "NewRiskDisposition",
    "ReconciliationSnapshotReader",
    "evaluate_new_risk_admission",
    "evaluate_new_risk_from_reader",
    "validate_injected_snapshot",
]
