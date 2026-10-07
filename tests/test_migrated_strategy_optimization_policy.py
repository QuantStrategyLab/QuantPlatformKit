from __future__ import annotations

import unittest

from quant_platform_kit.strategy_lifecycle.watch.strategy_optimization_policy import SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_NONE, evaluate_strategy_metrics


class StrategyOptimizationPolicyTest(unittest.TestCase):
    def test_detects_multi_metric_degradation_as_high_severity(self) -> None:
        result = evaluate_strategy_metrics(
            {"sharpe": 0.8, "cagr": 0.15, "calmar": 0.7, "win_rate": 0.55, "max_dd": 0.16},
            {"sharpe": 1.0, "cagr": 0.2, "calmar": 1.0, "win_rate": 0.6, "max_dd": 0.10},
        )

        self.assertTrue(result["should_open_issue"])
        self.assertEqual(result["severity"], SEVERITY_HIGH)
        self.assertEqual(
            {signal["metric"] for signal in result["signals"]},
            {"sharpe", "cagr", "calmar", "win_rate", "max_dd"},
        )

    def test_single_small_degradation_is_medium_severity(self) -> None:
        result = evaluate_strategy_metrics(
            {"sharpe": 0.9, "cagr": 0.2, "calmar": 1.0, "win_rate": 0.6, "max_dd": 0.1},
            {"sharpe": 1.0, "cagr": 0.2, "calmar": 1.0, "win_rate": 0.6, "max_dd": 0.1},
        )

        self.assertTrue(result["should_open_issue"])
        self.assertEqual(result["severity"], SEVERITY_MEDIUM)

    def test_baseline_zero_negative_current_is_degradation(self) -> None:
        result = evaluate_strategy_metrics(
            {"sharpe": -0.2, "cagr": 0.2, "calmar": 1.0, "win_rate": 0.6, "max_dd": 0.1},
            {"sharpe": 0.0, "cagr": 0.2, "calmar": 1.0, "win_rate": 0.6, "max_dd": 0.1},
        )

        self.assertTrue(result["should_open_issue"])
        self.assertEqual(result["severity"], SEVERITY_MEDIUM)
        self.assertEqual(result["signals"][0]["metric"], "sharpe")

    def test_ignores_missing_or_below_threshold_metrics(self) -> None:
        result = evaluate_strategy_metrics(
            {"sharpe": 0.98, "max_dd": 0.111, "calmar": "not-a-number"},
            {"sharpe": 1.0, "max_dd": 0.10, "calmar": 1.2},
        )

        self.assertFalse(result["should_open_issue"])
        self.assertEqual(result["severity"], SEVERITY_NONE)
        self.assertEqual(result["signals"], [])


if __name__ == "__main__":
    unittest.main()
