"""QPK #659: explicit metric semantics for ``compute_window_metrics``.

These tests pin three things:

* new, additive fields (``metric_semantics_version``, ``daily_win_rate_ex_zero``,
  ``zero_return_days``, ``volatility_ddof`` and the benchmark alignment report);
* the opt-in ``volatility_ddof`` parameter and its relation to
  ``research_stats.sharpe_inference`` (sample std, ddof=1);
* that pre-existing fields retain the values from main b99092b3, with only
  a small absolute rounding allowance for the covariance-derived alpha.
"""

from __future__ import annotations

import math
import unittest
from datetime import date
from fractions import Fraction

import numpy as np
import pandas as pd

from quant_platform_kit.research_stats.sharpe_inference import _moments
from quant_platform_kit.strategy_lifecycle.contracts import WindowPerformance
from quant_platform_kit.strategy_lifecycle.performance_metrics import (
    WINDOW_METRICS_SEMANTICS_VERSION,
    compute_window_metrics,
    compute_windows,
)
from quant_platform_kit.strategy_lifecycle.performance_store import _snapshot_from_dict
from quant_platform_kit.strategy_lifecycle.contracts import StrategyPerformanceSnapshot
from quant_platform_kit.position_sizing import estimate_kelly


_IDX = pd.bdate_range("2025-01-01", periods=12)
_RETURNS = pd.Series(
    [0.01, 0.0, -0.005, 0.02, 0.0, -0.01, 0.003, 0.0, 0.007, -0.002, 0.0, 0.004],
    index=_IDX,
)


def _gapped_benchmark() -> pd.Series:
    bench = pd.Series(
        [0.004, 0.001, -0.003, 0.01, 0.002, -0.006, 0.001, -0.001, 0.003, 0.0, 0.002, 0.001],
        index=_IDX,
    )
    # Two strategy sessions have no benchmark print...
    bench = bench.drop(_IDX[[2, 7]])
    # ...and one benchmark-only date (Saturday 2025-01-04) has no strategy row.
    extra = pd.Series([0.005], index=pd.DatetimeIndex(["2025-01-04"]))
    return pd.concat([bench, extra]).sort_index()


# Golden values produced by the unmodified implementation at main b99092b3
# (see A3 audit report). Alpha's covariance reduction can round differently
# across numerical libraries; its daily units and formula are checked below.
_LEGACY_GOLDEN = {
    "window_name": "12d",
    "window_days": 12,
    "start_date": "2025-01-01",
    "end_date": "2025-01-16",
    "observation_count": 12,
    "total_return": 0.02700954173800052,
    "cagr": 0.7501047749359862,
    "volatility": 0.11613462016125942,
    "sharpe_ratio": 4.710051139276643,
    "sortino_ratio": 10.39955416963117,
    "calmar_ratio": 75.01047749359854,
    "max_drawdown": -0.010000000000000009,
    "win_rate": 0.4166666666666667,
    "profit_factor": 2.5882352941176467,
    "benchmark_symbol": "SPY",
    "benchmark_return": 0.01807571857454815,
    "benchmark_cagr": 0.5705725533767365,
    "benchmark_max_drawdown": -0.006000000000000005,
    "excess_cagr": 0.650359258712913,
    "alpha": -0.0002121708282166743,
    "information_ratio": 5.321757314781575,
    "calendar_id": "",
    "periods_per_year": 252.0,
}


class LegacyFieldRegressionTest(unittest.TestCase):
    def test_legacy_fields_match_pre_659_values(self) -> None:
        wp = compute_window_metrics(
            _RETURNS, benchmark_returns=_gapped_benchmark(), benchmark_symbol="SPY",
            risk_free_rate=0.02,
        )
        d = wp.to_dict()
        for key, expected in _LEGACY_GOLDEN.items():
            with self.subTest(key=key):
                if key == "alpha":
                    # Cancellation after covariance reduction can move a few
                    # low bits; this bound is 1e-13 basis points per day.
                    self.assertAlmostEqual(d[key], expected, delta=1e-17)
                else:
                    self.assertEqual(d[key], expected)

    def test_daily_alpha_matches_exact_aligned_scalar_regression(self) -> None:
        benchmark = _gapped_benchmark()
        dates = _RETURNS.index.intersection(benchmark.index)
        x = [Fraction(str(benchmark.loc[day])) for day in dates]
        y = [Fraction(str(_RETURNS.loc[day])) for day in dates]
        mean_x, mean_y = sum(x) / len(x), sum(y) / len(y)
        beta = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y)) / sum(
            (a - mean_x) ** 2 for a in x
        )
        daily_rf = Fraction("0.02") / 252
        expected = mean_y - daily_rf - beta * (mean_x - daily_rf)
        wp = compute_window_metrics(
            _RETURNS, benchmark_returns=benchmark, risk_free_rate=0.02,
        )
        self.assertAlmostEqual(wp.alpha, float(expected), delta=1e-17)

    def test_explicit_default_ddof_equals_implicit_default(self) -> None:
        implicit = compute_window_metrics(_RETURNS, benchmark_returns=_gapped_benchmark())
        explicit = compute_window_metrics(
            _RETURNS, benchmark_returns=_gapped_benchmark(), volatility_ddof=0
        )
        self.assertEqual(implicit, explicit)

    def test_legacy_dict_keys_are_a_prefix_subset(self) -> None:
        wp = compute_window_metrics(_RETURNS)
        self.assertTrue(set(_LEGACY_GOLDEN) <= set(wp.to_dict()))


class DailyWinRateSemanticsTest(unittest.TestCase):
    def test_semantics_version_is_stamped(self) -> None:
        wp = compute_window_metrics(_RETURNS)
        self.assertEqual(WINDOW_METRICS_SEMANTICS_VERSION, "qpk.window_metrics.v2")
        self.assertEqual(wp.metric_semantics_version, WINDOW_METRICS_SEMANTICS_VERSION)
        self.assertEqual(wp.to_dict()["metric_semantics_version"], "qpk.window_metrics.v2")

    def test_zero_days_counted_and_excluded_from_ex_zero_rate(self) -> None:
        wp = compute_window_metrics(_RETURNS)
        # 5 positive, 3 negative, 4 exactly-zero sessions.
        self.assertEqual(wp.zero_return_days, 4)
        self.assertAlmostEqual(wp.win_rate, 5 / 12)  # legacy: zeros in denominator
        self.assertAlmostEqual(wp.daily_win_rate_ex_zero, 5 / 8)

    def test_ex_zero_rate_matches_estimate_kelly_definition(self) -> None:
        wp = compute_window_metrics(_RETURNS)
        kelly = estimate_kelly([float(v) for v in _RETURNS])
        self.assertAlmostEqual(wp.daily_win_rate_ex_zero, kelly.win_rate)

    def test_all_zero_window_has_no_ex_zero_rate(self) -> None:
        flat = pd.Series([0.0] * 5, index=pd.bdate_range("2025-01-01", periods=5))
        wp = compute_window_metrics(flat)
        self.assertEqual(wp.win_rate, 0.0)  # legacy value unchanged
        self.assertIsNone(wp.daily_win_rate_ex_zero)
        self.assertEqual(wp.zero_return_days, 5)

    def test_empty_window_reports_unknown_counts(self) -> None:
        wp = compute_window_metrics(pd.Series(dtype=float), window_days=21)
        self.assertEqual(wp.metric_semantics_version, WINDOW_METRICS_SEMANTICS_VERSION)
        self.assertIsNone(wp.daily_win_rate_ex_zero)
        self.assertEqual(wp.zero_return_days, 0)
        self.assertEqual(wp.volatility_ddof, 0)


class VolatilityDdofTest(unittest.TestCase):
    def test_default_ddof_zero_is_reported(self) -> None:
        wp = compute_window_metrics(_RETURNS)
        self.assertEqual(wp.volatility_ddof, 0)
        expected = float(_RETURNS.std(ddof=0)) * math.sqrt(252)
        self.assertAlmostEqual(wp.volatility, expected, places=15)

    def test_ddof_one_matches_research_stats_sharpe(self) -> None:
        wp = compute_window_metrics(_RETURNS, volatility_ddof=1)
        self.assertEqual(wp.volatility_ddof, 1)
        per_period_sharpe, sample_std, _, _ = _moments([float(v) for v in _RETURNS])
        self.assertAlmostEqual(wp.volatility, sample_std * math.sqrt(252), places=12)
        self.assertAlmostEqual(wp.sharpe_ratio, per_period_sharpe * math.sqrt(252), places=12)

    def test_ddof_scales_by_bessel_factor_only(self) -> None:
        pop = compute_window_metrics(_RETURNS)
        sample = compute_window_metrics(_RETURNS, volatility_ddof=1)
        n = len(_RETURNS)
        factor = math.sqrt(n / (n - 1))
        self.assertAlmostEqual(sample.volatility, pop.volatility * factor, places=12)
        self.assertAlmostEqual(sample.sharpe_ratio, pop.sharpe_ratio / factor, places=12)
        # Everything except vol / Sharpe / ddof stamp is unchanged.
        changed = {"volatility", "sharpe_ratio", "volatility_ddof"}
        a, b = pop.to_dict(), sample.to_dict()
        for key in a:
            if key not in changed:
                with self.subTest(key=key):
                    self.assertEqual(a[key], b[key])

    def test_invalid_ddof_rejected(self) -> None:
        for bad in (-1, 2, 0.5, True, "1", None):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    compute_window_metrics(_RETURNS, volatility_ddof=bad)  # type: ignore[arg-type]

    def test_ddof_one_constant_and_single_observation(self) -> None:
        const = pd.Series([0.001] * 4, index=pd.bdate_range("2025-01-01", periods=4))
        wp = compute_window_metrics(const, volatility_ddof=1)
        self.assertEqual(wp.volatility, 0.0)
        self.assertTrue(np.isnan(wp.sharpe_ratio))
        single = compute_window_metrics(const.iloc[:1], volatility_ddof=1)
        self.assertEqual(single.volatility, 0.0)
        self.assertTrue(np.isnan(single.sharpe_ratio))

    def test_compute_windows_forwards_ddof(self) -> None:
        out = compute_windows(_RETURNS, windows=(5, 12), volatility_ddof=1)
        self.assertEqual({wp.volatility_ddof for wp in out.values()}, {1})
        default = compute_windows(_RETURNS, windows=(5, 12))
        self.assertEqual({wp.volatility_ddof for wp in default.values()}, {0})


class BenchmarkAlignmentReportTest(unittest.TestCase):
    def test_gapped_benchmark_reports_dropped_days(self) -> None:
        wp = compute_window_metrics(_RETURNS, benchmark_returns=_gapped_benchmark())
        self.assertEqual(wp.benchmark_aligned_days, 10)
        self.assertEqual(wp.benchmark_dropped_strategy_days, 2)
        self.assertEqual(wp.benchmark_dropped_benchmark_days, 1)

    def test_benchmark_history_outside_window_is_not_counted_as_dropped(self) -> None:
        long_bench = pd.Series(0.001, index=pd.bdate_range("2024-06-03", "2025-03-31"))
        wp = compute_window_metrics(_RETURNS, benchmark_returns=long_bench)
        self.assertEqual(wp.benchmark_aligned_days, 12)
        self.assertEqual(wp.benchmark_dropped_strategy_days, 0)
        self.assertEqual(wp.benchmark_dropped_benchmark_days, 0)

    def test_window_slice_alignment_counts(self) -> None:
        wp = compute_window_metrics(
            _RETURNS, benchmark_returns=_gapped_benchmark(), window_days=6
        )
        # Last six sessions: idx[6..11]; benchmark lacks idx[7].
        self.assertEqual(wp.observation_count, 6)
        self.assertEqual(wp.benchmark_aligned_days, 5)
        self.assertEqual(wp.benchmark_dropped_strategy_days, 1)
        self.assertEqual(wp.benchmark_dropped_benchmark_days, 0)

    def test_disjoint_benchmark_reports_zero_alignment(self) -> None:
        other = pd.Series([0.001, 0.002], index=pd.DatetimeIndex(["2025-01-04", "2025-01-05"]))
        wp = compute_window_metrics(_RETURNS, benchmark_returns=other)
        self.assertIsNone(wp.benchmark_cagr)  # legacy behaviour unchanged
        self.assertEqual(wp.benchmark_aligned_days, 0)
        self.assertEqual(wp.benchmark_dropped_strategy_days, 12)
        self.assertEqual(wp.benchmark_dropped_benchmark_days, 2)

    def test_no_benchmark_leaves_alignment_unset(self) -> None:
        wp = compute_window_metrics(_RETURNS)
        self.assertIsNone(wp.benchmark_aligned_days)
        self.assertIsNone(wp.benchmark_dropped_strategy_days)
        self.assertIsNone(wp.benchmark_dropped_benchmark_days)


class ContractCompatibilityTest(unittest.TestCase):
    def test_legacy_constructor_still_works_with_neutral_defaults(self) -> None:
        wp = WindowPerformance(
            window_name="t", window_days=21, start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31), observation_count=21, total_return=0.02,
            cagr=0.05, volatility=0.10, sharpe_ratio=0.5, sortino_ratio=1.0,
            calmar_ratio=0.3, max_drawdown=-0.05, win_rate=0.6,
        )
        # A hand-built / legacy record does not claim v2 semantics.
        self.assertEqual(wp.metric_semantics_version, "")
        self.assertIsNone(wp.daily_win_rate_ex_zero)
        self.assertIsNone(wp.zero_return_days)
        self.assertEqual(wp.volatility_ddof, 0)
        self.assertIsNone(wp.benchmark_aligned_days)

    def test_snapshot_round_trip_preserves_new_fields(self) -> None:
        wp = compute_window_metrics(
            _RETURNS, benchmark_returns=_gapped_benchmark(), volatility_ddof=1
        )
        snap = StrategyPerformanceSnapshot(
            strategy_profile="p", domain="us_equity", platform="t",
            as_of=date(2025, 1, 16), windows={12: wp},
        )
        loaded = _snapshot_from_dict(snap.to_dict())
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.windows[12].to_dict(), wp.to_dict())

    def test_legacy_snapshot_payload_loads_with_neutral_defaults(self) -> None:
        wp = compute_window_metrics(_RETURNS)
        snap = StrategyPerformanceSnapshot(
            strategy_profile="p", domain="us_equity", platform="t",
            as_of=date(2025, 1, 16), windows={12: wp},
        )
        payload = snap.to_dict()
        legacy_window = {k: v for k, v in payload["windows"]["12"].items() if k in _LEGACY_GOLDEN}
        payload["windows"] = {"12": legacy_window}
        loaded = _snapshot_from_dict(payload)
        self.assertIsNotNone(loaded)
        w = loaded.windows[12]
        self.assertEqual(w.metric_semantics_version, "")
        self.assertIsNone(w.daily_win_rate_ex_zero)
        self.assertIsNone(w.zero_return_days)
        self.assertEqual(w.volatility_ddof, 0)
        self.assertIsNone(w.benchmark_aligned_days)


if __name__ == "__main__":
    unittest.main()
