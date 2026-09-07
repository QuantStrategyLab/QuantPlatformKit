"""Unit tests for production_drift → NEW_RISK reason mapping (Policy A)."""

from __future__ import annotations

from datetime import date

from quant_platform_kit.risk.production_drift_new_risk import (
    normalize_production_drift_status,
    production_drift_new_risk_reasons,
    production_drift_status_from_probe_summary,
    production_drift_status_from_result,
    resolve_production_drift_status_from_store,
)
from quant_platform_kit.strategy_lifecycle.contracts import DriftResult, DriftStatus


def test_absent_and_non_actionable_yield_no_reasons() -> None:
    assert production_drift_new_risk_reasons(None) == ()
    assert production_drift_new_risk_reasons("") == ()
    assert production_drift_new_risk_reasons("healthy") == ()
    assert production_drift_new_risk_reasons("watch") == ()
    assert production_drift_new_risk_reasons(DriftStatus.HEALTHY) == ()
    assert production_drift_new_risk_reasons(DriftStatus.WATCH) == ()


def test_actionable_statuses_ban_new_risk_only() -> None:
    assert production_drift_new_risk_reasons("review") == ("PRODUCTION_DRIFT_REVIEW",)
    assert production_drift_new_risk_reasons("CRITICAL") == ("PRODUCTION_DRIFT_CRITICAL",)
    assert production_drift_new_risk_reasons(DriftStatus.REVIEW) == (
        "PRODUCTION_DRIFT_REVIEW",
    )
    assert production_drift_new_risk_reasons(DriftStatus.CRITICAL) == (
        "PRODUCTION_DRIFT_CRITICAL",
    )


def test_invalid_status_fails_closed() -> None:
    assert production_drift_new_risk_reasons("maybe") == (
        "PRODUCTION_DRIFT_STATUS_INVALID_FAIL_CLOSED",
    )
    assert production_drift_new_risk_reasons(1.5) == (
        "PRODUCTION_DRIFT_STATUS_INVALID_FAIL_CLOSED",
    )


def test_status_from_drift_result() -> None:
    drift = DriftResult(
        strategy_profile="demo",
        domain="us_equity",
        as_of=date(2026, 9, 7),
        drift_score=0.8,
        status=DriftStatus.CRITICAL,
    )
    assert production_drift_status_from_result(drift) == "critical"
    assert normalize_production_drift_status(" Review ") == "review"
    assert production_drift_status_from_result(None) is None


def test_status_from_result_omits_when_baseline_unavailable() -> None:
    drift = DriftResult(
        strategy_profile="demo",
        domain="us_equity",
        as_of=date(2026, 9, 7),
        drift_score=0.0,
        status=DriftStatus.HEALTHY,
        baseline_available=False,
    )
    assert production_drift_status_from_result(drift) is None



def test_probe_summary_parked_omits_status() -> None:
    assert production_drift_status_from_probe_summary(None) is None
    assert (
        production_drift_status_from_probe_summary(
            {"status": "parked", "actionable": False}
        )
        is None
    )
    assert (
        production_drift_status_from_probe_summary(
            {"status": "unavailable", "actionable": False}
        )
        is None
    )


def test_probe_summary_maps_allowed_statuses() -> None:
    assert production_drift_status_from_probe_summary({"status": "review"}) == "review"
    assert production_drift_status_from_probe_summary({"status": "critical"}) == "critical"
    assert production_drift_status_from_probe_summary({"status": "healthy"}) == "healthy"
    assert production_drift_status_from_probe_summary({"status": "WATCH"}) == "watch"


def test_resolve_from_store_uses_probe() -> None:
    calls: list[dict[str, object]] = []

    def fake_probe(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {"status": "review", "actionable": True}

    assert (
        resolve_production_drift_status_from_store(
            strategy_profile="demo",
            domain="us_equity",
            as_of=date(2026, 9, 7),
            probe=fake_probe,
        )
        == "review"
    )
    assert len(calls) == 1
    assert calls[0]["strategy_profile"] == "demo"
    assert calls[0]["domain"] == "us_equity"


def test_resolve_from_store_probe_error_fail_soft() -> None:
    def boom(**_kwargs: object) -> dict[str, object]:
        raise RuntimeError("store down")

    assert (
        resolve_production_drift_status_from_store(
            strategy_profile="demo",
            domain="us_equity",
            probe=boom,
        )
        is None
    )


def test_resolve_from_store_empty_profile_skips_probe() -> None:
    def should_not_run(**_kwargs: object) -> dict[str, object]:
        raise AssertionError("probe must not be called")

    assert (
        resolve_production_drift_status_from_store(
            strategy_profile="",
            domain="us_equity",
            probe=should_not_run,
        )
        is None
    )
    assert (
        resolve_production_drift_status_from_store(
            strategy_profile="demo",
            domain="  ",
            probe=should_not_run,
        )
        is None
    )
