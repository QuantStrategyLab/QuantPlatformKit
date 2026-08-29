import numpy as np
import pandas as pd
import pytest

from quant_platform_kit.strategy_lifecycle.market_regime import RegimeDetector


def test_correlation_percentile_compares_equivalent_rolling_windows():
    """The percentile must be empirical, not a remapping of correlation [-1, 1]."""
    rng = np.random.default_rng(17)
    index = pd.bdate_range("2025-01-01", periods=320)
    benchmark = pd.Series(rng.normal(0, 0.01, len(index)), index=index)
    universe = pd.DataFrame(
        {
            "a": rng.normal(0, 0.01, len(index)),
            "b": rng.normal(0, 0.01, len(index)),
            "c": rng.normal(0, 0.01, len(index)),
        },
        index=index,
    )
    # Make only the latest correlation window materially more correlated.
    anchor = universe["a"].iloc[-60:].to_numpy()
    universe.loc[index[-60:], "b"] = 0.6 * anchor + 0.8 * rng.normal(0, 0.01, 60)
    universe.loc[index[-60:], "c"] = 0.6 * anchor + 0.8 * rng.normal(0, 0.01, 60)

    detector = RegimeDetector(benchmark_returns=benchmark)
    average, percentile = detector._compute_correlation_metrics(benchmark, universe)

    history = []
    for end in range(detector.CORRELATION_WINDOW_DAYS, len(universe) + 1):
        history.append(
            detector._average_pairwise_correlation(
                universe.iloc[end - detector.CORRELATION_WINDOW_DAYS:end]
            )
        )
    expected_percentile = float((np.asarray(history) < history[-1]).mean())

    assert average == pytest.approx(history[-1])
    assert percentile == pytest.approx(expected_percentile)
    assert percentile != pytest.approx((average + 1.0) / 2.0)


def test_correlation_percentile_falls_back_without_full_year_of_aligned_data():
    index = pd.bdate_range("2025-01-01", periods=251)
    benchmark = pd.Series(0.001, index=index)
    universe = pd.DataFrame({"a": 0.001, "b": 0.002, "c": 0.003}, index=index)

    average, percentile = RegimeDetector()._compute_correlation_metrics(benchmark, universe)

    assert np.isnan(average)
    assert percentile == 0.5
