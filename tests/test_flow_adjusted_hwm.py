"""Unit tests for canonical P0 net-inflow HWM, cushion, and split reconciliation."""

from __future__ import annotations

import math

import pytest

from quant_platform_kit.risk.flow_adjusted_hwm import (
    CorporateActionSplit,
    ExternalCashFlow,
    FlowAdjustedHwmState,
    adjust_position_for_split,
    advance_flow_adjusted_hwm,
)


def _initial_state(equity: float = 50_000.0, reserve_h: float = 0.0) -> FlowAdjustedHwmState:
    return FlowAdjustedHwmState(equity_usd=equity, governed_hwm_usd=equity, external_reserve_h_usd=reserve_h)


def test_end_of_day_deposit_and_withdrawal_preserve_drawdown_and_cushion() -> None:
    s0 = _initial_state(100.0)
    # 10% market loss before any flow.
    u1 = advance_flow_adjusted_hwm(s0, ending_equity_usd=90.0, tier_loss_budget_d=0.30)
    assert u1.ok
    assert math.isclose(u1.bankroll_drawdown, 0.10, rel_tol=1e-12)
    assert math.isclose(u1.cushion, 0.20 / 0.90, rel_tol=1e-12)
    assert math.isclose(u1.reference_peak_bankroll_usd - u1.accumulated_loss_usd, 90.0, rel_tol=1e-12)

    # Large mid-drawdown deposit (+50 USD at session close with flat market return -> ending=140):
    # W_ref scales to preserve dd=0.10 and cushion, while governed E* ratchets to 140 and emits audit flag.
    u2 = advance_flow_adjusted_hwm(
        u1.next_state,
        ending_equity_usd=140.0,
        flows=(ExternalCashFlow(amount_usd=50.0, is_end_of_session=True),),
        tier_loss_budget_d=0.30,
    )
    assert u2.ok
    assert u2.mid_drawdown_deposit_audit is True
    assert math.isclose(u2.session_return, 0.0, abs_tol=1e-12)
    assert math.isclose(u2.bankroll_drawdown, 0.10, rel_tol=1e-12)
    assert math.isclose(u2.cushion, 0.20 / 0.90, rel_tol=1e-12)
    assert math.isclose(u2.next_state.governed_hwm_usd, 140.0, rel_tol=1e-12)
    assert math.isclose(u2.reference_peak_bankroll_usd - u2.accumulated_loss_usd, 140.0, rel_tol=1e-12)

    # Withdrawal (-40 USD at session close with flat market return -> ending=100) never lowers E*.
    u3 = advance_flow_adjusted_hwm(
        u2.next_state,
        ending_equity_usd=100.0,
        flows=(ExternalCashFlow(amount_usd=-40.0, is_end_of_session=True),),
        tier_loss_budget_d=0.30,
    )
    assert u3.ok
    assert math.isclose(u3.bankroll_drawdown, 0.10, rel_tol=1e-12)
    assert math.isclose(u3.next_state.governed_hwm_usd, 140.0, rel_tol=1e-12)
    assert math.isclose(u3.reference_peak_bankroll_usd - u3.accumulated_loss_usd, 100.0, rel_tol=1e-12)


def test_gain_before_withdrawal_ratchets_pre_flow_peak() -> None:
    s0 = _initial_state(100.0)
    # Example from definitions-contract §3.2(1): E_{t-1}=100, pre-flow=101, F_t=-0.5, E_t=100.5 -> E*_t=101.
    u1 = advance_flow_adjusted_hwm(
        s0,
        ending_equity_usd=100.5,
        flows=(ExternalCashFlow(amount_usd=-0.5, is_end_of_session=True),),
    )
    assert u1.ok
    assert math.isclose(u1.session_return, 0.01, rel_tol=1e-12)
    assert math.isclose(u1.next_state.governed_hwm_usd, 101.0, rel_tol=1e-12)
    assert math.isclose(u1.bankroll_drawdown, 0.0, abs_tol=1e-12)


def test_intraday_flow_chains_exact_twr_and_missing_pre_flow_fails_closed() -> None:
    s0 = _initial_state(100.0, reserve_h=100.0)
    # Intraday gain +10% (100->110), then +100 deposit (->210), then flat afternoon (ending=210).
    # Account factor = 1.10 * 1.00 = 1.10; bankroll factor = ((110+100)/(100+100)) = 210/200 = 1.05.
    u_ok = advance_flow_adjusted_hwm(
        s0,
        ending_equity_usd=210.0,
        flows=(ExternalCashFlow(amount_usd=100.0, pre_flow_equity_usd=110.0, is_end_of_session=False),),
    )
    assert u_ok.ok
    assert math.isclose(u_ok.session_return, 0.10, rel_tol=1e-12)
    assert math.isclose(u_ok.bankroll_return, 0.05, rel_tol=1e-12)
    assert math.isclose(u_ok.next_state.governed_hwm_usd, 210.0, rel_tol=1e-12)

    u_fail = advance_flow_adjusted_hwm(
        s0,
        ending_equity_usd=210.0,
        flows=(ExternalCashFlow(amount_usd=100.0, pre_flow_equity_usd=None, is_end_of_session=False),),
    )
    assert not u_fail.ok
    assert "O1_MISSING_PRE_FLOW_VALUATION_FAIL_CLOSED" in u_fail.fail_closed_reasons


def test_owner_downward_reset_respects_amber_lock_and_cooling_off() -> None:
    s0 = _initial_state(100.0)
    # Drawdown 12% (>= D/3 = 10% for D=0.30) triggers Amber L1 lock.
    u_amber = advance_flow_adjusted_hwm(s0, ending_equity_usd=88.0, tier_loss_budget_d=0.30)
    assert u_amber.ok

    # Recover only to 5% drawdown (< 10% Amber) so Amber lock clears, but test cooldown < 30 days.
    u_low_dd = advance_flow_adjusted_hwm(
        u_amber.next_state,
        ending_equity_usd=95.0,
        tier_loss_budget_d=0.30,
    )
    assert u_low_dd.ok
    assert u_low_dd.bankroll_drawdown < 0.10

    blocked_amber = advance_flow_adjusted_hwm(
        s0,
        ending_equity_usd=88.0,
        owner_hwm_reset_usd=88.0,
        days_since_last_reset=45,
        tier_loss_budget_d=0.30,
    )
    assert not blocked_amber.ok
    assert "L1_AMBER_RESET_LOCKED" in blocked_amber.fail_closed_reasons

    blocked_cooldown = advance_flow_adjusted_hwm(
        u_amber.next_state,
        ending_equity_usd=95.0,
        owner_hwm_reset_usd=95.0,
        days_since_last_reset=29,
        tier_loss_budget_d=0.30,
    )
    assert not blocked_cooldown.ok
    assert "OWNER_RESET_COOLDOWN_ACTIVE" in blocked_cooldown.fail_closed_reasons

    allowed_reset = advance_flow_adjusted_hwm(
        u_amber.next_state,
        ending_equity_usd=95.0,
        owner_hwm_reset_usd=95.0,
        days_since_last_reset=30,
        tier_loss_budget_d=0.30,
    )
    assert allowed_reset.ok
    assert math.isclose(allowed_reset.next_state.governed_hwm_usd, 95.0, rel_tol=1e-12)


def test_forward_and_reverse_split_reconciliation_and_fail_closed() -> None:
    s0 = _initial_state(50_000.0)
    post_shares, post_price = adjust_position_for_split(100.0, 60.0, 3.0)
    assert math.isclose(post_shares, 300.0)
    assert math.isclose(post_price, 20.0)

    fwd_split = CorporateActionSplit(
        symbol="TQQQ",
        split_ratio=3.0,
        pre_shares=100.0,
        post_shares=300.0,
        pre_price=60.0,
        post_price=20.0,
    )
    rev_split = CorporateActionSplit(
        symbol="SOXL",
        split_ratio=0.2,
        pre_shares=103.0,
        post_shares=20.0,
        pre_price=10.0,
        post_price=50.0,
        cash_in_lieu_usd=30.0,
    )
    u_split = advance_flow_adjusted_hwm(
        s0,
        ending_equity_usd=50_000.0,
        splits=(fwd_split, rev_split),
    )
    assert u_split.ok
    assert math.isclose(u_split.session_return, 0.0, abs_tol=1e-12)
    assert math.isclose(u_split.bankroll_drawdown, 0.0, abs_tol=1e-12)

    bad_split = CorporateActionSplit(
        symbol="SOXL",
        split_ratio=0.2,
        pre_shares=100.0,
        post_shares=20.0,
        pre_price=10.0,
        post_price=10.0,  # Unadjusted price drops notional from 1000 to 200.
    )
    u_bad = advance_flow_adjusted_hwm(s0, ending_equity_usd=50_000.0, splits=(bad_split,))
    assert not u_bad.ok
    assert "V2_SPLIT_RECONCILIATION_FAIL_CLOSED" in u_bad.fail_closed_reasons
    with pytest.raises(ValueError, match="INVALID_SPLIT_RATIO"):
        adjust_position_for_split(10.0, 50.0, 0.0)
