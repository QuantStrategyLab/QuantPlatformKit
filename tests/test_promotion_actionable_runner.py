"""Tests for explicit actionable-only research promotion."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(autouse=True)
def _fixed_probe_clock():
    from quant_platform_kit.strategy_lifecycle import production_drift_health_probe as probe
    from datetime import datetime, timezone
    with patch.object(probe, "datetime") as clock:
        clock.now.return_value = datetime(2026, 9, 8, tzinfo=timezone.utc)
        yield

from quant_platform_kit.strategy_lifecycle.contracts import DriftResult, DriftStatus, StrategyPerformanceSnapshot
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
        enforce_backtest_gates=Mock(),
        record_shadow=Mock(),
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
            return StrategyPerformanceSnapshot(
                strategy_profile=strategy_profile, domain=domain, platform="test",
                as_of=date(2026, 9, 7), source_revision="source-v1",
            )

    cycle = Mock(return_value=_Ticket())
    summary = run_actionable_research_promotion(
        strategy_profile="demo",
        domain="us_equity",
        from_store=True,
        store=_Store(),
        cycle=cycle,
        enforce_backtest_gates=Mock(),
        record_shadow=Mock(),
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


def test_cli_actionable_without_research_bindings_parks_before_cycle(capsys) -> None:
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

    assert exit_code == 2
    cycle.assert_not_called()
    result = json.loads(capsys.readouterr().out)
    assert result["actionable"] is True
    assert result["status"] == "parked"
    assert result["reason"] == "research_bindings_unavailable"


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


# Synthetic wiring checks: no provider, broker, or console network is used.
def _run_bound_cycle(*, score=0.75, evidence=None, shadow_kind="paired_shadow", sync=None):
    from tests.test_research_promotion_cycle import _proposal, _promotion_backtest_evidence

    events = []

    def optimize(drift, budget):
        events.append("optimize")
        assert budget.max_search_iterations == 25
        assert budget.max_param_keys == 4
        assert budget.allow_live_enablement is False
        return _proposal()

    def gate(proposal):
        events.append("gate")
        return evidence if evidence is not None else _promotion_backtest_evidence()

    def shadow(proposal):
        events.append("shadow")
        return {"evidence_kind": shadow_kind, "passed": True}

    def publish(ticket):
        events.append("console")
        assert ticket.live_authority_granted is False
        assert ticket.state is ResearchPromotionState.AWAITING_HUMAN
        return sync(ticket) if sync is not None else True

    result = run_actionable_research_promotion(
        strategy_profile="demo_strategy", domain="us_equity", as_of="2026-09-07",
        drift_score=score, optimize=optimize, enforce_backtest_gates=gate,
        record_shadow=shadow, sync_console=publish,
    )
    return result, events


def test_runner_delivers_only_after_strict_gate_and_paired_shadow() -> None:
    result, events = _run_bound_cycle()
    assert events == ["optimize", "gate", "shadow", "console"]
    assert result["status"] == "awaiting_human"
    assert result["console_synced"] is True
    assert result["ticket"]["budget"]["require_paired_shadow"] is True
    assert result["ticket"]["live_authority_granted"] is False


def test_runner_below_threshold_does_not_touch_research_or_console() -> None:
    result, events = _run_bound_cycle(score=0.49)
    assert result["status"] == "parked"
    assert events == []


def test_runner_gate_failure_prevents_shadow_and_console() -> None:
    result, events = _run_bound_cycle(evidence={"status": "FAIL"})
    assert result["status"] == "parked"
    assert result["console_synced"] is None
    assert events == ["optimize", "gate"]


def test_runner_proxy_shadow_cannot_reach_human_queue() -> None:
    result, events = _run_bound_cycle(shadow_kind="proxy_shadow")
    assert result["status"] == "parked"
    assert "paired_shadow_required" in result["ticket"]["notes"]
    assert result["console_synced"] is None
    assert events == ["optimize", "gate", "shadow"]


@pytest.mark.parametrize("result", [False, None, "true", 1])
def test_runner_never_reports_unconfirmed_console_delivery_as_success(result) -> None:
    summary, events = _run_bound_cycle(sync=lambda ticket: result)
    assert summary["status"] == "awaiting_human"
    assert summary["console_synced"] is False
    assert events.count("console") == 1
    assert summary["ticket"]["live_authority_granted"] is False


def test_runner_sync_exception_is_sanitized_and_not_retried() -> None:
    def failed(ticket):
        raise RuntimeError("sensitive provider detail")

    result, events = _run_bound_cycle(sync=failed)
    assert result["status"] == "awaiting_human"
    assert result["console_synced"] is False
    assert "sensitive" not in json.dumps(result)
    assert events.count("console") == 1


def test_runner_binds_existing_console_sync_by_default() -> None:
    captured = []

    def cycle(drift, **kwargs):
        ticket = _Ticket()
        captured.append(kwargs["sync_console"](ticket))
        return ticket

    sync = Mock(return_value=True)
    with patch(
        "quant_platform_kit.strategy_lifecycle.promotion_actionable_runner."
        "make_console_research_promotion_sync", return_value=sync,
    ):
        summary = run_actionable_research_promotion(
            strategy_profile="demo", domain="us_equity", as_of="2026-09-07",
            drift_score=0.75, cycle=cycle, enforce_backtest_gates=Mock(),
            record_shadow=Mock(),
        )
    assert captured == [True]
    assert summary["console_synced"] is True
    sync.assert_called_once()


@pytest.mark.parametrize("broken_gate", ["short_oos", "reused_oos", "missing_fold", "no_purge"])
def test_runner_preserves_strict_wfa_oos_rejection(broken_gate) -> None:
    from tests.test_research_promotion_cycle import _promotion_backtest_evidence

    evidence = _promotion_backtest_evidence()
    if broken_gate == "short_oos":
        evidence["promotion_run"]["locked_oos_end"] = "2024-01-01"
    elif broken_gate == "reused_oos":
        evidence["locked_independent_oos"]["reused_for_selection"] = True
    elif broken_gate == "missing_fold":
        evidence["promotion_run"]["folds"].pop()
    else:
        evidence["promotion_run"]["purge_days"] = 0
    summary, events = _run_bound_cycle(evidence=evidence)
    assert summary["status"] == "parked"
    assert events == ["optimize", "gate"]


def test_runner_adapter_to_console_then_accept_remains_intent_only() -> None:
    from tests.test_paired_shadow_adapter import _observation
    from tests.test_research_promotion_cycle import _proposal, _promotion_backtest_evidence
    from quant_platform_kit.strategy_lifecycle.paired_shadow_adapter import resolve_promotion_shadow_record
    from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import (
        apply_human_promotion_decision, make_console_research_promotion_sync,
        ResearchPromotionTicket,
    )

    post = Mock(return_value=200)
    summary = run_actionable_research_promotion(
        strategy_profile="demo_strategy", domain="us_equity", as_of="2026-09-07",
        drift_score=0.75, optimize=lambda *_: _proposal(),
        enforce_backtest_gates=lambda _: _promotion_backtest_evidence(),
        record_shadow=lambda proposal: resolve_promotion_shadow_record(
            proposal=proposal, collector=lambda **_: _observation(),
            allow_proxy_fallback=False,
        ),
        sync_console=make_console_research_promotion_sync(
            endpoint_url="https://console.invalid/api/internal/sync-research-promotion-ticket",
            sync_token="synthetic-test-only", post_json=post,
            pull_console=lambda _: post.call_args.kwargs["payload"] if post.called else None,
        ),
    )
    assert summary["console_synced"] is True
    post.assert_called_once()
    sent = post.call_args.kwargs["payload"]
    assert sent["state"] == "awaiting_human"
    assert sent["shadow_evidence_kind"] == "paired_shadow"
    assert sent["live_authority_granted"] is False
    ticket = ResearchPromotionTicket.from_dict(summary["ticket"])
    decided = apply_human_promotion_decision(
        ticket, decision="accept", confirmation={
            "target_platform": "ibkr", "execution_mode": "live",
            "risk_profile": "CAPITAL_PRESERVATION",
        },
    )
    assert decided.state is ResearchPromotionState.HUMAN_ACCEPTED
    assert decided.live_authority_granted is False


@pytest.mark.parametrize(
    "gate,shadow,missing",
    [
        (None, None, ["enforce_backtest_gates", "record_shadow"]),
        (None, Mock(), ["enforce_backtest_gates"]),
        (Mock(), None, ["record_shadow"]),
        (False, Mock(), ["enforce_backtest_gates"]),
        (Mock(), {}, ["record_shadow"]),
    ],
)
def test_missing_research_bindings_prevent_optimize_and_sync(gate, shadow, missing) -> None:
    from tests.test_research_promotion_cycle import _proposal

    optimize = Mock(return_value=_proposal())
    sync = Mock()
    summary = run_actionable_research_promotion(
        strategy_profile="demo_strategy", domain="us_equity", as_of="2026-09-07",
        drift_score=0.75, optimize=optimize, enforce_backtest_gates=gate,
        record_shadow=shadow, sync_console=sync,
    )
    optimize.assert_not_called()
    sync.assert_not_called()
    assert summary["status"] == "parked"
    assert summary["reason"] == "research_bindings_unavailable"
    assert summary["missing_bindings"] == missing
    assert summary["console_synced"] is None
