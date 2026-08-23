"""Immutable, research-only portfolio risk snapshots.

The snapshot is an observation contract.  It is deliberately not an order
intent and has no execution dependencies.  Invalid or stale inputs produce a
parked, zeroed snapshot rather than a partially trusted risk recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any, Mapping


_CIRCUIT_STATES = frozenset({"ACTIVE", "REDUCE", "TRIPPED", "PARKED"})


@dataclass(frozen=True)
class RiskSnapshot:
    """Read-only risk state consumed by research and control-plane views."""

    status: str
    account_equity: float
    risk_budget: float
    effective_exposure: float
    max_loss_estimate: float
    drawdown_scalar: float
    kelly_fraction: float
    applied_fraction: float
    circuit_state: str
    evidence_package_id: str | None
    expires_at: str | None
    reason_codes: tuple[str, ...] = ()

    @property
    def is_usable(self) -> bool:
        """Whether the snapshot is complete enough for downstream research."""

        return self.status == "READY"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible copy without execution instructions."""

        return {
            "status": self.status,
            "account_equity": self.account_equity,
            "risk_budget": self.risk_budget,
            "effective_exposure": self.effective_exposure,
            "max_loss_estimate": self.max_loss_estimate,
            "drawdown_scalar": self.drawdown_scalar,
            "kelly_fraction": self.kelly_fraction,
            "applied_fraction": self.applied_fraction,
            "circuit_state": self.circuit_state,
            "evidence_package_id": self.evidence_package_id,
            "expires_at": self.expires_at,
            "reason_codes": list(self.reason_codes),
        }


def _parked(reasons: tuple[str, ...]) -> RiskSnapshot:
    return RiskSnapshot(
        status="PARKED",
        account_equity=0.0,
        risk_budget=0.0,
        effective_exposure=0.0,
        max_loss_estimate=0.0,
        drawdown_scalar=0.0,
        kelly_fraction=0.0,
        applied_fraction=0.0,
        circuit_state="PARKED",
        evidence_package_id=None,
        expires_at=None,
        reason_codes=reasons,
    )


def _parse_utc_timestamp(value: str) -> datetime | None:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def build_risk_snapshot(
    values: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> RiskSnapshot:
    """Build a validated risk observation, failing closed on bad input.

    Required evidence identity and expiry are intentional: a risk number
    without provenance or freshness must not be treated as current.  This
    function only returns data and never allocates, submits, or mutates orders.
    """

    if not isinstance(values, Mapping):
        return _parked(("invalid_snapshot",))

    numeric_names = (
        "account_equity", "risk_budget", "effective_exposure",
        "max_loss_estimate", "drawdown_scalar", "kelly_fraction",
        "applied_fraction",
    )
    numbers: dict[str, float] = {}
    for name in numeric_names:
        value = values.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return _parked((f"invalid_{name}",))
        number = float(value)
        if not math.isfinite(number):
            return _parked((f"invalid_{name}",))
        numbers[name] = number

    if numbers["account_equity"] <= 0.0:
        return _parked(("invalid_account_equity",))
    if not 0.0 <= numbers["risk_budget"] <= 1.0:
        return _parked(("invalid_risk_budget",))
    if numbers["effective_exposure"] < 0.0:
        return _parked(("invalid_effective_exposure",))
    if numbers["max_loss_estimate"] < 0.0:
        return _parked(("invalid_max_loss_estimate",))
    if not 0.0 <= numbers["drawdown_scalar"] <= 1.0:
        return _parked(("invalid_drawdown_scalar",))
    if not 0.0 <= numbers["kelly_fraction"] <= 1.0:
        return _parked(("invalid_kelly_fraction",))
    if not 0.0 <= numbers["applied_fraction"] <= numbers["kelly_fraction"]:
        return _parked(("invalid_applied_fraction",))

    circuit = values.get("circuit_state")
    evidence = values.get("evidence_package_id")
    expires = values.get("expires_at")
    if circuit not in _CIRCUIT_STATES:
        return _parked(("invalid_circuit_state",))
    if not isinstance(evidence, str) or not evidence.strip():
        return _parked(("missing_evidence_package_id",))
    if not isinstance(expires, str) or not expires.strip():
        return _parked(("missing_expiry",))
    expires_at = _parse_utc_timestamp(expires)
    if expires_at is None:
        return _parked(("invalid_expiry",))
    reference_time = datetime.now(timezone.utc) if now is None else now
    if reference_time.tzinfo is None:
        return _parked(("invalid_reference_time",))
    if expires_at <= reference_time.astimezone(timezone.utc):
        return _parked(("expired_evidence",))
    if circuit != "ACTIVE":
        return _parked((f"circuit_{circuit.lower()}",))

    return RiskSnapshot(
        status="READY", circuit_state=circuit,
        evidence_package_id=evidence.strip(), expires_at=expires.strip(),
        reason_codes=(), **numbers,
    )
