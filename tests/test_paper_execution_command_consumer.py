from __future__ import annotations

from pathlib import Path

from quant_platform_kit.common.execution_commands import (
    ExecutionCommand,
    ExecutionCommandState,
    ExecutionCommandStore,
)
from quant_platform_kit.common.paper_execution_admission import (
    PaperRiskAdmissionDisposition,
    build_paper_risk_admission_receipt,
)
from quant_platform_kit.common.paper_execution_command_consumer import (
    PAPER_EXECUTION_COMMAND_CONSUMER_SCHEMA_VERSION,
    PaperExecutionProposal,
    PaperExecutionReconciliation,
    consume_due_paper_execution_commands,
)
from quant_platform_kit.common.runtime_command_gate import RuntimeCommandExposureEffect
from quant_platform_kit.common.strategy_release import build_runtime_loaded_receipt


def _release_identity() -> dict[str, str]:
    return {
        "release_id": "soxl-p2-v3.20260824",
        "manifest_sha256": "a" * 64,
        "strategy_revision": "soxl-p2-v3",
        "config_sha256": "b" * 64,
        "risk_policy_sha256": "c" * 64,
        "evidence_sha256": "d" * 64,
        "plugin_bundle_sha256": "e" * 64,
        "effective_session": "2026-08-25",
    }


def _command(
    *,
    disposition: PaperRiskAdmissionDisposition = PaperRiskAdmissionDisposition.ALLOW_NEW_RISK,
    reason_codes: tuple[str, ...] = (),
) -> ExecutionCommand:
    release = _release_identity()
    receipt = build_paper_risk_admission_receipt(
        strategy_profile="soxl_soxx_trend_income",
        release_id=release["release_id"],
        risk_policy_sha256=release["risk_policy_sha256"],
        decision_digest="d" * 64,
        effective_session="2026-08-25",
        disposition=disposition,
        reason_codes=reason_codes,
    )
    return ExecutionCommand.from_decision(
        platform="longbridge",
        account_scope="paper-sg",
        strategy_profile="soxl_soxx_trend_income",
        execution_mode="paper",
        signal_date="2026-08-24",
        effective_date="2026-08-25",
        execution_timing_contract="next_trading_day",
        decision_digest="d" * 64,
        intent={
            "strategy_release": release,
            "paper_risk_admission_receipt": receipt.to_dict(),
            "platform_order_shape": {"intentionally": "platform-owned"},
        },
        created_at="2026-08-24T20:00:00+00:00",
    )


def _runtime_receipt() -> dict[str, object]:
    return build_runtime_loaded_receipt(strategy_release=_release_identity())


def _binding() -> dict[str, str]:
    return {
        "platform": "longbridge",
        "account_scope": "paper-sg",
        "strategy_profile": "soxl_soxx_trend_income",
    }


def _increasing_reconciliation(_: ExecutionCommand) -> PaperExecutionReconciliation:
    return PaperExecutionReconciliation(
        proposals=(
            PaperExecutionProposal(
                symbol="SOXL",
                exposure_effect=RuntimeCommandExposureEffect.INCREASES,
                details={"side": "buy", "quantity": 1.0, "reference_price": 10.0},
            ),
        )
    )


def test_consumer_persists_a_paper_only_lifecycle_for_reconciled_proposals(tmp_path: Path) -> None:
    store = ExecutionCommandStore(local_dir=tmp_path)
    command = _command()
    assert store.enqueue(command)

    result = consume_due_paper_execution_commands(
        store=store,
        as_of_session="2026-08-25",
        claimant="paper-command-verify",
        reconcile_command=_increasing_reconciliation,
        runtime_release_receipt=_runtime_receipt(),
        expected_strategy_release=_release_identity(),
        expected_command_binding=_binding(),
    )

    assert result == {
        "schema_version": PAPER_EXECUTION_COMMAND_CONSUMER_SCHEMA_VERSION,
        "status": "ok",
        "as_of_session": "2026-08-25",
        "commands": [
            {
                "command_id": command.command_id,
                "status": "filled",
                "proposals_count": 1,
                "would_block": False,
            }
        ],
    }
    assert store.current_state(command) is ExecutionCommandState.FILLED
    events = store.events(command)
    assert [event.state for event in events] == [
        ExecutionCommandState.CLAIMED,
        ExecutionCommandState.SUBMITTED,
        ExecutionCommandState.ACCEPTED,
        ExecutionCommandState.FILLED,
    ]
    submitted = events[1].details
    assert submitted["paper_simulation"] is True
    assert submitted["claimant"] == "paper-command-verify"
    assert submitted["proposals"] == [
        {
            "symbol": "SOXL",
            "exposure_effect": "increases",
            "details": {"side": "buy", "quantity": 1.0, "reference_price": 10.0},
        }
    ]
    assert submitted["runtime_command_gate_receipts"][0]["broker_write_allowed"] is True


def test_consumer_requires_runtime_release_before_claiming(tmp_path: Path) -> None:
    store = ExecutionCommandStore(local_dir=tmp_path)
    command = _command()
    assert store.enqueue(command)

    result = consume_due_paper_execution_commands(
        store=store,
        as_of_session="2026-08-25",
        claimant="paper-command-verify",
        reconcile_command=_increasing_reconciliation,
        runtime_release_receipt=None,
        expected_strategy_release=_release_identity(),
        expected_command_binding=_binding(),
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "release_receipt_missing"
    assert store.current_state(command) is ExecutionCommandState.QUEUED


def test_consumer_rejects_new_risk_when_admission_is_reducing_only(tmp_path: Path) -> None:
    store = ExecutionCommandStore(local_dir=tmp_path)
    command = _command(
        disposition=PaperRiskAdmissionDisposition.REDUCING_ONLY,
        reason_codes=("DAILY_LOSS_LIMIT_EXCEEDED",),
    )
    assert store.enqueue(command)

    result = consume_due_paper_execution_commands(
        store=store,
        as_of_session="2026-08-25",
        claimant="paper-command-verify",
        reconcile_command=_increasing_reconciliation,
        runtime_release_receipt=_runtime_receipt(),
        expected_strategy_release=_release_identity(),
        expected_command_binding=_binding(),
    )

    assert result["commands"][0]["status"] == "rejected"
    assert result["commands"][0]["would_block"] is True
    assert store.current_state(command) is ExecutionCommandState.REJECTED
    receipt = store.events(command)[-1].details["runtime_command_gate_receipts"][0]
    assert receipt["mode"] == "reducing"
    assert receipt["broker_write_allowed"] is False
    assert "paper_risk_admission_reducing_only" in receipt["reasons"]


def test_consumer_marks_unfinished_work_for_manual_reconciliation(tmp_path: Path) -> None:
    store = ExecutionCommandStore(local_dir=tmp_path)
    command = _command()
    assert store.enqueue(command)

    def _failing_reconciliation(_: ExecutionCommand) -> PaperExecutionReconciliation:
        raise RuntimeError("market snapshot unavailable")

    result = consume_due_paper_execution_commands(
        store=store,
        as_of_session="2026-08-25",
        claimant="paper-command-verify",
        reconcile_command=_failing_reconciliation,
        runtime_release_receipt=_runtime_receipt(),
        expected_strategy_release=_release_identity(),
        expected_command_binding=_binding(),
    )

    assert result["commands"] == [
        {
            "command_id": command.command_id,
            "status": "reconciliation_required",
            "error_type": "RuntimeError",
        }
    ]
    assert store.current_state(command) is ExecutionCommandState.RECONCILIATION_REQUIRED
    event = store.events(command)[-1]
    assert event.details["paper_simulation"] is True
    assert event.details["error_type"] == "RuntimeError"


def test_consumer_rejects_unknown_platform_integrity_findings(tmp_path: Path) -> None:
    store = ExecutionCommandStore(local_dir=tmp_path)
    command = _command()
    assert store.enqueue(command)

    def _unknown_finding(_: ExecutionCommand) -> PaperExecutionReconciliation:
        return PaperExecutionReconciliation(
            proposals=(),
            integrity_findings=("untrusted callback message",),
        )

    result = consume_due_paper_execution_commands(
        store=store,
        as_of_session="2026-08-25",
        claimant="paper-command-verify",
        reconcile_command=_unknown_finding,
        runtime_release_receipt=_runtime_receipt(),
        expected_strategy_release=_release_identity(),
        expected_command_binding=_binding(),
    )

    assert result["commands"][0]["status"] == "rejected"
    receipt = store.events(command)[-1].details["runtime_command_gate_receipts"][0]
    assert receipt["mode"] == "halted"
    assert receipt["reasons"] == ["unknown_integrity_finding"]


def test_consumer_rejects_a_command_for_another_platform_without_reconciling(tmp_path: Path) -> None:
    store = ExecutionCommandStore(local_dir=tmp_path)
    command = ExecutionCommand.from_decision(
        platform="schwab",
        account_scope="paper-sg",
        strategy_profile="soxl_soxx_trend_income",
        execution_mode="paper",
        signal_date="2026-08-24",
        effective_date="2026-08-25",
        execution_timing_contract="next_trading_day",
        decision_digest="d" * 64,
        intent=_command().intent,
        created_at="2026-08-24T20:00:00+00:00",
    )
    assert store.enqueue(command)
    reconciled = False

    def _must_not_reconcile(_: ExecutionCommand) -> PaperExecutionReconciliation:
        nonlocal reconciled
        reconciled = True
        return _increasing_reconciliation(command)

    result = consume_due_paper_execution_commands(
        store=store,
        as_of_session="2026-08-25",
        claimant="paper-command-verify",
        reconcile_command=_must_not_reconcile,
        runtime_release_receipt=_runtime_receipt(),
        expected_strategy_release=_release_identity(),
        expected_command_binding=_binding(),
    )

    assert reconciled is False
    assert result["commands"][0]["status"] == "rejected"
    receipt = store.events(command)[-1].details["runtime_command_gate_receipts"][0]
    assert receipt["mode"] == "halted"
    assert receipt["reasons"] == ["command_platform_mismatch"]


def test_consumer_blocks_before_claiming_when_runtime_binding_is_invalid(tmp_path: Path) -> None:
    store = ExecutionCommandStore(local_dir=tmp_path)
    command = _command()
    assert store.enqueue(command)

    result = consume_due_paper_execution_commands(
        store=store,
        as_of_session="2026-08-25",
        claimant="paper-command-verify",
        reconcile_command=_increasing_reconciliation,
        runtime_release_receipt=_runtime_receipt(),
        expected_strategy_release=_release_identity(),
        expected_command_binding={"platform": "longbridge"},
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "command_binding_invalid"
    assert store.current_state(command) is ExecutionCommandState.QUEUED
