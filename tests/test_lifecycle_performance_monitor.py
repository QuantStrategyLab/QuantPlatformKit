from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from quant_platform_kit.common.strategy_contracts import PositionTarget, StrategyDecision
from quant_platform_kit.strategy_lifecycle.performance_monitor import (
    PerformanceMonitor,
    infer_strategy_domain,
    run_monitor,
    try_record_platform_execution,
)
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore
from quant_platform_kit.strategy_lifecycle.return_collector import ReturnCollector


class PerformanceMonitorTests(unittest.TestCase):
    def test_record_persists_live_run_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            monitor = PerformanceMonitor(store=store)
            decision = StrategyDecision(
                positions=(PositionTarget(symbol="BTCUSDT", target_weight=0.5, role="target"),),
                risk_flags=("risk_gate:passed",),
            )
            result = monitor.record(
                "crypto_live_pool_rotation",
                decision,
                {"filled_orders": 1},
                domain="crypto",
            )
            self.assertTrue(result["ok"])
            files = list(Path(tmp).rglob("live_runs/crypto/crypto_live_pool_rotation/*.json"))
            self.assertEqual(len(files), 1)
            payload = files[0].read_text(encoding="utf-8")
            self.assertIn("BTCUSDT", payload)
            self.assertIn("filled_orders", payload)

    def test_record_execution_persists_execution_only_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            monitor = PerformanceMonitor(store=store)
            result = monitor.record_execution(
                "global_etf_rotation",
                {"orders_filled": ["VOO"], "status": "ok"},
                domain="us_equity",
            )
            self.assertTrue(result["ok"])
            files = list(Path(tmp).rglob("live_runs/us_equity/global_etf_rotation/*.json"))
            self.assertEqual(len(files), 1)
            payload = files[0].read_text(encoding="utf-8")
            self.assertIn("record_kind", payload)
            self.assertIn("orders_filled", payload)

    def test_infer_strategy_domain_from_profile_prefix(self) -> None:
        self.assertEqual(infer_strategy_domain("cn_index_etf_tactical_rotation"), "cn_equity")
        self.assertEqual(infer_strategy_domain("hk_global_etf_tactical_rotation"), "hk_equity")
        self.assertEqual(infer_strategy_domain("crypto_live_pool_rotation"), "crypto")
        self.assertEqual(infer_strategy_domain("global_etf_rotation"), "us_equity")

    def test_try_record_platform_execution_swallows_errors(self) -> None:
        try_record_platform_execution("", {"status": "ok"})

    def test_run_monitor_fails_closed_when_no_profiles_found(self) -> None:
        class EmptyCollector:
            def collect(self, _domain: str) -> dict[str, pd.Series]:
                return {}

        with self.assertRaisesRegex(RuntimeError, "No strategy return series found"):
            run_monitor("us_equity", collector=EmptyCollector())

    def test_csv_collector_to_monitor_rejects_duplicate_daily_returns(self) -> None:
        for dates, values in (
            (["2026-09-08", "2026-09-08"], [0.01, 0.01]),
            (["2026-09-08T09:00:00", "2026-09-08T16:00:00"], [0.01, -0.02]),
        ):
            with self.subTest(dates=dates), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                matrix = root / "portfolio_and_tracker_returns.csv"
                pd.DataFrame({"as_of": dates, "synthetic_soxl": values}).to_csv(matrix, index=False)
                store = PerformanceStore(local_root=root / "store")
                collector = ReturnCollector(artifact_roots={"us_equity": root}, projects_root=root, store=store)
                with patch.object(PerformanceStore, "save_snapshot", autospec=True) as save:
                    with self.assertRaisesRegex(RuntimeError, "No strategy return series found"):
                        run_monitor("us_equity", strategy_profile="synthetic_soxl", collector=collector,
                                    store=store, windows=(2,), min_observations=2)
                    self.assertEqual(run_monitor(
                        "us_equity", collector=collector, store=store, min_observations=2, fail_on_empty=False,
                    ), [])
                    save.assert_not_called()

    def test_csv_collector_to_monitor_preserves_unique_daily_returns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame({
                "as_of": ["2026-09-08T16:00:00", "2026-09-09T16:00:00"],
                "synthetic_soxl": [0.01, -0.02],
                "SPY": [0.01, -0.02],
            }).to_csv(root / "portfolio_and_tracker_returns.csv", index=False)
            store = PerformanceStore(local_root=root / "store")
            collector = ReturnCollector(artifact_roots={"us_equity": root}, projects_root=root, store=store)
            snapshots = run_monitor(
                "us_equity", strategy_profile="synthetic_soxl", collector=collector, store=store,
                windows=(2,), min_observations=2, require_explicit_benchmark=True,
                strategy_benchmarks={"synthetic_soxl": "SPY"},
            )
            self.assertEqual(len(snapshots), 1)
            metrics = snapshots[0].windows[2]
            self.assertEqual(metrics.observation_count, 2)
            self.assertAlmostEqual(metrics.total_return, 1.01 * 0.98 - 1.0)
            self.assertAlmostEqual(metrics.excess_cagr, 0.0)

    def test_csv_collector_to_monitor_rejects_duplicate_required_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame({"as_of": ["2026-09-08", "2026-09-09"], "synthetic_soxl": [0.01, -0.02]}).to_csv(
                root / "portfolio_and_tracker_returns.csv", index=False,
            )
            benchmark_dir = root / "benchmark"
            benchmark_dir.mkdir()
            pd.DataFrame({"as_of": ["2026-09-08", "2026-09-08"], "SPY": [0.01, -0.02]}).to_csv(
                benchmark_dir / "portfolio_and_tracker_returns.csv", index=False,
            )
            store = PerformanceStore(local_root=root / "store")
            collector = ReturnCollector(artifact_roots={"us_equity": root}, projects_root=root, store=store)
            with patch.object(PerformanceStore, "save_snapshot", autospec=True) as save:
                with self.assertRaisesRegex(RuntimeError, "explicit benchmark data is unavailable or insufficient"):
                    run_monitor(
                        "us_equity", strategy_profile="synthetic_soxl", collector=collector, store=store,
                        windows=(2,), min_observations=2, require_explicit_benchmark=True,
                        strategy_benchmarks={"synthetic_soxl": "SPY"},
                    )
                save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
