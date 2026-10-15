"""Synthetic-only tests for cost-stress recomputation. No real market data."""

from __future__ import annotations

import math

import pytest

from quant_platform_kit.research_stats import cost_stress_recompute
from quant_platform_kit.research_stats.cost_stress import STATUS_PARKED

GROSS = [0.01, -0.005, 0.002, 0.0, 0.004]
TURNOVER = [1.0, 0.0, 0.5, 0.0, 2.0]


def test_default_scenarios_are_1x_2x_3x_and_monotone() -> None:
    result = cost_stress_recompute(GROSS, TURNOVER, cost_bps_per_side=10)
    assert [s.multiplier for s in result.scenarios] == [1.0, 2.0, 3.0]
    growth = [s.log_growth_per_period for s in result.scenarios]
    assert growth[0] > growth[1] > growth[2]
    drags = [s.total_cost_log_drag for s in result.scenarios]
    assert 0 < drags[0] < drags[1] < drags[2]


def test_exact_formula() -> None:
    result = cost_stress_recompute([0.02], [1.5], cost_bps_per_side=20, multipliers=[1])
    expected = (1 - 1.5 * 0.002) * 1.02 - 1
    assert result.scenario(1.0).net_returns[0] == pytest.approx(expected, rel=1e-15)
    assert result.scenario(1.0).cost_bps_per_side == 20


def test_zero_turnover_or_zero_cost_leaves_returns_unchanged() -> None:
    for turnover, bps in (([0.0] * 5, 25), (TURNOVER, 0)):
        result = cost_stress_recompute(GROSS, turnover, cost_bps_per_side=bps)
        for scenario in result.scenarios:
            assert scenario.net_returns == pytest.approx(tuple(GROSS))
            assert scenario.total_cost_log_drag == pytest.approx(0.0, abs=1e-15)


def test_ruin_is_flagged_without_log_growth() -> None:
    result = cost_stress_recompute([0.01], [2.0], cost_bps_per_side=5000, multipliers=[1])
    scenario = result.scenario(1.0)
    assert scenario.ruined is True
    assert scenario.log_growth_per_period is None


@pytest.mark.parametrize(
    ("gross", "turnover", "kwargs", "reason"),
    [
        (GROSS, TURNOVER[:-1], {"cost_bps_per_side": 10}, "length_mismatch"),
        (GROSS, [-0.1] + TURNOVER[1:], {"cost_bps_per_side": 10}, "invalid_input"),
        ([math.nan] + GROSS[1:], TURNOVER, {"cost_bps_per_side": 10}, "invalid_input"),
        (GROSS, TURNOVER, {"cost_bps_per_side": -1}, "invalid_input"),
        (GROSS, TURNOVER, {"cost_bps_per_side": 10, "multipliers": [1, 1]}, "invalid_input"),
        (GROSS, TURNOVER, {"cost_bps_per_side": 10, "multipliers": [0]}, "invalid_input"),
        ([], [], {"cost_bps_per_side": 10}, "empty_returns"),
    ],
)
def test_invalid_inputs_are_parked(gross, turnover, kwargs, reason) -> None:
    result = cost_stress_recompute(gross, turnover, **kwargs)
    assert result.status == STATUS_PARKED
    assert result.reason_code == reason
    assert result.scenarios == ()
