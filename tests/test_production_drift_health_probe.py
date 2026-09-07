"""Read-only production drift health probe tests."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from quant_platform_kit.strategy_lifecycle.production_drift_health_probe import (
    main,
    probe_production_drift_health,
)


@pytest.mark.parametrize(
    ("score", "status", "actionable"),
    [
        (0.49, "healthy", False),
        (0.50, "review", True),
        (0.75, "critical", True),
    ],
)
def test_probe_reports_only_actionable_review_or_critical(
    score: float,
    status: str,
    actionable: bool,
) -> None:
    summary = probe_production_drift_health(
        strategy_profile="demo",
        domain="us_equity",
        as_of="2026-09-07",
        drift_score=score,
    )

    assert summary == {
        "status": status,
        "score": score,
        "threshold_version": "production_drift.v1",
        "actionable": actionable,
    }


@pytest.mark.parametrize("score", [-0.01, 1.01, float("nan"), float("inf")])
def test_probe_invalid_score_fails_closed(score: float) -> None:
    with pytest.raises(ValueError):
        probe_production_drift_health(
            strategy_profile="demo",
            domain="us_equity",
            as_of="2026-09-07",
            drift_score=score,
        )


def test_cli_emits_json_without_triggering_optimization(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with (
        patch("quant_platform_kit.strategy_lifecycle.cli._run_optimize") as optimize,
        patch(
            "quant_platform_kit.strategy_lifecycle.research_promotion_cycle."
            "run_research_promotion_cycle"
        ) as promotion,
    ):
        exit_code = main(
            [
                "--strategy-profile",
                "demo",
                "--domain",
                "us_equity",
                "--as-of",
                "2026-09-07",
                "--drift-score",
                "0.60",
                "--threshold-version",
                "production_drift.v2",
                "--review",
                "0.40",
                "--critical",
                "0.80",
            ]
        )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "actionable": True,
        "score": 0.6,
        "status": "review",
        "threshold_version": "production_drift.v2",
    }
    optimize.assert_not_called()
    promotion.assert_not_called()
