from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from quant_platform_kit.strategy_lifecycle.backtest_orchestrator import BacktestOrchestrator
from quant_platform_kit.strategy_lifecycle.contracts import BacktestResult
from quant_platform_kit.strategy_lifecycle.param_optimizer import _attach_walkforward, _auto_register_runner


class ParamOptimizerRunnerRegistrationTests(unittest.TestCase):
    def test_attach_walkforward_preserves_result_identity_metadata(self) -> None:
        result = BacktestResult(
            strategy_profile="SOXL", domain="us_equity", param_set_id="grid",
            params={"lookback": 20}, execution_timing="next_close",
            result_identity_version=2, persist_mode="durable",
            start_date=date(2020, 1, 1), end_date=date(2024, 1, 1), computed_at="2026-01-01",
        )
        with patch("quant_platform_kit.strategy_lifecycle.param_optimizer._run_walkforward_validation", return_value=(0.8, 1.0, 0.5, -0.2)):
            copied = _attach_walkforward("SOXL", "us_equity", result, result.params, BacktestOrchestrator(), None, None)
        self.assertEqual(copied.execution_timing, "next_close")
        self.assertEqual(copied.result_identity_version, 2)
        self.assertEqual(copied.persist_mode, "durable")

    def test_auto_register_runner_rejects_placeholder_runner(self) -> None:
        orchestrator = BacktestOrchestrator()

        class PlaceholderRunner:
            runner_kind = "placeholder"

        fake_module = SimpleNamespace(build_backtest_runner=lambda: PlaceholderRunner())

        with patch("importlib.import_module", return_value=fake_module):
            with self.assertRaisesRegex(RuntimeError, "placeholder runners are blocked"):
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
