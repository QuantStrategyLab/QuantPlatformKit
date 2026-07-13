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


class _TimingRunner(_RecordingRunner):
    def run(
        self,
        strategy_profile: str,
        params: Mapping[str, Any],
        start_date: date | None = None,
        end_date: date | None = None,
        *,
        execution_timing: str,
        persist: bool = True,
    ) -> BacktestResult:
        self.calls.append({"execution_timing": execution_timing, "persist": persist})
        return super().run(strategy_profile, params, start_date, end_date)


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

    def test_run_forwards_timing_and_can_skip_persistence(self) -> None:
        runner = _TimingRunner()
        orchestrator = BacktestOrchestrator(store=self.store)
        orchestrator.register_runner("us_equity", runner)

        result = orchestrator.run(
            "soxl_soxx_trend_income",
            domain="us_equity",
            params={"lookback": 20},
            execution_timing="next_open",
            persist=False,
        )

        self.assertEqual(runner.calls[0]["execution_timing"], "next_open")
        self.assertFalse(runner.calls[0]["persist"])
        self.assertIsNone(orchestrator.run_latest(result.strategy_profile, domain="us_equity"))

    def test_persisted_timing_is_part_of_result_identity(self) -> None:
        runner = _TimingRunner()
        orchestrator = BacktestOrchestrator(store=self.store)
        orchestrator.register_runner("us_equity", runner)

        orchestrator.run("test_strat", domain="us_equity", params={}, execution_timing="next_open")
        orchestrator.run("test_strat", domain="us_equity", params={}, execution_timing="next_close")

        self.assertEqual(
            orchestrator.run_latest("test_strat", domain="us_equity", execution_timing="next_open").execution_timing,
            "next_open",
        )
        self.assertEqual(
            orchestrator.run_latest("test_strat", domain="us_equity", execution_timing="next_close").execution_timing,
            "next_close",
        )
        self.assertEqual(orchestrator.run_latest("test_strat", domain="us_equity").execution_timing, "next_close")
        self.assertIsNone(orchestrator.run_latest("test_strat", domain="us_equity", execution_timing=None))

    def test_explicit_timing_rejects_kwargs_only_runner(self) -> None:
        class KeywordRunner(_RecordingRunner):
            def run(self, strategy_profile, params, **kwargs):
                return super().run(strategy_profile, params)

        orchestrator = BacktestOrchestrator(store=self.store)
        orchestrator.register_runner("us_equity", KeywordRunner())
        with self.assertRaisesRegex(TypeError, "execution_timing"):
            orchestrator.run(
                "test_strat", domain="us_equity", params={}, execution_timing="next_close", persist=False
            )

    def test_ephemeral_mode_requires_runner_persist_capability(self) -> None:
        with self.assertRaisesRegex(TypeError, "persist"):
            self.orchestrator.run("test_strat", domain="us_equity", params={}, persist=False)

    def test_run_rejects_unknown_timing(self) -> None:
        with self.assertRaises(ValueError):
            self.orchestrator.run(
                "test_strat", domain="us_equity", params={}, execution_timing="same_close", persist=False
            )

    def test_persist_result_preserves_existing_param_version_by_default(self) -> None:
        result = BacktestResult(
            strategy_profile="test_strat",
            domain="us_equity",
            param_set_id="candidate",
            params={"lookback": 30},
            param_version=7,
            sharpe_ratio=1.3,
            cagr=0.12,
            max_drawdown=-0.08,
            observation_count=252,
        )

        persisted = self.orchestrator.persist_result(
            result,
            strategy_profile="test_strat",
            domain="us_equity",
            params={"lookback": 30},
            param_set_id="persisted",
        )

        self.assertEqual(persisted.param_version, 7)

    def test_persist_result_clamps_explicit_zero_param_version(self) -> None:
        result = BacktestResult(
            strategy_profile="test_strat",
            domain="us_equity",
            param_set_id="candidate",
            params={"lookback": 30},
            param_version=7,
            sharpe_ratio=1.3,
            cagr=0.12,
            max_drawdown=-0.08,
            observation_count=252,
        )

        persisted = self.orchestrator.persist_result(
            result,
            strategy_profile="test_strat",
            domain="us_equity",
            params={"lookback": 30},
            param_set_id="persisted",
            param_version=0,
        )

        self.assertEqual(persisted.param_version, 1)

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
