from __future__ import annotations

import json
import tempfile
import threading
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from quant_platform_kit.common.execution_commands import (
    ExecutionCommand,
    ExecutionCommandRecoveryEntry,
    ExecutionCommandState,
    ExecutionCommandStore,
    build_recovery_report,
    validate_execution_command_release_binding,
    validate_execution_command_transition,
)


def _command(
    *, effective_date: str = "2026-08-25", decision_digest: str = "sha256:decision-v1"
) -> ExecutionCommand:
    return ExecutionCommand.from_decision(
        platform="longbridge",
        account_scope="SG",
        strategy_profile="soxl_soxx_trend_income",
        execution_mode="live",
        signal_date="2026-08-24",
        effective_date=effective_date,
        execution_timing_contract="next_trading_day",
        decision_digest=decision_digest,
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

    def test_next_trading_day_command_cannot_be_claimed_on_signal_friday(self) -> None:
        """A Friday decision stays queued until its explicit Monday session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExecutionCommandStore(local_dir=tmpdir)
            command = ExecutionCommand.from_decision(
                platform="longbridge",
                account_scope="SG",
                strategy_profile="soxl_soxx_trend_income",
                execution_mode="paper",
                signal_date="2026-08-28",  # Friday
                effective_date="2026-08-31",  # Monday
                execution_timing_contract="next_trading_day",
                decision_digest="sha256:friday-to-monday",
                intent={"targets": {"SOXL": 0.0, "SOXX": 0.70}},
                created_at="2026-08-28T20:00:00+00:00",
            )

            self.assertTrue(store.enqueue(command))
            self.assertEqual(store.list_due("2026-08-28"), ())
            self.assertIsNone(store.claim_due(command, as_of_date="2026-08-28", claimant="friday-run"))
            self.assertEqual(store.current_state(command), ExecutionCommandState.QUEUED)

            self.assertEqual(store.list_due("2026-08-31"), (command,))
            self.assertIsNotNone(store.claim_due(command, as_of_date="2026-08-31", claimant="monday-run"))
            self.assertEqual(store.current_state(command), ExecutionCommandState.CLAIMED)

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

    def test_recovery_report_includes_reconciliation_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExecutionCommandStore(local_dir=tmpdir)
            command = _command()
            store.enqueue(command)
            store.claim_due(command, as_of_date=command.effective_date, claimant="consumer")
            store.append_event(command, next_state=ExecutionCommandState.RECONCILIATION_REQUIRED)

            restarted = ExecutionCommandStore(local_dir=tmpdir)
            self.assertEqual(restarted.list_unresolved(), (command,))
            report = build_recovery_report(restarted, as_of_date="2026-08-26")
            self.assertEqual(
                report,
                (ExecutionCommandRecoveryEntry(command.command_id, "2026-08-25", "reconciliation_required", 1),),
            )
            with self.assertRaises(FrozenInstanceError):
                report[0].age_days = 2

    def test_recovery_filters_only_terminal_states(self) -> None:
        for state in ExecutionCommandState:
            with self.subTest(state=state), tempfile.TemporaryDirectory() as tmpdir:
                store = ExecutionCommandStore(local_dir=tmpdir)
                command = _command()
                store.enqueue(command)
                if state != ExecutionCommandState.QUEUED:
                    store.claim_due(command, as_of_date=command.effective_date, claimant="consumer")
                if state in {
                    ExecutionCommandState.SUBMITTED,
                    ExecutionCommandState.ACCEPTED,
                    ExecutionCommandState.PARTIALLY_FILLED,
                    ExecutionCommandState.FILLED,
                }:
                    store.append_event(command, next_state=ExecutionCommandState.SUBMITTED)
                if state in {
                    ExecutionCommandState.ACCEPTED,
                    ExecutionCommandState.PARTIALLY_FILLED,
                    ExecutionCommandState.FILLED,
                }:
                    store.append_event(command, next_state=state)
                elif state in {
                    ExecutionCommandState.CANCELLED,
                    ExecutionCommandState.REJECTED,
                    ExecutionCommandState.RECONCILIATION_REQUIRED,
                }:
                    store.append_event(command, next_state=state)

                self.assertEqual(store.current_state(command), state)
                terminal = state in {
                    ExecutionCommandState.FILLED,
                    ExecutionCommandState.CANCELLED,
                    ExecutionCommandState.REJECTED,
                }
                self.assertEqual(store.list_unresolved(), () if terminal else (command,))
                expected = () if terminal else (
                    ExecutionCommandRecoveryEntry(command.command_id, command.effective_date, state.value, 1),
                )
                self.assertEqual(build_recovery_report(store, as_of_date="2026-08-26"), expected)

    def test_recovery_queries_leave_events_and_files_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExecutionCommandStore(local_dir=tmpdir)
            commands = (_command(), _command(decision_digest="sha256:queued"))
            for command in commands:
                store.enqueue(command)
            store.claim_due(commands[0], as_of_date="2026-08-25", claimant="consumer")
            store.append_event(commands[0], next_state=ExecutionCommandState.RECONCILIATION_REQUIRED)
            before_events = tuple(store.events(command) for command in commands)
            before_paths = set(Path(tmpdir).rglob("*"))
            before_files = {path: path.read_bytes() for path in before_paths if path.is_file()}

            store.list_unresolved()
            build_recovery_report(store, as_of_date="2026-08-26")

            self.assertEqual(tuple(store.events(command) for command in commands), before_events)
            self.assertEqual(set(Path(tmpdir).rglob("*")), before_paths)
            self.assertEqual({path: path.read_bytes() for path in before_files}, before_files)

    def test_recovery_queries_do_not_create_an_empty_store_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "absent"
            store = ExecutionCommandStore(local_dir=root)
            self.assertEqual(store.list_unresolved(), ())
            self.assertEqual(build_recovery_report(store, as_of_date="2026-08-26"), ())
            self.assertFalse(root.exists())

    def test_future_command_enters_recovery_on_effective_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExecutionCommandStore(local_dir=tmpdir)
            command = _command(effective_date="2026-08-27")
            store.enqueue(command)

            self.assertEqual(store.list_unresolved(), (command,))
            self.assertEqual(build_recovery_report(store, as_of_date="2026-08-26"), ())
            self.assertEqual(
                build_recovery_report(store, as_of_date="2026-08-27"),
                (ExecutionCommandRecoveryEntry(command.command_id, "2026-08-27", "queued", 0),),
            )

    def test_recovery_results_sort_by_date_then_command_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExecutionCommandStore(local_dir=tmpdir)
            commands = [
                _command(effective_date=effective_date, decision_digest=f"sha256:{label}")
                for effective_date in ("2026-08-27", "2026-08-25", "2026-08-26")
                for label in ("b", "a")
            ]
            for command in commands:
                store.enqueue(command)

            expected = tuple(sorted(commands, key=lambda command: (command.effective_date, command.command_id)))
            self.assertEqual(store.list_unresolved(), expected)
            self.assertEqual(
                build_recovery_report(store, as_of_date="2026-08-28"),
                tuple(
                    ExecutionCommandRecoveryEntry(
                        command.command_id, command.effective_date, "queued", 28 - int(command.effective_date[-2:])
                    )
                    for command in expected
                ),
            )

    def test_recovery_rejects_invalid_as_of_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExecutionCommandStore(local_dir=tmpdir)
            for invalid in ("", "not-a-date", "2026-02-30"):
                with self.subTest(as_of_date=invalid), self.assertRaisesRegex(ValueError, "as_of_date"):
                    build_recovery_report(store, as_of_date=invalid)

    def test_recovery_propagates_invalid_or_incomplete_event_history(self) -> None:
        for corruption in ("missing_sequence", "invalid_previous_state"):
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as tmpdir:
                store = ExecutionCommandStore(local_dir=tmpdir)
                command = _command()
                store.enqueue(command)
                store.claim_due(command, as_of_date=command.effective_date, claimant="consumer")
                store.append_event(command, next_state=ExecutionCommandState.CANCELLED)
                event_paths = sorted(Path(tmpdir).rglob("events/*.json"))
                if corruption == "missing_sequence":
                    event_paths[0].unlink()
                else:
                    event_paths[1].write_text(
                        event_paths[1].read_text().replace('"previous_state": "claimed"', '"previous_state": "queued"')
                    )

                with self.assertRaises(RuntimeError):
                    store.list_unresolved()
                with self.assertRaises(RuntimeError):
                    build_recovery_report(store, as_of_date="2026-08-26")

    def test_cloud_recovery_lists_version_root_and_reads_only_command_keys(self) -> None:
        class MemoryObjectStore:
            def __init__(self):
                self.objects = {}
                self.listed = []
                self.read = []

            def list(self, prefix):
                self.listed.append(prefix)
                return [key for key in reversed(self.objects) if key.startswith(prefix)]

            def read_text(self, key):
                self.read.append(key)
                return self.objects[key]

        backend = MemoryObjectStore()
        store = ExecutionCommandStore(
            cloud_prefix_uri="gs://bucket/root/", namespace="custom_commands", object_store=backend
        )
        version_root = "gs://bucket/root/custom_commands/execution_command.v1/"
        commands = (_command(), _command(effective_date="2026-08-26"))
        command_keys = []
        for command in commands:
            key = f"{version_root}{command.effective_date}/{command.command_id}/command.json"
            command_keys.append(key)
            backend.objects[key] = json.dumps(command.to_dict())
        backend.objects[f"{version_root}2026-08-25/unrelated/command.json.bak"] = "not JSON"
        backend.objects[f"{version_root}2026-08-25/unrelated/metadata.json"] = "not JSON"
        backend.objects[f"{version_root}command.json.bak"] = "not JSON"
        backend.objects["gs://bucket/root/custom_commands/execution_command.v2/2026-08-25/other/command.json"] = "not JSON"
        backend.objects["gs://bucket/root/other/execution_command.v1/2026-08-25/other/command.json"] = "not JSON"
        before_objects = dict(backend.objects)

        self.assertEqual(store.list_unresolved(), commands)
        self.assertEqual(backend.listed[0], version_root)
        self.assertEqual(
            build_recovery_report(store, as_of_date="2026-08-26"),
            (
                ExecutionCommandRecoveryEntry(commands[0].command_id, "2026-08-25", "queued", 1),
                ExecutionCommandRecoveryEntry(commands[1].command_id, "2026-08-26", "queued", 0),
            ),
        )
        self.assertEqual(set(backend.read), set(command_keys))
        self.assertEqual(backend.objects, before_objects)

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
