"""Shared execution outcome semantics for platform runtimes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

STAGE_ORDERS_PLANNED = "ORDERS_PLANNED"
STAGE_DRY_RUN_COMPLETED = "DRY_RUN_COMPLETED"
STAGE_NO_ACTION = "NO_ACTION"
STAGE_SUBMITTED = "SUBMITTED"
STAGE_EXECUTION_BLOCKED = "EXECUTION_BLOCKED"
STAGE_PARTIAL_SUBMITTED = "PARTIAL_SUBMITTED"
STAGE_FUNDING_BLOCKED = "FUNDING_BLOCKED"
STAGE_RECONCILED = "RECONCILED"
STAGE_COMPLETED = "COMPLETED"

DEFAULT_TERMINAL_STRATEGY_RUN_STAGES = frozenset(
    {
        STAGE_SUBMITTED,
        STAGE_FUNDING_BLOCKED,
        STAGE_RECONCILED,
        STAGE_COMPLETED,
    }
)

DEFAULT_EXECUTION_BLOCKING_SKIP_REASONS = frozenset(
    {
        "buy_quantity_zero",
        "insufficient_cash_for_whole_share",
        "quote_unavailable",
        "sell_quantity_zero",
    }
)
DEFAULT_TERMINAL_FUNDING_BLOCK_SKIP_REASONS = frozenset(
    {"insufficient_cash_for_whole_share"}
)


def normalize_stage(value: object) -> str:
    return str(value or "").strip().upper()


def normalize_skip_reason(value: object) -> str:
    return str(value or "").strip()


def is_terminal_strategy_run_stage(
    value: object,
    *,
    terminal_stages: frozenset[str] = DEFAULT_TERMINAL_STRATEGY_RUN_STAGES,
) -> bool:
    return normalize_stage(value) in terminal_stages


def filter_execution_blocking_skips(
    skipped_orders: Sequence[Mapping[str, Any]],
    *,
    blocking_reasons: frozenset[str] = DEFAULT_EXECUTION_BLOCKING_SKIP_REASONS,
) -> list[dict[str, Any]]:
    return [
        dict(item)
        for item in skipped_orders
        if normalize_skip_reason(item.get("reason")) in blocking_reasons
    ]


def is_terminal_funding_block(
    blocking_skips: Sequence[Mapping[str, Any]],
    *,
    funding_block_reasons: frozenset[str] = DEFAULT_TERMINAL_FUNDING_BLOCK_SKIP_REASONS,
) -> bool:
    if not blocking_skips:
        return False
    return all(
        normalize_skip_reason(item.get("reason")) in funding_block_reasons
        for item in blocking_skips
    )


def resolve_strategy_run_stage(
    *,
    dry_run_only: bool,
    execution_blocked: bool,
    terminal_funding_block: bool,
    action_done: bool,
) -> str:
    if dry_run_only:
        return STAGE_DRY_RUN_COMPLETED
    if terminal_funding_block and not action_done:
        return STAGE_FUNDING_BLOCKED
    if execution_blocked and action_done:
        return STAGE_PARTIAL_SUBMITTED
    if execution_blocked:
        return STAGE_EXECUTION_BLOCKED
    return STAGE_SUBMITTED if action_done else STAGE_NO_ACTION
