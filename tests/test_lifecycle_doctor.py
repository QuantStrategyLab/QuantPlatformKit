from __future__ import annotations

from datetime import date
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from quant_platform_kit.strategy_lifecycle.contracts import BacktestResult, StrategyPerformanceSnapshot, WindowPerformance
from quant_platform_kit.strategy_lifecycle.doctor import doctor_lifecycle
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore
from quant_platform_kit.strategy_lifecycle.return_collector import ReturnCollector


def _window() -> WindowPerformance:
    return WindowPerformance(
        window_name="trailing_6m",
        window_days=126,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 6, 30),
        observation_count=126,
        total_return=0.1,
        cagr=0.18,
        volatility=0.2,
        sharpe_ratio=1.1,
        sortino_ratio=1.4,
        calmar_ratio=1.0,
        max_drawdown=-0.1,
        win_rate=0.55,
    )


class LifecycleDoctorTests(unittest.TestCase):
    def test_doctor_reports_missing_backtest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_snapshot(
                StrategyPerformanceSnapshot(
                    strategy_profile="global_etf_rotation",
                    domain="us_equity",
                    platform="schwab",
                    as_of=date(2026, 6, 30),
                    windows={126: _window()},
                )
            )
            collector = ReturnCollector(store=store)
            collector.collect_from_live_runs = lambda domain: {"global_etf_rotation": pd.Series([0.01], index=pd.to_datetime(["2026-06-30"]))}  # type: ignore[method-assign]

            result = doctor_lifecycle(
                "us_equity",
                require_snapshot=True,
                require_backtest=True,
                store=store,
                collector=collector,
            )

            self.assertFalse(result["ok"])
            self.assertIn("global_etf_rotation: missing lifecycle backtest", result["issues"])

    def test_doctor_passes_when_snapshot_and_backtest_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_snapshot(
                StrategyPerformanceSnapshot(
                    strategy_profile="global_etf_rotation",
                    domain="us_equity",
                    platform="schwab",
                    as_of=date(2026, 6, 30),
                    windows={126: _window()},
                    data_freshness_days=0,
                )
            )
            store.save_backtest_result(
                BacktestResult(
                    strategy_profile="global_etf_rotation",
                    domain="us_equity",
                    param_set_id="baseline",
                    params={},
                    param_version=1,
                    sharpe_ratio=1.2,
                    calmar_ratio=1.0,
                    max_drawdown=-0.1,
                    cagr=0.2,
                    volatility=0.2,
                    win_rate=0.56,
                    computed_at="2026-06-30T00:00:00Z",
                )
            )
            collector = ReturnCollector(store=store)
            collector.collect_from_live_runs = lambda domain: {"global_etf_rotation": pd.Series([0.01], index=pd.to_datetime(["2026-06-30"]))}  # type: ignore[method-assign]

            result = doctor_lifecycle(
                "us_equity",
                require_snapshot=True,
                require_backtest=True,
                max_freshness_days=1,
                store=store,
                collector=collector,
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["issues"], [])

    def test_doctor_can_require_one_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            collector = ReturnCollector(store=store)
            collector.collect_from_live_runs = lambda domain: {"global_etf_rotation": pd.Series([0.01], index=pd.to_datetime(["2026-06-30"]))}  # type: ignore[method-assign]

            result = doctor_lifecycle(
                "us_equity",
                strategy_profile="missing_profile",
                store=store,
                collector=collector,
            )

            self.assertFalse(result["ok"])
            self.assertEqual(result["profiles_discovered"], 0)
            self.assertIn("missing_profile: no strategy return series discovered", result["issues"][0])


if __name__ == "__main__":
    unittest.main()
