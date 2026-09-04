"""Tests for strategy_lifecycle.performance_metrics — rolling window calculations."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from quant_platform_kit.strategy_lifecycle.performance_metrics import (
    compute_window_metrics,
    compute_windows,
    normalize_return_series,
    DEFAULT_WINDOWS,
)


class PerformanceMetricsTest(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        self.dates = pd.date_range("2025-01-01", periods=252, freq="B")
        self.returns = pd.Series(np.random.normal(0.0008, 0.015, 252), index=self.dates)

    def test_normalize_return_series(self) -> None:
        s = normalize_return_series(self.returns)
        self.assertGreater(len(s), 0)
        # Index should be datetime
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(s.index))

    def test_compute_window_metrics_basic(self) -> None:
        r = self.returns
        wp = compute_window_metrics(r, window_days=126, window_label="test_6m")
        self.assertGreater(wp.observation_count, 0)
        self.assertEqual(wp.window_name, "test_6m")
        self.assertFalse(np.isnan(wp.sharpe_ratio))
        self.assertFalse(np.isnan(wp.cagr))
        self.assertIsNotNone(wp.start_date)
        self.assertIsNotNone(wp.end_date)

    def test_compute_window_metrics_empty(self) -> None:
        wp = compute_window_metrics(pd.Series(dtype=float), window_days=63, window_label="empty")
        self.assertEqual(wp.observation_count, 0)
        self.assertTrue(np.isnan(wp.sharpe_ratio))

    def test_compute_window_metrics_with_benchmark(self) -> None:
        r = self.returns
        bench = pd.Series(np.random.normal(0.0005, 0.012, 252), index=self.dates)
        wp = compute_window_metrics(r, benchmark_returns=bench, benchmark_symbol="SPY", window_days=126)
        self.assertEqual(wp.benchmark_symbol, "SPY")
        self.assertIsNotNone(wp.benchmark_return)
        self.assertIsNotNone(wp.excess_cagr)
        self.assertIsNotNone(wp.information_ratio)

    def test_non_negative_sharpe(self) -> None:
        r = pd.Series(np.random.normal(0.001, 0.02, 252), index=self.dates)
        wp = compute_window_metrics(r, window_days=252, window_label="full")
        self.assertGreater(wp.sharpe_ratio, -2.0)  # basic sanity

    def test_max_drawdown_non_positive(self) -> None:
        r = pd.Series(np.random.normal(0.001, 0.015, 252), index=self.dates)
        wp = compute_window_metrics(r, window_days=252, window_label="full")
        self.assertLessEqual(wp.max_drawdown, 0)  # DD should be <= 0

    def test_compute_windows_returns_all_windows(self) -> None:
        r = pd.Series(np.random.normal(0.001, 0.015, 300), index=pd.date_range("2025-01-01", periods=300, freq="B"))
        windows = compute_windows(r)
        for w in DEFAULT_WINDOWS:
            self.assertIn(w, windows)
        self.assertEqual(windows[252].window_name, "trailing_1y")

    def test_compute_windows_with_benchmark(self) -> None:
        r = pd.Series(np.random.normal(0.001, 0.015, 252), index=self.dates)
        bench = pd.Series(np.random.normal(0.0005, 0.012, 252), index=self.dates)
        windows = compute_windows(r, benchmark_returns=bench, benchmark_symbol="SPY")
        for w in DEFAULT_WINDOWS:
            self.assertIn(w, windows)
        wp = windows[252]
        self.assertEqual(wp.benchmark_symbol, "SPY")

    def test_win_rate_between_0_and_1(self) -> None:
        r = pd.Series(np.random.normal(0.001, 0.02, 252), index=self.dates)
        wp = compute_window_metrics(r, window_days=252)
        self.assertGreaterEqual(wp.win_rate, 0.0)
        self.assertLessEqual(wp.win_rate, 1.0)

    def test_volatility_positive(self) -> None:
        r = pd.Series(np.random.normal(0.001, 0.015, 252), index=self.dates)
        wp = compute_window_metrics(r, window_days=252)
        self.assertGreater(wp.volatility, 0.0)

    def test_drawdown_includes_initial_capital_for_strategy_and_benchmark(self) -> None:
        for values, expected in (([-0.2, 0.1], -0.2), ([-0.2, -0.1], -0.28), ([0.1, -0.2], -0.2), ([0.1, 0.2], 0.0)):
            with self.subTest(values=values):
                returns = pd.Series(values, index=self.dates[:2])
                wp = compute_window_metrics(returns, benchmark_returns=returns)
                self.assertAlmostEqual(wp.max_drawdown, expected)
                self.assertAlmostEqual(wp.benchmark_max_drawdown, expected)
                self.assertEqual(wp.observation_count, 2)
                self.assertEqual(wp.start_date, self.dates[0].date())
                self.assertAlmostEqual(wp.total_return, (1 + values[0]) * (1 + values[1]) - 1)
                if expected < 0:
                    self.assertAlmostEqual(wp.calmar_ratio, wp.cagr / abs(expected))

    def test_window_slice_rebases_initial_capital_without_extra_observation(self) -> None:
        returns = pd.Series([0.5, -0.2, -0.1], index=self.dates[:3])
        direct = compute_window_metrics(returns, benchmark_returns=returns, window_days=2)
        rolling = compute_windows(returns, benchmark_returns=returns, windows=(2,))[2]
        for wp in (direct, rolling):
            self.assertAlmostEqual(wp.max_drawdown, -0.28)
            self.assertAlmostEqual(wp.benchmark_max_drawdown, -0.28)
            self.assertAlmostEqual(wp.total_return, -0.28)
            self.assertEqual(wp.observation_count, 2)
            self.assertEqual(wp.start_date, self.dates[1].date())
            self.assertEqual(wp.end_date, self.dates[2].date())

    def test_sortino_uses_full_sample_rms_shortfall_and_daily_mar(self) -> None:
        cases = (
            ([0.02, -0.01, 0.02, -0.01], 0.0, 0.005 / np.sqrt(0.0002 / 4) * np.sqrt(252)),
            ([-0.01, -0.01, -0.01], 0.0, -np.sqrt(252)),
            # All returns are positive, but one falls below the daily MAR of .002.
            ([0.001, 0.003, 0.004], 0.504, (0.002 / 3) / np.sqrt(0.000001 / 3) * np.sqrt(252)),
            ([0.02, np.nan, -0.01, 0.02, -0.01], 0.0, 0.005 / np.sqrt(0.0002 / 4) * np.sqrt(252)),
        )
        for values, risk_free_rate, expected in cases:
            with self.subTest(values=values, risk_free_rate=risk_free_rate):
                wp = compute_window_metrics(
                    pd.Series(values, index=self.dates[:len(values)]), risk_free_rate=risk_free_rate,
                )
                self.assertAlmostEqual(wp.sortino_ratio, expected)

    def test_zero_downside_and_empty_inputs_remain_undefined(self) -> None:
        for values in ([0.01, 0.02], [0.0, 0.0], []):
            with self.subTest(values=values):
                returns = pd.Series(values, index=self.dates[:len(values)], dtype=float)
                wp = compute_window_metrics(returns, benchmark_returns=returns)
                self.assertTrue(np.isnan(wp.sortino_ratio))
                if not values:
                    self.assertTrue(np.isnan(wp.max_drawdown))
                    self.assertIsNone(wp.benchmark_return)
                    self.assertIsNone(wp.alpha)

    def test_identical_strategy_and_benchmark_have_zero_daily_alpha(self) -> None:
        returns = pd.Series([0.01, 0.02, 0.03], index=self.dates[:3])
        for risk_free_rate in (0.0, 0.252):
            with self.subTest(risk_free_rate=risk_free_rate):
                wp = compute_window_metrics(returns, benchmark_returns=returns, risk_free_rate=risk_free_rate)
                self.assertAlmostEqual(wp.alpha, 0.0, places=12)
                self.assertAlmostEqual(wp.excess_cagr, 0.0)
                self.assertTrue(np.isnan(wp.information_ratio))

    def test_jensen_alpha_keeps_daily_units_and_non_unit_beta(self) -> None:
        benchmark = pd.Series([-0.01, 0.01, 0.03], index=self.dates[:3])
        # Strategy = 2 * benchmark + .003; daily Rf=.001, so alpha=.003+.001=.004.
        wp = compute_window_metrics(2 * benchmark + 0.003, benchmark_returns=benchmark, risk_free_rate=0.252)
        self.assertAlmostEqual(wp.alpha, 0.004, places=12)

    def test_benchmark_comparisons_use_only_common_dates(self) -> None:
        returns = pd.Series([0.5, 0.002, -0.4, 0.005], index=self.dates[:4])
        benchmark = pd.Series([0.001, 0.002, 0.8], index=self.dates[[1, 3, 4]])
        wp = compute_window_metrics(returns, benchmark_returns=benchmark, risk_free_rate=0.0252)
        # Aligned active returns [.001, .003]: mean=.002, population std=.001.
        self.assertAlmostEqual(wp.information_ratio, 2 * np.sqrt(252))
        # Aligned slope=3, intercept=-.001; daily Rf=.0001 => alpha=-.0008.
        self.assertAlmostEqual(wp.alpha, -0.0008, places=12)
        self.assertAlmostEqual(wp.benchmark_return, 1.001 * 1.002 - 1)
        self.assertAlmostEqual(wp.benchmark_cagr, (1.001 * 1.002) ** 126 - 1)
        self.assertAlmostEqual(wp.excess_cagr, (1.002 * 1.005) ** 126 - (1.001 * 1.002) ** 126)
        self.assertEqual(wp.observation_count, 4)
        self.assertAlmostEqual(wp.total_return, 1.5 * 1.002 * 0.6 * 1.005 - 1)

    def test_constant_benchmark_does_not_identify_beta_or_alpha(self) -> None:
        for constant in (0.0, 0.1):
            with self.subTest(constant=constant):
                returns = pd.Series([0.01, 0.02, 0.03], index=self.dates[:3])
                benchmark = pd.Series(constant, index=self.dates[:3])
                wp = compute_window_metrics(returns, benchmark_returns=benchmark)
                self.assertIsNone(wp.alpha)
                self.assertIsNotNone(wp.benchmark_return)
                self.assertTrue(np.isfinite(wp.information_ratio))

    def test_constant_returns_and_active_returns_have_zero_variance(self) -> None:
        returns = pd.Series([0.1, 0.1, 0.1], index=self.dates[:3])
        wp = compute_window_metrics(returns, benchmark_returns=returns * 0.0)
        self.assertEqual(wp.volatility, 0.0)
        self.assertTrue(np.isnan(wp.sharpe_ratio))
        self.assertTrue(np.isnan(wp.information_ratio))

    def test_absent_overlap_and_single_observation_are_not_regressions(self) -> None:
        returns = pd.Series([-0.2], index=self.dates[:1])
        for benchmark in (pd.Series(dtype=float), pd.Series([0.1], index=self.dates[1:2])):
            wp = compute_window_metrics(returns, benchmark_returns=benchmark)
            self.assertIsNone(wp.benchmark_return)
            self.assertIsNone(wp.excess_cagr)
            self.assertIsNone(wp.information_ratio)
            self.assertIsNone(wp.alpha)
        wp = compute_window_metrics(returns, benchmark_returns=returns)
        self.assertIsNone(wp.alpha)
        self.assertTrue(np.isnan(wp.information_ratio))
        self.assertAlmostEqual(wp.max_drawdown, -0.2)
        self.assertAlmostEqual(wp.benchmark_max_drawdown, -0.2)


if __name__ == "__main__":
    unittest.main()
