from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from quant_platform_kit.strategy_lifecycle.contracts import BacktestResult
from quant_platform_kit.strategy_lifecycle.performance_store import (
    ANY_EXECUTION_TIMING,
    LEGACY_EXECUTION_TIMING,
    PerformanceStore,
)


def _result(*, timing: str | None, computed_at: str = "2026-01-01T00:00:00+00:00", profile: str = "SOXL"):
    return BacktestResult(
        strategy_profile=profile,
        domain="us_equity",
        param_set_id="baseline",
        params={"lookback": 20},
        execution_timing=timing,
        computed_at=computed_at,
        start_date=date(2020, 1, 1),
        end_date=date(2024, 1, 1),
    )


class ResultStoreRedesignATests(unittest.TestCase):
    def test_old_positional_order_and_v1_codec(self) -> None:
        result = BacktestResult("s", "d", "p", {}, 3, 1.1, 0.9, 0.8, -0.2, 0.1, 0.3, 0.5, 0.4)
        self.assertEqual(result.total_return, 0.4)
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store._write(
                "backtest/us_equity/SOXL/backtest_v1_legacy.json",
                {"strategy_profile": "SOXL", "domain": "us_equity", "param_set_id": "legacy", "params": {}},
            )
            loaded = store.load_latest_backtest("us_equity", "SOXL")
        self.assertIsNotNone(loaded)
        self.assertIsNone(loaded.execution_timing)
        self.assertEqual(loaded.result_identity_version, 1)

    def test_timing_round_trip_and_aliases_have_same_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            opened = _result(timing="next_open", profile="SOXL")
            alias = _result(timing="next_open", profile="soxl_soxx_trend_income")
            self.assertEqual(store._backtest_key(opened), store._backtest_key(alias))
            store.save_backtest_result(opened)
            payload = store._read(store._list_local_json_keys("backtest/us_equity/SOXL/")[0])
            loaded = store.load_latest_backtest("us_equity", "SOXL", execution_timing="next_open")
        self.assertEqual(payload["canonical_profile_id"], "SOXL")
        self.assertEqual(loaded.execution_timing, "next_open")
        self.assertEqual(loaded.result_identity_version, 2)

    def test_default_none_legacy_any_and_specific_filters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_backtest_result(_result(timing=None, computed_at="2026-01-01T00:00:00+00:00"))
            store.save_backtest_result(_result(timing="next_open", computed_at="2026-01-02T00:00:00+00:00"))
            default = store.load_latest_backtest("us_equity", "SOXL")
            explicit_none = store.load_latest_backtest("us_equity", "SOXL", execution_timing=None)
            legacy = store.load_latest_backtest("us_equity", "SOXL", execution_timing=LEGACY_EXECUTION_TIMING)
            any_timing = store.load_latest_backtest("us_equity", "SOXL", execution_timing=ANY_EXECUTION_TIMING)
            specific = store.load_latest_backtest("us_equity", "SOXL", execution_timing="next_open")
        self.assertIsNone(default.execution_timing)
        self.assertIsNone(explicit_none.execution_timing)
        self.assertIsNone(legacy.execution_timing)
        self.assertEqual(any_timing.execution_timing, "next_open")
        self.assertEqual(specific.execution_timing, "next_open")

    def test_mixed_timing_same_slot_uses_revision_only_for_any_timing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_backtest_result(_result(timing="next_open"))
            store.save_backtest_result(_result(timing="next_close"))
            latest = store.load_latest_backtest("us_equity", "SOXL", execution_timing=ANY_EXECUTION_TIMING)
            legacy_key = "backtest/us_equity/SOXL/backtest_v1_legacy.json"
            store._write(legacy_key, {"strategy_profile": "SOXL", "domain": "us_equity", "params": {}})
            legacy = store.load_latest_backtest("us_equity", "SOXL", execution_timing=LEGACY_EXECUTION_TIMING)
        self.assertEqual(latest.execution_timing, "next_close")
        self.assertIsNone(legacy.execution_timing)

    def test_literal_empty_and_invalid_timing_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            for value in ("", 123):
                store._write(
                    f"backtest/us_equity/SOXL/invalid-{value}.json",
                    {"strategy_profile": "SOXL", "domain": "us_equity", "execution_timing": value, "params": {}},
                )
            self.assertIsNone(store.load_latest_backtest("us_equity", "SOXL", execution_timing=ANY_EXECUTION_TIMING))

    def test_reads_legacy_raw_profile_prefixes_and_deduplicates_prefixes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            legacy = _result(timing=None, computed_at="2026-01-01T00:00:00+00:00", profile="soxl_soxx_trend_income")
            raw_key = "backtest/us_equity/soxl_soxx_trend_income/backtest_v1_legacy.json"
            store._write(raw_key, legacy.to_dict())
            loaded_legacy = store.load_latest_backtest("us_equity", "soxl_soxx_trend_income")
            store.save_backtest_result(_result(timing=None, computed_at="2026-01-02T00:00:00+00:00"))
            loaded_mixed = store.load_latest_backtest("us_equity", "SOXL")
        self.assertEqual(loaded_legacy.computed_at, "2026-01-01T00:00:00+00:00")
        self.assertEqual(loaded_mixed.computed_at, "2026-01-02T00:00:00+00:00")

    def test_path_sanitization_applies_to_raw_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store._write(
                "backtest/us_equity/unsafe-profile/backtest_v1_legacy.json",
                {"strategy_profile": "unsafe-profile", "domain": "us_equity", "params": {}},
            )
            loaded = store.load_latest_backtest("us_equity", "../unsafe-profile")
        self.assertIsNotNone(loaded)


if __name__ == "__main__":
    unittest.main()
