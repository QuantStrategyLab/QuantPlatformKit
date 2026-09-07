"""Tests for explicit actionable-only research promotion."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import Mock, patch

import pytest

from quant_platform_kit.strategy_lifecycle.contracts import DriftResult, DriftStatus
from quant_platform_kit.strategy_lifecycle.promotion_actionable_runner import (
    _bounded_optimize,
    main,
    run_actionable_research_promotion,
)
from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import (
    ResearchPromotionBudget,
    ResearchPromotionState,
)


class _Ticket:
    state = ResearchPromotionState.PARKED
    live_authority_granted = False

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "live_authority_granted": self.live_authority_granted,
        }


def test_non_actionable_drift_parks_without_cycle_or_optimize() -> None:
    cycle = Mock()
    optimize = Mock()

    summary = run_actionable_research_promotion(
        strategy_profile="demo",
        domain="us_equity",
        as_of="2026-09-07",
        drift_score=0.49,
        cycle=cycle,
        optimize=optimize,
    )

    assert summary["status"] == "parked"
    assert summary["reason"] == "drift_not_actionable"
    assert summary["actionable"] is False
    cycle.assert_not_called()
    optimize.assert_not_called()


def test_actionable_drift_calls_cycle_once_with_non_live_budget() -> None:
    cycle = Mock(return_value=_Ticket())
    optimize = Mock()

    summary = run_actionable_research_promotion(
        strategy_profile="demo",
        domain="us_equity",
        as_of="2026-09-07",
        drift_score=0.50,
        cycle=cycle,
        optimize=optimize,
    )

    cycle.assert_called_once()
    kwargs = cycle.call_args.kwargs
    assert kwargs["optimize"] is optimize
    assert kwargs["budget"].allow_live_enablement is False
    assert summary["actionable"] is True
    assert summary["ticket"]["live_authority_granted"] is False


def test_from_store_actionable_drift_calls_cycle_once() -> None:
    class _Store:
        def load_latest_drift(self, domain, strategy_profile):
            return DriftResult(
                strategy_profile=strategy_profile,
                domain=domain,
                as_of=date(2026, 9, 7),
                drift_score=0.75,
                status=DriftStatus.CRITICAL,
            )

        def load_latest_snapshot(self, domain, strategy_profile):
            return None

    cycle = Mock(return_value=_Ticket())
    summary = run_actionable_research_promotion(
        strategy_profile="demo",
        domain="us_equity",
        from_store=True,
        store=_Store(),
        cycle=cycle,
    )

    cycle.assert_called_once()
    assert summary["actionable"] is True


def test_default_optimizer_consumes_cycle_search_budget() -> None:
    drift = DriftResult(
        strategy_profile="demo",
        domain="us_equity",
        as_of=date(2026, 9, 7),
        drift_score=0.75,
        status=DriftStatus.CRITICAL,
    )
    with patch(
        "quant_platform_kit.strategy_lifecycle.param_optimizer.run_optimization"
    ) as optimize:
        _bounded_optimize(
            drift,
            ResearchPromotionBudget(max_search_iterations=7),
        )

    optimize.assert_called_once_with(
        "demo",
        domain="us_equity",
        max_combinations=7,
    )


@pytest.mark.parametrize("score", [-0.01, 1.01, float("nan"), float("inf")])
def test_invalid_score_fails_closed_without_cycle(score: float) -> None:
    cycle = Mock()

    with pytest.raises(ValueError, match="drift_score"):
        run_actionable_research_promotion(
            strategy_profile="demo",
            domain="us_equity",
            as_of="2026-09-07",
            drift_score=score,
            cycle=cycle,
        )

    cycle.assert_not_called()


def test_cli_non_actionable_emits_parked_json_and_exits_zero(capsys) -> None:
    exit_code = main(
        [
            "--strategy-profile",
            "demo",
            "--domain",
            "us_equity",
            "--as-of",
            "2026-09-07",
            "--drift-score",
            "0.20",
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "parked"


def test_cli_actionable_calls_cycle_once(capsys) -> None:
    with patch(
        "quant_platform_kit.strategy_lifecycle.promotion_actionable_runner."
        "run_research_promotion_cycle",
        return_value=_Ticket(),
    ) as cycle:
        exit_code = main(
            [
                "--strategy-profile",
                "demo",
                "--domain",
                "us_equity",
                "--as-of",
                "2026-09-07",
                "--drift-score",
                "0.75",
            ]
        )

    assert exit_code == 0
    cycle.assert_called_once()
    assert json.loads(capsys.readouterr().out)["actionable"] is True


def test_cli_invalid_score_emits_parked_json_and_fails(capsys) -> None:
    exit_code = main(
        [
            "--strategy-profile",
            "demo",
            "--domain",
            "us_equity",
            "--as-of",
            "2026-09-07",
            "--drift-score",
            "nan",
        ]
    )

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert summary == {
        "actionable": False,
        "reason": "invalid_drift_input",
        "status": "parked",
    }
