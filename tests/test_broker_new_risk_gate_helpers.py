"""Boundary unit tests for quant_platform_kit.common.broker_new_risk_gate_helpers."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone

import pytest

from quant_platform_kit.common.broker_new_risk_gate_helpers import (
    coerce_optional_float,
    mapping_or_empty,
    max_daily_loss_from_runtime_target_json,
    portfolio_metadata,
    positive_limit_or_none,
    resolve_daily_loss_runtime_risk_limits,
    resolve_drawdown_from_peak,
    resolve_durable_breaker_open,
    resolve_equity_usd,
    resolve_explicit_daily_loss_usd,
    resolve_max_daily_loss_usd,
    resolve_production_drift_status,
    resolve_unknown_pending,
    runtime_risk_limits_for_daily_loss_axis,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        (True, None),
        (False, None),
        ("", None),
        ("bad", None),
        (float("nan"), None),
        (float("inf"), None),
        (float("-inf"), None),
        ("inf", None),
        ("1e400", None),
        (0, 0.0),
        (-12.5, -12.5),
        ("123.45", 123.45),
        (42, 42.0),
    ],
)
def test_coerce_optional_float_boundaries(raw, expected):
    assert coerce_optional_float(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        (True, None),
        (False, None),
        (0, None),
        (0.0, None),
        (-10.0, None),
        (float("nan"), None),
        (float("inf"), None),
        ("0", None),
        ("250.5", 250.5),
        (100, 100.0),
    ],
)
def test_positive_limit_or_none_boundaries(raw, expected):
    assert positive_limit_or_none(raw) == expected


def test_mapping_or_empty_and_portfolio_metadata():
    assert mapping_or_empty(None) == {}
    assert mapping_or_empty(["a"]) == {}
    assert mapping_or_empty({"k": 1}) == {"k": 1}

    assert portfolio_metadata(None) == {}
    assert portfolio_metadata({"metadata": "invalid"}) == {}
    assert portfolio_metadata({"metadata": {"account": "demo"}}) == {"account": "demo"}


def test_resolve_equity_usd_default_and_ibkr_modes():
    assert resolve_equity_usd({}) is None
    assert resolve_equity_usd({"total_equity": 0.0, "total_strategy_equity": 5000.0}) == 5000.0
    assert resolve_equity_usd({"broker_capital": {"net_assets": "7500"}}) == 7500.0
    assert resolve_equity_usd({}, {"portfolio_total_equity": 9000}) == 9000.0
    assert resolve_equity_usd({"total_equity": float("nan")}, {"portfolio_total_equity": -1}) is None

    # IBKR fail-closed mode stops as soon as any configured native key is present.
    assert (
        resolve_equity_usd(
            {"account_equity_usd": 0.0, "total_equity": 10_000.0},
            {"portfolio_total_equity": 10_000.0},
            equity_keys=("account_equity_usd", "total_equity", "total_strategy_equity", "equity"),
            include_broker_capital=False,
            stop_on_present_key=True,
        )
        is None
    )
    assert (
        resolve_equity_usd(
            {"account_equity_usd": 25_000.0},
            equity_keys=("account_equity_usd", "total_equity", "total_strategy_equity", "equity"),
            include_broker_capital=False,
            stop_on_present_key=True,
        )
        == 25_000.0
    )
    assert (
        resolve_equity_usd(
            {"broker_capital": {"net_assets": 7500}},
            {"portfolio_total_equity": 8800},
            equity_keys=("account_equity_usd", "total_equity", "total_strategy_equity", "equity"),
            include_broker_capital=False,
            stop_on_present_key=True,
        )
        == 8800.0
    )


def test_resolve_unknown_pending_variants():
    # Default precedence (projection > portfolio > metadata)
    assert resolve_unknown_pending({"unknown_pending_orders": True}, {"unknown_pending_orders": False}) is False
    assert resolve_unknown_pending({"unknown_pending_orders": True}, {}) is True
    assert resolve_unknown_pending({"metadata": {"unknown_pending_orders": True}}, {}) is True
    assert resolve_unknown_pending({}, {}) is False

    # IBKR fail_closed_any: projection=False cannot clear portfolio unsafe/None signal
    assert (
        resolve_unknown_pending(
            {"unknown_pending_orders": None},
            {"unknown_pending_orders": False},
            fail_closed_any=True,
        )
        is True
    )
    assert (
        resolve_unknown_pending(
            {"unknown_pending_orders": False, "metadata": {"unknown_pending_orders": False}},
            {"unknown_pending_orders": False},
            fail_closed_any=True,
        )
        is False
    )

    # Schwab pending_reconciliation across portfolio / execution / metadata
    assert (
        resolve_unknown_pending(
            {},
            {},
            execution={"metadata": {"pending_reconciliation": True}},
            include_pending_reconciliation=True,
        )
        is True
    )
    assert resolve_unknown_pending({}, {}, execution={}, include_pending_reconciliation=True) is False


def test_resolve_durable_breaker_open_variants():
    assert resolve_durable_breaker_open({}, {}) is False
    assert resolve_durable_breaker_open({"durable_circuit_breaker_state": "OPEN"}, {}) is True
    assert resolve_durable_breaker_open({"durable_circuit_breaker_state": "open"}, {}) is True
    assert resolve_durable_breaker_open({"durable_circuit_breaker_state": "CLOSED"}, {}) is False
    assert resolve_durable_breaker_open({"metadata": {"durable_circuit_breaker_state": "OPEN"}}, {}) is True

    # IBKR strict_closed_only treats non-CLOSED / invalid values as OPEN even if projection says CLOSED
    assert (
        resolve_durable_breaker_open(
            {"durable_circuit_breaker_state": "UNKNOWN"},
            {"durable_circuit_breaker_state": "CLOSED"},
            strict_closed_only=True,
        )
        is True
    )
    assert (
        resolve_durable_breaker_open(
            {"durable_circuit_breaker_state": None},
            {},
            strict_closed_only=True,
        )
        is True
    )
    assert (
        resolve_durable_breaker_open(
            {"durable_circuit_breaker_state": "closed"},
            {},
            strict_closed_only=True,
        )
        is False
    )

    # Schwab check_projection_circuit_breaker
    assert (
        resolve_durable_breaker_open(
            {},
            {"circuit_breaker_state": "OPEN"},
            check_projection_circuit_breaker=True,
        )
        is True
    )


def test_resolve_production_drift_status_uses_explicit_and_store_fallback():
    seen: list[tuple[str, str]] = []

    def fake_store(*, strategy_profile: str, domain: str) -> str | None:
        seen.append((strategy_profile, domain))
        return "watch"

    assert (
        resolve_production_drift_status(
            {"production_drift_status": "review"},
            {"production_drift_status": "healthy"},
            store_resolver=fake_store,
        )
        == "healthy"
    )
    assert (
        resolve_production_drift_status(
            {"production_drift_status": "review"},
            {"production_drift_status": "healthy"},
            portfolio_first=True,
            store_resolver=fake_store,
        )
        == "review"
    )
    assert seen == []

    status = resolve_production_drift_status(
        {"metadata": {"strategy_profile": "tqqq_growth_income", "domain": "us_equity"}},
        {},
        environ={"STRATEGY_PROFILE": "ignored", "STRATEGY_DOMAIN": "ignored"},
        store_resolver=fake_store,
    )
    assert status == "watch"
    assert seen == [("tqqq_growth_income", "us_equity")]


def test_resolve_drawdown_from_peak_explicit_and_timestamped_cache_modes():
    assert resolve_drawdown_from_peak(equity_usd=80.0, peak_equity_usd=100.0, explicit=0.05) == 0.05
    assert resolve_drawdown_from_peak(equity_usd=80.0, peak_equity_usd=100.0) == pytest.approx(0.2)
    assert resolve_drawdown_from_peak(equity_usd=120.0, peak_equity_usd=100.0) == 0.0
    assert resolve_drawdown_from_peak(equity_usd=80.0, peak_equity_usd=0.0) is None
    assert resolve_drawdown_from_peak(equity_usd=None, peak_equity_usd=100.0) is None

    now = datetime(2026, 11, 18, 12, 0, 0, tzinfo=timezone.utc)
    fresh_ts = (now - timedelta(seconds=60)).isoformat()
    stale_ts = (now - timedelta(seconds=301)).isoformat()
    future_ts = (now + timedelta(seconds=10)).isoformat()

    # Derived NAV/peak beats cached broker drawdown when both positive.
    assert resolve_drawdown_from_peak(
        equity_usd=40_000.0,
        peak_equity_usd=50_000.0,
        explicit_source={"drawdown_from_peak": 0.01},
        observed_at=fresh_ts,
        now=now,
    ) == pytest.approx(0.2)

    # Without peak, fresh UTC timestamp allows non-negative fallback; stale/future/naive/negative fail closed.
    assert (
        resolve_drawdown_from_peak(
            equity_usd=40_000.0,
            peak_equity_usd=None,
            explicit_source={"drawdown_from_peak": 0.12},
            observed_at=fresh_ts,
            now=now,
        )
        == 0.12
    )
    for bad_source, bad_ts in (
        ({"drawdown_from_peak": 0.12}, stale_ts),
        ({"drawdown_from_peak": 0.12}, future_ts),
        ({"drawdown_from_peak": 0.12}, "2026-11-18T12:00:00"),
        ({"drawdown_from_peak": 0.12}, None),
        ({"drawdown_from_peak": -0.01}, fresh_ts),
        ({"drawdown_from_peak": math.nan}, fresh_ts),
    ):
        assert (
            resolve_drawdown_from_peak(
                equity_usd=40_000.0,
                peak_equity_usd=None,
                explicit_source=bad_source,
                observed_at=bad_ts,
                now=now,
            )
            is None
        )


def test_resolve_explicit_daily_loss_and_pluggable_limit_callbacks():
    assert (
        resolve_explicit_daily_loss_usd(
            {"daily_loss_usd": "125.5"},
            {"daily_loss_usd": 50.0},
            {"daily_loss_usd": 10.0},
        )
        == 125.5
    )
    assert (
        resolve_explicit_daily_loss_usd(
            {"daily_loss_usd": "125.5"},
            {"daily_loss_usd": 50.0},
            {"daily_loss_usd": 10.0},
            portfolio_first=True,
        )
        == 50.0
    )
    assert resolve_explicit_daily_loss_usd({}, {}, {"daily_loss_usd": float("nan")}) is None
    assert resolve_explicit_daily_loss_usd({}, {}, None) is None

    # RUNTIME_TARGET_JSON parsing soft-omits malformed payloads
    assert max_daily_loss_from_runtime_target_json("{bad json") is None
    assert max_daily_loss_from_runtime_target_json(json.dumps(["not", "dict"])) is None
    assert max_daily_loss_from_runtime_target_json(json.dumps({"runtime_risk_limits": {"max_daily_loss_usd": -1}})) is None
    assert (
        max_daily_loss_from_runtime_target_json(
            json.dumps({"runtime_risk_limits": {"max_daily_loss_usd": 300.0}})
        )
        == 300.0
    )

    # Explicit portfolio key (even invalid) does not fall through to env or callback
    called = []
    assert (
        resolve_max_daily_loss_usd(
            {"account_new_risk_snapshot": {"max_daily_loss_usd": 0}},
            env_keys=("IBKR_MAX_DAILY_LOSS_USD",),
            environ={"IBKR_MAX_DAILY_LOSS_USD": "500"},
            limit_callback=lambda _p: called.append(True) or 999.0,
        )
        is None
    )
    assert called == []

    # Pluggable limit_callback executes after RUNTIME_TARGET_JSON and before env fallback
    assert (
        resolve_max_daily_loss_usd(
            {"total_equity": 10_000.0},
            env_keys=("SCHWAB_MAX_DAILY_LOSS_USD", "MAX_DAILY_LOSS_USD"),
            environ={"SCHWAB_MAX_DAILY_LOSS_USD": "500"},
            limit_callback=lambda p: float(p["total_equity"]) * 0.02 if p else None,
        )
        == 200.0
    )
    assert (
        resolve_max_daily_loss_usd(
            {},
            env_keys=("SCHWAB_MAX_DAILY_LOSS_USD", "MAX_DAILY_LOSS_USD"),
            environ={"SCHWAB_MAX_DAILY_LOSS_USD": "bad", "MAX_DAILY_LOSS_USD": "450"},
            limit_callback=lambda _p: -5.0,
        )
        == 450.0
    )

    # runtime_risk_limits_for_daily_loss_axis & resolve_daily_loss_runtime_risk_limits
    assert runtime_risk_limits_for_daily_loss_axis(None) is None
    assert runtime_risk_limits_for_daily_loss_axis(-10.0) is None
    limits = resolve_daily_loss_runtime_risk_limits(
        {"total_equity": 20_000.0},
        max_daily_loss_resolver=lambda p: float(p["total_equity"]) * 0.015 if p else None,
    )
    assert limits is not None
    assert limits.allowed_symbols == ("SPY",)
    assert limits.max_daily_loss_usd == 300.0

    # Invalid callback output fails soft to None (axis omitted)
    assert (
        resolve_daily_loss_runtime_risk_limits(
            {},
            max_daily_loss_resolver=lambda _p: float("nan"),
        )
        is None
    )
