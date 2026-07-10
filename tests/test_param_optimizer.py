from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from quant_platform_kit.strategy_lifecycle.backtest_orchestrator import BacktestOrchestrator
from quant_platform_kit.strategy_lifecycle.param_optimizer import _auto_register_runner


class ParamOptimizerRunnerRegistrationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
