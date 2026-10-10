"""Synthetic-only tests for the stationary block bootstrap. No real market data."""

from __future__ import annotations

import random

import numpy as np
import pytest

from quant_platform_kit.research_stats import STATUS_COMPUTED, STATUS_UNCOMPUTABLE, stationary_bootstrap_ci
from quant_platform_kit.research_stats.bootstrap import _stationary_indices


def _synthetic(n: int = 300, seed: int = 11) -> list[float]:
    rng = random.Random(seed)
    return [0.0003 + rng.gauss(0.0, 0.012) for _ in range(n)]


def test_same_seed_reproduces_and_different_seed_differs() -> None:
    xs = _synthetic()
    a = stationary_bootstrap_ci(xs, seed=42, mean_block_length=5, n_resamples=300)
    b = stationary_bootstrap_ci(xs, seed=42, mean_block_length=5, n_resamples=300)
    c = stationary_bootstrap_ci(xs, seed=43, mean_block_length=5, n_resamples=300)
    assert a.to_dict() == b.to_dict()
    assert a.intervals["sharpe"].lower != c.intervals["sharpe"].lower
    assert a.status == STATUS_COMPUTED and a.seed == 42 and a.method == "stationary_bootstrap"


def test_intervals_are_ordered_and_point_estimates_match_manual() -> None:
    xs = _synthetic()
    result = stationary_bootstrap_ci(xs, seed=1, mean_block_length=10, n_resamples=200, confidence=0.9)
    for interval in result.intervals.values():
        assert interval.status == STATUS_COMPUTED
        assert interval.lower <= interval.upper
    arr = np.asarray(xs)
    assert result.intervals["log_growth"].estimate == pytest.approx(float(np.log1p(arr).mean()))
    assert result.intervals["sharpe"].estimate == pytest.approx(float(arr.mean() / arr.std(ddof=1)))
    equity = np.cumprod(1 + arr)
    peak = np.maximum.accumulate(np.maximum(equity, 1.0))
    assert result.intervals["max_drawdown"].estimate == pytest.approx(float((equity / peak - 1).min()))


def test_drawdown_counts_initial_equity() -> None:
    result = stationary_bootstrap_ci([-0.1] + [0.01] * 5, seed=0, mean_block_length=1, n_resamples=100)
    assert result.intervals["max_drawdown"].estimate == pytest.approx(-0.1)


def test_constant_series_sharpe_uncomputable_other_stats_degenerate() -> None:
    result = stationary_bootstrap_ci([0.001] * 50, seed=3, mean_block_length=4, n_resamples=100)
    sharpe = result.intervals["sharpe"]
    assert sharpe.status == STATUS_UNCOMPUTABLE and sharpe.estimate is None and sharpe.lower is None
    growth = result.intervals["log_growth"]
    assert growth.status == STATUS_COMPUTED
    assert growth.lower == pytest.approx(growth.estimate) and growth.upper == pytest.approx(growth.estimate)
    assert result.intervals["max_drawdown"].estimate == 0.0


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"seed": True, "mean_block_length": 5}, "invalid_input"),
        ({"seed": -1, "mean_block_length": 5}, "invalid_input"),
        ({"seed": 1, "mean_block_length": 0.5}, "invalid_input"),
        ({"seed": 1, "mean_block_length": 5, "n_resamples": 10}, "invalid_input"),
        ({"seed": 1, "mean_block_length": 5, "confidence": 1.0}, "invalid_input"),
        ({"seed": 1, "mean_block_length": 5, "statistics": ("cagr",)}, "invalid_input"),
        ({"seed": 1, "mean_block_length": 500}, "block_longer_than_sample"),
    ],
)
def test_invalid_inputs_fail_closed(kwargs: dict, reason: str) -> None:
    result = stationary_bootstrap_ci(_synthetic(), **kwargs)
    assert result.status == STATUS_UNCOMPUTABLE
    assert result.reason_code == reason
    assert result.intervals == {}


def test_seed_is_mandatory() -> None:
    with pytest.raises(TypeError):
        stationary_bootstrap_ci(_synthetic(), mean_block_length=5)  # type: ignore[call-arg]


def test_missing_values_are_rejected_not_filled() -> None:
    xs = _synthetic()
    xs[10] = float("nan")
    assert stationary_bootstrap_ci(xs, seed=1, mean_block_length=5).reason_code == "invalid_input"


def test_stationary_indices_follow_wrapped_blocks_with_expected_mean_length() -> None:
    rng = np.random.default_rng(2026)
    n, block = 200, 8.0
    idx = _stationary_indices(np, rng, n, 400, block)
    steps = (idx[:, 1:] - idx[:, :-1]) % n
    continuation = steps == 1
    # Every non-continuation is a fresh block start; observed mean block length
    # is close to the requested one (deterministic under the fixed seed).
    breaks = (~continuation).sum() + idx.shape[0]
    observed_mean = idx.size / breaks
    assert 0.85 * block < observed_mean < 1.15 * block
