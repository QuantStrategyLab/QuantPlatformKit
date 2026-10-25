from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from quant_platform_kit.common.execution_state import (
    ExecutionMarkerStore,
    build_account_owner_marker_key,
    build_execution_marker_key,
    build_execution_marker_store_from_env,
    claim_account_owner,
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

    def test_live_modes_require_explicit_durable_backend(self) -> None:
        for mode in ("live", "real", "production", " LIVE "):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(
                    ValueError, "^EXECUTION_STATE_DURABLE_PATH_REQUIRED$",
                ):
                    build_execution_marker_store_from_env(
                        platform_env_prefix="SCHWAB",
                        env_reader=lambda name, default=None: default,
                        execution_mode=mode,
                    )

    def test_live_mode_from_env_requires_durable_backend(self) -> None:
        for mode in ("live", " LIVE "):
            env = {"SCHWAB_EXECUTION_MODE": mode}
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(
                    ValueError, "^EXECUTION_STATE_DURABLE_PATH_REQUIRED$",
                ):
                    build_execution_marker_store_from_env(
                        platform_env_prefix="SCHWAB", env_reader=env.get,
                    )

    def test_live_rejects_ephemeral_env_directory(self) -> None:
        for directory in ("/tmp", "/tmp/qsl", str(Path("/tmp").resolve() / "qsl")):
            env = {"SCHWAB_EXECUTION_STATE_DIR": directory}
            with self.subTest(directory=directory):
                with self.assertRaisesRegex(
                    ValueError, "^EXECUTION_STATE_DURABLE_PATH_REQUIRED$",
                ):
                    build_execution_marker_store_from_env(
                        platform_env_prefix="SCHWAB", env_reader=env.get,
                        execution_mode="live",
                    )

    def test_live_rejects_ephemeral_default_directory(self) -> None:
        with self.assertRaisesRegex(ValueError, "^EXECUTION_STATE_DURABLE_PATH_REQUIRED$"):
            build_execution_marker_store_from_env(
                platform_env_prefix="SCHWAB",
                env_reader=lambda name, default=None: default,
                execution_mode="live", default_local_dir="/tmp/qsl",
            )

    def test_live_rejects_system_temp_directory(self) -> None:
        with patch("tempfile.gettempdir", return_value="/var/tmp/qpk-g5"):
            for directory in ("/var/tmp/qpk-g5", "/var/tmp/qpk-g5/execution"):
                env = {"SCHWAB_EXECUTION_STATE_DIR": directory}
                with self.subTest(directory=directory):
                    with self.assertRaisesRegex(
                        ValueError, "^EXECUTION_STATE_DURABLE_PATH_REQUIRED$",
                    ):
                        build_execution_marker_store_from_env(
                            platform_env_prefix="SCHWAB", env_reader=env.get,
                            execution_mode="live",
                        )

    def test_live_rejects_symlink_to_ephemeral_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir) / "state"
            directory.symlink_to("/tmp/qsl", target_is_directory=True)
            env = {"SCHWAB_EXECUTION_STATE_DIR": str(directory)}
            with self.assertRaisesRegex(ValueError, "^EXECUTION_STATE_DURABLE_PATH_REQUIRED$"):
                build_execution_marker_store_from_env(
                    platform_env_prefix="SCHWAB", env_reader=env.get,
                    execution_mode="live",
                )

    def test_live_accepts_durable_env_directory(self) -> None:
        env = {"SCHWAB_EXECUTION_STATE_DIR": "/var/lib/qsl/execution"}
        store = build_execution_marker_store_from_env(
            platform_env_prefix="SCHWAB", env_reader=env.get, execution_mode="live",
        )
        self.assertEqual(store.local_dir, "/var/lib/qsl/execution")

    def test_live_accepts_durable_default_directory_with_blank_env(self) -> None:
        env = {"SCHWAB_EXECUTION_STATE_DIR": "  "}
        directory = Path("/var/lib/qsl/execution")
        store = build_execution_marker_store_from_env(
            platform_env_prefix="SCHWAB", env_reader=env.get,
            execution_mode="live", default_local_dir=directory,
        )
        self.assertEqual(store.local_dir, directory)

    def test_live_rejects_blank_directories_and_cloud_uri(self) -> None:
        env = {
            "SCHWAB_EXECUTION_STATE_DIR": "  ",
            "SCHWAB_EXECUTION_STATE_CLOUD_URI": "  ",
        }
        with self.assertRaisesRegex(ValueError, "^EXECUTION_STATE_DURABLE_PATH_REQUIRED$"):
            build_execution_marker_store_from_env(
                platform_env_prefix="SCHWAB", env_reader=env.get,
                execution_mode="live", default_local_dir="  ",
            )

    def test_live_accepts_cloud_uri_including_report_fallbacks(self) -> None:
        for key in (
            "SCHWAB_EXECUTION_STATE_CLOUD_URI", "SCHWAB_EXECUTION_STATE_GCS_URI",
            "QSL_EXECUTION_REPORT_CLOUD_URI", "QSL_EXECUTION_REPORT_GCS_URI",
            "EXECUTION_REPORT_CLOUD_URI", "EXECUTION_REPORT_GCS_URI",
        ):
            for uri in ("gs://bucket/execution", "s3://bucket/execution"):
                env = {key: uri}
                with self.subTest(key=key, uri=uri):
                    store = build_execution_marker_store_from_env(
                        platform_env_prefix="SCHWAB", env_reader=env.get,
                        execution_mode="live",
                    )
                    self.assertEqual(store.cloud_prefix_uri, uri)

    def test_live_expands_user_directory_before_ephemeral_check(self) -> None:
        env = {"SCHWAB_EXECUTION_STATE_DIR": "~/qsl-state"}
        with patch.dict(os.environ, {"HOME": "/tmp/qsl-home"}):
            with self.assertRaisesRegex(ValueError, "^EXECUTION_STATE_DURABLE_PATH_REQUIRED$"):
                build_execution_marker_store_from_env(
                    platform_env_prefix="SCHWAB", env_reader=env.get, execution_mode="live",
                )
        with patch.dict(os.environ, {"HOME": "/var/lib/qsl-home"}):
            store = build_execution_marker_store_from_env(
                platform_env_prefix="SCHWAB", env_reader=env.get, execution_mode="live",
            )
            self.assertEqual(store.local_dir, "~/qsl-state")

    def test_blank_explicit_cloud_uri_uses_report_fallback_for_validation(self) -> None:
        env = {
            "SCHWAB_EXECUTION_STATE_CLOUD_URI": "  ",
            "QSL_EXECUTION_REPORT_CLOUD_URI": "gs://bucket/execution",
        }
        store = build_execution_marker_store_from_env(
            platform_env_prefix="SCHWAB", env_reader=env.get, execution_mode="live",
        )
        self.assertEqual(store.cloud_prefix_uri, "  ")

    def test_empty_cloud_uris_do_not_satisfy_live(self) -> None:
        env = {
            "SCHWAB_EXECUTION_STATE_CLOUD_URI": "",
            "QSL_EXECUTION_REPORT_CLOUD_URI": "",
        }
        with self.assertRaisesRegex(ValueError, "^EXECUTION_STATE_DURABLE_PATH_REQUIRED$"):
            build_execution_marker_store_from_env(
                platform_env_prefix="SCHWAB", env_reader=env.get, execution_mode="live",
            )

    def test_live_rejects_before_constructing_store(self) -> None:
        with patch(
            "quant_platform_kit.common.execution_state.ExecutionMarkerStore",
        ) as store_class:
            with self.assertRaisesRegex(ValueError, "^EXECUTION_STATE_DURABLE_PATH_REQUIRED$"):
                build_execution_marker_store_from_env(
                    platform_env_prefix="SCHWAB",
                    env_reader=lambda name, default=None: default,
                    execution_mode="live",
                )
            store_class.assert_not_called()

    def test_non_live_modes_keep_default_directory(self) -> None:
        for mode in ("paper", "dry_run", "backtest", "", "unknown", None):
            with self.subTest(mode=mode):
                store = build_execution_marker_store_from_env(
                    platform_env_prefix="SCHWAB",
                    env_reader=lambda name, default=None: default,
                    execution_mode=mode,
                )
                self.assertEqual(store.local_dir, "/tmp/quant_execution_state")

    def test_no_mode_keeps_default_directory(self) -> None:
        store = build_execution_marker_store_from_env(
            platform_env_prefix="SCHWAB",
            env_reader=lambda name, default=None: default,
        )
        self.assertEqual(store.local_dir, "/tmp/quant_execution_state")

    def test_explicit_mode_overrides_environment(self) -> None:
        env = {"SCHWAB_EXECUTION_MODE": "live"}
        store = build_execution_marker_store_from_env(
            platform_env_prefix="SCHWAB", env_reader=env.get, execution_mode="paper",
        )
        self.assertEqual(store.local_dir, "/tmp/quant_execution_state")
        env["SCHWAB_EXECUTION_MODE"] = "paper"
        with self.assertRaisesRegex(ValueError, "^EXECUTION_STATE_DURABLE_PATH_REQUIRED$"):
            build_execution_marker_store_from_env(
                platform_env_prefix="SCHWAB", env_reader=env.get, execution_mode="live",
            )

    def test_blank_explicit_mode_falls_back_to_environment(self) -> None:
        env = {"SCHWAB_EXECUTION_MODE": "live"}
        with self.assertRaisesRegex(ValueError, "^EXECUTION_STATE_DURABLE_PATH_REQUIRED$"):
            build_execution_marker_store_from_env(
                platform_env_prefix="SCHWAB", env_reader=env.get, execution_mode="  ",
            )

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

    def test_build_account_owner_marker_key_excludes_strategy_profile(self) -> None:
        key = build_account_owner_marker_key(broker="schwab", account_id="acct-hash-1")
        self.assertEqual(key, "v1/account-owner/schwab/acct-hash-1")
        self.assertNotIn("strategy", key)

    def test_read_marker_returns_claim_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExecutionMarkerStore(local_dir=tmpdir, cloud_prefix_uri=None)
            key = "v1/account-owner/schwab/acct-1"
            self.assertIsNone(store.read_marker(key))
            self.assertTrue(store.claim_marker(key, metadata={"owner_id": "profile-a"}))
            payload = store.read_marker(key)
            assert payload is not None
            self.assertEqual(payload["metadata"]["owner_id"], "profile-a")
            self.assertEqual(payload["state"], "claimed")

    def test_claim_account_owner_allows_same_owner_and_rejects_other(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExecutionMarkerStore(local_dir=tmpdir, cloud_prefix_uri=None)
            first = claim_account_owner(
                store,
                broker="schwab",
                account_id="acct-hash-1",
                owner_id="global_etf_rotation",
                metadata={"platform": "schwab"},
            )
            self.assertTrue(first.allowed)
            self.assertFalse(first.contested)
            self.assertTrue(first.created)
            self.assertEqual(first.owner_id, "global_etf_rotation")

            same = claim_account_owner(
                store,
                broker="schwab",
                account_id="acct-hash-1",
                owner_id="global_etf_rotation",
            )
            self.assertTrue(same.allowed)
            self.assertFalse(same.contested)
            self.assertFalse(same.created)

            other = claim_account_owner(
                store,
                broker="schwab",
                account_id="acct-hash-1",
                owner_id="other_profile",
            )
            self.assertFalse(other.allowed)
            self.assertTrue(other.contested)
            self.assertEqual(other.owner_id, "global_etf_rotation")

            # Different physical account remains independent.
            other_account = claim_account_owner(
                store,
                broker="schwab",
                account_id="acct-hash-2",
                owner_id="other_profile",
            )
            self.assertTrue(other_account.allowed)
            self.assertTrue(other_account.created)


if __name__ == "__main__":
    unittest.main()


# Account submission journal tests use only local/fake ObjectStore, never brokers.
def _account_session(store, *, account="U00000001", broker="ibkr", intent="a" * 64,
                     owner="synthetic-owner", profile="synthetic-profile", release="b" * 64):
    from quant_platform_kit.common import execution_state
    return execution_state.AccountSubmissionSession(
        store, broker=broker, account_id=account, owner_id=owner,
        profile=profile, intent_id=intent, release_id=release,
    )


def _account_order(*, symbol="VOO", account="U00000001", quantity=5):
    from quant_platform_kit.common.models import OrderIntent
    return OrderIntent(symbol=symbol, side="buy", quantity=quantity, account_id=account)


def _account_report(status="Submitted", *, filled=0, price=0, order_id="synthetic-order"):
    from types import SimpleNamespace
    return SimpleNamespace(status=status, broker_order_id=order_id,
                           filled_quantity=filled, average_fill_price=price)


def test_account_journal_unknown_blocks_new_intent_after_reopen(tmp_path):
    import pytest
    store = ExecutionMarkerStore(local_dir=tmp_path)
    session = _account_session(store)
    order = _account_order()
    grant = session.reserve(order)
    session.dispatch(grant, order, lambda: _account_report("Unknown", filled=1, price=50))
    reopened = _account_session(ExecutionMarkerStore(local_dir=tmp_path), intent="c" * 64,
                                owner="another-owner", profile="another-profile")
    with pytest.raises(RuntimeError, match="unresolved|uncertain|UNKNOWN"):
        reopened.reserve(_account_order(symbol="QQQM"))
    assert next(iter(reopened.read_state()["attempts"].values()))["filled_quantity"] == 1


class _JournalObjects:
    """Memory ObjectStore with explicit response-loss/read fault controls."""
    def __init__(self):
        self.data = {}
        self.lock = threading.Lock()
        self.list_transform = lambda uris: uris
        self.lose_kind = None
        self.lose_mode = "raise"
        self.fail_read = False
        self.before_write = False

    def list(self, prefix):
        return self.list_transform(sorted(k for k in self.data if k.startswith(prefix)))

    def read_text(self, uri):
        if self.fail_read:
            raise OSError("synthetic read unavailable")
        return self.data[uri]

    def create_text(self, uri, text, _content_type):
        kind = json.loads(text)["kind"]
        if kind == self.lose_kind and self.before_write:
            raise OSError("synthetic write unavailable before commit")
        with self.lock:
            if uri in self.data:
                return False
            self.data[uri] = text
        if kind == self.lose_kind:
            if self.lose_mode == "false":
                return False
            raise OSError("synthetic response lost after commit")
        return True


class _JournalStore(ExecutionMarkerStore):
    def __init__(self, objects):
        super().__init__(local_dir=None, cloud_prefix_uri="gs://synthetic-bucket/existing-prefix")
        object.__setattr__(self, "objects", objects)

    def _object_store(self):
        return self.objects


def test_account_journal_normal_ack_partial_and_terminal_remain_usable(tmp_path):
    import pytest
    store = ExecutionMarkerStore(local_dir=tmp_path)
    session = _account_session(store)
    for symbol, report in [
        ("VOO", _account_report()),
        ("QQQM", _account_report("PartiallyFilled", filled=2, price=50, order_id="partial")),
        ("TQQQ", _account_report("Filled", filled=5, price=51, order_id="filled")),
        ("BIL", _account_report("Rejected", order_id=None)),
    ]:
        order = _account_order(symbol=symbol)
        grant = session.reserve(order)
        assert session.dispatch(grant, order, lambda: report) is report
        before = session.read_state()["generation"]
        assert session.record_observation(grant, report) is False
        assert session.read_state()["generation"] == before
        with pytest.raises(RuntimeError):
            session.dispatch(grant, order, lambda: pytest.fail("duplicate submit"))
        with pytest.raises(RuntimeError, match="same intent"):
            _account_session(store).reserve(order)
    states = {a["certainty"] for a in session.read_state()["attempts"].values()}
    assert states == {"KNOWN_PENDING", "TERMINAL"}


def test_account_journal_scope_aliases_owner_profile_and_broker(tmp_path):
    import pytest
    store = ExecutionMarkerStore(local_dir=tmp_path)
    old = _account_session(store)
    order = _account_order()
    old.dispatch(old.reserve(order), order, lambda: _account_report("Unknown"))
    for kwargs in [dict(account="u00000001"), dict(owner="different"), dict(profile="different"), dict(intent="c"*64)]:
        session = _account_session(store, **kwargs)
        assert session.account_root == old.account_root
        with pytest.raises(RuntimeError, match="unresolved"):
            session.reserve(order)
    for kwargs in [dict(account="U00000002"), dict(broker="other")]:
        session = _account_session(store, **kwargs)
        assert session.account_root != old.account_root
        assert session.reserve(_account_order(account=session.account_id))
    for account in ["", "LIVE", "group-a", " U00000001", "U/00000001", "U_00000001"]:
        with pytest.raises(RuntimeError):
            _account_session(store, account=account)


def test_account_journal_no_later_observation_clears_unknown(tmp_path):
    import pytest
    s = _account_session(ExecutionMarkerStore(local_dir=tmp_path))
    o = _account_order()
    g = s.reserve(o)
    s.dispatch(g, o, lambda: _account_report("Unknown", filled=1, price=50))
    for report in [_account_report(), _account_report("PartiallyFilled", filled=2, price=50),
                   _account_report("Filled", filled=5, price=50), _account_report("Cancelled")]:
        with pytest.raises(RuntimeError, match="historical"):
            s.record_observation(g, report)
    assert next(iter(s.read_state()["attempts"].values()))["certainty"] == "UNKNOWN"
    assert not any(hasattr(s, name) for name in ["reset", "clear", "remove", "resolve", "expire"])


def test_account_journal_old_wrong_or_reopened_grant_is_not_dispatch_permission(tmp_path):
    import pytest
    from dataclasses import replace
    store = ExecutionMarkerStore(local_dir=tmp_path)
    s = _account_session(store)
    o = _account_order()
    g = s.reserve(o)
    for wrong in [replace(g), replace(g, fence="f"*64), replace(g, release_id="f"*64)]:
        with pytest.raises(RuntimeError):
            s.dispatch(wrong, o, lambda: pytest.fail("wrong grant submitted"))
    with pytest.raises(RuntimeError):
        _account_session(store).dispatch(g, o, lambda: pytest.fail("reopened grant submitted"))
    with pytest.raises(RuntimeError):
        s.dispatch(g, _account_order(symbol="QQQM"), lambda: pytest.fail("wrong order submitted"))
    s.dispatch(g, o, lambda: _account_report())
    with pytest.raises(RuntimeError):
        s.dispatch(g, o, lambda: pytest.fail("used grant submitted"))


def test_account_journal_paused_original_worker_has_only_unrevoked_once_grant(tmp_path):
    import pytest
    store = ExecutionMarkerStore(local_dir=tmp_path)
    s = _account_session(store)
    o = _account_order()
    g = s.reserve(o)
    ready, resume = threading.Event(), threading.Event()
    submitted = []

    def worker():
        ready.set()
        assert resume.wait(5)
        s.dispatch(g, o, lambda: submitted.append("venue") or _account_report())

    thread = threading.Thread(target=worker)
    thread.start()
    assert ready.wait(5)
    try:
        with pytest.raises(RuntimeError, match="unresolved"):
            _account_session(store, intent="c"*64).reserve(_account_order(symbol="QQQM"))
        assert submitted == []
    finally:
        resume.set()
        thread.join(5)
    assert not thread.is_alive()
    assert submitted == ["venue"]
    with pytest.raises(RuntimeError):
        s.dispatch(g, o, lambda: submitted.append("duplicate"))
    assert submitted == ["venue"]


def test_account_journal_concurrent_same_intent_create_has_one_grant():
    from concurrent.futures import ThreadPoolExecutor
    objects = _JournalObjects()
    barrier = threading.Barrier(2)

    def reserve(_):
        session = _account_session(_JournalStore(objects))
        barrier.wait(5)
        try:
            return session.reserve(_account_order())
        except RuntimeError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        grants = list(pool.map(reserve, range(2)))
    assert sum(g is not None for g in grants) == 1
    assert len(objects.data) == 1


def test_account_journal_response_lost_never_reissues_grant():
    import pytest
    for kind in ["PREPARED", "OBSERVED"]:
        for mode in ["raise", "false"]:
            objects = _JournalObjects()
            objects.lose_kind, objects.lose_mode = kind, mode
            s = _account_session(_JournalStore(objects))
            submitted = []
            with pytest.raises((OSError, RuntimeError)):
                g = s.reserve(_account_order())
                s.dispatch(g, _account_order(), lambda: submitted.append("once") or _account_report())
            assert submitted == ([] if kind == "PREPARED" else ["once"])
            objects.lose_kind = None
            with pytest.raises(RuntimeError):
                s.reserve(_account_order(symbol="QQQM"))
            reopened = _account_session(_JournalStore(objects))
            with pytest.raises(RuntimeError):
                reopened.reserve(_account_order())
            certainty = next(iter(reopened.read_state()["attempts"].values()))["certainty"]
            assert certainty == ("PREPARED" if kind == "PREPARED" else "KNOWN_PENDING")
            # A committed ACK is a known durable observation for a NEW intent,
            # never permission to replay this failed call or original intent.
            if kind == "OBSERVED":
                assert _account_session(_JournalStore(objects), intent="c"*64).reserve(_account_order(symbol="QQQM"))


def test_account_journal_write_before_commit_and_confirmation_failures():
    import pytest
    for kind in ["PREPARED", "OBSERVED"]:
        objects = _JournalObjects()
        objects.lose_kind, objects.before_write = kind, True
        s = _account_session(_JournalStore(objects))
        calls = []
        with pytest.raises(OSError):
            g = s.reserve(_account_order())
            s.dispatch(g, _account_order(), lambda: calls.append(1) or _account_report())
        assert len(calls) == (0 if kind == "PREPARED" else 1)
        if kind == "OBSERVED":
            objects.lose_kind = None
            with pytest.raises(RuntimeError, match="unresolved"):
                _account_session(_JournalStore(objects), intent="c"*64).reserve(_account_order(symbol="QQQM"))
    objects = _JournalObjects()
    original = objects.create_text

    def commit_without_readback(uri, text, content_type):
        created = original(uri, text, content_type)
        objects.fail_read = True
        return created

    objects.create_text = commit_without_readback
    with pytest.raises(OSError):
        _account_session(_JournalStore(objects)).reserve(_account_order())
    assert len(objects.data) == 1


def test_account_journal_incomplete_stale_duplicate_and_corrupt_sources():
    import pytest
    for fault in ["old-prefix", "missing-tail", "missing-middle", "duplicate", "wrong-root", "schema", "hash", "unknown-event"]:
        objects = _JournalObjects()
        s = _account_session(_JournalStore(objects))
        o = _account_order()
        s.dispatch(s.reserve(o), o, lambda: _account_report())
        _account_session(_JournalStore(objects), intent="c"*64).reserve(_account_order(symbol="QQQM"))
        before = len(objects.data)
        if fault == "old-prefix":
            objects.list_transform = lambda xs: xs[:2]  # stale healthy prefix, occupied next slot
        elif fault == "missing-tail":
            objects.list_transform = lambda xs: xs[:1]
        elif fault == "missing-middle":
            objects.list_transform = lambda xs: xs[1:]
        elif fault == "duplicate":
            objects.list_transform = lambda xs: xs + xs[:1]
        else:
            uri = sorted(objects.data)[0]
            event = json.loads(objects.data[uri])
            if fault == "wrong-root":
                event["account_root"] = "v1/" + "f"*64
            elif fault == "schema":
                event["schema_version"] = "future.v2"
            elif fault == "hash":
                event["data"]["quantity"] = 4
            else:
                event["kind"] = "CLEAR"
            if fault != "hash":
                event["event_sha256"] = s._event_hash(event)
            objects.data[uri] = json.dumps(event)
        with pytest.raises(RuntimeError):
            _account_session(_JournalStore(objects), intent="d"*64).reserve(_account_order(symbol="TQQQ"))
        assert len(objects.data) == before


def test_account_journal_fills_monotonic_and_unknown_facts_not_erased(tmp_path):
    import pytest
    s = _account_session(ExecutionMarkerStore(local_dir=tmp_path))
    o = _account_order()
    g = s.reserve(o)
    s.dispatch(g, o, lambda: _account_report("PartiallyFilled", filled=1, price=50))
    assert s.record_observation(g, _account_report("PartiallyFilled", filled=2, price=51)) is True
    with pytest.raises(RuntimeError, match="non-monotonic"):
        s.record_observation(g, _account_report("PartiallyFilled", filled=1, price=50))
    state = s.read_state()["attempts"][g.attempt_id]
    assert state["certainty"] == "UNKNOWN"
    assert state["filled_quantity"] == 2
    with pytest.raises(RuntimeError):
        s.reserve(_account_order(symbol="QQQM"))


def test_account_journal_transport_and_malformed_known_result_stop(tmp_path):
    import pytest
    for index, result in enumerate([TimeoutError("synthetic after placeOrder"),
                                    _account_report("Filled", filled=0),
                                    _account_report("Submitted", order_id=None)]):
        s = _account_session(ExecutionMarkerStore(local_dir=tmp_path / str(index)))
        o = _account_order()
        g = s.reserve(o)
        calls = []

        def submit():
            calls.append(1)
            if isinstance(result, Exception):
                raise result
            return result

        with pytest.raises((RuntimeError, TimeoutError)):
            s.dispatch(g, o, submit)
        assert calls == [1]
        assert s.read_state()["attempts"][g.attempt_id]["certainty"] == "UNKNOWN"


def test_account_journal_confirmation_of_different_payload_never_grants():
    import pytest
    objects = _JournalObjects()
    original = objects.create_text

    def wrong_confirmed_payload(uri, text, content_type):
        event = json.loads(text)
        event["data"]["fence"] = "f"*64
        event["event_sha256"] = _account_session(_JournalStore(objects))._event_hash(event)
        return original(uri, json.dumps(event), content_type)

    objects.create_text = wrong_confirmed_payload
    with pytest.raises(RuntimeError, match="confirmation"):
        _account_session(_JournalStore(objects)).reserve(_account_order())
    assert len(objects.data) == 1


def test_account_journal_bindings_immutable_release_time_not_identity(tmp_path):
    import pytest
    from dataclasses import FrozenInstanceError
    from quant_platform_kit.common.execution_state import submission_release_digest
    receipt = {"attestation_state": "self_attested", "release_id": "synthetic-release",
               "strategy_release": {"strategy_revision": "a"*40}, "loaded_at": "one"}
    assert submission_release_digest(receipt) == submission_release_digest({**receipt, "loaded_at": "two"})
    assert submission_release_digest(receipt) != submission_release_digest({**receipt, "release_id": "different"})
    with pytest.raises(RuntimeError):
        submission_release_digest({"attestation_state": "legacy_unattested"})
    session = _account_session(ExecutionMarkerStore(local_dir=tmp_path))
    with pytest.raises(FrozenInstanceError):
        session.account_root = "v1/" + "f"*64
    assert not list(tmp_path.rglob("*.json"))


def test_account_journal_invalid_order_and_read_failure_never_register(tmp_path):
    import pytest
    for quantity in [0, -1, float("nan"), float("inf")]:
        session = _account_session(ExecutionMarkerStore(local_dir=tmp_path))
        with pytest.raises(RuntimeError):
            session.reserve(_account_order(quantity=quantity))
    assert not list(tmp_path.rglob("*.json"))
    objects = _JournalObjects()
    session = _account_session(_JournalStore(objects))
    objects.list = lambda _prefix: (_ for _ in ()).throw(OSError("synthetic listing unavailable"))
    with pytest.raises(OSError):
        session.reserve(_account_order())
    assert objects.data == {}


def test_account_journal_empty_unknown_and_pending_cancel_keep_obligations(tmp_path):
    import pytest
    from types import SimpleNamespace
    for index, report in enumerate([None, SimpleNamespace(), _account_report("PendingCancel", filled=1, price=50),
                                    _account_report("Inactive"), _account_report("unrecognized")]):
        store = ExecutionMarkerStore(local_dir=tmp_path / str(index))
        session = _account_session(store)
        order = _account_order()
        session.dispatch(session.reserve(order), order, lambda: report)
        state = _account_session(store, intent="c"*64).read_state()
        assert {a["certainty"] for a in state["attempts"].values()} == {"UNKNOWN"}
        with pytest.raises(RuntimeError, match="unresolved"):
            _account_session(store, intent="d"*64).reserve(_account_order(symbol="QQQM"))
