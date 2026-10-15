"""Synthetic-only tests for research_stats PSR/DSR. No real market data."""

from __future__ import annotations

import math
import random
from statistics import NormalDist

import pytest

from quant_platform_kit.research_stats import (
    STATUS_COMPUTED,
    STATUS_UNCOMPUTABLE,
    deflated_sharpe_ratio,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)


def _synthetic(n: int = 250, seed: int = 7, drift: float = 0.0005, scale: float = 0.01) -> list[float]:
    rng = random.Random(seed)
    return [drift + rng.gauss(0.0, scale) for _ in range(n)]


def _manual_moments(xs: list[float]) -> tuple[float, float, float]:
    n = len(xs)
    mean = sum(xs) / n
    m2 = sum((x - mean) ** 2 for x in xs) / n
    m3 = sum((x - mean) ** 3 for x in xs) / n
    m4 = sum((x - mean) ** 4 for x in xs) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in xs) / (n - 1))
    return mean / sd, m3 / m2 ** 1.5, m4 / m2 ** 2


def test_psr_matches_independent_closed_form() -> None:
    xs = _synthetic()
    sr, skew, kurt = _manual_moments(xs)
    z = sr * math.sqrt(len(xs) - 1) / math.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr * sr)
    result = probabilistic_sharpe_ratio(xs)
    assert result.status == STATUS_COMPUTED
    assert result.value == pytest.approx(NormalDist().cdf(z), rel=1e-12)
    assert result.details["sharpe_per_period"] == pytest.approx(sr, rel=1e-12)


def test_psr_is_one_half_when_benchmark_equals_sample_sharpe() -> None:
    xs = _synthetic()
    sr = probabilistic_sharpe_ratio(xs).details["sharpe_per_period"]
    assert probabilistic_sharpe_ratio(xs, sr_benchmark=sr).value == pytest.approx(0.5, abs=1e-12)


def test_psr_decreases_as_benchmark_rises() -> None:
    xs = _synthetic()
    values = [probabilistic_sharpe_ratio(xs, sr_benchmark=b).value for b in (-0.1, 0.0, 0.05, 0.1)]
    assert values == sorted(values, reverse=True)


@pytest.mark.parametrize(
    ("returns", "reason"),
    [
        ([0.01] * 40, "zero_variance"),
        (_synthetic(n=10), "insufficient_observations"),
        ([0.01, float("nan")] * 20, "invalid_input"),
        ([0.01, -1.0] * 20, "invalid_input"),
        ([True, False] * 20, "invalid_input"),
        ("0.01", "invalid_input"),
    ],
)
def test_psr_fails_closed_without_numbers(returns: object, reason: str) -> None:
    result = probabilistic_sharpe_ratio(returns)  # type: ignore[arg-type]
    assert result.status == STATUS_UNCOMPUTABLE
    assert result.value is None
    assert result.reason_code == reason


def test_expected_max_sharpe_requires_two_trials_and_grows_with_trials() -> None:
    assert expected_max_sharpe(0.01, 1).status == STATUS_UNCOMPUTABLE
    assert expected_max_sharpe(0.0, 10).reason_code == "zero_trial_sharpe_variance"
    values = [expected_max_sharpe(0.01, n).value for n in (2, 5, 10, 100, 1000)]
    assert all(v is not None for v in values)
    assert values == sorted(values)
    # Scales with the trial Sharpe standard deviation.
    assert expected_max_sharpe(0.04, 10).value == pytest.approx(2 * expected_max_sharpe(0.01, 10).value)


def test_dsr_single_trial_is_uncomputable_not_zero() -> None:
    result = deflated_sharpe_ratio(_synthetic(), [0.05])
    assert result.status == STATUS_UNCOMPUTABLE
    assert result.value is None
    assert result.reason_code == "insufficient_trials"


def test_dsr_effective_trial_guards() -> None:
    xs, trials = _synthetic(), [0.01, 0.03, 0.05]
    assert deflated_sharpe_ratio(xs, trials, n_effective_trials=1).reason_code == "insufficient_trials"
    assert deflated_sharpe_ratio(xs, trials, n_effective_trials=4).reason_code == "effective_trials_exceed_recorded"
    assert deflated_sharpe_ratio(xs, [0.02, 0.02]).reason_code == "zero_trial_sharpe_variance"
    assert deflated_sharpe_ratio(_synthetic(n=10), trials).reason_code == "insufficient_observations"


def test_dsr_equals_psr_against_expected_max_sharpe() -> None:
    xs = _synthetic()
    trials = [0.01 * k for k in range(-3, 8)]
    mean = sum(trials) / len(trials)
    variance = sum((t - mean) ** 2 for t in trials) / (len(trials) - 1)
    sr0 = expected_max_sharpe(variance, len(trials)).value
    dsr = deflated_sharpe_ratio(xs, trials)
    assert dsr.status == STATUS_COMPUTED
    assert dsr.value == pytest.approx(probabilistic_sharpe_ratio(xs, sr_benchmark=sr0).value, rel=1e-12)
    assert dsr.value < probabilistic_sharpe_ratio(xs).value


def test_dsr_non_increasing_in_effective_trials() -> None:
    xs = _synthetic()
    trials = [0.002 * k for k in range(200)]
    values = [deflated_sharpe_ratio(xs, trials, n_effective_trials=n).value for n in (2, 5, 20, 100, 200)]
    assert all(v is not None for v in values)
    assert all(a >= b for a, b in zip(values, values[1:]))
