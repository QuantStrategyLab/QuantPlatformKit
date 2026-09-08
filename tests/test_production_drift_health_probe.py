"""Read-only production drift health probe tests."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import patch

import pytest

from quant_platform_kit.strategy_lifecycle.production_drift_health_probe import (
    main,
    probe_production_drift_health,
    probe_production_drift_health_from_store,
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
        evaluation_date="2026-09-08",
    )

    assert summary == {
        "strategy_profile": "demo", "domain": "us_equity", "as_of": "2026-09-07",
        "evaluated_as_of": "2026-09-08", "valid_until": "2026-09-14", "max_age_days": 7,
        "input_source": "caller_injected",
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
                "--evaluation-date",
                "2026-09-08",
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
        "strategy_profile": "demo", "domain": "us_equity", "as_of": "2026-09-07",
        "evaluated_as_of": "2026-09-08", "valid_until": "2026-09-14", "max_age_days": 7,
        "input_source": "caller_injected",
        "actionable": True,
        "score": 0.6,
        "status": "review",
        "threshold_version": "production_drift.v2",
    }
    optimize.assert_not_called()
    promotion.assert_not_called()


def test_from_store_parks_when_score_unavailable() -> None:
    class _EmptyStore:
        def load_latest_drift(self, domain: str, strategy_profile: str):
            return None

        def load_latest_snapshot(self, domain: str, strategy_profile: str):
            return None

    summary = probe_production_drift_health_from_store(
        strategy_profile="demo",
        domain="us_equity",
        store=_EmptyStore(),  # type: ignore[arg-type]
        evaluation_date="2026-09-08",
    )
    assert summary == {
        "strategy_profile": "demo", "domain": "us_equity", "as_of": None,
        "evaluated_as_of": "2026-09-08", "max_age_days": 7, "input_source": "missing",
        "source_revision": None, "baseline_artifact_id": None,
        "baseline_param_set_id": None, "baseline_param_version": None,
        "status": "parked",
        "score": None,
        "threshold_version": "production_drift.v1",
        "actionable": False,
        "reason": "drift_score_unavailable",
    }


def test_from_store_injects_drift_result_without_optimize() -> None:
    from quant_platform_kit.strategy_lifecycle.contracts import DriftResult, DriftStatus, StrategyPerformanceSnapshot

    class _Store:
        def load_latest_drift(self, domain: str, strategy_profile: str):
            return DriftResult(
                strategy_profile=strategy_profile,
                domain=domain,
                as_of=date(2026, 9, 7),
                drift_score=0.55,
                status=DriftStatus.REVIEW,
            )

        def load_latest_snapshot(self, domain: str, strategy_profile: str):
            return StrategyPerformanceSnapshot(
                strategy_profile=strategy_profile, domain=domain, platform="test",
                as_of=date(2026, 9, 7), source_revision="source-v1",
            )

    with patch(
        "quant_platform_kit.strategy_lifecycle.research_promotion_cycle."
        "run_research_promotion_cycle"
    ) as promotion:
        summary = probe_production_drift_health_from_store(
            strategy_profile="demo",
            domain="us_equity",
            store=_Store(),  # type: ignore[arg-type]
            evaluation_date="2026-09-08",
        )

    assert summary == {
        "strategy_profile": "demo", "domain": "us_equity", "as_of": "2026-09-07",
        "evaluated_as_of": "2026-09-08", "valid_until": "2026-09-14", "max_age_days": 7,
        "input_source": "drift_result", "source_revision": "source-v1",
        "baseline_artifact_id": None, "baseline_param_set_id": None, "baseline_param_version": None,
        "status": "review",
        "score": 0.55,
        "threshold_version": "production_drift.v1",
        "actionable": True,
        "reason": "store_injected",
    }
    promotion.assert_not_called()


def test_cli_from_store_emits_parked_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _EmptyStore:
        def load_latest_drift(self, domain: str, strategy_profile: str):
            return None

        def load_latest_snapshot(self, domain: str, strategy_profile: str):
            return None

    with patch(
        "quant_platform_kit.strategy_lifecycle.production_drift_health_probe."
        "PerformanceStore.from_env",
        return_value=_EmptyStore(),
    ):
        exit_code = main(
            [
                "--strategy-profile",
                "demo",
                "--domain",
                "us_equity",
                "--from-store",
            ]
        )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["reason"] == "drift_score_unavailable"
