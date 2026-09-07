"""Unit tests for production_drift → NEW_RISK reason mapping (Policy A)."""

from __future__ import annotations

from datetime import date

from quant_platform_kit.risk.production_drift_new_risk import (
    normalize_production_drift_status,
    production_drift_new_risk_reasons,
    production_drift_status_from_result,
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
