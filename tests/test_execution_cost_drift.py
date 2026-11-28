"""Unit tests for pure-offline execution cost & slippage drift monitor."""

from __future__ import annotations

from datetime import date
import math

import pytest

from quant_platform_kit.risk import (
    ExecutionCostDriftConfig,
    FillCostObservation,
    compute_adverse_slippage_bps,
    evaluate_execution_cost_drift,
)


def _obs(
    day: int,
    *,
    side: str = "BUY",
    model_price: float = 100.0,
    fill_price: float = 100.05,
    model_comm: float = 1.0,
    actual_comm: float = 1.0,
) -> FillCostObservation:
    return FillCostObservation(
        session_date=date(2026, 11, day),
        symbol="TQQQ",
        side=side,
        filled_qty=10.0,
        model_price=model_price,
        fill_price=fill_price,
        model_commission_usd=model_comm,
        actual_commission_usd=actual_comm,
    )


def test_adverse_slippage_sign_symmetry_buy_and_sell() -> None:
    buy_worse = _obs(1, side="BUY", model_price=100.0, fill_price=100.10)
    buy_better = _obs(2, side="BUY", model_price=100.0, fill_price=99.90)
    sell_worse = _obs(3, side="SELL", model_price=100.0, fill_price=99.90)
    sell_better = _obs(4, side="SELL", model_price=100.0, fill_price=100.10)

    assert math.isclose(compute_adverse_slippage_bps(buy_worse), 10.0, rel_tol=1e-12)
    assert math.isclose(compute_adverse_slippage_bps(buy_better), -10.0, rel_tol=1e-12)
    assert math.isclose(compute_adverse_slippage_bps(sell_worse), 10.0, rel_tol=1e-12)
    assert math.isclose(compute_adverse_slippage_bps(sell_better), -10.0, rel_tol=1e-12)


def test_empty_and_insufficient_samples_never_pause_promotion() -> None:
    empty = evaluate_execution_cost_drift(())
    assert empty.sample_count == 0
    assert empty.sufficient_samples is False
    assert empty.pause_promotion is False
    assert empty.commission_ratio is None

    small = evaluate_execution_cost_drift(
        [_obs(d, fill_price=102.0, actual_comm=10.0) for d in range(1, 5)],
        ExecutionCostDriftConfig(min_sample_count=5),
    )
    assert small.sample_count == 4
    assert small.sufficient_samples is False
    assert small.pause_promotion is False
    assert small.breach_reasons == ()


def test_within_bounds_and_each_threshold_breach_pauses_promotion() -> None:
    healthy = evaluate_execution_cost_drift(
        [
            _obs(1, fill_price=100.05, model_comm=1.0, actual_comm=1.1),
            _obs(2, side="SELL", fill_price=99.95, model_comm=1.0, actual_comm=1.0),
            _obs(3, fill_price=100.10, model_comm=1.0, actual_comm=1.2),
            _obs(4, fill_price=100.00, model_comm=1.0, actual_comm=1.0),
            _obs(5, fill_price=100.12, model_comm=1.0, actual_comm=1.2),
        ]
    )
    assert healthy.sufficient_samples is True
    assert healthy.pause_promotion is False
    assert healthy.breach_reasons == ()
    assert math.isclose(healthy.commission_ratio or 0.0, 5.5 / 5.0, rel_tol=1e-12)

    median_breach = evaluate_execution_cost_drift(
        [_obs(d, fill_price=100.20) for d in range(1, 6)],
        ExecutionCostDriftConfig(max_median_slippage_bps=15.0, max_p95_slippage_bps=40.0),
    )
    assert median_breach.pause_promotion is True
    assert median_breach.breach_reasons == ("MEDIAN_SLIPPAGE_DRIFT_EXCEEDED",)

    p95_and_comm_breach = evaluate_execution_cost_drift(
        [
            _obs(1, fill_price=100.02, actual_comm=2.0),
            _obs(2, fill_price=100.02, actual_comm=2.0),
            _obs(3, fill_price=100.02, actual_comm=2.0),
            _obs(4, fill_price=100.02, actual_comm=2.0),
            _obs(5, fill_price=100.60, actual_comm=2.0),
        ]
    )
    assert p95_and_comm_breach.pause_promotion is True
    assert p95_and_comm_breach.breach_reasons == (
        "P95_SLIPPAGE_DRIFT_EXCEEDED",
        "COMMISSION_RATIO_DRIFT_EXCEEDED",
    )


def test_zero_model_commission_handles_zero_and_positive_actual() -> None:
    zero_both = evaluate_execution_cost_drift(
        [_obs(d, model_comm=0.0, actual_comm=0.0) for d in range(1, 6)]
    )
    assert math.isclose(zero_both.commission_ratio or 0.0, 1.0, rel_tol=1e-12)
    assert zero_both.pause_promotion is False

    unexpected_fee = evaluate_execution_cost_drift(
        [_obs(d, model_comm=0.0, actual_comm=0.5) for d in range(1, 6)]
    )
    assert math.isinf(unexpected_fee.commission_ratio or 0.0)
    assert unexpected_fee.pause_promotion is True
    assert "COMMISSION_RATIO_DRIFT_EXCEEDED" in unexpected_fee.breach_reasons


@pytest.mark.parametrize(
    "bad_obs",
    [
        FillCostObservation(date(2026, 11, 1), "", "BUY", 1.0, 100.0, 100.0, 1.0, 1.0),
        FillCostObservation(date(2026, 11, 1), "TQQQ", "HOLD", 1.0, 100.0, 100.0, 1.0, 1.0),
        FillCostObservation(date(2026, 11, 1), "TQQQ", "BUY", 0.0, 100.0, 100.0, 1.0, 1.0),
        FillCostObservation(date(2026, 11, 1), "TQQQ", "BUY", 1.0, math.nan, 100.0, 1.0, 1.0),
        FillCostObservation(date(2026, 11, 1), "TQQQ", "BUY", 1.0, 100.0, -1.0, 1.0, 1.0),
        FillCostObservation(date(2026, 11, 1), "TQQQ", "BUY", 1.0, 100.0, 100.0, -0.01, 1.0),
        FillCostObservation(date(2026, 11, 1), "TQQQ", "BUY", 1.0, 100.0, 100.0, 1.0, math.inf),
    ],
)
def test_invalid_observations_fail_closed(bad_obs: FillCostObservation) -> None:
    with pytest.raises(ValueError):
        evaluate_execution_cost_drift([bad_obs])
