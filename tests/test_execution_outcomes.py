from quant_platform_kit.common.execution_outcomes import (
    STAGE_DRY_RUN_COMPLETED,
    STAGE_EXECUTION_BLOCKED,
    STAGE_FUNDING_BLOCKED,
    STAGE_NO_ACTION,
    STAGE_PARTIAL_SUBMITTED,
    STAGE_SUBMITTED,
    filter_execution_blocking_skips,
    is_terminal_funding_block,
    is_terminal_strategy_run_stage,
    resolve_strategy_run_stage,
)


def test_resolve_strategy_run_stage_uses_shared_terminal_semantics():
    assert (
        resolve_strategy_run_stage(
            dry_run_only=True,
            execution_blocked=True,
            terminal_funding_block=True,
            action_done=False,
        )
        == STAGE_DRY_RUN_COMPLETED
    )
    assert (
        resolve_strategy_run_stage(
            dry_run_only=False,
            execution_blocked=True,
            terminal_funding_block=True,
            action_done=False,
        )
        == STAGE_FUNDING_BLOCKED
    )
    assert (
        resolve_strategy_run_stage(
            dry_run_only=False,
            execution_blocked=True,
            terminal_funding_block=False,
            action_done=True,
        )
        == STAGE_PARTIAL_SUBMITTED
    )
    assert (
        resolve_strategy_run_stage(
            dry_run_only=False,
            execution_blocked=True,
            terminal_funding_block=False,
            action_done=False,
        )
        == STAGE_EXECUTION_BLOCKED
    )
    assert (
        resolve_strategy_run_stage(
            dry_run_only=False,
            execution_blocked=False,
            terminal_funding_block=False,
            action_done=True,
        )
        == STAGE_SUBMITTED
    )
    assert (
        resolve_strategy_run_stage(
            dry_run_only=False,
            execution_blocked=False,
            terminal_funding_block=False,
            action_done=False,
        )
        == STAGE_NO_ACTION
    )


def test_filter_execution_blocking_skips_and_terminal_funding_block():
    skipped = [
        {"symbol": "AAA", "reason": "below_trade_threshold"},
        {"symbol": "BBB", "reason": "quote_unavailable"},
        {"symbol": "CCC", "reason": "insufficient_cash_for_whole_share"},
    ]

    blocking = filter_execution_blocking_skips(skipped)

    assert blocking == [
        {"symbol": "BBB", "reason": "quote_unavailable"},
        {"symbol": "CCC", "reason": "insufficient_cash_for_whole_share"},
    ]
    assert is_terminal_funding_block(blocking) is False
    assert is_terminal_funding_block(blocking[1:]) is True


def test_terminal_strategy_run_stage_includes_funding_blocked():
    assert is_terminal_strategy_run_stage("submitted") is True
    assert is_terminal_strategy_run_stage("FUNDING_BLOCKED") is True
    assert is_terminal_strategy_run_stage("EXECUTION_BLOCKED") is False
