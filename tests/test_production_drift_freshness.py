"""Observation freshness is research admission, not a risk-ban reset."""
from dataclasses import replace
from datetime import date
from unittest.mock import Mock

import pytest

from quant_platform_kit.risk.production_drift_new_risk import (
    production_drift_new_risk_reasons,
    production_drift_status_from_probe_summary,
)
from quant_platform_kit.strategy_lifecycle.contracts import (
    DriftResult, DriftStatus, StrategyPerformanceSnapshot,
)
from quant_platform_kit.strategy_lifecycle.performance_store import (
    _drift_from_dict, _snapshot_from_dict,
)
from quant_platform_kit.strategy_lifecycle.production_drift_health_probe import (
    probe_production_drift_health, probe_production_drift_health_from_store,
)
from quant_platform_kit.strategy_lifecycle.promotion_actionable_runner import run_actionable_research_promotion

CLOCK = date(2026, 9, 8)


def _store(observed: date, *, score: float = 0.8, revision: str = "source-v1"):
    drift = DriftResult(
        strategy_profile="demo", domain="us_equity", as_of=observed,
        drift_score=score, status=DriftStatus.CRITICAL,
        baseline_artifact_id="baseline-v1", baseline_param_set_id="params-v1",
        baseline_param_version=1,
    )
    snapshot = StrategyPerformanceSnapshot(
        strategy_profile="demo", domain="us_equity", platform="test",
        as_of=observed, source_revision=revision,
    )
    return Mock(load_latest_drift=Mock(return_value=drift), load_latest_snapshot=Mock(return_value=snapshot))


@pytest.mark.parametrize(("observed", "reason"), [
    (date(2020, 1, 1), "observation_stale"),
    (date(2026, 9, 9), "observation_in_future"),
])
@pytest.mark.parametrize(("score", "risk"), [(0.8, "critical"), (0.6, "review")])
def test_unusable_observation_never_starts_research_or_clears_known_risk(observed, reason, score, risk):
    summary = probe_production_drift_health_from_store(
        strategy_profile="demo", domain="us_equity", store=_store(observed, score=score),
        evaluation_date=CLOCK,
    )
    assert summary["actionable"] is False
    assert summary["status"] == "unavailable"
    assert summary["reason"] == reason
    assert summary["as_of"] == observed.isoformat()
    assert summary["risk_status"] == risk
    assert production_drift_new_risk_reasons(production_drift_status_from_probe_summary(summary)) == (f"PRODUCTION_DRIFT_{risk.upper()}",)


def test_expired_healthy_is_unavailable_not_healthy():
    summary = probe_production_drift_health_from_store(
        strategy_profile="demo", domain="us_equity", store=_store(date(2020, 1, 1), score=0.2),
        evaluation_date=CLOCK,
    )
    assert summary["status"] == "unavailable"
    assert summary["risk_status"] is None
    assert production_drift_status_from_probe_summary(summary) is None


def test_store_as_of_cannot_relabel_stale_source_as_today():
    summary = probe_production_drift_health_from_store(
        strategy_profile="demo", domain="us_equity", store=_store(date(2020, 1, 1)),
        as_of=CLOCK, evaluation_date=CLOCK,
    )
    assert summary["as_of"] == "2020-01-01"
    assert summary["actionable"] is False


def test_explicit_replay_clock_keeps_source_identity_and_configurable_expiry():
    summary = probe_production_drift_health_from_store(
        strategy_profile="demo", domain="us_equity", store=_store(date(2020, 1, 1)),
        evaluation_date=date(2020, 1, 2), max_age_days=2,
    )
    assert summary["actionable"] is True
    assert summary["as_of"] == "2020-01-01"
    assert summary["evaluated_as_of"] == "2020-01-02"
    assert summary["valid_until"] == "2020-01-03"
    assert summary["source_revision"] == "source-v1"
    assert summary["baseline_artifact_id"] == "baseline-v1"
    assert summary["baseline_param_set_id"] == "params-v1"
    assert summary["baseline_param_version"] == 1


@pytest.mark.parametrize("broken", ["revision", "snapshot_date", "snapshot_profile", "drift_profile"])
def test_missing_or_mismatched_source_cannot_launch_research(broken):
    store = _store(CLOCK)
    if broken == "revision":
        store.load_latest_snapshot.return_value = replace(store.load_latest_snapshot.return_value, source_revision="")
    elif broken == "snapshot_date":
        store.load_latest_snapshot.return_value = replace(store.load_latest_snapshot.return_value, as_of=date(2026, 9, 7))
    elif broken == "snapshot_profile":
        store.load_latest_snapshot.return_value = replace(store.load_latest_snapshot.return_value, strategy_profile="other")
    else:
        store.load_latest_drift.return_value = replace(store.load_latest_drift.return_value, strategy_profile="other")
    summary = probe_production_drift_health_from_store(
        strategy_profile="demo", domain="us_equity", store=store, evaluation_date=CLOCK,
    )
    assert summary["status"] == "unavailable"
    assert summary["actionable"] is False
    if broken == "drift_profile":
        assert summary["risk_status"] is None


@pytest.mark.parametrize("loader,payload", [
    (_drift_from_dict, {"strategy_profile": "demo", "domain": "us_equity", "drift_score": 0.8, "status": "critical"}),
    (_snapshot_from_dict, {"strategy_profile": "demo", "domain": "us_equity", "platform": "test", "drift_score": 0.8}),
])
def test_missing_observation_date_is_not_synthesized(loader, payload):
    record = loader(payload)
    assert record is not None
    assert record.as_of is None
    assert record.to_dict()["as_of"] is None
    store = Mock(load_latest_drift=Mock(return_value=record if loader is _drift_from_dict else None),
                 load_latest_snapshot=Mock(return_value=record if loader is _snapshot_from_dict else None))
    summary = probe_production_drift_health_from_store(
        strategy_profile="demo", domain="us_equity", store=store, evaluation_date=CLOCK,
    )
    assert summary["reason"] == "observation_time_unavailable"
    assert summary["as_of"] is None
    assert summary["actionable"] is False
    assert production_drift_new_risk_reasons(production_drift_status_from_probe_summary(summary)) == ("PRODUCTION_DRIFT_CRITICAL",)


def test_direct_injected_stale_score_is_not_actionable():
    summary = probe_production_drift_health(
        strategy_profile="demo", domain="us_equity", as_of="2020-01-01", drift_score=0.8,
        evaluation_date=CLOCK,
    )
    assert summary["actionable"] is False
    assert summary["as_of"] == "2020-01-01"


def test_stale_record_stops_before_cycle_and_ai_and_fresh_record_keeps_observed_date():
    cycle = Mock(return_value=Mock(to_dict=Mock(return_value={}), state=Mock(value="parked"), live_authority_granted=False))
    bindings = dict(cycle=cycle, optimize=Mock(), record_shadow=Mock(), enforce_backtest_gates=Mock())
    summary = run_actionable_research_promotion(
        strategy_profile="demo", domain="us_equity", from_store=True,
        store=_store(date(2020, 1, 1)), evaluation_date=CLOCK, **bindings,
    )
    assert summary["status"] == "parked"
    cycle.assert_not_called()
    bindings["optimize"].assert_not_called()
    run_actionable_research_promotion(
        strategy_profile="demo", domain="us_equity", from_store=True,
        store=_store(date(2026, 9, 7)), evaluation_date=CLOCK, **bindings,
    )
    assert cycle.call_args.args[0].as_of == date(2026, 9, 7)
    assert cycle.call_args.args[0].source_revision == "source-v1"
    assert cycle.call_args.args[0].baseline_artifact_id == "baseline-v1"


def test_risk_status_field_cannot_exempt_existing_critical_or_treat_unknown_as_healthy():
    assert production_drift_status_from_probe_summary({"status": "critical", "risk_status": "healthy"}) == "critical"
    assert production_drift_status_from_probe_summary({"status": "unavailable", "risk_status": "healthy"}) is None


def test_existing_store_entry_point_rejects_2020_alert_today():
    summary = probe_production_drift_health_from_store(
        strategy_profile="demo", domain="us_equity", store=_store(date(2020, 1, 1)),
    )
    assert summary["actionable"] is False
    assert summary["as_of"] == "2020-01-01"


@pytest.mark.parametrize("invalid", [None, "", "not-a-date", "2026-99-99"])
def test_invalid_stored_date_keeps_strict_risk_evidence(invalid):
    record = _drift_from_dict({"strategy_profile": "demo", "domain": "us_equity",
                              "as_of": invalid, "drift_score": 0.8, "status": "critical"})
    assert record is not None
    assert record.as_of is None
    assert record.to_dict()["as_of"] is None


@pytest.mark.parametrize("age,actionable", [(7, True), (8, False)])
def test_calendar_day_expiry_boundary(age, actionable):
    from datetime import timedelta
    summary = probe_production_drift_health_from_store(
        strategy_profile="demo", domain="us_equity", store=_store(CLOCK - timedelta(days=age)),
        evaluation_date=CLOCK,
    )
    assert summary["actionable"] is actionable


def test_observation_revision_change_is_not_joined_to_old_drift():
    store = _store(CLOCK)
    store.load_latest_drift.return_value = replace(store.load_latest_drift.return_value, source_revision="source-v0")
    summary = probe_production_drift_health_from_store(
        strategy_profile="demo", domain="us_equity", store=store, evaluation_date=CLOCK,
    )
    assert summary["reason"] == "observation_source_mismatch"
    assert summary["actionable"] is False
    assert summary["risk_status"] == "critical"


def test_drift_computation_retains_unknown_time_and_source_revision():
    from quant_platform_kit.strategy_lifecycle.drift_detector import detect_drift
    snapshot = replace(_store(CLOCK).load_latest_snapshot.return_value, as_of=None)
    with pytest.raises(ValueError, match="observation_date_unavailable"):
        detect_drift(snapshot)



def test_unknown_date_dashboard_keeps_other_profiles_and_null_scores(tmp_path):
    from unittest.mock import patch
    from quant_platform_kit.strategy_lifecycle.health_dashboard import build_dashboard
    old = replace(_store(CLOCK).load_latest_snapshot.return_value, as_of=None)
    good = replace(old, strategy_profile="valid", as_of=CLOCK)
    store = Mock()
    prefix = "quant_platform_kit.strategy_lifecycle.health_dashboard."
    with patch(prefix + "_collect_domain_snapshots", return_value={"demo": old, "valid": good}), patch(prefix + "_collect_domain_drifts", return_value={}):
        summary = build_dashboard(store=store, domains=["us_equity"], output_dir=str(tmp_path))
    assert summary["strategy_count"] == 2
    assert summary["unavailable"] == 1
    import json
    rows = json.loads((tmp_path / "strategy_health_dashboard.json").read_text())["strategies"]
    missing = next(row for row in rows if row["strategy_profile"] == "demo")
    assert missing["status"] == "unavailable"
    assert missing["as_of"] is None
    assert missing["overall_score"] is None
    assert next(row for row in rows if row["strategy_profile"] == "valid")["as_of"] == CLOCK.isoformat()
    assert "unavailable" in (tmp_path / "strategy_health_dashboard.md").read_text()
    assert "0001-01-01" not in (tmp_path / "strategy_health_dashboard.json").read_text()


@pytest.mark.parametrize("as_of", [None, date(2020, 1, 1)])
def test_incomplete_or_old_drift_stops_before_issue_and_codex(as_of):
    from unittest.mock import patch
    from quant_platform_kit.strategy_lifecycle.codex_integration import (
        AiOptimizationContext, _process_optimization_decision, call_ai_optimization_decision,
        create_github_issue,
    )
    drift = replace(_store(CLOCK).load_latest_drift.return_value, as_of=as_of)
    with patch("quant_platform_kit.strategy_lifecycle.codex_integration.subprocess.run") as gh, patch("quant_platform_kit.strategy_lifecycle.ai_provider.AiServiceClient.execute") as ai:
        issue = create_github_issue(drift)
        decision = call_ai_optimization_decision(AiOptimizationContext("demo", "us_equity", drift=drift))
        result = _process_optimization_decision(drift, Mock(), dry_run=False, enforce_backtest_gates=Mock(), record_shadow=Mock())
    assert issue["actionable"] is False
    assert decision["optimization_needed"] is False
    assert result["research_promotion_state"] == "parked"
    gh.assert_not_called()
    ai.assert_not_called()


def test_unknown_date_record_cannot_be_saved_as_new_observation(tmp_path):
    from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore
    store = PerformanceStore(local_root=tmp_path)
    for record, save in [(replace(_store(CLOCK).load_latest_drift.return_value, as_of=None), store.save_drift_result),
                         (replace(_store(CLOCK).load_latest_snapshot.return_value, as_of=None), store.save_snapshot)]:
        with pytest.raises(ValueError, match="observation_date_unavailable"):
            save(record)
    assert not list(tmp_path.rglob("*.json"))



def test_automatic_codex_decision_rejects_missing_observation_source_before_ai():
    from unittest.mock import patch
    from quant_platform_kit.strategy_lifecycle.codex_integration import _process_optimization_decision
    store = _store(date.today(), revision="")
    with patch("quant_platform_kit.strategy_lifecycle.codex_integration.call_ai_optimization_decision") as ai:
        result = _process_optimization_decision(store.load_latest_drift.return_value, store, False,
            enforce_backtest_gates=Mock(), record_shadow=Mock())
    assert result["reason"] == "observation_source_unavailable"
    ai.assert_not_called()



@pytest.mark.parametrize("observed,max_age,reason", [
    (date.max, 7, "observation_in_future"),
    (CLOCK, 10**20, "observation_validity_unavailable"),
])
def test_extreme_dates_and_validity_windows_fail_closed_without_overflow(observed, max_age, reason):
    summary = probe_production_drift_health(
        strategy_profile="demo", domain="us_equity", as_of=observed, drift_score=0.8,
        evaluation_date=CLOCK, max_age_days=max_age,
    )
    assert summary["actionable"] is False
    assert summary["reason"] == reason
    assert summary["valid_until"] is None
    assert summary["risk_status"] == "critical"
