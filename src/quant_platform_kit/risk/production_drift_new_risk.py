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

from collections.abc import Callable, Mapping
from datetime import date
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
    """Extract status string from a ``DriftResult``-like object (inject helper).

    Missing baseline (``baseline_available=False``) omits status so NEW_RISK
    does not treat no-baseline 0.0 scores as healthy.
    """
    if drift is None:
        return None
    if getattr(drift, "baseline_available", True) is False:
        return None
    status = getattr(drift, "status", drift)
    return normalize_production_drift_status(status)


def production_drift_status_from_probe_summary(
    summary: Mapping[str, Any] | None,
) -> str | None:
    """Map probe summary → inject status; parked/unavailable/missing → None."""
    if summary is None:
        return None
    raw = summary.get("status")
    try:
        normalized = normalize_production_drift_status(raw)
    except TypeError:
        return None
    if normalized is None:
        return None
    if normalized in {"parked", "unavailable"}:
        return None
    if normalized in _ALLOWED_STATUSES:
        return normalized
    return None


def resolve_production_drift_status_from_store(
    *,
    strategy_profile: str,
    domain: str,
    as_of: date | str | None = None,
    store: Any | None = None,
    probe: Callable[..., Mapping[str, Any]] | None = None,
) -> str | None:
    """Read-only store probe → status | None. Any exception → None (fail-soft).

    Does not optimize, grant live, or reset breakers.
    """
    profile = (strategy_profile or "").strip()
    domain_key = (domain or "").strip()
    if not profile or not domain_key:
        return None
    active_probe = probe
    if active_probe is None:
        from quant_platform_kit.strategy_lifecycle.production_drift_health_probe import (
            probe_production_drift_health_from_store,
        )

        active_probe = probe_production_drift_health_from_store
    try:
        summary = active_probe(
            strategy_profile=profile,
            domain=domain_key,
            as_of=as_of,
            store=store,
        )
    except Exception:
        return None
    return production_drift_status_from_probe_summary(summary)


__all__ = [
    "normalize_production_drift_status",
    "production_drift_new_risk_reasons",
    "production_drift_status_from_probe_summary",
    "production_drift_status_from_result",
    "resolve_production_drift_status_from_store",
]
