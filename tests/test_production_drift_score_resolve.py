"""Tests for production drift score sanitize/resolve helpers."""

from __future__ import annotations

from datetime import date

import pytest

from quant_platform_kit.strategy_lifecycle.contracts import (
    DriftResult,
    DriftStatus,
    StrategyPerformanceSnapshot,
)
from quant_platform_kit.strategy_lifecycle.production_drift_evaluator import (
    resolve_injected_drift_score,
    sanitize_unit_drift_score,
)


def test_sanitize_unit_drift_score_accepts_unit_interval() -> None:
    assert sanitize_unit_drift_score(0.0) == 0.0
    assert sanitize_unit_drift_score(0.42) == 0.42
    assert sanitize_unit_drift_score(1) == 1.0


@pytest.mark.parametrize("score", [-0.01, 1.01, float("nan"), float("inf"), None, True, "0.5"])
def test_sanitize_unit_drift_score_rejects_invalid(score: object) -> None:
    with pytest.raises(ValueError):
        sanitize_unit_drift_score(score)


def test_resolve_prefers_drift_result_over_snapshot() -> None:
    drift = DriftResult(
        strategy_profile="demo",
        domain="us_equity",
        as_of=date(2026, 9, 7),
        drift_score=0.8,
        status=DriftStatus.CRITICAL,
    )
    snapshot = StrategyPerformanceSnapshot(
        strategy_profile="demo",
        domain="us_equity",
        platform="test",
        as_of=date(2026, 9, 6),
        drift_score=0.2,
    )
    assert resolve_injected_drift_score(drift=drift, snapshot=snapshot) == 0.8


def test_resolve_falls_back_to_snapshot_score() -> None:
    snapshot = StrategyPerformanceSnapshot(
        strategy_profile="demo",
        domain="us_equity",
        platform="test",
        as_of=date(2026, 9, 6),
        drift_score=0.33,
    )
    assert resolve_injected_drift_score(snapshot=snapshot) == 0.33


def test_resolve_returns_none_when_missing_or_invalid() -> None:
    assert resolve_injected_drift_score() is None
    snapshot = StrategyPerformanceSnapshot(
        strategy_profile="demo",
        domain="us_equity",
        platform="test",
        as_of=date(2026, 9, 6),
        drift_score=None,
    )
    assert resolve_injected_drift_score(snapshot=snapshot) is None
    bad = StrategyPerformanceSnapshot(
        strategy_profile="demo",
        domain="us_equity",
        platform="test",
        as_of=date(2026, 9, 6),
        drift_score=1.5,
    )
    assert resolve_injected_drift_score(snapshot=bad) is None


def test_resolve_omits_score_when_baseline_unavailable() -> None:
    drift = DriftResult(
        strategy_profile="demo",
        domain="us_equity",
        as_of=date(2026, 9, 7),
        drift_score=0.0,
        status=DriftStatus.HEALTHY,
        baseline_available=False,
    )
    snapshot = StrategyPerformanceSnapshot(
        strategy_profile="demo",
        domain="us_equity",
        platform="test",
        as_of=date(2026, 9, 6),
        drift_score=0.2,
    )
    # Must not fall through to snapshot when drift exists but baseline is missing.
    assert resolve_injected_drift_score(drift=drift, snapshot=snapshot) is None
