"""Account-level NEW_RISK prohibition adapter (D2 inject; not live-wired).

Module boundary
---------------
- Consumes an **injected**, already-redacted reconciliation snapshot projection
  that may include a capital summary (``equity_usd`` and optional peak / DD / vol).
- Decides only whether **new risk is prohibited**.
- Does **not** read brokers/accounts, deploy, enable/disable accounts, flatten
  positions, or reset circuit breakers. Callers that receive
  ``NEW_RISK_PROHIBITED`` must fail closed without auto-recovery.

Capital envelope (D2)
---------------------
When a capital summary is present, this adapter calls
``evaluate_capital_risk_envelope``. Missing / invalid equity or
``new_risk_allowed=False`` maps to ``NEW_RISK_PROHIBITED`` (fail-closed).
Optional ``peak_equity_usd`` may derive drawdown when ``drawdown_from_peak``
is omitted.

Wiring status
-------------
Still **not** attached to any real account read-back or production deploy.
Production gateways must inject a verified snapshot (including equity) and
treat validation errors as ``NEW_RISK_PROHIBITED``. This module does not grant
live authority and does not weaken ``RiskEngine``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Protocol

from quant_platform_kit.risk.capital_risk_envelope import evaluate_capital_risk_envelope


class NewRiskDisposition(str, Enum):
    """Only dispositions this adapter may emit."""

    ALLOW_NEW_RISK = "ALLOW_NEW_RISK"
    NEW_RISK_PROHIBITED = "NEW_RISK_PROHIBITED"


class AccountNewRiskGateError(ValueError):
    """Raised when an injected snapshot projection is structurally unsafe."""


@dataclass(frozen=True)
class InjectedReconciliationSnapshot:
    """Redacted, caller-injected projection of a reconciliation snapshot.

    Field values for health axes are closed enums. Capital fields are optional
    inject-only numbers (no account ids, credentials, broker endpoints, or
    order payloads). Missing equity is treated as unknown → prohibit at the
    gate, not as a silent healthy default.
    """

    observation_status: str
    reconciliation_status: str
    circuit_breaker_state: str
    equity_usd: float | None = None
    peak_equity_usd: float | None = None
    drawdown_from_peak: float | None = None
    realized_vol: float | None = None


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

# Envelope reason codes that already imply new-risk prohibition.
_ENVELOPE_PROHIBIT_REASONS = frozenset(
    {
        "INVALID_EQUITY_FAIL_CLOSED",
        "INVALID_DRAWDOWN_FAIL_CLOSED",
        "DRAWDOWN_BRAKE_TRIPPED",
    }
)


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


def _derive_drawdown_from_peak(
    equity_usd: float,
    peak_equity_usd: float | None,
    drawdown_from_peak: float | None,
) -> float | None:
    """Prefer explicit DD; else derive from peak when both numbers are finite."""
    if drawdown_from_peak is not None:
        return drawdown_from_peak
    if peak_equity_usd is None:
        return None
    if (
        isinstance(peak_equity_usd, bool)
        or not isinstance(peak_equity_usd, (int, float))
        or not math.isfinite(float(peak_equity_usd))
        or float(peak_equity_usd) <= 0.0
    ):
        return float("nan")  # force envelope fail-closed on bad peak
    peak = float(peak_equity_usd)
    return max(0.0, 1.0 - float(equity_usd) / peak)


def _evaluate_capital_axis(
    snapshot: InjectedReconciliationSnapshot,
) -> list[str]:
    """Return capital-axis prohibit reasons (empty ⇒ capital axis allows)."""
    if snapshot.equity_usd is None:
        return ["EQUITY_UNKNOWN_FAIL_CLOSED"]

    drawdown = _derive_drawdown_from_peak(
        float(snapshot.equity_usd)
        if isinstance(snapshot.equity_usd, (int, float))
        and not isinstance(snapshot.equity_usd, bool)
        else float("nan"),
        snapshot.peak_equity_usd,
        snapshot.drawdown_from_peak,
    )
    envelope = evaluate_capital_risk_envelope(
        snapshot.equity_usd,
        realized_vol=snapshot.realized_vol,
        drawdown_from_peak=drawdown,
    )
    if envelope.new_risk_allowed:
        return []
    reasons = [code for code in envelope.reasons if code in _ENVELOPE_PROHIBIT_REASONS]
    if not reasons:
        reasons = ["CAPITAL_ENVELOPE_NEW_RISK_PROHIBITED"]
    return reasons


def evaluate_new_risk_admission(
    snapshot: InjectedReconciliationSnapshot,
) -> NewRiskAdmissionResult:
    """Map unhealthy injected snapshots / capital envelope to ``NEW_RISK_PROHIBITED``.

    Healthy reconciliation axes **and** an allowing capital envelope may return
    ``ALLOW_NEW_RISK``. That is **not** an order permission, never grants live,
    never flattens, and never resets breakers. Still not wired to real accounts.
    """
    validated = validate_injected_snapshot(snapshot)
    reasons: list[str] = []
    if validated.observation_status != _HEALTHY_OBSERVATION:
        reasons.append("OBSERVATION_NOT_COMPLETE")
    if validated.reconciliation_status != _HEALTHY_RECONCILIATION:
        reasons.append("RECONCILIATION_NOT_VERIFIED")
    if validated.circuit_breaker_state != _HEALTHY_BREAKER:
        reasons.append("CIRCUIT_BREAKER_OPEN")
    reasons.extend(_evaluate_capital_axis(validated))
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
