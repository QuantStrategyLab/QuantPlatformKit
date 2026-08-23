"""Canonical lifecycle names and conservative legacy catalog compatibility.

Lifecycle metadata describes where a strategy is in the research-to-production
process.  It is deliberately not an execution authorization mechanism.
"""

from __future__ import annotations

from types import MappingProxyType


CANONICAL_LIFECYCLE_STATES = frozenset(
    {
        "research_active",
        "shadow_active",
        "paper_active",
        "live_candidate",
        "live_enabled",
    }
)

# Legacy catalog values are normalized conservatively.  In particular,
# ``runtime_enabled`` historically meant that a strategy package was selectable
# by a runtime.  It did not prove broker permission, a current risk approval, or
# an operator-approved deployment; therefore it cannot become ``live_enabled``
# from catalog metadata alone.
LEGACY_CATALOG_STATUS_MAP = MappingProxyType(
    {
        "research_backtest_only": "research_active",
        "ai_monitored_candidate": "research_active",
        "shadow_candidate": "shadow_active",
        "runtime_enabled": "live_candidate",
    }
)


def normalize_catalog_lifecycle_status(status: str) -> str:
    """Return a canonical lifecycle status for read-only catalog metadata.

    The result is descriptive only and grants no paper or live execution
    permission.  Unknown values fail closed instead of being guessed.
    """

    normalized = str(status or "").strip().lower()
    if normalized in CANONICAL_LIFECYCLE_STATES:
        return normalized
    try:
        return LEGACY_CATALOG_STATUS_MAP[normalized]
    except KeyError as exc:
        raise ValueError(f"unsupported lifecycle status: {status!r}") from exc


def catalog_status_grants_execution_permission(status: str) -> bool:
    """Always return False: catalog and inventory records are not authorities."""

    normalize_catalog_lifecycle_status(status)
    return False
