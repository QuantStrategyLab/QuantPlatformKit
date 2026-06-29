"""Immutable audit log for all parameter updates."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from quant_platform_kit.strategy_lifecycle.contracts import UpdateLogEntry, UpdateStage
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _entry_id() -> str:
    return uuid.uuid4().hex[:12]


def record_audit_entry(
    strategy_profile: str,
    domain: str,
    stage: UpdateStage,
    *,
    operator: str = "auto_optimizer",
    param_version_from: int | None = None,
    param_version_to: int | None = None,
    params_before: Mapping[str, Any] | None = None,
    params_after: Mapping[str, Any] | None = None,
    reason: str = "",
    approval_source: str = "",
    improvement_score: float | None = None,
    shadow_days: int = 0,
    store: PerformanceStore | None = None,
) -> UpdateLogEntry:
    """Create and persist an immutable audit log entry."""
    store = store or PerformanceStore.from_env()

    entry = UpdateLogEntry(
        strategy_profile=strategy_profile,
        domain=domain,
        entry_id=_entry_id(),
        stage=stage,
        timestamp=_now_iso(),
        operator=operator,
        param_version_from=param_version_from,
        param_version_to=param_version_to,
        params_before=dict(params_before or {}),
        params_after=dict(params_after or {}),
        reason=reason,
        approval_source=approval_source,
        improvement_score=improvement_score,
        shadow_days=shadow_days,
    )

    store.save_audit_entry(entry)
    return entry


def get_audit_trail(
    strategy_profile: str,
    *,
    limit: int = 20,
    store: PerformanceStore | None = None,
) -> tuple[UpdateLogEntry, ...]:
    """Retrieve recent audit entries for a strategy."""
    store = store or PerformanceStore.from_env()
    return store.load_audit_entries(strategy_profile, limit=limit)
