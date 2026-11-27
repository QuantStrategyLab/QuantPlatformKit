"""Unit tests for Phase 9 PAPER policy v0 IBKR whole-share sizing core."""

from __future__ import annotations

import math

import pytest

from quant_platform_kit.risk import (
    BETA_SOXL,
    DIVERSIFICATION_CREDIT,
    FlowAdjustedHwmState,
    advance_flow_adjusted_hwm,
    compute_policy_v0_rebalance,
    estimate_ibkr_commission_usd,
    get_policy_v0_tier,
)


def test_tier_constants_and_beta_budget_match_prereg_r5_option_a() -> None:
    bal = get_policy_v0_tier("BALANCED_COMPOUNDING")
    assert bal.drawdown_budget_d == pytest.approx(0.30)
    assert bal.m_full == pytest.approx(0.27)
    assert bal.no_trade_band == pytest.approx(0.10)
    assert DIVERSIFICATION_CREDIT == pytest.approx(0.0)
    assert BETA_SOXL == pytest.approx(1.50)

    res = compute_policy_v0_rebalance(
        tier="BALANCED_COMPOUNDING",
        equity_usd=10_000.0,
        settled_cash_usd=10_000.0,
        cushion=0.30,
        prices_usd={"TQQQ": 80.0, "SOXL": 30.0},
        current_shares={"TQQQ": 0, "SOXL": 0},
    )
    assert res.ok
    assert res.target_effective_exposure == pytest.approx(0.27)
    w_tqqq = res.proposals["TQQQ"].target_weight
    w_soxl = res.proposals["SOXL"].target_weight
    assert w_tqqq == pytest.approx(0.135)
    assert w_soxl == pytest.approx(0.09)
    assert w_tqqq + BETA_SOXL * w_soxl == pytest.approx(res.target_effective_exposure)
    assert res.cash_target_weight == pytest.approx(1.0 - (0.135 + 0.09))
    assert res.safety_invariants.live is False
    assert res.safety_invariants.kelly_applied is False
    assert res.safety_invariants.stop_loss_return_rule is False
    assert res.safety_invariants.vol_scale_enabled is False
    assert res.safety_invariants.dd_scale_enabled is False
    assert res.safety_invariants.cash_only is True
    assert res.safety_invariants.external_reserve_h_usd == 0.0
    assert res.safety_invariants.whole_shares_only is True


def test_proportional_cushion_scaling_and_zero_cushion_liquidation() -> None:
    half = compute_policy_v0_rebalance(
        tier="GROWTH_COMPOUNDING",
        equity_usd=20_000.0,
        settled_cash_usd=5_000.0,
        cushion=0.25,
        prices_usd={"TQQQ": 80.0, "SOXL": 40.0},
        current_shares={"TQQQ": 0, "SOXL": 0},
    )
    assert half.ok
    assert half.target_effective_exposure == pytest.approx(0.23)

    # Zero cushion drives target weights to 0.0 and must never be suppressed by P-C band.
    flat = compute_policy_v0_rebalance(
        tier="CAPITAL_PRESERVATION",
        equity_usd=10_000.0,
        settled_cash_usd=2_000.0,
        cushion=0.0,
        prices_usd={"TQQQ": 80.0, "SOXL": 40.0},
        current_shares={"TQQQ": 1, "SOXL": 2},
    )
    assert flat.ok
    assert flat.target_effective_exposure == pytest.approx(0.0)
    assert flat.proposals["TQQQ"].delta_shares == -1
    assert flat.proposals["SOXL"].delta_shares == -2
    assert flat.proposals["TQQQ"].suppressed_by_no_trade_band is False


def test_no_trade_band_suppresses_small_drift() -> None:
    # Balanced target weight: TQQQ=0.135, SOXL=0.090, P-C=10%.
    # At equity=10_000, price=100: TQQQ=13 shares -> weight=0.130 (-3.7% drift <= 10%),
    # SOXL=9 shares -> weight=0.090 (0%), plus overweight TQQQ=14 (+3.7% drift <= 10%)
    # which is also intentionally suppressed even when FUSE is blocked.
    res = compute_policy_v0_rebalance(
        tier="BALANCED_COMPOUNDING",
        equity_usd=10_000.0,
        settled_cash_usd=5_000.0,
        cushion=0.30,
        prices_usd={"TQQQ": 100.0, "SOXL": 100.0},
        current_shares={"TQQQ": 13, "SOXL": 9},
    )
    assert res.ok
    assert res.proposals["TQQQ"].suppressed_by_no_trade_band is True
    assert res.proposals["TQQQ"].delta_shares == 0
    assert res.proposals["SOXL"].suppressed_by_no_trade_band is True
    assert res.proposals["SOXL"].delta_shares == 0

    overweight_in_band = compute_policy_v0_rebalance(
        tier="BALANCED_COMPOUNDING",
        equity_usd=10_000.0,
        settled_cash_usd=5_000.0,
        cushion=0.30,
        prices_usd={"TQQQ": 100.0, "SOXL": 100.0},
        current_shares={"TQQQ": 14, "SOXL": 9},
        fuse_new_risk_allowed=False,
    )
    assert overweight_in_band.ok
    assert overweight_in_band.proposals["TQQQ"].suppressed_by_no_trade_band is True
    assert overweight_in_band.proposals["TQQQ"].delta_shares == 0
    assert overweight_in_band.proposals["TQQQ"].suppressed_by_fuse is False


def test_large_order_proportional_cash_trim_and_zero_weight_sleeve() -> None:
    # Both sleeves want ~67.5k + ~45k on $500k equity (~50k total shares at $2 prices),
    # capped proportionally by settled_cash_usd=20_000 in fixed O(log N) bisection steps.
    large = compute_policy_v0_rebalance(
        tier="BALANCED_COMPOUNDING",
        equity_usd=500_000.0,
        settled_cash_usd=20_000.0,
        cushion=0.30,
        prices_usd={"TQQQ": 2.0, "SOXL": 2.0},
        current_shares={"TQQQ": 0, "SOXL": 0},
    )
    assert large.ok
    assert large.proposals["TQQQ"].trimmed_for_settled_cash is True
    assert large.proposals["SOXL"].trimmed_for_settled_cash is True
    assert large.proposals["TQQQ"].delta_shares > 0
    assert large.proposals["SOXL"].delta_shares > 0
    assert 0.0 <= large.projected_settled_cash_usd <= 20.0

    # Zero target weight sleeve sells while non-zero buying sleeve is trimmed for settled cash.
    zero_soxl = compute_policy_v0_rebalance(
        tier="BALANCED_COMPOUNDING",
        equity_usd=10_000.0,
        settled_cash_usd=100.0,
        cushion=0.30,
        prices_usd={"TQQQ": 40.0, "SOXL": 50.0},
        current_shares={"TQQQ": 0, "SOXL": 5},
        sleeve_beta_shares=(1.0, 0.0),
    )
    assert zero_soxl.ok
    assert zero_soxl.proposals["SOXL"].target_weight == pytest.approx(0.0)
    assert zero_soxl.proposals["SOXL"].delta_shares == -5
    assert zero_soxl.proposals["SOXL"].trimmed_for_settled_cash is False
    assert zero_soxl.proposals["TQQQ"].final_target_shares == 2
    assert zero_soxl.proposals["TQQQ"].trimmed_for_settled_cash is True


def test_fuse_gate_blocks_buys_but_permits_sells() -> None:
    res = compute_policy_v0_rebalance(
        tier="BALANCED_COMPOUNDING",
        equity_usd=10_000.0,
        settled_cash_usd=5_000.0,
        cushion=0.30,
        prices_usd={"TQQQ": 50.0, "SOXL": 50.0},
        current_shares={"TQQQ": 0, "SOXL": 30},
        fuse_new_risk_allowed=False,
    )
    assert res.ok
    assert res.proposals["TQQQ"].suppressed_by_fuse is True
    assert res.proposals["TQQQ"].delta_shares == 0
    assert res.proposals["SOXL"].suppressed_by_fuse is False
    assert res.proposals["SOXL"].delta_shares == 18 - 30


def test_settled_cash_cap_never_spends_unsettled_sell_proceeds() -> None:
    # Selling SOXL yields unsettled cash, while TQQQ buy is strictly capped by settled_cash_usd=100.
    res = compute_policy_v0_rebalance(
        tier="BALANCED_COMPOUNDING",
        equity_usd=10_000.0,
        settled_cash_usd=100.0,
        cushion=0.30,
        prices_usd={"TQQQ": 40.0, "SOXL": 50.0},
        current_shares={"TQQQ": 0, "SOXL": 40},
        pricing_plan="PRO_TIERED",
    )
    assert res.ok
    assert res.proposals["SOXL"].delta_shares < 0
    # 2 shares @ $40 + $0.35 = $80.35 <= $100; 3 shares would be $120.35 > $100.
    assert res.proposals["TQQQ"].final_target_shares == 2
    assert res.proposals["TQQQ"].trimmed_for_settled_cash is True
    assert res.projected_settled_cash_usd == pytest.approx(100.0 - 80.35)


def test_ibkr_commission_tiers() -> None:
    assert estimate_ibkr_commission_usd(0, 50.0, pricing_plan="PRO_TIERED") == 0.0
    assert estimate_ibkr_commission_usd(10, 50.0, pricing_plan="PRO_TIERED") == pytest.approx(0.35)
    assert estimate_ibkr_commission_usd(10, 50.0, pricing_plan="PRO_FIXED") == pytest.approx(1.00)
    assert estimate_ibkr_commission_usd(1000, 50.0, pricing_plan="PRO_TIERED") == pytest.approx(3.50)
    assert estimate_ibkr_commission_usd(1, 20.0, pricing_plan="PRO_TIERED") == pytest.approx(0.20)


def test_fail_closed_validation_and_hwm_composition() -> None:
    frac = compute_policy_v0_rebalance(
        tier="BALANCED_COMPOUNDING",
        equity_usd=10_000.0,
        settled_cash_usd=10_000.0,
        cushion=0.30,
        prices_usd={"TQQQ": 50.0, "SOXL": 50.0},
        current_shares={"TQQQ": 0, "SOXL": 0},
        whole_shares_only=False,
    )
    assert not frac.ok
    assert "IBKR_FRACTIONAL_EQUITY_API_UNSUPPORTED" in frac.fail_closed_reasons

    bad = compute_policy_v0_rebalance(
        tier="UNKNOWN",
        equity_usd=float("nan"),
        settled_cash_usd=-1.0,
        cushion=-0.1,
        prices_usd={"TQQQ": 0.0, "SOXL": 50.0},
        current_shares={"TQQQ": True, "SOXL": -1},  # type: ignore[dict-item]
        pricing_plan="FREE",
    )
    assert not bad.ok
    assert "UNKNOWN_POLICY_V0_TIER" in bad.fail_closed_reasons
    assert "UNKNOWN_IBKR_PRICING_PLAN" in bad.fail_closed_reasons
    assert "INVALID_EQUITY_USD" in bad.fail_closed_reasons
    assert "INVALID_SETTLED_CASH_USD" in bad.fail_closed_reasons
    assert "INVALID_CUSHION" in bad.fail_closed_reasons
    assert "INVALID_PRICE_TQQQ" in bad.fail_closed_reasons
    assert "INVALID_HOLDINGS_TQQQ" in bad.fail_closed_reasons
    assert "INVALID_HOLDINGS_SOXL" in bad.fail_closed_reasons

    # Compose directly with flow_adjusted_hwm (#816).
    hwm0 = FlowAdjustedHwmState(equity_usd=10_000.0, governed_hwm_usd=10_000.0)
    upd = advance_flow_adjusted_hwm(hwm0, ending_equity_usd=9_000.0, tier_loss_budget_d=0.30)
    assert upd.ok
    sized = compute_policy_v0_rebalance(
        tier="BALANCED_COMPOUNDING",
        equity_usd=upd.next_state.equity_usd,
        settled_cash_usd=9_000.0,
        cushion=upd.cushion,
        prices_usd={"TQQQ": 80.0, "SOXL": 30.0},
        current_shares={"TQQQ": 0, "SOXL": 0},
    )
    assert sized.ok
    assert math.isclose(sized.target_effective_exposure, 0.27 * (upd.cushion / 0.30), rel_tol=1e-12)
