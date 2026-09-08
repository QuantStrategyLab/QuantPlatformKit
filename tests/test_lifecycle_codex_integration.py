import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(autouse=True)
def _fixed_probe_clock():
    from quant_platform_kit.strategy_lifecycle import production_drift_health_probe as probe
    from datetime import datetime, timezone
    with patch.object(probe, "datetime") as clock:
        clock.now.return_value = datetime(2026, 9, 8, tzinfo=timezone.utc)
        yield

from quant_platform_kit.strategy_lifecycle.codex_integration import (
    AutoIssueConfig,
    _process_optimization_decision,
    _run_drift_phase,
    create_github_issue,
)
from quant_platform_kit.strategy_lifecycle.contracts import DriftResult, DriftStatus, StrategyPerformanceSnapshot
from tests.test_research_promotion_resume import IDENTITY


def test_drift_phase_excludes_suppressed_results_from_automation() -> None:
    suppressed = DriftResult(
        strategy_profile="missing-baseline",
        domain="us_equity",
        as_of=date(2026, 7, 11),
        drift_score=0.0,
        status=DriftStatus.REVIEW,
        alert_suppressed=True,
        baseline_available=False,
    )
    critical = DriftResult(
        strategy_profile="active-baseline",
        domain="us_equity",
        as_of=date(2026, 7, 11),
        drift_score=0.8,
        status=DriftStatus.CRITICAL,
    )

    with patch(
        "quant_platform_kit.strategy_lifecycle.drift_detector.run_drift_detection",
        return_value=[suppressed, critical],
    ):
        drifts, alerts = _run_drift_phase("us_equity", Mock())

    assert drifts == [suppressed, critical]
    assert alerts == [critical]


def test_create_github_issue_reuses_matching_open_issue() -> None:
    drift = DriftResult(
        strategy_profile="us-core",
        domain="us_equity",
        as_of=date(2026, 9, 7),
        drift_score=0.8,
        status=DriftStatus.CRITICAL,
    )
    title = "[us_equity] Drift CRITICAL: us-core (score=0.80)"
    existing_issue = {
        "number": 42,
        "title": title,
        "url": "https://github.com/QuantStrategyLab/UsEquityStrategies/issues/42",
    }
    with patch(
        "quant_platform_kit.strategy_lifecycle.codex_integration.subprocess.run",
        return_value=Mock(returncode=0, stdout=json.dumps([existing_issue]), stderr=""),
    ) as run:
        result = create_github_issue(
            drift,
            config=AutoIssueConfig(owner="QuantStrategyLab", repo="UsEquityStrategies"),
        )

    assert result["issue_url"] == existing_issue["url"]
    assert result["issue_number"] == 42
    assert result["deduplicated"] is True
    assert run.call_count == 1
    assert run.call_args.args[0][:3] == ["gh", "issue", "list"]


def _critical():
    return DriftResult(strategy_profile="demo_strategy", domain="us_equity",
                       as_of=date(2026, 9, 7), drift_score=0.8, status=DriftStatus.CRITICAL)


def test_automatic_research_requires_bindings_before_ai_or_optimization():
    with patch("quant_platform_kit.strategy_lifecycle.codex_integration.call_ai_optimization_decision") as ai:
        result = _process_optimization_decision(_critical(), SimpleNamespace(), dry_run=False)
    ai.assert_not_called()
    assert result["reason"] == "research_bindings_unavailable"
    assert result["execution_authorized"] is False


@pytest.mark.parametrize("gate_passes,risk_passes", [(True, True), (False, True), (True, False)])
def test_autopilot_runs_bounded_strict_research_to_human_queue(tmp_path, gate_passes, risk_passes):
    from quant_platform_kit.strategy_lifecycle.codex_integration import run_auto_pilot_cycle
    from quant_platform_kit.strategy_lifecycle.paired_shadow_adapter import resolve_promotion_shadow_record
    from tests.test_paired_shadow_adapter import _observation
    from tests.test_research_promotion_cycle import _proposal, _promotion_backtest_evidence
    from dataclasses import replace
    from quant_platform_kit.strategy_lifecycle.contracts import BacktestResult

    events = []
    store = SimpleNamespace(local_root=tmp_path, load_latest_snapshot=lambda *_: StrategyPerformanceSnapshot(
        strategy_profile="demo_strategy", domain="us_equity", platform="test", as_of=date(2026, 9, 7), source_revision="source-v1"))

    def decision(*args, **kwargs):
        events.append("codex")
        return {"optimization_needed": True, "recommended_method": "grid_search"}

    def optimize(drift, budget):
        events.append("optimize")
        assert budget.max_search_iterations == 25
        assert budget.max_param_keys == 4
        assert budget.require_paired_shadow is True
        return replace(_proposal(recommendation="research_candidate"), confidence=0.9,
            proposed_metrics=BacktestResult(strategy_profile="demo_strategy", domain="us_equity",
                param_set_id="synthetic", params={"a": 2, "b": 3}, sharpe_ratio=1.2,
                max_drawdown=-0.2 if risk_passes else -0.6, observation_count=252))

    def gates(proposal):
        events.append("gates")
        return _promotion_backtest_evidence() if gate_passes else {"status": "FAIL"}

    def shadow(proposal):
        events.append("shadow")
        return resolve_promotion_shadow_record(proposal=proposal,
            collector=lambda **_: _observation(), allow_proxy_fallback=False)

    def sync(ticket):
        events.append("console")
        assert ticket.live_authority_granted is False
        return True

    prefix = "quant_platform_kit.strategy_lifecycle.codex_integration."
    with (patch(prefix + "_run_monitor_phase", return_value=[]),
          patch(prefix + "_run_drift_phase", return_value=([_critical()], [_critical()])),
          patch(prefix + "call_ai_optimization_decision", side_effect=decision)):
        result = run_auto_pilot_cycle("us_equity", store=store, create_issues=False,
            optimize=optimize, enforce_backtest_gates=gates,
            record_shadow=shadow, sync_console=sync, research_identity=IDENTITY)
    action = result["actions"][0]
    assert events == (["codex", "optimize", "gates", "shadow", "console"] if gate_passes and risk_passes
                      else ["codex", "optimize", "gates"] if risk_passes else ["codex", "optimize"])
    assert action["research_promotion_state"] == ("awaiting_human" if gate_passes and risk_passes else "parked")
    assert action["execution_authorized"] is False
    saved = json.loads(next((tmp_path / "research_promotion_tickets").glob("*.json")).read_text())
    assert saved["live_authority_granted"] is False
    assert saved["state"] == action["research_promotion_state"]


@pytest.mark.parametrize("status", [DriftStatus.HEALTHY, DriftStatus.WATCH])
def test_autopilot_non_actionable_has_zero_ai_or_research(status):
    from quant_platform_kit.strategy_lifecycle.codex_integration import run_auto_pilot_cycle
    drift = _critical()
    drift = DriftResult(strategy_profile=drift.strategy_profile, domain=drift.domain,
                        as_of=drift.as_of, drift_score=0.3, status=status)
    prefix = "quant_platform_kit.strategy_lifecycle.codex_integration."
    optimize = Mock()
    with (patch(prefix + "_run_monitor_phase", return_value=[]),
          patch(prefix + "_run_drift_phase", return_value=([drift], [drift])),
          patch(prefix + "call_ai_optimization_decision") as ai):
        result = run_auto_pilot_cycle("us_equity", store=SimpleNamespace(), create_issues=False,
            optimize=optimize, enforce_backtest_gates=Mock(), record_shadow=Mock())
    assert result["actions"] == []
    ai.assert_not_called()
    optimize.assert_not_called()


@pytest.mark.parametrize("success,output,needed", [
    (True, '{"optimization_needed":true,"recommended_method":"grid_search"}', True),
    (False, '{"optimization_needed":true}', False),
    (True, '{"optimization_needed":"true"}', False),
    (True, '{"optimization_needed":true,"recommended_method":"bayesian"}', False),
    (True, 'not json', False),
    (True, '[]', False),
])
def test_optimization_decision_is_codex_only_with_no_paid_fallback(success, output, needed):
    from quant_platform_kit.strategy_lifecycle.codex_integration import AiOptimizationContext, call_ai_optimization_decision
    from quant_platform_kit.strategy_lifecycle.ai_provider import AiProviderId
    with patch("quant_platform_kit.strategy_lifecycle.ai_provider.AiServiceClient") as factory:
        client = factory.return_value
        client.execute.return_value = SimpleNamespace(success=success, output=output, provider="codex")
        result = call_ai_optimization_decision(AiOptimizationContext("demo_strategy", "us_equity", drift=_critical()))
    config = factory.call_args.args[0]
    assert config.primary.provider is AiProviderId.CODEX_VPS
    assert config.fallback == ()
    assert config.reviewers == ()
    client.execute.assert_called_once()
    assert client.execute.call_args.kwargs["research_stage"] == "optimization"
    client.review.assert_not_called()
    assert result["optimization_needed"] is needed


def test_codex_deferral_is_pending_instead_of_a_negative_research_recommendation(tmp_path):
    from datetime import datetime, timezone
    from quant_platform_kit.strategy_lifecycle.codex_integration import _process_optimization_decision
    retry_at = datetime.now(timezone.utc).timestamp() + 3600
    store = Mock(local_root=tmp_path)
    store.load_latest_snapshot.return_value = StrategyPerformanceSnapshot(
        strategy_profile="demo_strategy", domain="us_equity", platform="test", as_of=date(2026, 9, 7), source_revision="source-v1")
    optimize = Mock()
    with patch("quant_platform_kit.strategy_lifecycle.ai_provider.AiServiceClient") as factory:
        factory.return_value.execute.return_value = SimpleNamespace(success=False, provider="codex", output="",
            raw={"status": "deferred", "retry_at": retry_at})
        result = _process_optimization_decision(_critical(), store, False,
            optimize=optimize, enforce_backtest_gates=Mock(), record_shadow=Mock(), research_identity=IDENTITY)
    assert result["research_promotion_state"] == "deferred"
    assert result["retry_at"] == retry_at
    optimize.assert_not_called()


def test_codex_failure_never_simulates_success_or_leaks_error():
    from quant_platform_kit.strategy_lifecycle.codex_integration import AiOptimizationContext, call_ai_optimization_decision
    with patch("quant_platform_kit.strategy_lifecycle.ai_provider.AiServiceClient", side_effect=ImportError("sensitive")):
        result = call_ai_optimization_decision(AiOptimizationContext("demo_strategy", "us_equity", drift=_critical()))
    assert result["optimization_needed"] is False
    assert "sensitive" not in json.dumps(result)
