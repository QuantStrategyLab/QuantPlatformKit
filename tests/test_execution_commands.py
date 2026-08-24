from __future__ import annotations

import tempfile
import threading
import unittest

from quant_platform_kit.common.execution_commands import (
    ExecutionCommand,
    ExecutionCommandState,
    ExecutionCommandStore,
    validate_execution_command_release_binding,
    validate_execution_command_transition,
)


def _command() -> ExecutionCommand:
    return ExecutionCommand.from_decision(
        platform="longbridge",
        account_scope="SG",
        strategy_profile="soxl_soxx_trend_income",
        execution_mode="live",
        signal_date="2026-08-24",
        effective_date="2026-08-25",
        execution_timing_contract="next_trading_day",
        decision_digest="sha256:decision-v1",
        intent={"targets": {"SOXL": 0.0, "SOXX": 0.70}, "reason": "volatility_delever"},
        created_at="2026-08-24T20:00:00+00:00",
    )


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


class ExecutionCommandTests(unittest.TestCase):
    def test_command_identity_is_deterministic_and_content_addressed(self) -> None:
        command = _command()
        same = _command()
        changed = ExecutionCommand.from_decision(
            platform="longbridge",
            account_scope="SG",
            strategy_profile="soxl_soxx_trend_income",
            execution_mode="live",
            signal_date="2026-08-24",
            effective_date="2026-08-25",
            execution_timing_contract="next_trading_day",
            decision_digest="sha256:decision-v2",
            intent={"targets": {"SOXL": 0.70, "SOXX": 0.0}},
        )

        self.assertEqual(command.command_id, same.command_id)
        self.assertNotEqual(command.command_id, changed.command_id)
        self.assertEqual(command.intent["targets"]["SOXX"], 0.70)
        self.assertTrue(command.is_due_on("2026-08-25"))
        self.assertFalse(command.is_due_on("2026-08-26"))

    def test_command_release_binding_is_immutable_and_fail_closed(self) -> None:
        release = _release_identity()
        command = ExecutionCommand.from_decision(
            platform="longbridge",
            account_scope="SG",
            strategy_profile="soxl_soxx_trend_income",
            execution_mode="paper",
            signal_date="2026-08-24",
            effective_date="2026-08-25",
            execution_timing_contract="next_trading_day",
            decision_digest="sha256:decision-v1",
            intent={"targets": {"SOXL": 0.0}, "strategy_release": release},
        )

        valid = validate_execution_command_release_binding(
            command,
            expected_strategy_release=release,
        )
        missing = validate_execution_command_release_binding(
            _command(),
            expected_strategy_release=release,
        )

        self.assertTrue(valid.is_valid)
        self.assertEqual(valid.release_id, release["release_id"])
        self.assertEqual(missing.findings, ("release_identity_mismatch",))

    def test_enqueue_is_create_only_and_lists_due_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExecutionCommandStore(local_dir=tmpdir)
            command = _command()

            self.assertTrue(store.enqueue(command))
            self.assertFalse(store.enqueue(command))
            self.assertEqual(store.list_due("2026-08-25"), (command,))
            self.assertEqual(store.list_due("2026-08-26"), ())

    def test_due_claim_is_single_winner_and_crash_stays_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExecutionCommandStore(local_dir=tmpdir)
            command = _command()
            self.assertTrue(store.enqueue(command))
            barrier = threading.Barrier(8)
            results = []

            def claim(worker: str) -> None:
                barrier.wait()
                results.append(store.claim_due(command, as_of_date="2026-08-25", claimant=worker))

            threads = [threading.Thread(target=claim, args=(f"worker-{index}",)) for index in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            claimed = [result for result in results if result is not None]
            self.assertEqual(len(claimed), 1)
            self.assertEqual(store.current_state(command), ExecutionCommandState.CLAIMED)
            self.assertIsNone(store.claim_due(command, as_of_date="2026-08-25", claimant="retry"))
            self.assertIsNone(store.claim_due(command, as_of_date="2026-08-26", claimant="late-retry"))

    def test_broker_outcomes_are_distinct_and_terminal_states_cannot_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExecutionCommandStore(local_dir=tmpdir)
            command = _command()
            self.assertTrue(store.enqueue(command))
            self.assertIsNotNone(store.claim_due(command, as_of_date="2026-08-25", claimant="consumer-a"))
            self.assertIsNotNone(
                store.append_event(command, next_state=ExecutionCommandState.SUBMITTED, details={"attempt": 1})
            )
            self.assertIsNotNone(
                store.append_event(
                    command,
                    next_state=ExecutionCommandState.ACCEPTED,
                    details={"broker_order_id": "order-1"},
                )
            )
            self.assertIsNotNone(
                store.append_event(
                    command,
                    next_state=ExecutionCommandState.PARTIALLY_FILLED,
                    details={"broker_order_id": "order-1", "filled_quantity": 1},
                )
            )
            self.assertIsNotNone(
                store.append_event(
                    command,
                    next_state=ExecutionCommandState.FILLED,
                    details={"broker_order_id": "order-1", "filled_quantity": 2},
                )
            )

            self.assertEqual(store.current_state(command), ExecutionCommandState.FILLED)
            with self.assertRaises(ValueError):
                store.append_event(command, next_state=ExecutionCommandState.CANCELLED)

    def test_invalid_state_transition_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_execution_command_transition(ExecutionCommandState.QUEUED, ExecutionCommandState.FILLED)

    def test_cloud_backend_without_atomic_create_fails_closed(self) -> None:
        class BrokenCloudStore:
            def create_text(self, *_args, **_kwargs):
                raise OSError("cloud backend unavailable")

        store = ExecutionCommandStore(
            local_dir=None,
            cloud_prefix_uri="gs://bucket/execution-commands",
            object_store=BrokenCloudStore(),
        )

        with self.assertRaises(OSError):
            store.enqueue(_command())


if __name__ == "__main__":
    unittest.main()
