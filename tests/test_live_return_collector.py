from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from quant_platform_kit.strategy_lifecycle.live_equity import (
    consecutive_losses_from_live_run_records,
    count_consecutive_losses,
    extract_equity_value,
    live_run_records_to_return_series,
    resolve_consecutive_losses,
    stamp_consecutive_losses_on_snapshot,
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

    def test_count_consecutive_losses_trailing_only(self) -> None:
        self.assertEqual(count_consecutive_losses(pd.Series([-0.01, 0.02, -0.01, -0.03])), 2)
        self.assertEqual(count_consecutive_losses(pd.Series([-0.01, -0.02, 0.0])), 0)
        self.assertEqual(count_consecutive_losses(pd.Series(dtype=float)), 0)

    def test_consecutive_losses_from_live_run_records(self) -> None:
        streak = consecutive_losses_from_live_run_records(
            [
                {"recorded_at": "2026-07-01T10:00:00+00:00", "total_equity": 100.0},
                {"recorded_at": "2026-07-02T10:00:00+00:00", "total_equity": 99.0},
                {"recorded_at": "2026-07-03T10:00:00+00:00", "total_equity": 97.0},
                {"recorded_at": "2026-07-04T10:00:00+00:00", "total_equity": 98.0},
                {"recorded_at": "2026-07-05T10:00:00+00:00", "total_equity": 96.0},
                {"recorded_at": "2026-07-06T10:00:00+00:00", "total_equity": 95.0},
            ]
        )
        # returns: -1%, -2.02%, +1.03%, -2.04%, -1.04% → trailing streak 2
        self.assertEqual(streak, 2)

    def test_resolve_consecutive_losses_from_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            for day, equity in (
                ("2026-07-01T10:00:00+00:00", 100.0),
                ("2026-07-02T10:00:00+00:00", 98.0),
                ("2026-07-03T10:00:00+00:00", 96.0),
            ):
                store.save_live_run_record(
                    "global_etf_rotation",
                    "us_equity",
                    {
                        "strategy_profile": "global_etf_rotation",
                        "domain": "us_equity",
                        "recorded_at": day,
                        "record_kind": "execution",
                        "execution_result": {"total_equity": equity},
                    },
                )
            self.assertEqual(
                resolve_consecutive_losses(
                    domain="us_equity",
                    strategy_profile="global_etf_rotation",
                    store=store,
                ),
                2,
            )
            self.assertIsNone(
                resolve_consecutive_losses(
                    domain="us_equity",
                    strategy_profile="missing_profile",
                    store=store,
                )
            )

    def test_stamp_consecutive_losses_on_snapshot(self) -> None:
        from datetime import datetime, timezone

        from quant_platform_kit.common.models import PortfolioSnapshot

        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            for day, equity in (
                ("2026-07-01T10:00:00+00:00", 100.0),
                ("2026-07-02T10:00:00+00:00", 98.0),
                ("2026-07-03T10:00:00+00:00", 96.0),
            ):
                store.save_live_run_record(
                    "global_etf_rotation",
                    "us_equity",
                    {
                        "strategy_profile": "global_etf_rotation",
                        "domain": "us_equity",
                        "recorded_at": day,
                        "record_kind": "execution",
                        "execution_result": {"total_equity": equity},
                    },
                )
            snapshot = PortfolioSnapshot(
                as_of=datetime.now(timezone.utc),
                total_equity=96.0,
                positions=(),
                metadata={},
            )
            stamped = stamp_consecutive_losses_on_snapshot(
                snapshot,
                strategy_profile="global_etf_rotation",
                domain="us_equity",
                store=store,
            )
            self.assertIsNot(stamped, snapshot)
            self.assertEqual(stamped.metadata["consecutive_losses"], 2)

            preserved = stamp_consecutive_losses_on_snapshot(
                stamped,
                strategy_profile="global_etf_rotation",
                domain="us_equity",
                store=store,
            )
            self.assertIs(preserved, stamped)


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
            first_record = store.list_live_run_records("us_equity", strategy_profile="global_etf_rotation")[0]
            second_recorded_at = (
                pd.Timestamp(first_record["recorded_at"]).normalize() + pd.Timedelta(days=1, hours=10)
            ).isoformat()
            # Second record on a later day so pct_change has one observation.
            second = store._local_path("live_runs/us_equity/global_etf_rotation/manual-day2.json")
            second.parent.mkdir(parents=True, exist_ok=True)
            second.write_text(
                (
                    '{"strategy_profile":"global_etf_rotation","domain":"us_equity",'
                    f'"recorded_at":"{second_recorded_at}","record_kind":"execution",'
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
