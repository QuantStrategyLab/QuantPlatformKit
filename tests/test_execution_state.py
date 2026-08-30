from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path

from quant_platform_kit.common.execution_state import (
    ExecutionMarkerStore,
    build_execution_marker_key,
    build_execution_marker_store_from_env,
    resolve_execution_dedup_enabled,
)
from quant_platform_kit.common.runtime_config import resolve_dry_run_env


class ResolveDryRunEnvTests(unittest.TestCase):
    def test_defaults_to_dry_run_when_unset(self) -> None:
        self.assertTrue(resolve_dry_run_env({}, "SCHWAB_DRY_RUN_ONLY"))
        self.assertTrue(resolve_dry_run_env({"SCHWAB_DRY_RUN_ONLY": ""}, "SCHWAB_DRY_RUN_ONLY"))
        self.assertTrue(resolve_dry_run_env({"SCHWAB_DRY_RUN_ONLY": "  "}, "SCHWAB_DRY_RUN_ONLY"))

    def test_respects_explicit_false_and_true(self) -> None:
        self.assertFalse(resolve_dry_run_env({"SCHWAB_DRY_RUN_ONLY": "false"}, "SCHWAB_DRY_RUN_ONLY"))
        self.assertFalse(resolve_dry_run_env({"SCHWAB_DRY_RUN_ONLY": "0"}, "SCHWAB_DRY_RUN_ONLY"))
        self.assertTrue(resolve_dry_run_env({"SCHWAB_DRY_RUN_ONLY": "true"}, "SCHWAB_DRY_RUN_ONLY"))

    def test_custom_default(self) -> None:
        self.assertFalse(resolve_dry_run_env({}, "SCHWAB_DRY_RUN_ONLY", default=False))


class ExecutionStateTests(unittest.TestCase):
    def test_build_execution_marker_key(self) -> None:
        key = build_execution_marker_key(
            platform="schwab",
            strategy_profile="global_etf_rotation",
            account_scope="PAPER",
            execution_mode="paper",
            signal_date="2026-06-01",
            effective_date="2026-06-02",
            execution_timing_contract="t+1",
        )
        self.assertIn("schwab", key)
        self.assertIn("global_etf_rotation", key)
        self.assertIn("2026-06-01", key)

    def test_local_marker_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExecutionMarkerStore(local_dir=tmpdir, cloud_prefix_uri=None)
            key = build_execution_marker_key(
                platform="ibkr",
                strategy_profile="test",
                account_scope="PAPER",
                execution_mode="paper",
                signal_date="2026-06-01",
                effective_date="2026-06-02",
            )
            self.assertFalse(store.has_marker(key))
            store.record_marker(key, metadata={"dry_run_only": True})
            self.assertTrue(store.has_marker(key))
            marker_path = Path(tmpdir) / "execution_markers"
            self.assertTrue(any(marker_path.iterdir()))

    def test_local_claim_is_single_winner_under_concurrency(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExecutionMarkerStore(local_dir=tmpdir, cloud_prefix_uri=None)
            barrier = threading.Barrier(8)
            results: list[bool] = []

            def claim() -> None:
                barrier.wait()
                results.append(store.claim_marker("live/account/strategy/2026-08-24"))

            threads = [threading.Thread(target=claim) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(results.count(True), 1)
            self.assertEqual(results.count(False), 7)

    def test_recent_ledger_digest_is_redacted_stable_and_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExecutionMarkerStore(local_dir=tmpdir, cloud_prefix_uri=None)
            first_key = build_execution_marker_key(
                platform="ibkr",
                strategy_profile="soxl_soxx_trend_income",
                account_scope="LIVE",
                execution_mode="live",
                signal_date="2026-08-28",
                effective_date="2026-08-29",
            )
            second_key = build_execution_marker_key(
                platform="ibkr",
                strategy_profile="soxl_soxx_trend_income",
                account_scope="LIVE",
                execution_mode="live",
                signal_date="2026-08-29",
                effective_date="2026-08-30",
            )
            other_scope_key = build_execution_marker_key(
                platform="ibkr",
                strategy_profile="soxl_soxx_trend_income",
                account_scope="PAPER",
                execution_mode="paper",
                signal_date="2026-08-29",
                effective_date="2026-08-30",
            )
            store.record_marker(first_key, metadata={"order_id": "sensitive"})
            store.record_outcome(first_key, metadata={"status": "submitted"})
            store.record_marker(second_key, metadata={"order_id": "sensitive-2"})
            store.record_marker(other_scope_key, metadata={"order_id": "other"})

            digest, count = store.calculate_recent_ledger_digest(
                platform="ibkr",
                strategy_profile="soxl_soxx_trend_income",
                account_scope="LIVE",
                execution_mode="live",
            )
            repeated_digest, repeated_count = store.calculate_recent_ledger_digest(
                platform="ibkr",
                strategy_profile="soxl_soxx_trend_income",
                account_scope="LIVE",
                execution_mode="live",
            )

            self.assertEqual(count, 3)
            self.assertEqual((repeated_digest, repeated_count), (digest, count))
            self.assertEqual(len(digest), 64)
            self.assertNotIn("sensitive", digest)

    def test_recent_ledger_digest_uses_bounded_newest_records_per_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExecutionMarkerStore(local_dir=tmpdir, cloud_prefix_uri=None)
            for day in ("2026-08-27", "2026-08-28", "2026-08-29"):
                key = build_execution_marker_key(
                    platform="ibkr",
                    strategy_profile="soxl_soxx_trend_income",
                    account_scope="LIVE",
                    execution_mode="live",
                    signal_date=day,
                    effective_date=day,
                )
                store.record_marker(key)

            _digest, count = store.calculate_recent_ledger_digest(
                platform="ibkr",
                strategy_profile="soxl_soxx_trend_income",
                account_scope="LIVE",
                execution_mode="live",
                record_limit=2,
            )
            self.assertEqual(count, 2)

    def test_recent_ledger_digest_reads_only_scoped_cloud_prefixes(self) -> None:
        observed: list[str] = []

        class CloudStore:
            def list(self, prefix):
                observed.append(prefix)
                return [prefix + "2026-08-30/next.json"]

            def read_text(self, uri):
                return '{"metadata":{"broker_order":"private"}}'

        class CloudExecutionStore(ExecutionMarkerStore):
            def _object_store(self):
                return CloudStore()

        store = CloudExecutionStore(local_dir=None, cloud_prefix_uri="gs://bucket/runtime")
        digest, count = store.calculate_recent_ledger_digest(
            platform="ibkr",
            strategy_profile="soxl_soxx_trend_income",
            account_scope="LIVE",
            execution_mode="live",
        )

        self.assertEqual(count, 2)
        self.assertEqual(len(digest), 64)
        self.assertEqual(
            observed,
            [
                "gs://bucket/runtime/execution_markers/v1/ibkr/live/soxl_soxx_trend_income/live/",
                "gs://bucket/runtime/execution_outcomes/v1/ibkr/live/soxl_soxx_trend_income/live/",
            ],
        )

    def test_outcome_is_append_only_and_does_not_replace_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExecutionMarkerStore(local_dir=tmpdir, cloud_prefix_uri=None)
            key = "live/account/strategy/2026-08-24"

            self.assertTrue(store.claim_marker(key, metadata={"phase": "claimed"}))
            self.assertTrue(store.record_outcome(key, metadata={"phase": "completed"}))
            self.assertFalse(store.record_outcome(key, metadata={"phase": "replayed"}))

            claim = json.loads(store._local_path(key).read_text(encoding="utf-8"))
            outcome = json.loads(store._outcome_local_path(key).read_text(encoding="utf-8"))
            self.assertEqual(claim["schema_version"], "execution_claim.v1")
            self.assertEqual(claim["metadata"]["phase"], "claimed")
            self.assertEqual(outcome["schema_version"], "execution_outcome.v1")
            self.assertEqual(outcome["metadata"]["phase"], "completed")

    def test_cloud_outcome_uses_create_only_without_an_overwrite(self) -> None:
        observed: dict[str, object] = {}

        class CloudStore:
            def create_text(self, uri, payload, content_type):
                observed.setdefault("calls", []).append((uri, payload, content_type))
                return len(observed["calls"]) == 1

            def write_text(self, *_args, **_kwargs):
                raise AssertionError("outcome must never use an overwrite")

        class CloudExecutionStore(ExecutionMarkerStore):
            def _object_store(self):
                return CloudStore()

        store = CloudExecutionStore(local_dir=None, cloud_prefix_uri="gs://bucket/runtime")
        self.assertTrue(store.record_outcome("live/account/strategy", metadata={"action_done": True}))
        self.assertFalse(store.record_outcome("live/account/strategy", metadata={"action_done": True}))
        calls = observed["calls"]
        self.assertEqual(len(calls), 2)
        self.assertIn("/execution_outcomes/live/account/strategy.json", calls[0][0])

    def test_claim_backend_failure_is_not_treated_as_success(self) -> None:
        class BrokenStore:
            def create_text(self, *_args, **_kwargs):
                raise OSError("backend unavailable")

        class CloudExecutionStore(ExecutionMarkerStore):
            def _object_store(self):
                return BrokenStore()

        store = CloudExecutionStore(local_dir=None, cloud_prefix_uri="gs://bucket/claims")
        with self.assertRaises(OSError):
            store.claim_marker("live/account/strategy/2026-08-24")

    def test_claim_without_durable_backend_fails_closed(self) -> None:
        store = ExecutionMarkerStore(local_dir=None, cloud_prefix_uri=None)
        with self.assertRaises(RuntimeError):
            store.claim_marker("live/account/strategy/2026-08-24")

    def test_build_store_from_env(self) -> None:
        env = {
            "SCHWAB_EXECUTION_STATE_CLOUD_URI": "gs://bucket/reports",
            "SCHWAB_EXECUTION_STATE_DIR": "/tmp/schwab",
        }

        def reader(name: str, default: str | None = None) -> str | None:
            return env.get(name, default)

        store = build_execution_marker_store_from_env(
            platform_env_prefix="SCHWAB",
            env_reader=reader,
        )
        self.assertEqual(store.cloud_prefix_uri, "gs://bucket/reports")
        self.assertEqual(str(store.local_dir), "/tmp/schwab")

    def test_resolve_execution_dedup_enabled(self) -> None:
        def reader(name: str, default: str | None = None) -> str | None:
            values = {"SCHWAB_EXECUTION_DEDUP_ENABLED": "true"}
            return values.get(name, default)

        self.assertTrue(
            resolve_execution_dedup_enabled(
                platform_env_prefix="SCHWAB",
                env_reader=reader,
                dry_run_only=False,
                account_scope="LIVE",
            )
        )
        self.assertTrue(
            resolve_execution_dedup_enabled(
                platform_env_prefix="SCHWAB",
                env_reader=lambda _n, _d=None: None,
                dry_run_only=True,
                account_scope="LIVE",
            )
        )


if __name__ == "__main__":
    unittest.main()
