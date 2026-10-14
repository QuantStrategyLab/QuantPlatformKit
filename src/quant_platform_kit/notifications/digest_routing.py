"""Opt-in routing for routine cycles whose persisted reports feed a daily digest.

This decides notification delivery only. It never changes an execution result,
calls a broker, grants order permissions, or treats deferral as delivery.
"""

from __future__ import annotations

import os
from collections.abc import Mapping


def defer_routine_cycle_to_digest(
    execution: Mapping[str, object],
    *,
    submitted_order_count: int,
    mode: str | None = None,
) -> bool:
    """Defer verified no-order cycles only; all uncertain/urgent states stay live.

    Default ``QSL_ROUTINE_NOTIFICATION_MODE=immediate`` preserves existing
    callers. An owner can opt a verified producer/recipient into ``daily_digest``
    after validating the existing private report-to-digest replacement path.
    """
    selected = mode if mode is not None else os.getenv("QSL_ROUTINE_NOTIFICATION_MODE", "immediate")
    if selected != "daily_digest" or type(submitted_order_count) is not int or submitted_order_count != 0:
        return False
    if not isinstance(execution, Mapping):
        return False
    if str(execution.get("execution_status") or "").lower() not in {"no_action", "no_op", "completed"}:
        return False
    if execution.get("no_op_reason") not in (
        None, "", "no_action", "no_signal", "no_rebalance", "below_threshold",
        "rebalance_diff_below_threshold", "threshold_not_met",
    ):
        return False
    if any(execution.get(key) for key in (
        "error", "errors", "fail_reason", "execution_blocked_reason",
        "plugin_error", "persistence_error", "report_persistence_error", "notification_error",
        "pending_reconciliation", "reconciliation_required", "market_data_retry_required",
        "notification_attention_reason_codes", "orders_pending_count", "broker_submission_done",
        "account_new_risk_buy_blocked", "small_account_buy_blocked", "risk_flags",
    )):
        # Only an explicit healthy no-order fact is eligible. Even a failed
        # routine notification or unclassified no-op reason stays immediate.
        return False
    if str(execution.get("risk_gate") or "").upper() in {"BLOCK", "BLOCKED", "REJECT", "REJECTED", "DENY", "DENIED"}:
        return False
    return True
