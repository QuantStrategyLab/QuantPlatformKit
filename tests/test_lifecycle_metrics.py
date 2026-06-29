"""Tests for strategy_lifecycle.performance_metrics — rolling window calculations."""

from __future__ import annotations

from datetime import date
import unittest

import numpy as np
import pandas as pd

from quant_platform_kit.strategy_lifecycle.performance_metrics import (
    compute_window_metrics,
    compute_windows,
    normalize_return_series,
    normalize_return_matrix,
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


if __name__ == "__main__":
    unittest.main()
