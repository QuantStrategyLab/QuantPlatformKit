from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from quant_platform_kit.strategy_lifecycle.contracts import BacktestResult, OptimizationProposal, StrategyPerformanceSnapshot, WindowPerformance
from quant_platform_kit.strategy_lifecycle.performance_export import export_strategy_performance
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore


def _window() -> WindowPerformance:
    return WindowPerformance(
        window_name="trailing_6m",
        window_days=126,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 6, 30),
        observation_count=126,
        total_return=0.11,
        cagr=0.18,
        volatility=0.22,
        sharpe_ratio=1.2,
        sortino_ratio=1.6,
        calmar_ratio=1.1,
        max_drawdown=-0.12,
        win_rate=0.58,
        benchmark_symbol="buy_hold_BTC",
        benchmark_return=0.08,
        benchmark_cagr=0.13,
        benchmark_max_drawdown=-0.18,
        excess_cagr=0.05,
        alpha=0.03,
        information_ratio=0.7,
    )


class StrategyPerformanceExportTests(unittest.TestCase):
    def test_export_strategy_performance_writes_canonical_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            snapshot = StrategyPerformanceSnapshot(
                strategy_profile="crypto_live_pool_rotation",
                domain="crypto",
                platform="binance",
                as_of=date(2026, 6, 30),
                windows={126: _window()},
                latest_return=0.01,
                benchmark_symbol="buy_hold_BTC",
                drift_score=0.2,
                data_freshness_days=1,
                source_artifact_path="data/output/live_returns.csv",
                computed_at="2026-06-30T00:00:00Z",
            )
            backtest = BacktestResult(
                strategy_profile="crypto_live_pool_rotation",
                domain="crypto",
                param_set_id="baseline",
                params={"top_n": 10},
                param_version=3,
                sharpe_ratio=1.4,
                calmar_ratio=1.2,
                max_drawdown=-0.10,
                cagr=0.22,
                volatility=0.25,
                win_rate=0.6,
                total_return=0.3,
                observation_count=756,
                benchmark_symbol="buy_hold_BTC",
                benchmark_cagr=0.14,
                benchmark_max_drawdown=-0.2,
                excess_cagr=0.08,
                computed_at="2026-06-29T00:00:00Z",
            )
            store.save_snapshot(snapshot)
            store.save_backtest_result(backtest)
            output = Path(tmp) / "strategy_metrics.json"

            payload = export_strategy_performance("crypto", repo="QuantStrategyLab/CryptoLivePoolPipelines", store=store, output_path=output)

            self.assertEqual(payload["schema_version"], "strategy_performance.v2")
            self.assertEqual(payload["metrics_kind"], "performance")
            self.assertEqual(len(payload["snapshots"]), 1)
            exported = payload["snapshots"][0]
            self.assertEqual(exported["current_metrics"]["sharpe"], 1.2)
            self.assertEqual(exported["baseline_metrics"]["sharpe"], 1.4)
            self.assertEqual(exported["metadata"]["window_days"], 126)
            self.assertTrue(output.exists())
            on_disk = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["schema_version"], "strategy_performance.v2")

    def test_export_strategy_performance_fails_without_backtest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_snapshot(
                StrategyPerformanceSnapshot(
                    strategy_profile="crypto_live_pool_rotation",
                    domain="crypto",
                    platform="binance",
                    as_of=date(2026, 6, 30),
                    windows={126: _window()},
                )
            )

            with self.assertRaisesRegex(ValueError, "Missing latest lifecycle backtest"):
                export_strategy_performance("crypto", repo="QuantStrategyLab/CryptoLivePoolPipelines", store=store)

    def test_performance_store_load_latest_backtest_falls_back_to_local(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            result = BacktestResult(
                strategy_profile="crypto_live_pool_rotation",
                domain="crypto",
                param_set_id="baseline",
                params={},
                param_version=2,
                sharpe_ratio=1.0,
                calmar_ratio=1.0,
                max_drawdown=-0.1,
                cagr=0.2,
                volatility=0.2,
                win_rate=0.55,
            )
            store.save_backtest_result(result)

            loaded = store.load_latest_backtest("crypto", "crypto_live_pool_rotation")

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.param_version, 2)

    def test_performance_store_keeps_multiple_backtests_same_param_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            first = BacktestResult(
                strategy_profile="crypto_live_pool_rotation",
                domain="crypto",
                param_set_id="wf0",
                params={},
                param_version=2,
                sharpe_ratio=1.0,
                calmar_ratio=1.0,
                max_drawdown=-0.1,
                cagr=0.2,
                volatility=0.2,
                win_rate=0.55,
                computed_at="2026-06-28T00:00:00Z",
            )
            second = BacktestResult(
                strategy_profile="crypto_live_pool_rotation",
                domain="crypto",
                param_set_id="wf1",
                params={},
                param_version=2,
                sharpe_ratio=1.2,
                calmar_ratio=1.1,
                max_drawdown=-0.09,
                cagr=0.22,
                volatility=0.21,
                win_rate=0.57,
                computed_at="2026-06-29T00:00:00Z",
            )
            store.save_backtest_result(first)
            store.save_backtest_result(second)

            files = list((Path(tmp) / "backtest" / "crypto" / "crypto_live_pool_rotation").glob("*.json"))
            loaded = store.load_latest_backtest("crypto", "crypto_live_pool_rotation")

            self.assertEqual(len(files), 2)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.param_set_id, "wf1")

    def test_performance_store_prefers_baseline_backtest_over_newer_walk_forward(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            baseline = BacktestResult(
                strategy_profile="crypto_live_pool_rotation",
                domain="crypto",
                param_set_id="crypto_live_pool_rotation_baseline_deadbeef",
                params={},
                param_version=2,
                sharpe_ratio=1.0,
                calmar_ratio=1.0,
                max_drawdown=-0.1,
                cagr=0.2,
                volatility=0.2,
                win_rate=0.55,
                computed_at="2026-06-28T00:00:00Z",
            )
            wf = BacktestResult(
                strategy_profile="crypto_live_pool_rotation",
                domain="crypto",
                param_set_id="crypto_live_pool_rotation_wf0",
                params={},
                param_version=2,
                sharpe_ratio=1.3,
                calmar_ratio=1.2,
                max_drawdown=-0.08,
                cagr=0.24,
                volatility=0.22,
                win_rate=0.58,
                computed_at="2026-06-29T00:00:00Z",
            )
            store.save_backtest_result(baseline)
            store.save_backtest_result(wf)

            loaded = store.load_latest_backtest("crypto", "crypto_live_pool_rotation")

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.param_set_id, baseline.param_set_id)

    def test_performance_store_keeps_multiple_proposals_same_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            first_metrics = BacktestResult(
                strategy_profile="crypto_live_pool_rotation",
                domain="crypto",
                param_set_id="candidate_a",
                params={"top_n": 8},
                param_version=3,
                sharpe_ratio=1.1,
                calmar_ratio=1.0,
                max_drawdown=-0.12,
                cagr=0.2,
                volatility=0.22,
                win_rate=0.56,
                computed_at="2026-06-28T00:00:00Z",
            )
            second_metrics = BacktestResult(
                strategy_profile="crypto_live_pool_rotation",
                domain="crypto",
                param_set_id="candidate_b",
                params={"top_n": 10},
                param_version=3,
                sharpe_ratio=1.3,
                calmar_ratio=1.1,
                max_drawdown=-0.10,
                cagr=0.23,
                volatility=0.21,
                win_rate=0.58,
                computed_at="2026-06-29T00:00:00Z",
            )
            first = OptimizationProposal(
                strategy_profile="crypto_live_pool_rotation",
                domain="crypto",
                current_params={"top_n": 6},
                proposed_params={"top_n": 8},
                proposed_metrics=first_metrics,
                recommendation="review",
                computed_at="2026-06-28T00:00:00Z",
            )
            second = OptimizationProposal(
                strategy_profile="crypto_live_pool_rotation",
                domain="crypto",
                current_params={"top_n": 8},
                proposed_params={"top_n": 10},
                proposed_metrics=second_metrics,
                recommendation="promote",
                computed_at="2026-06-29T00:00:00Z",
            )
            store.save_proposal(first)
            store.save_proposal(second)

            files = list((Path(tmp) / "optimization" / "crypto" / "crypto_live_pool_rotation").glob("*.json"))
            loaded = store.load_proposal("crypto", "crypto_live_pool_rotation", version=3)

            self.assertEqual(len(files), 2)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.proposed_params["top_n"], 10)

    def test_performance_store_load_proposal_does_not_cross_version_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            v1_metrics = BacktestResult(
                strategy_profile="crypto_live_pool_rotation",
                domain="crypto",
                param_set_id="candidate_v1",
                params={},
                param_version=1,
                sharpe_ratio=1.0,
                calmar_ratio=1.0,
                max_drawdown=-0.1,
                cagr=0.2,
                volatility=0.2,
                win_rate=0.55,
                computed_at="2026-06-28T00:00:00Z",
            )
            v10_metrics = BacktestResult(
                strategy_profile="crypto_live_pool_rotation",
                domain="crypto",
                param_set_id="candidate_v10",
                params={},
                param_version=10,
                sharpe_ratio=1.5,
                calmar_ratio=1.4,
                max_drawdown=-0.07,
                cagr=0.3,
                volatility=0.24,
                win_rate=0.61,
                computed_at="2026-06-29T00:00:00Z",
            )
            store.save_proposal(
                OptimizationProposal(
                    strategy_profile="crypto_live_pool_rotation",
                    domain="crypto",
                    current_params={"top_n": 6},
                    proposed_params={"top_n": 8},
                    proposed_metrics=v1_metrics,
                    recommendation="review",
                    computed_at="2026-06-28T00:00:00Z",
                )
            )
            store.save_proposal(
                OptimizationProposal(
                    strategy_profile="crypto_live_pool_rotation",
                    domain="crypto",
                    current_params={"top_n": 8},
                    proposed_params={"top_n": 10},
                    proposed_metrics=v10_metrics,
                    recommendation="promote",
                    computed_at="2026-06-29T00:00:00Z",
                )
            )

            loaded = store.load_proposal("crypto", "crypto_live_pool_rotation", version=1)

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.proposed_metrics.param_version, 1)


if __name__ == "__main__":
    unittest.main()
