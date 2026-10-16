"""Geometric net research metrics, using hand-computable synthetic returns."""
import math

import pytest

from quant_platform_kit.research_stats._validation import ResearchInputError
from quant_platform_kit.research_stats.unified_report import build_unified_net_report


def test_hand_math_first_loss_zeros_and_initial_nav():
    r = [-.2, 0., .25]
    report = build_unified_net_report(r, periods_per_year=3)
    assert report.observations == 3
    assert report.metric("max_drawdown").value == pytest.approx(-.2)
    assert report.metric("net_cagr").value == pytest.approx(0., abs=1e-15)
    assert report.metric("net_calmar_ratio").value == pytest.approx(0., abs=1e-14)
    assert report.metric("net_cagr").details["initial_nav_is_observation"] is False
    # Arithmetic mean is positive; geometric growth is zero.
    assert sum(r) / len(r) > 0


def test_same_window_geometric_cagr_and_negative_calmar():
    report = build_unified_net_report([.1, -.2], periods_per_year=2)
    assert report.metric("net_cagr").value == pytest.approx(-.12)
    assert report.metric("max_drawdown").value == pytest.approx(-.2)
    assert report.metric("net_calmar_ratio").value == pytest.approx(-.6)


def test_year_basis_and_costs_are_explicit():
    report = build_unified_net_report([.1, -.1], gross_returns=[.11, -.09], periods_per_year=4)
    assert report.metric("net_cagr").value == pytest.approx(.99 ** 2 - 1)
    assert report.metric("net_calmar_ratio").value == pytest.approx((.99 ** 2 - 1) / .1)
    assert report.metric("net_cagr").details["periods_per_year"] == 4
    assert report.no_order is True and report.live_ready is False


@pytest.mark.parametrize("returns", [[0., 0.], [.01, .02]])
def test_zero_drawdown_calmar_is_null_not_pass(returns):
    report = build_unified_net_report(returns, periods_per_year=252)
    metric = report.metric("net_calmar_ratio")
    assert metric.value is None and metric.status == "UNCOMPUTABLE"
    assert metric.reason_code == "zero_drawdown"


def test_opt_in_keeps_existing_report_exact():
    old = build_unified_net_report([-.1, 0., .2], include_outcome_diagnostics=True)
    new = build_unified_net_report([-.1, 0., .2], include_outcome_diagnostics=True, periods_per_year=252)
    assert len(old.metrics) == 12 and len(new.metrics) == 14
    assert new.metrics[:12] == old.metrics
    assert build_unified_net_report([0.]).metric("max_drawdown").value == 0


@pytest.mark.parametrize("bad", [True, 0, -1, 252., math.nan, math.inf, "252"])
def test_invalid_year_basis_rejects(bad):
    with pytest.raises(ResearchInputError):
        build_unified_net_report([.01], periods_per_year=bad)


@pytest.mark.parametrize("returns", [[], [math.nan], [math.inf], [-1.], [-1.1]])
def test_missing_and_ruined_inputs_cannot_be_dropped(returns):
    with pytest.raises(ResearchInputError):
        build_unified_net_report(returns, periods_per_year=252)


def test_extreme_annualization_does_not_publish_infinity():
    report = build_unified_net_report([1., -.01], periods_per_year=10_000)
    assert report.metric("net_cagr").status == "UNCOMPUTABLE"
    assert report.metric("net_calmar_ratio").value is None
