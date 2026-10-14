"""Synthetic fixtures for opt-in security-level netting (no real data, rates are test inputs)."""
from __future__ import annotations

import random

import pytest

from quant_platform_kit.research_stats import CostModel
from quant_platform_kit.research_stats.security_netting import (
    ROLE_A2_ZERO_RETURN_CASH,
    ROLE_INNER_CASH_LIKE_SECURITY,
    ROLE_INNER_RESIDUAL_CASH,
    ROLE_OUTER_CASH_LEG,
    SecurityNettingSpec,
    compose_security_targets,
    drift_inner_weights,
    net_security_session,
)

TOL = 1e-12
BPS = {"AAA": 5.0, "BBB": 7.0, "CSH": 1.0}


def spec(**kw):
    return SecurityNettingSpec(bps_per_side=BPS, cash_like_symbols=("CSH",), **kw)


def test_full_f_no_outer_change_equals_inner_turnover():
    r = net_security_session(f_pre=1.0, inner_pre={"AAA": 0.6, "CSH": 0.4},
                             f_target=1.0, inner_target={"AAA": 0.2, "BBB": 0.5, "CSH": 0.3}, spec=spec())
    assert r.outer_unnetted_turnover == 0
    assert abs(r.net_security_turnover - r.inner_unnetted_turnover) < TOL
    # parity with existing aggregate CostModel when all bps equal
    eq = SecurityNettingSpec(bps_per_side={k: 5.0 for k in BPS})
    r2 = net_security_session(f_pre=1.0, inner_pre={"AAA": 0.6}, f_target=1.0,
                              inner_target={"BBB": 0.6}, spec=eq)
    assert abs(r2.cost_fraction - CostModel(commission_bps=5.0).fraction(r2.net_security_turnover)) < TOL


def test_opposite_directions_net_below_sum():
    r = net_security_session(f_pre=0.5, inner_pre={"AAA": 0.2}, f_target=0.25,
                             inner_target={"AAA": 1.0}, spec=spec())
    # inner buys AAA, outer f cut sells it
    assert r.net_security_turnover < r.inner_unnetted_turnover + r.outer_unnetted_turnover - 1e-9
    assert abs(r.net_trades["AAA"] - (0.25 - 0.1)) < TOL
    assert r.turnover_columns_summable is False


def test_separate_outer_cash_leg_is_free_and_not_netted_with_cash_like():
    r = net_security_session(f_pre=1.0, inner_pre={"CSH": 1.0}, f_target=0.5,
                             inner_target={"CSH": 1.0}, spec=spec())
    assert "CSH" in r.net_trades and abs(r.net_trades["CSH"] + 0.5) < TOL
    assert abs(r.cost_fraction - 0.5 * 1.0 / 1e4) < TOL
    assert abs(r.role_weights[ROLE_OUTER_CASH_LEG] - 0.5) < TOL
    assert abs(r.role_weights[ROLE_INNER_CASH_LIKE_SECURITY] - 0.5) < TOL


def test_merge_outer_cash_into_security_nets_against_inner_cash_like():
    s = spec(outer_cash_mode="merge_into_security", outer_cash_symbol="CSH")
    r = net_security_session(f_pre=1.0, inner_pre={"CSH": 1.0}, f_target=0.5,
                             inner_target={"CSH": 1.0}, spec=s)
    assert abs(r.net_security_turnover) < TOL and r.cost_fraction == 0
    assert abs(sum(r.target_weights.values()) - 1.0) < TOL


def test_residual_roles_zero_return_and_uncharged():
    s = spec(inner_residual_role=ROLE_A2_ZERO_RETURN_CASH)
    w, roles = compose_security_targets(f=0.8, inner_weights={"AAA": 0.5}, spec=s)
    assert abs(roles[ROLE_A2_ZERO_RETURN_CASH] - 0.4) < TOL and ROLE_INNER_RESIDUAL_CASH not in roles
    assert abs(sum(w.values()) + sum(v for k, v in roles.items() if k != ROLE_INNER_CASH_LIKE_SECURITY) - 1) < TOL
    drifted, gross = drift_inner_weights({"AAA": 0.5}, {"AAA": 0.1})
    assert abs(gross - 0.05) < TOL and abs(drifted["AAA"] - 0.55 / 1.05) < TOL


def test_seeded_random_invariants_deterministic():
    rng = random.Random(20261014)
    s = spec()
    def book():
        a, b = rng.random(), rng.random()
        t = a + b + rng.random()
        return {"AAA": a / t, "BBB": b / t}
    outs = []
    for _ in range(500):
        args = dict(f_pre=rng.random(), inner_pre=book(), f_target=rng.random(), inner_target=book(), spec=s)
        r = net_security_session(**args)
        assert r.net_security_turnover <= r.inner_unnetted_turnover + r.outer_unnetted_turnover + TOL
        assert r == net_security_session(**args)
        outs.append(r.cost_fraction)
    assert len(outs) == 500


@pytest.mark.parametrize("kw,code", [
    (dict(outer_cash_mode="x"), "OUTER_CASH_MODE_INVALID"),
    (dict(outer_cash_mode="merge_into_security"), "OUTER_CASH_SYMBOL_REQUIRED"),
    (dict(outer_cash_symbol="CSH"), "OUTER_CASH_SYMBOL_UNEXPECTED"),
    (dict(inner_residual_role="outer_cash_leg"), "INNER_RESIDUAL_ROLE_INVALID"),
    (dict(multiplier=0), "MULTIPLIER_INVALID"),
])
def test_spec_rejections(kw, code):
    with pytest.raises(ValueError, match=code):
        spec(**kw)


def test_input_rejections():
    with pytest.raises(ValueError, match="BPS_MISSING:ZZZ"):
        net_security_session(f_pre=1, inner_pre={}, f_target=1, inner_target={"ZZZ": 1.0}, spec=spec())
    with pytest.raises(ValueError, match="OUTER_FRACTION_INVALID"):
        net_security_session(f_pre=1.5, inner_pre={}, f_target=1, inner_target={}, spec=spec())
    with pytest.raises(ValueError, match="INNER_WEIGHTS_INVALID"):
        net_security_session(f_pre=1, inner_pre={"AAA": 0.7, "BBB": 0.7}, f_target=1, inner_target={}, spec=spec())
    with pytest.raises(ValueError, match="BPS_INVALID"):
        SecurityNettingSpec(bps_per_side={"AAA": -1})
    with pytest.raises(ValueError, match="RETURN_MISSING:AAA"):
        drift_inner_weights({"AAA": 0.5}, {})
    with pytest.raises(ValueError, match="RUINED"):
        drift_inner_weights({"AAA": 0.5}, {"AAA": -1})
