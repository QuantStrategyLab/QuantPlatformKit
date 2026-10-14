import json
from datetime import datetime, timezone
from unittest.mock import Mock

from quant_platform_kit.strategy_lifecycle.review_deadman import check_lane
from quant_platform_kit.strategy_lifecycle.review_disposition import disposition, GitHubReviewStore
from test_review_loop import Store


def completed(verdict="approve", severity="none"):
    return {"status": "completed", "outcome": "agree_approve" if verdict == "approve" else "agree_reject",
            "reviews": {r: {"verdict": verdict, "severity": severity, "summary": "Frozen synthetic evidence."}
                        for r in ("primary", "secondary", "verification")}, "advisory_only": True,
            "execution_authority_granted": False}


def test_disposition_never_changes_evidence_gate_or_execution_authority():
    store, dot = Store(), Mock()
    dot.request.return_value = {}
    dot.submit.return_value = {"id": "task"}
    dot.result.return_value = {"confirmed": False, "severity": "none", "summary": "Unsupported."}
    result = disposition({}, completed("reject"), identity="evidence:frozen", store=store, dot=dot)
    assert result["outcome"] == "agree_reject"
    assert result["execution_authority_granted"] is False
    assert result["loop"]["disposition"] == "dismissed"
    dot.submit.assert_called_once()


def test_existing_pause_is_injected_and_only_called_for_severe_consensus():
    store, pause = Store(), Mock(return_value=True)
    result = disposition({}, completed("reject", "data_integrity"), identity="drift:cycle",
                         store=store, pause_cycle=pause)
    assert result["loop"]["pause"] == "paused"
    pause.assert_called_once_with("drift:cycle")


def test_absent_opt_in_keeps_original_contract(monkeypatch):
    monkeypatch.delenv("AI_REVIEW_CLOSED_LOOP", raising=False)
    result = completed()
    assert disposition({}, result, identity="frozen") is result


def test_issue_store_refuses_pr_closure_and_never_has_a_trading_actuator(tmp_path):
    api = Mock(side_effect=[[{"number": 9, "body": "", "user": {"login": "github-actions[bot]"}}]])
    store = GitHubReviewStore("frozen", env={"GITHUB_REPOSITORY": "Example/Repo", "REVIEW_VERDICT_DIR": str(tmp_path)}, api=api)
    store.issue = 9
    api.side_effect = None
    api.return_value = {"pull_request": {}}
    import pytest
    with pytest.raises(ValueError):
        store.close({"disposition": "auto_verified"})
    assert api.call_count == 1


def test_deadman_counts_job_skips_and_missing_schedule():
    now = datetime(2026, 11, 10, tzinfo=timezone.utc)
    runs = [{"id": i, "event": "schedule", "created_at": "2026-11-09T00:00:00Z"} for i in range(3)]
    api = Mock(side_effect=[{"workflow_runs": runs}, *[{"total_count": 1, "jobs": [{"name": "drift / drift", "conclusion": "skipped"}]}] * 3])
    unhealthy, outcomes = check_lane(api, "repos/Example/Repo", {"workflow": "drift-check.yml", "job": "drift"}, 3, now)
    assert unhealthy and outcomes == ["skipped"] * 3
    api = Mock(return_value={"workflow_runs": []})
    assert check_lane(api, "repos/Example/Repo", {"workflow": "drift-check.yml", "job": "drift", "interval_hours": 24,
                                                "enabled_at": "2026-11-01T00:00:00Z"}, 3, now)[0]


def test_summary_is_withheld_unless_its_review_loop_verifies(monkeypatch):
    from test_research_summary_v2 import callback, locales
    monkeypatch.setenv("AI_REVIEW_CLOSED_LOOP", "true")
    monkeypatch.setenv("AI_SERVICE_URL", "https://example.test/mcp")
    monkeypatch.setenv("AI_SERVICE_REVIEWERS_JSON", json.dumps([
        {"label": r, "mode": "agent", "profile": r, "model": "configured-dot"}
        for r in ("primary", "secondary", "verification")]))
    from unittest.mock import patch
    summarize, _ = callback({"locales": locales()})
    with patch("quant_platform_kit.strategy_lifecycle.task_review.review_material", return_value={"loop": {"disposition": "confirmed"}}):
        assert summarize({})["status"] == "unavailable"
    with patch("quant_platform_kit.strategy_lifecycle.task_review.review_material", return_value={"loop": {"disposition": "auto_verified"}}):
        assert summarize({})["status"] == "available"


def test_deadman_observes_unavailable_summary_in_successful_host_job():
    run = {"id": 7, "event": "schedule", "created_at": "2026-11-09T00:00:00Z"}
    state = {"run_id": "7", "disposition": "review_unavailable"}
    api = Mock(side_effect=[{"workflow_runs": [run]},
        {"total_count": 1, "jobs": [{"name": "research", "conclusion": "success"}]},
        [{"number": 9, "body": "<!-- advisory-review:test -->", "user": {"login": "github-actions[bot]"}}],
        [{"body": "<!-- advisory-review-loop-v1 " + json.dumps(state) + " -->", "user": {"login": "github-actions[bot]"}}]])
    unhealthy, outcomes = check_lane(api, "repos/Example/Repo", {"workflow": "research.yml", "job": "research"},
                                     1, datetime(2026, 11, 10, tzinfo=timezone.utc))
    assert unhealthy and outcomes == ["unavailable"]


def test_original_drift_alert_is_selected_only_for_exact_frozen_observation(tmp_path):
    observation = {"strategy_profile": "synthetic", "domain": "crypto", "drift_score": .8, "as_of": "2026-11-01"}
    meta = {"schema": "strategy_lifecycle_drift_issue.v1", **observation}
    issue = {"number": 12, "state": "open", "title": "[crypto] Drift CRITICAL: synthetic (score=0.80)",
             "labels": [{"name": "drift-alert"}], "user": {"login": "github-actions[bot]"},
             "body": "```json\n" + json.dumps(meta) + "\n```"}
    api = Mock(return_value=[issue])
    env = {"GITHUB_REPOSITORY": "Example/Repo", "REVIEW_VERDICT_DIR": str(tmp_path)}
    store = GitHubReviewStore("frozen", env=env, api=api, material={"observation": observation})
    assert store._find() == 12
    store = GitHubReviewStore("frozen", env=env, api=api, material={"observation": {**observation, "as_of": "2026-11-02"}})
    assert store._find() is None


def test_invalid_summary_is_recorded_for_independent_monitor(monkeypatch):
    from test_research_summary_v2 import callback
    from unittest.mock import patch
    monkeypatch.setenv("AI_REVIEW_CLOSED_LOOP", "true")
    summarize, _ = callback({"locales": {}})
    with patch("quant_platform_kit.strategy_lifecycle.review_disposition.disposition") as record:
        assert summarize({})["status"] == "unavailable"
        assert record.call_args.args[1]["status"] == "unavailable"
