"""Broker-independent synthetic references; no personal security or risk policy."""
from copy import deepcopy
import json
import socket

import pytest

from quant_platform_kit.strategy_lifecycle.security_drawdown_reference import (
    SecurityDrawdownReferenceError, describe_security_drawdown_reference,
)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("reference contract must remain offline")
    monkeypatch.setattr(socket.socket, "connect", denied)


def packet():
    return dict(schema_version="qsl.security_drawdown_reference.v1", benchmark_symbol="TEST",
        reference_id="artificial-source", available_at_utc="2000-01-03T00:00:00Z",
        frozen_at_utc="2000-01-04T00:00:00Z", dates=["1999-12-29", "1999-12-30", "1999-12-31"],
        returns=[.04, -.17, .03], context=dict(currency="CAD", calendar_id="ARTIFICIAL_CALENDAR",
            window_id="ARTIFICIAL_WINDOW", series_id="TEST", frequency="daily", source_sha256="a" * 64,
            wealth_scope="SECURITY_BENCHMARK_REFERENCE", return_basis="PROVIDER_ADJUSTED_CLOSE_RATIO",
            distribution_treatment="PROVIDER_SPLIT_DIVIDEND_ADJUSTED", cost_treatment="ACCOUNT_TRADING_COSTS_EXCLUDED",
            cash_flow_basis="NOT_AN_ACCOUNT", cash_income_treatment="NOT_AN_ACCOUNT", valuation_sampling="DAILY_CLOSE"))


def describe(reference=None, **kwargs):
    options = dict(selected_benchmark="TEST", currency="CAD", calendar_id="ARTIFICIAL_CALENDAR",
                   valuation_sampling="DAILY_CLOSE", decision_cutoff_utc="2000-01-05T00:00:00Z")
    options.update(kwargs)
    return describe_security_drawdown_reference(packet() if reference is None else reference, **options)


def test_proxy_description_requires_no_account_budget_or_broker():
    out = describe()
    assert out["max_drawdown_loss_fraction"] == pytest.approx(.17)
    assert out["reference_window"]["observations"] == 3
    assert out["reference_return_basis"] == "PROVIDER_ADJUSTED_CLOSE_RATIO"
    assert out["account_costs_included"] is False
    for key in ("reference_qualified", "calendar_coverage_verified", "model_calibrated",
                "enforcement_eligible", "policy_selected", "settings_applied", "execution_authorized"):
        assert out[key] is False
    assert not {"dates", "returns", "context", "account_scope", "limit_fraction"} & set(out)
    json.dumps(out, allow_nan=False)


def test_drawdown_includes_initial_wealth_and_later_compounding():
    ref = packet(); ref["returns"] = [-.2, .1, -.1]
    assert describe(ref)["max_drawdown_loss_fraction"] == pytest.approx(.208)
    ref["returns"] = [.01, .01, .01]
    assert describe(ref)["max_drawdown_loss_fraction"] == 0


def test_source_or_freeze_changes_are_bound_without_changing_observed_risk():
    first = describe()
    for key, value in (("reference_id", "another"), ("frozen_at_utc", "2000-01-04T01:00:00Z")):
        ref = packet(); ref[key] = value
        other = describe(ref)
        assert first["input_sha256"] != other["input_sha256"]
        assert first["max_drawdown_loss_fraction"] == other["max_drawdown_loss_fraction"]
    later = describe(decision_cutoff_utc="2000-01-05T01:00:00Z")
    assert later["input_sha256"] != first["input_sha256"]


@pytest.mark.parametrize("error", [ValueError, TypeError])
def test_metric_failure_does_not_expose_source_details(monkeypatch, error):
    from quant_platform_kit.strategy_lifecycle import performance_metrics

    def fail(*args, **kwargs):
        raise error("untrusted-private-source-details")
    monkeypatch.setattr(performance_metrics, "compute_window_metrics", fail)
    with pytest.raises(SecurityDrawdownReferenceError, match="^SECURITY_REFERENCE_METRIC_UNCOMPUTABLE$"):
        describe()


@pytest.mark.parametrize("field,value", [
    ("wealth_scope", "ALLOCATED_ACCOUNT_NET_WEALTH"), ("account_scope", "ARTIFICIAL_ACCOUNT"),
    ("return_basis", "NET_SIMPLE_TOTAL_RETURN"), ("distribution_treatment", "UNKNOWN"),
    ("cost_treatment", "APPLICABLE_COSTS_INCLUDED"), ("cash_flow_basis", "EXTERNAL_FLOWS_REMOVED"),
    ("cash_income_treatment", "INCLUDED_IN_NET_WEALTH"), ("valuation_sampling", "INTRADAY"),
    ("frequency", "hourly"), ("source_sha256", None), ("series_id", "OTHER"), ("currency", "USD"),
    ("calendar_id", "OTHER"), ("window_id", "")])
def test_unknown_basis_or_unmatched_source_is_rejected(field, value):
    ref = packet(); ref["context"][field] = value
    with pytest.raises(SecurityDrawdownReferenceError):
        describe(ref)


@pytest.mark.parametrize("fault", ["schema", "short", "mismatch", "duplicate", "unsorted", "invalid_date",
    "bool", "string", "nan", "bankrupt", "below_bankruptcy", "future_available", "future_freeze", "naive_time"])
def test_incomplete_dates_returns_and_clock_are_rejected(fault):
    ref = deepcopy(packet())
    if fault == "schema": ref["schema_version"] = "UNKNOWN"
    elif fault == "short": ref["returns"] = ref["returns"][:1]; ref["dates"] = ref["dates"][:1]
    elif fault == "mismatch": ref["returns"].pop()
    elif fault == "duplicate": ref["dates"][1] = ref["dates"][0]
    elif fault == "unsorted": ref["dates"].reverse()
    elif fault == "invalid_date": ref["dates"][0] = "1999-12-32"
    elif fault == "bool": ref["returns"][1] = True
    elif fault == "string": ref["returns"][1] = "-.17"
    elif fault == "nan": ref["returns"][1] = float("nan")
    elif fault == "bankrupt": ref["returns"][1] = -1
    elif fault == "below_bankruptcy": ref["returns"][1] = -2
    elif fault == "future_available": ref["available_at_utc"] = "2000-01-06T00:00:00Z"
    elif fault == "future_freeze": ref["frozen_at_utc"] = "2000-01-06T00:00:00Z"
    else: ref["frozen_at_utc"] = "2000-01-04"
    with pytest.raises(SecurityDrawdownReferenceError):
        describe(ref)


def test_daily_reference_cannot_be_silently_used_for_intraday_observations():
    with pytest.raises(SecurityDrawdownReferenceError, match="^SECURITY_REFERENCE_DAILY_CLOSE_REQUIRED$"):
        describe(valuation_sampling="INTRADAY")


def test_finite_daily_returns_cannot_hide_overflowed_wealth_as_zero_drawdown():
    ref = packet(); ref["returns"] = [1e308, 1e308, -.5]
    with pytest.raises(SecurityDrawdownReferenceError, match="^SECURITY_REFERENCE_WEALTH_UNCOMPUTABLE$"):
        describe(ref)
