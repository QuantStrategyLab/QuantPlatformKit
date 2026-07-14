from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from quant_platform_kit.strategy_lifecycle.contracts import BacktestResult
from quant_platform_kit.strategy_lifecycle.backtest_orchestrator import BacktestOrchestrator
from quant_platform_kit.strategy_lifecycle.performance_store import (
    LEGACY_EXECUTION_TIMING,
    PerformanceStore,
)


def _result(*, timing: str | None, computed_at: str, profile: str = "SOXL") -> BacktestResult:
    return BacktestResult(
        strategy_profile=profile,
        domain="us_equity",
        param_set_id="baseline",
        params={"lookback": 20},
        execution_timing=timing,
        result_identity_version=2,
        persist_mode="durable",
        computed_at=computed_at,
        start_date=date(2020, 1, 1),
        end_date=date(2024, 1, 1),
    )


class BacktestResultStoreMigrationTests(unittest.TestCase):
    def test_old_positional_backtest_result_order_is_unchanged(self) -> None:
        result = BacktestResult("s", "d", "p", {}, 3, 1.1, 0.9, 0.8, -0.2, 0.1, 0.3, 0.5, 0.4)
        self.assertEqual(result.param_version, 3)
        self.assertEqual(result.sharpe_ratio, 1.1)
        self.assertEqual(result.total_return, 0.4)
        self.assertIsNone(result.execution_timing)

    def test_v1_record_without_metadata_remains_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            key = "backtest/us_equity/SOXL/backtest_v1_legacy.json"
            store._write(key, {"strategy_profile": "SOXL", "domain": "us_equity", "param_set_id": "legacy", "params": {}})
            loaded = store.load_latest_backtest("us_equity", "SOXL", execution_timing=LEGACY_EXECUTION_TIMING)
        self.assertIsNotNone(loaded)
        self.assertIsNone(loaded.execution_timing)
        self.assertEqual(loaded.result_identity_version, 1)
        self.assertEqual(loaded.persist_mode, "durable")

    def test_mixed_timing_records_have_distinct_keys_and_filters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_backtest_result(_result(timing="next_open", computed_at="2026-01-01T00:00:00+00:00"))
            store.save_backtest_result(_result(timing="next_close", computed_at="2026-01-01T00:00:00+00:00"))
            keys = store._list_local_json_keys("backtest/us_equity/SOXL/")
            latest = store.load_latest_backtest("us_equity", "SOXL")
            opened = store.load_latest_backtest("us_equity", "SOXL", execution_timing="next_open")
            closed = store.load_latest_backtest("us_equity", "SOXL", execution_timing="next_close")
        self.assertEqual(len(keys), 2)
        self.assertEqual(latest.execution_timing, "next_close")
        self.assertEqual(opened.execution_timing, "next_open")
        self.assertEqual(closed.execution_timing, "next_close")

    def test_reserved_looking_timing_does_not_collide_with_missing_timing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_backtest_result(_result(timing=None, computed_at="2026-01-01T00:00:00+00:00"))
            store.save_backtest_result(
                _result(timing="legacy_unknown", computed_at="2026-01-01T00:00:00+00:00")
            )
            keys = store._list_local_json_keys("backtest/us_equity/SOXL/")
        self.assertEqual(len(keys), 2)

    def test_save_records_write_revision_for_equal_logical_slots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_backtest_result(_result(timing="next_open", computed_at="2026-01-01T00:00:00+00:00"))
            store.save_backtest_result(_result(timing="next_close", computed_at="2026-01-01T00:00:00+00:00"))
            payloads = [store._read(key) for key in store._list_local_json_keys("backtest/us_equity/SOXL/")]
        revisions = [payload["store_write_revision"] for payload in payloads]
        self.assertEqual(len(set(revisions)), 2)
        self.assertTrue(all(payload.get("store_write_timestamp") for payload in payloads))

    def test_explicit_legacy_sentinel_is_distinct_from_omitted_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_backtest_result(_result(timing=None, computed_at="2026-01-01T00:00:00+00:00"))
            store.save_backtest_result(_result(timing="next_open", computed_at="2026-01-02T00:00:00+00:00"))
            omitted = store.load_latest_backtest("us_equity", "SOXL")
            explicit_none = store.load_latest_backtest("us_equity", "SOXL", execution_timing=None)
            legacy = store.load_latest_backtest("us_equity", "SOXL", execution_timing=LEGACY_EXECUTION_TIMING)
        self.assertEqual(omitted.execution_timing, "next_open")
        self.assertEqual(explicit_none.execution_timing, "next_open")
        self.assertIsNone(legacy.execution_timing)

    def test_empty_timing_is_rejected_on_write_and_codec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            with self.assertRaises(ValueError):
                store.save_backtest_result(_result(timing="", computed_at="2026-01-01T00:00:00+00:00"))
            store._write(
                "backtest/us_equity/SOXL/invalid.json",
                {"strategy_profile": "SOXL", "domain": "us_equity", "execution_timing": "", "params": {}},
            )
            self.assertIsNone(store.load_latest_backtest("us_equity", "SOXL", execution_timing=""))

    def test_orchestrator_persistence_preserves_result_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            orchestrator = BacktestOrchestrator(store=store)
            source = _result(timing="next_close", computed_at="2026-01-01T00:00:00+00:00")
            persisted = orchestrator.persist_result(
                source,
                strategy_profile=source.strategy_profile,
                domain=source.domain,
                params=source.params,
                param_set_id=source.param_set_id,
                param_version=source.param_version,
            )
            loaded = store.load_latest_backtest("us_equity", "SOXL", execution_timing="next_close")
        self.assertEqual(persisted.execution_timing, "next_close")
        self.assertEqual(persisted.result_identity_version, 2)
        self.assertEqual(persisted.persist_mode, "durable")
        self.assertEqual(loaded.execution_timing, "next_close")
        self.assertEqual(loaded.result_identity_version, 2)

    def test_result_json_round_trip_preserves_dates_and_nan(self) -> None:
        result = _result(timing="next_open", computed_at="2026-01-01T00:00:00+00:00")
        payload = result.to_dict()
        self.assertEqual(payload["start_date"], "2020-01-01")
        self.assertEqual(payload["end_date"], "2024-01-01")
        self.assertEqual(json.loads(json.dumps(payload))["execution_timing"], "next_open")


if __name__ == "__main__":
    unittest.main()
