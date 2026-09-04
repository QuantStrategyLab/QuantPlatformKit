from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from quant_platform_kit.strategy_lifecycle.backtest_orchestrator import BacktestOrchestrator
from quant_platform_kit.strategy_lifecycle.contracts import BacktestResult
from quant_platform_kit.strategy_lifecycle.param_optimizer import (
    _auto_register_runner,
    _build_optimization_proposal,
)


class ParamOptimizerRecommendationTests(unittest.TestCase):
    def test_strong_ordinary_optimization_is_only_a_research_candidate(self) -> None:
        baseline = BacktestResult(
            strategy_profile="test_strategy",
            domain="us_equity",
            param_set_id="baseline",
            params={"window": 20},
            sharpe_ratio=0.5,
            calmar_ratio=0.5,
            sortino_ratio=0.5,
            max_drawdown=-0.2,
            cagr=0.1,
        )
        candidate = BacktestResult(
            strategy_profile="test_strategy",
            domain="us_equity",
            param_set_id="candidate",
            params={"window": 50},
            sharpe_ratio=1.0,
            calmar_ratio=1.0,
            sortino_ratio=1.0,
            max_drawdown=-0.1,
            cagr=0.2,
            walk_forward_stability=0.9,
        )

        proposal = _build_optimization_proposal(
            "test_strategy",
            "us_equity",
            baseline.params,
            candidate.params,
            baseline,
            candidate,
            improvement=0.38,
            search_count=10,
        )

        self.assertEqual(proposal.recommendation, "research_candidate")
        self.assertNotEqual(proposal.recommendation, "promote")


class ParamOptimizerRunnerRegistrationTests(unittest.TestCase):
    def test_auto_register_runner_requires_exact_real_marker(self) -> None:
        missing = object()
        for marker in (missing, None, "", " ", "placeholder", "REAL", " real "):
            with self.subTest(marker=marker):
                orchestrator = BacktestOrchestrator()
                runner = SimpleNamespace()
                if marker is not missing:
                    runner.runner_kind = marker
                fake_module = SimpleNamespace(build_backtest_runner=lambda: runner)

                with (
                    patch("importlib.import_module", return_value=fake_module),
                    self.assertRaisesRegex(RuntimeError, "explicit runner_kind='real'"),
                ):
                    _auto_register_runner(orchestrator, "us_equity")

    def test_auto_register_runner_raises_when_all_candidates_fail(self) -> None:
        orchestrator = BacktestOrchestrator()

        def _raise(name: str) -> None:
            raise ImportError(f"missing {name}")

        with patch("importlib.import_module", side_effect=_raise):
            with self.assertRaisesRegex(RuntimeError, "Unable to register BacktestRunner"):
                _auto_register_runner(orchestrator, "crypto")

    def test_auto_register_runner_falls_back_to_legacy_us_equity_module(self) -> None:
        orchestrator = BacktestOrchestrator()

        class RealRunner:
            runner_kind = "real"

        fake_module = SimpleNamespace(build_backtest_runner=lambda: RealRunner())

        def _import(name: str) -> SimpleNamespace:
            if name == "us_equity_snapshot_pipelines.strategy_lifecycle.backtest_wrapper":
                return fake_module
            raise ImportError(f"missing {name}")

        with patch("importlib.import_module", side_effect=_import):
            _auto_register_runner(orchestrator, "us_equity")

        self.assertIsNotNone(orchestrator.get_runner("us_equity"))


if __name__ == "__main__":
    unittest.main()
