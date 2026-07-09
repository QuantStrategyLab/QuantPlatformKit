from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from quant_platform_kit.strategy_lifecycle.live_equity import (
    extract_equity_value,
    live_run_records_to_return_series,
)
from quant_platform_kit.strategy_lifecycle.performance_monitor import PerformanceMonitor
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore
from quant_platform_kit.strategy_lifecycle.return_collector import ReturnCollector


class LiveEquityTests(unittest.TestCase):
    def test_extract_equity_from_nested_execution_result(self) -> None:
        value = extract_equity_value(
            {
                "execution_result": {
                    "portfolio": {"total_strategy_equity": 1_250_000.0},
                }
            }
        )
        self.assertEqual(value, 1_250_000.0)

    def test_live_run_records_to_return_series(self) -> None:
        series = live_run_records_to_return_series(
            [
                {"recorded_at": "2026-07-07T10:00:00+00:00", "total_equity": 100.0},
                {"recorded_at": "2026-07-08T10:00:00+00:00", "total_equity": 101.0},
            ]
        )
        self.assertEqual(len(series), 1)
        self.assertAlmostEqual(float(series.iloc[0]), 0.01)


class ReturnCollectorLiveRunTests(unittest.TestCase):
    def test_collect_merges_live_run_returns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            monitor = PerformanceMonitor(store=store)
            monitor.record_execution(
                "global_etf_rotation",
                {"platform": "schwab", "total_equity": 100.0},
                domain="us_equity",
            )
            # Second record on a later day so pct_change has one observation.
            second = store._local_path("live_runs/us_equity/global_etf_rotation/manual-day2.json")
            second.parent.mkdir(parents=True, exist_ok=True)
            second.write_text(
                (
                    '{"strategy_profile":"global_etf_rotation","domain":"us_equity",'
                    '"recorded_at":"2026-07-10T10:00:00+00:00","record_kind":"execution",'
                    '"execution_result":{"total_equity":102.0}}'
                ),
                encoding="utf-8",
            )

            collector = ReturnCollector(store=store, projects_root=Path(tmp))
            returns = collector.collect_from_live_runs("us_equity")
            self.assertIn("global_etf_rotation", returns)
            self.assertEqual(len(returns["global_etf_rotation"]), 1)
            self.assertAlmostEqual(float(returns["global_etf_rotation"].iloc[0]), 0.02)

            merged = collector.collect("us_equity")
            self.assertIn("global_etf_rotation", merged)
            self.assertIsInstance(merged["global_etf_rotation"], pd.Series)


if __name__ == "__main__":
    unittest.main()
