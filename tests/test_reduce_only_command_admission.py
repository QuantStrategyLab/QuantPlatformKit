from __future__ import annotations

from quant_platform_kit.common.execution_commands import ExecutionCommand
from quant_platform_kit.common.models import OrderIntent
from quant_platform_kit.common.reduce_only_command_admission import (
    REDUCE_ONLY_ORDER_DIGEST_FIELD,
    ReduceOnlyCommandFinding,
    build_reduce_only_order_digest,
    evaluate_reduce_only_command_admission,
)
from quant_platform_kit.common.strategy_release import build_runtime_loaded_receipt


def _release() -> dict[str, str]:
    return {
        "release_id": "soxl-reduce-v1",
        "manifest_sha256": "a" * 64,
        "strategy_revision": "soxl-reduce-v1",
        "config_sha256": "b" * 64,
        "risk_policy_sha256": "c" * 64,
        "evidence_sha256": "d" * 64,
        "plugin_bundle_sha256": "e" * 64,
        "effective_session": "2026-08-27",
    }


def _order(*, quantity: float = 3.0) -> OrderIntent:
    return OrderIntent(
        symbol="SOXL",
        side="sell",
        quantity=quantity,
        order_type="market",
        account_id="paper-account",
    )


def _command(order: OrderIntent, *, digest: str | None = None) -> ExecutionCommand:
    release = _release()
    return ExecutionCommand.from_decision(
        platform="schwab",
        account_scope="paper-account-scope",
        strategy_profile="soxl_soxx_trend_income",
        execution_mode="paper",
        signal_date="2026-08-26",
        effective_date="2026-08-27",
        execution_timing_contract="next_trading_day",
        decision_digest="sha256:soxl-reduce",
        intent={
            "strategy_release": release,
            REDUCE_ONLY_ORDER_DIGEST_FIELD: digest or build_reduce_only_order_digest(order),
        },
        created_at="2026-08-26T20:00:00+00:00",
    )


def _evaluate(order: OrderIntent, **overrides):
    release = _release()
    payload = {
        "order": order,
        "long_quantities": {"SOXL": 10.0},
        "short_quantities": {"SOXL": 0.0},
        "sellable_quantities": {"SOXL": 8.0},
        "allowed_symbols": ("SOXL",),
        "command": _command(order),
        "as_of_session": "2026-08-27",
        "runtime_release_receipt": build_runtime_loaded_receipt(strategy_release=release),
        "expected_strategy_release": release,
        **overrides,
    }
    return evaluate_reduce_only_command_admission(**payload)


def test_matching_command_and_reconciliation_admit_reduction() -> None:
    result = _evaluate(_order())

    assert result.approved is True
    assert result.runtime_command_gate.mode.value == "reducing"
    assert result.to_safe_dict()["approved"] is True


def test_command_cannot_be_replayed_with_another_quantity() -> None:
    approved_order = _order(quantity=3.0)
    result = _evaluate(_order(quantity=2.0), command=_command(approved_order))

    assert result.approved is False
    assert ReduceOnlyCommandFinding.COMMAND_ORDER_BINDING_MISMATCH in result.findings


def test_missing_reconciliation_or_command_fails_closed() -> None:
    result = _evaluate(
        _order(),
        command=None,
        sellable_quantities={},
    )

    assert result.approved is False
    assert ReduceOnlyCommandFinding.COMMAND_ORDER_BINDING_MISSING in result.findings
    assert "sellable_quantity_unavailable" in result.findings


def test_command_release_mismatch_fails_closed() -> None:
    command = _command(_order())
    mismatched = ExecutionCommand.from_decision(
        platform=command.platform,
        account_scope=command.account_scope,
        strategy_profile=command.strategy_profile,
        execution_mode=command.execution_mode,
        signal_date=command.signal_date,
        effective_date=command.effective_date,
        execution_timing_contract=command.execution_timing_contract,
        decision_digest=command.decision_digest,
        intent={
            "strategy_release": {**_release(), "release_id": "different-release"},
            REDUCE_ONLY_ORDER_DIGEST_FIELD: build_reduce_only_order_digest(_order()),
        },
        created_at=command.created_at,
    )

    result = _evaluate(_order(), command=mismatched)

    assert result.approved is False
    assert "release_identity_mismatch" in result.findings
