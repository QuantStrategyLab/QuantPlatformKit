"""Synthetic-only tests for PBO (CSCV). No real market data."""

from __future__ import annotations

import itertools
import math
import random
import statistics

import pytest

from quant_platform_kit.research_stats import (
    STATUS_COMPUTED,
    STATUS_UNCOMPUTABLE,
    probability_of_backtest_overfitting,
)


def _noise(n_trials: int, rows: int, seed: int) -> dict[str, list[float]]:
    rng = random.Random(seed)
    return {f"t{k}": [rng.gauss(0.0, 0.01) for _ in range(rows)] for k in range(n_trials)}


def test_persistent_skill_gives_zero_pbo() -> None:
    rng = random.Random(1)
    trials = {f"t{k}": [0.001 * k + rng.gauss(0.0, 0.0002) for _ in range(320)] for k in range(6)}
    result = probability_of_backtest_overfitting(trials, n_splits=8)
    assert result.status == STATUS_COMPUTED
    assert result.value == 0.0
    assert result.details["n_combinations"] == math.comb(8, 4)


def test_reversing_skill_gives_full_pbo() -> None:
    # Two blocks; A wins block 0 and loses block 1, B the opposite.
    a = [0.02, 0.01, 0.03, -0.02, -0.01, -0.03]
    b = [-0.02, -0.01, -0.03, 0.02, 0.01, 0.03]
    result = probability_of_backtest_overfitting({"A": a, "B": b}, n_splits=2, min_rows_per_block=3)
    assert result.status == STATUS_COMPUTED
    assert result.value == 1.0


def test_pure_noise_is_deterministic_and_far_from_zero() -> None:
    # With complementary IS/OOS halves, IS luck implies OOS give-back, so
    # pure-noise PBO sits well above zero (often above one half).
    trials = _noise(20, 400, seed=7)
    first = probability_of_backtest_overfitting(trials, n_splits=10)
    second = probability_of_backtest_overfitting(trials, n_splits=10)
    assert first.to_dict() == second.to_dict()
    assert 0.3 < first.value <= 1.0


def test_matches_independent_bruteforce() -> None:
    trials = _noise(5, 60, seed=3)
    cols = list(trials.values())
    S, rows = 6, 10
    lambdas = []
    for train in itertools.combinations(range(S), S // 2):
        test = [b for b in range(S) if b not in train]

        def perf(col, blocks):
            xs = [x for b in blocks for x in col[b * rows:(b + 1) * rows]]
            return statistics.mean(xs) / statistics.stdev(xs)

        is_p = [perf(c, train) for c in cols]
        oos_p = [perf(c, test) for c in cols]
        best = is_p.index(max(is_p))
        rank = sorted(oos_p).index(oos_p[best]) + 1
        omega = rank / (len(cols) + 1)
        lambdas.append(math.log(omega / (1 - omega)))
    expected = sum(1 for lam in lambdas if lam <= 0) / len(lambdas)
    result = probability_of_backtest_overfitting(trials, n_splits=S)
    assert result.value == pytest.approx(expected)


def test_log_growth_metric_and_leading_rows_dropped() -> None:
    trials = _noise(4, 103, seed=9)
    result = probability_of_backtest_overfitting(trials, n_splits=10, metric="mean_log_growth")
    assert result.status == STATUS_COMPUTED
    assert result.details["rows_dropped_leading"] == 3
    assert result.details["rows_per_block"] == 10


@pytest.mark.parametrize(
    ("data", "kwargs", "reason"),
    [
        ({"only": [0.01, -0.01] * 50}, {}, "insufficient_trials"),
        ({"a": [0.01, -0.01] * 50, "b": [0.01, -0.01] * 49}, {}, "trial_returns_not_aligned"),
        (_noise(3, 20, 1), {"n_splits": 16}, "insufficient_observations"),
        (_noise(3, 100, 1), {"n_splits": 7}, "invalid_input"),
        (_noise(3, 100, 1), {"n_splits": 18}, "invalid_input"),
        (_noise(3, 100, 1), {"metric": "cagr"}, "invalid_input"),
        ({"a": [0.01] * 64, "b": [0.01, -0.01] * 32}, {"n_splits": 4}, "undefined_performance"),
        ({"a": [math.nan] * 64, "b": [0.0] * 64}, {"n_splits": 4}, "invalid_input"),
        ({"a": [-1.0] * 64, "b": [0.0] * 64}, {"n_splits": 4}, "invalid_input"),
    ],
)
def test_fails_closed_without_a_number(data, kwargs, reason) -> None:
    result = probability_of_backtest_overfitting(data, **kwargs)
    assert result.status == STATUS_UNCOMPUTABLE
    assert result.value is None
    assert result.reason_code == reason


def test_sequence_input_and_tie_counting() -> None:
    col = [0.01, -0.005, 0.002, -0.001] * 10
    result = probability_of_backtest_overfitting([col, list(col)], n_splits=4)
    assert result.status == STATUS_COMPUTED
    assert result.details["is_best_ties"] == result.details["n_combinations"]
    assert result.details["trial_labels"] == ["0", "1"]
