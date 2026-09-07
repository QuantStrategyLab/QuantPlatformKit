"""Tests for the read-only production drift health evaluator."""

from datetime import date

import pytest

from quant_platform_kit.strategy_lifecycle import (
    ProductionDriftThresholds,
    evaluate_production_drift_health,
)
from quant_platform_kit.strategy_lifecycle.contracts import DriftStatus


def _evaluate(score: float):
    return evaluate_production_drift_health(
        strategy_profile="demo",
        domain="us_equity",
        as_of=date(2026, 9, 7),
        metrics={"drift_score": score},
    )


def test_default_thresholds_are_versioned_and_boundary_statuses_are_exact() -> None:
    thresholds = ProductionDriftThresholds()

    assert thresholds.threshold_version == "production_drift.v1"
    assert _evaluate(thresholds.review_score - 0.01).status is DriftStatus.HEALTHY
    assert _evaluate(thresholds.review_score).status is DriftStatus.REVIEW
    assert _evaluate(thresholds.critical_score).status is DriftStatus.CRITICAL


def test_evaluation_uses_selected_threshold_version() -> None:
    thresholds = ProductionDriftThresholds(
        threshold_version="production_drift.v2",
        review_score=0.40,
        critical_score=0.60,
    )

    result = evaluate_production_drift_health(
        strategy_profile="demo",
        domain="us_equity",
        as_of=date(2026, 9, 7),
        metrics={"drift_score": 0.40},
        thresholds=thresholds,
    )

    assert result.status is DriftStatus.REVIEW


@pytest.mark.parametrize(
    "kwargs",
    [
        {"threshold_version": ""},
        {"review_score": -0.1},
        {"review_score": 0.8, "critical_score": 0.8},
        {"critical_score": 1.1},
        {"review_score": float("nan")},
    ],
)
def test_invalid_thresholds_fail_closed(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ProductionDriftThresholds(**kwargs)


@pytest.mark.parametrize(
    "metrics",
    [
        {},
        {"drift_score": None},
        {"drift_score": float("nan")},
        {"drift_score": -0.1},
        {"drift_score": 1.1},
    ],
)
def test_invalid_metrics_fail_closed(metrics: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        evaluate_production_drift_health(
            strategy_profile="demo",
            domain="us_equity",
            as_of=date(2026, 9, 7),
            metrics=metrics,
        )
