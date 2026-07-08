"""Tests for strategy_lifecycle.backtest_orchestrator."""

from __future__ import annotations

from datetime import date
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping

from quant_platform_kit.strategy_lifecycle.backtest_orchestrator import BacktestOrchestrator
from quant_platform_kit.strategy_lifecycle.contracts import BacktestResult
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore


class _RecordingRunner:
    """Mock BacktestRunner that records calls and returns deterministic metrics."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def run(
        self,
        strategy_profile: str,
        params: Mapping[str, Any],
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> BacktestResult:
        self.calls.append(
            {
                "strategy_profile": strategy_profile,
                "params": dict(params),
                "start_date": start_date,
                "end_date": end_date,
            }
        )
        lookback = int(params.get("lookback", 20))
        sharpe = 1.0 + lookback * 0.01
        return BacktestResult(
            strategy_profile=strategy_profile,
            domain="us_equity",
            param_set_id="mock",
            params=dict(params),
            sharpe_ratio=sharpe,
            cagr=0.12,
            max_drawdown=-0.08,
            start_date=start_date,
            end_date=end_date,
            observation_count=252,
        )


class BacktestOrchestratorTests(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = PerformanceStore(local_root=Path(self.tmp.name))
        self.orchestrator = BacktestOrchestrator(store=self.store)
        self.runner = _RecordingRunner()
        self.orchestrator.register_runner("us_equity", self.runner)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_run_enriches_and_persists(self) -> None:
        result = self.orchestrator.run(
            "test_strat",
            domain="us_equity",
            params={"lookback": 30},
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
        )
        self.assertEqual(result.strategy_profile, "test_strat")
        self.assertEqual(result.domain, "us_equity")
        self.assertEqual(result.params, {"lookback": 30})
        self.assertAlmostEqual(result.sharpe_ratio, 1.3)
        self.assertTrue(result.run_id)
        self.assertTrue(result.computed_at)
        self.assertEqual(result.source_script, "backtest_orchestrator")

    def test_run_raises_without_runner(self) -> None:
        with self.assertRaises(ValueError):
            self.orchestrator.run("test_strat", domain="cn_equity", params={})

    def test_walk_forward_runs_each_window(self) -> None:
        windows = [
            (date(2020, 1, 1), date(2021, 12, 31)),
            (date(2022, 1, 1), date(2023, 12, 31)),
            (date(2024, 1, 1), date(2024, 12, 31)),
        ]
        results = self.orchestrator.walk_forward(
            "test_strat",
            domain="us_equity",
            params={"lookback": 20},
            windows=windows,
            param_set_id="wf_test",
        )
        self.assertEqual(len(results), 3)
        self.assertEqual(len(self.runner.calls), 3)
        for idx, (result, window) in enumerate(zip(results, windows)):
            self.assertEqual(result.start_date, window[0])
            self.assertEqual(result.end_date, window[1])
            self.assertEqual(result.param_set_id, f"wf_test_wf{idx}")
        self.assertEqual(
            [self.runner.calls[i]["start_date"] for i in range(3)],
            [w[0] for w in windows],
        )

    def test_walk_forward_empty_windows_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.orchestrator.walk_forward(
                "test_strat",
                domain="us_equity",
                params={},
                windows=[],
            )

    def test_sensitivity_runs_param_grid(self) -> None:
        report = self.orchestrator.sensitivity(
            "test_strat",
            domain="us_equity",
            base_params={"top_n": 2},
            param_ranges={"lookback": [10, 20, 30]},
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
        )
        self.assertEqual(report.combination_count, 3)
        self.assertEqual(len(report.results), 3)
        self.assertEqual(report.strategy_profile, "test_strat")
        self.assertEqual(report.base_params, {"top_n": 2})
        sharpes = [r.sharpe_ratio for r in report.results]
        self.assertEqual(sharpes, [1.1, 1.2, 1.3])
        for call, result in zip(self.runner.calls, report.results):
            self.assertEqual(call["params"]["top_n"], 2)
            self.assertIn("lookback", call["params"])
            self.assertEqual(result.params["top_n"], 2)

    def test_sensitivity_two_dim_grid(self) -> None:
        report = self.orchestrator.sensitivity(
            "test_strat",
            domain="us_equity",
            base_params={},
            param_ranges={"lookback": [10, 20], "top_n": [2, 3]},
        )
        self.assertEqual(report.combination_count, 4)
        lookbacks = sorted({r.params["lookback"] for r in report.results})
        top_ns = sorted({r.params["top_n"] for r in report.results})
        self.assertEqual(lookbacks, [10, 20])
        self.assertEqual(top_ns, [2, 3])

    def test_sensitivity_empty_ranges_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.orchestrator.sensitivity(
                "test_strat",
                domain="us_equity",
                base_params={},
                param_ranges={},
            )


if __name__ == "__main__":
    unittest.main()
