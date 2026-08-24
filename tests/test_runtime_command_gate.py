from __future__ import annotations

import unittest

from quant_platform_kit.common.execution_commands import ExecutionCommand, ExecutionCommandState
from quant_platform_kit.common.runtime_command_gate import (
    RUNTIME_COMMAND_GATE_RECEIPT_SCHEMA_VERSION,
    RuntimeCommandAction,
    RuntimeCommandExposureEffect,
    RuntimeCommandGateEnforcement,
    RuntimeCommandGateMode,
    RuntimeCommandGatePolicy,
    evaluate_runtime_command_gate,
)
from quant_platform_kit.common.strategy_release import build_runtime_loaded_receipt


def _release_identity(*, release_id: str = "soxl-p2-v3.20260824") -> dict[str, str]:
    return {
        "release_id": release_id,
        "manifest_sha256": "a" * 64,
        "strategy_revision": "soxl-p2-v3",
        "config_sha256": "b" * 64,
        "risk_policy_sha256": "c" * 64,
        "evidence_sha256": "d" * 64,
        "plugin_bundle_sha256": "e" * 64,
        "effective_session": "2026-08-25",
    }


def _command() -> ExecutionCommand:
    return ExecutionCommand.from_decision(
        platform="longbridge",
        account_scope="SG",
        strategy_profile="soxl_soxx_trend_income",
        execution_mode="paper",
        signal_date="2026-08-24",
        effective_date="2026-08-25",
        execution_timing_contract="next_trading_day",
        decision_digest="sha256:decision-v1",
        intent={"targets": {"SOXL": 0.0, "SOXX": 0.70}},
        created_at="2026-08-24T20:00:00+00:00",
    )


def _strict_policy() -> RuntimeCommandGatePolicy:
    return RuntimeCommandGatePolicy(enforcement=RuntimeCommandGateEnforcement.ENFORCE)


class RuntimeCommandGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.command = _command()
        self.release = _release_identity()
        self.receipt = build_runtime_loaded_receipt(
            strategy_release=self.release,
            loaded_at="2026-08-24T20:00:00Z",
        )

    def test_valid_due_command_with_matching_release_is_active(self) -> None:
        decision = evaluate_runtime_command_gate(
            action=RuntimeCommandAction.SUBMIT,
            exposure_effect=RuntimeCommandExposureEffect.INCREASES,
            command=self.command,
            as_of_session="2026-08-25",
            runtime_release_receipt=self.receipt,
            expected_strategy_release=self.release,
            policy=_strict_policy(),
        )

        self.assertEqual(decision.mode, RuntimeCommandGateMode.ACTIVE)
        self.assertTrue(decision.policy_allows)
        self.assertTrue(decision.broker_write_allowed)
        receipt = decision.to_receipt()
        self.assertEqual(receipt["schema_version"], RUNTIME_COMMAND_GATE_RECEIPT_SCHEMA_VERSION)
        self.assertNotIn("intent", receipt)

    def test_reducing_mode_denies_increase_but_allows_proven_reduction(self) -> None:
        common = {
            "action": "submit",
            "command": self.command,
            "as_of_session": "2026-08-25",
            "runtime_release_receipt": self.receipt,
            "expected_strategy_release": self.release,
            "integrity_findings": ("data_stale",),
            "policy": _strict_policy(),
        }
        increasing = evaluate_runtime_command_gate(
            exposure_effect="increases",
            **common,
        )
        reducing = evaluate_runtime_command_gate(
            exposure_effect="reduces",
            **common,
        )

        self.assertEqual(increasing.mode, RuntimeCommandGateMode.REDUCING)
        self.assertFalse(increasing.broker_write_allowed)
        self.assertIn("reducing_mode_requires_exposure_reduction", increasing.reasons)
        self.assertTrue(reducing.policy_allows)
        self.assertTrue(reducing.broker_write_allowed)

    def test_unreconciled_broker_outcome_halts_writes_but_keeps_cancel_and_query(self) -> None:
        common = {
            "command": self.command,
            "command_state": ExecutionCommandState.RECONCILIATION_REQUIRED,
            "policy": _strict_policy(),
        }
        submit = evaluate_runtime_command_gate(
            action="submit",
            exposure_effect="reduces",
            **common,
        )
        cancel = evaluate_runtime_command_gate(action="cancel", **common)
        query = evaluate_runtime_command_gate(action="query", **common)

        self.assertEqual(submit.mode, RuntimeCommandGateMode.HALTED)
        self.assertFalse(submit.broker_write_allowed)
        self.assertIn("broker_outcome_unknown", submit.reasons)
        self.assertTrue(cancel.broker_write_allowed)
        self.assertTrue(query.broker_write_allowed)

    def test_release_mismatch_is_observed_without_blocking_until_enforced(self) -> None:
        observed = evaluate_runtime_command_gate(
            action="submit",
            exposure_effect="increases",
            command=self.command,
            as_of_session="2026-08-25",
            runtime_release_receipt=self.receipt,
            expected_strategy_release=_release_identity(release_id="soxl-p2-v4.20260824"),
        )

        self.assertEqual(observed.mode, RuntimeCommandGateMode.HALTED)
        self.assertTrue(observed.would_block)
        self.assertTrue(observed.broker_write_allowed)
        self.assertIn("release_identity_mismatch", observed.reasons)
        self.assertTrue(observed.to_receipt()["would_block"])

    def test_late_command_and_unknown_exposure_cannot_pass_strict_gate(self) -> None:
        decision = evaluate_runtime_command_gate(
            action="modify",
            command=self.command,
            as_of_session="2026-08-26",
            runtime_release_receipt=self.receipt,
            expected_strategy_release=self.release,
            policy=_strict_policy(),
        )

        self.assertEqual(decision.mode, RuntimeCommandGateMode.HALTED)
        self.assertFalse(decision.broker_write_allowed)
        self.assertIn("signal_timing_invalid", decision.reasons)
        self.assertIn("exposure_effect_unknown", decision.reasons)

    def test_invalid_runtime_session_and_invalid_release_config_halt(self) -> None:
        decision = evaluate_runtime_command_gate(
            action="submit",
            exposure_effect="reduces",
            command=self.command,
            as_of_session="not-a-date",
            runtime_release_receipt=self.receipt,
            expected_strategy_release={"release_id": "incomplete"},
            policy=_strict_policy(),
        )

        self.assertEqual(decision.mode, RuntimeCommandGateMode.HALTED)
        self.assertFalse(decision.broker_write_allowed)
        self.assertIn("invalid_effective_session", decision.reasons)
        self.assertIn("release_identity_invalid", decision.reasons)

    def test_unknown_integrity_finding_is_fail_closed_to_halted(self) -> None:
        decision = evaluate_runtime_command_gate(
            action="submit",
            exposure_effect="increases",
            command=self.command,
            as_of_session="2026-08-25",
            runtime_release_receipt=self.receipt,
            expected_strategy_release=self.release,
            integrity_findings=("future_adapter_alarm",),
            policy=_strict_policy(),
        )

        self.assertEqual(decision.mode, RuntimeCommandGateMode.HALTED)
        self.assertFalse(decision.broker_write_allowed)
        self.assertIn("unknown_integrity_finding:future_adapter_alarm", decision.reasons)


if __name__ == "__main__":
    unittest.main()
