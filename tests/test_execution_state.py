from __future__ import annotations

import tempfile
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
