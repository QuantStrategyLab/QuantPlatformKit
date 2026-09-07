"""Map injected production-drift status → NEW_RISK prohibit reasons.

Policy A (monitoring → ban new risk; zero optimize)
---------------------------------------------------
When a caller injects an actionable production drift status (``review`` /
``critical``), the account NEW_RISK gate must prohibit new risk. This module
does **not** start optimization, research tickets, or live enablement.

Absent status is not invented as healthy or critical: no inject ⇒ no drift
axis reasons. Invalid status fails closed.
"""

from __future__ import annotations

from typing import Any

_ALLOWED_STATUSES = frozenset({"healthy", "watch", "review", "critical"})
_ACTIONABLE_STATUSES = frozenset({"review", "critical"})


def normalize_production_drift_status(value: object) -> str | None:
    """Return lowercase closed-enum status, or ``None`` when not injected."""
    if value is None:
        return None
    if hasattr(value, "value") and not isinstance(value, (str, bytes)):
        # DriftStatus / similar enums
        value = getattr(value, "value")
    if not isinstance(value, str):
        raise TypeError("production_drift_status must be str, enum, or None")
    normalized = value.strip().lower()
    if not normalized:
        return None
    return normalized


def production_drift_new_risk_reasons(status: object) -> tuple[str, ...]:
    """Return prohibit reason codes for an injected production-drift status.

    ``None`` / blank ⇒ no reasons (axis not injected).
    ``healthy`` / ``watch`` ⇒ no reasons.
    ``review`` / ``critical`` ⇒ ``PRODUCTION_DRIFT_*`` (ban new risk only).
    Anything else ⇒ ``PRODUCTION_DRIFT_STATUS_INVALID_FAIL_CLOSED``.
    """
    try:
        normalized = normalize_production_drift_status(status)
    except TypeError:
        return ("PRODUCTION_DRIFT_STATUS_INVALID_FAIL_CLOSED",)
    if normalized is None:
        return ()
    if normalized not in _ALLOWED_STATUSES:
        return ("PRODUCTION_DRIFT_STATUS_INVALID_FAIL_CLOSED",)
    if normalized in _ACTIONABLE_STATUSES:
        return (f"PRODUCTION_DRIFT_{normalized.upper()}",)
    return ()


def production_drift_status_from_result(drift: Any) -> str | None:
    """Extract status string from a ``DriftResult``-like object (inject helper)."""
    if drift is None:
        return None
    status = getattr(drift, "status", drift)
    return normalize_production_drift_status(status)


__all__ = [
    "normalize_production_drift_status",
    "production_drift_new_risk_reasons",
    "production_drift_status_from_result",
]
