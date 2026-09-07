"""Project trading-cycle health axes for account_new_risk_gate (inject-only).

Cycle-health semantics (distinct from RECONCILE_ONLY digest recovery):
- observation COMPLETE when the cycle's read-only equity/positions surface succeeded
- reconciliation VERIFIED when there is no UNKNOWN pending, and either expected
  digests are absent (cycle-health path) or configured digests fully match
- circuit breaker CLOSED only when no durable OPEN is recorded and the cycle
  did not trip; never auto-clears an OPEN durable state

This module does not read brokers, write durable breaker state, or grant live.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class CycleNewRiskHealthEvidence:
    """Caller-injected facts available inside one execution cycle."""

    observation_ok: bool
    unknown_pending: bool = False
    digests_configured: bool = False
    digests_verified: bool = False
    durable_breaker_open: bool = False
    cycle_trip_open: bool = False


def project_cycle_new_risk_health_axes(
    evidence: CycleNewRiskHealthEvidence,
) -> dict[str, str]:
    """Map cycle evidence to gate health axes (no equity fields)."""
    if not isinstance(evidence, CycleNewRiskHealthEvidence):
        raise TypeError("evidence must be CycleNewRiskHealthEvidence")

    observation_status = "COMPLETE" if evidence.observation_ok else "UNAVAILABLE"

    if evidence.unknown_pending:
        reconciliation_status = "UNVERIFIED"
    elif evidence.digests_configured:
        reconciliation_status = "VERIFIED" if evidence.digests_verified else "UNVERIFIED"
    elif evidence.observation_ok:
        reconciliation_status = "VERIFIED"
    else:
        reconciliation_status = "UNVERIFIED"

    tripped = bool(evidence.durable_breaker_open or evidence.cycle_trip_open or evidence.unknown_pending)
    circuit_breaker_state = "OPEN" if tripped else "CLOSED"

    return {
        "observation_status": observation_status,
        "reconciliation_status": reconciliation_status,
        "circuit_breaker_state": circuit_breaker_state,
    }


def apply_cycle_new_risk_health_axes(
    projection: Mapping[str, Any] | None,
    evidence: CycleNewRiskHealthEvidence,
) -> dict[str, Any]:
    """Merge projected axes into an existing snapshot dict without dropping capital fields.

    Explicit keys already present on ``projection`` win (tests / HITL overrides).
    """
    merged = dict(projection or {})
    axes = project_cycle_new_risk_health_axes(evidence)
    for key, value in axes.items():
        merged.setdefault(key, value)
    return merged
