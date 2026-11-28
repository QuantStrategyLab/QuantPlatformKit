"""Unit tests for pure-offline TWR & net-inflow capital ladder tracker."""

from __future__ import annotations

from datetime import date
import math

import pytest

from quant_platform_kit.risk import (
    DEFAULT_CAPITAL_LADDER_TIERS,
    CapitalLadderTier,
    NavCashFlowObservation,
    evaluate_twr_and_capital_ladder,
    resolve_capital_ladder_tier,
)


def test_twr_is_invariant_to_external_deposits_and_withdrawals() -> None:
    obs = (
        NavCashFlowObservation(date(2026, 11, 2), nav_usd=1_000.0, external_cash_flow_usd=1_000.0),
        # +10% return on 1,000 -> 1,100
        NavCashFlowObservation(date(2026, 11, 3), nav_usd=1_100.0, external_cash_flow_usd=0.0),
        # +500 deposit -> base 1,600; +5% market return -> 1,680
        NavCashFlowObservation(date(2026, 11, 4), nav_usd=1_680.0, external_cash_flow_usd=500.0),
        # -200 withdrawal -> base 1,480; -10% market return -> 1,332
        NavCashFlowObservation(date(2026, 11, 5), nav_usd=1_332.0, external_cash_flow_usd=-200.0),
    )
    report = evaluate_twr_and_capital_ladder(obs)

    expected_index = 1.10 * 1.05 * 0.90
    assert report.session_count == 4
    assert math.isclose(report.twr_index, expected_index, rel_tol=1e-12)
    assert math.isclose(report.cumulative_twr_return, expected_index - 1.0, rel_tol=1e-12)
    assert math.isclose(report.cumulative_net_inflow_usd, 1_300.0, rel_tol=1e-12)
    assert report.current_tier == DEFAULT_CAPITAL_LADDER_TIERS[1]
    assert report.next_tier == DEFAULT_CAPITAL_LADDER_TIERS[2]
    assert math.isclose(report.distance_to_next_tier_usd, 5_000.0 - 1_332.0, rel_tol=1e-12)
    assert report.annualized_twr_return is not None


def test_single_session_anchor_and_top_tier_graduation() -> None:
    single = evaluate_twr_and_capital_ladder(
        (NavCashFlowObservation(date(2026, 11, 2), nav_usd=900.0, external_cash_flow_usd=900.0),)
    )
    assert math.isclose(single.twr_index, 1.0, rel_tol=1e-12)
    assert single.annualized_twr_return is None
    assert single.current_tier.name == "STARTER"
    assert single.next_tier is not None and single.next_tier.name == "PILOT"
    assert math.isclose(single.distance_to_next_tier_usd, 100.0, rel_tol=1e-12)

    top_tier, next_tier, dist = resolve_capital_ladder_tier(30_000.0)
    assert top_tier.name == "SCALE"
    assert next_tier is None
    assert dist == 0.0


def test_invalid_series_and_tiers_fail_closed() -> None:
    with pytest.raises(ValueError, match="EMPTY_OBSERVATIONS"):
        evaluate_twr_and_capital_ladder(())

    with pytest.raises(ValueError, match="UNSORTED_OR_DUPLICATE_SESSION_DATE"):
        evaluate_twr_and_capital_ladder(
            (
                NavCashFlowObservation(date(2026, 11, 3), 1_000.0),
                NavCashFlowObservation(date(2026, 11, 3), 1_050.0),
            )
        )

    with pytest.raises(ValueError, match="NON_POSITIVE_RETURN_BASE"):
        evaluate_twr_and_capital_ladder(
            (
                NavCashFlowObservation(date(2026, 11, 2), 1_000.0),
                NavCashFlowObservation(date(2026, 11, 3), 100.0, external_cash_flow_usd=-1_000.0),
            )
        )

    with pytest.raises(ValueError, match="CAPITAL_LADDER_MUST_START_AT_ZERO"):
        resolve_capital_ladder_tier(500.0, tiers=(CapitalLadderTier("PILOT", 1_000.0),))
