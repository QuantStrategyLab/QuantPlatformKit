"""Synthetic local observations; no model, broker, real shadow or console."""

from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest

from quant_platform_kit.strategy_lifecycle import research_promotion_cycle as cycle
from quant_platform_kit.strategy_lifecycle.promotion_actionable_runner import run_actionable_research_promotion
from tests.test_research_promotion_resume import IDENTITY
from tests.test_research_promotion_cycle import _proposal, _promotion_backtest_evidence
from tests.test_paired_shadow_evidence import _dependencies, _leg, _policy


class Clock(datetime):
    current = datetime(2026, 9, 8, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.current.astimezone(tz)


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    Clock.current = datetime(2026, 9, 8, tzinfo=timezone.utc)
    monkeypatch.setattr(cycle, "datetime", Clock)


def pending(**changes):
    return {"status": "pending", "passed": False, "no_order": True,
            "live_authority_granted": False,
            "retry_at": datetime(2026, 9, 20, tzinfo=timezone.utc).timestamp(), **changes}


def complete():
    from quant_platform_kit.strategy_lifecycle.forward_observation_receipt import build_forward_observation_receipt
    from quant_platform_kit.strategy_lifecycle.paired_shadow_evidence import build_paired_shadow_evidence

    policy = _policy(strategy_profile="demo_strategy", required_trading_sessions=2,
                     review_milestones=(1,), observation_start_session="2026-09-07")
    first = build_forward_observation_receipt(policy=policy, observation_session="2026-09-07",
        observation_index=1, dependency_digests=_dependencies(), evidence_modes=policy.non_live_evidence_modes)
    earlier = build_paired_shadow_evidence(policy=policy, forward_observation_receipt=first,
        baseline_id="baseline", observed_at="2026-09-07T20:00:00Z", input_snapshot_sha256="a" * 64,
        candidate=_leg("candidate"), baseline=_leg("baseline"))
    second = build_forward_observation_receipt(policy=policy, observation_session="2026-09-08",
        observation_index=2, dependency_digests=_dependencies(), evidence_modes=policy.non_live_evidence_modes,
        previous_receipt=first)
    return {"status": "complete", "observation": dict(policy=policy, forward_observation_receipt=second,
        baseline_id="baseline", observed_at="2026-09-08T20:00:00Z", input_snapshot_sha256="a" * 64,
        candidate=_leg("candidate"), baseline=_leg("baseline"), previous_evidence=earlier,
        previous_forward_observation_receipt=first)}


def job(tmp_path, **changes):
    kwargs = dict(strategy_profile="demo_strategy", domain="us_equity", as_of="2026-09-07",
        drift_score=.8, source_revision="observation-v1", evaluation_date="2026-09-08",
        research_identity=IDENTITY, ticket_dir=tmp_path,
        diagnose=Mock(return_value={"optimization_needed": True}), optimize=Mock(return_value=_proposal()),
        enforce_backtest_gates=Mock(return_value=_promotion_backtest_evidence()),
        record_shadow=Mock(return_value=pending()), read_pending_shadow=Mock(return_value=complete()),
        sync_console=Mock(return_value=True), pull_console=Mock(return_value=None))
    return {**kwargs, **changes}


def test_actual_runner_resumes_only_local_shadow_after_original_drift_expires(tmp_path):
    args = job(tmp_path)
    first = run_actionable_research_promotion(**args)
    assert first["status"] == "deferred"
    assert first["ticket"]["state"] == "shadow_recorded"
    assert first["ticket"]["shadow_passed"] is False
    args["sync_console"].assert_not_called()
    Clock.current = datetime(2026, 9, 21, tzinfo=timezone.utc)
    second = run_actionable_research_promotion(**{**args, "evaluation_date": "2026-09-21"})
    assert second["status"] == "awaiting_human"
    assert second["research_key"] == first["research_key"]
    assert second["ticket"]["live_authority_granted"] is False
    assert [args[key].call_count for key in ("diagnose", "optimize", "enforce_backtest_gates",
                                            "record_shadow", "read_pending_shadow", "sync_console")] == [1] * 6


@pytest.mark.parametrize("retry", [None, True, float("nan"), float("inf"), 0])
def test_missing_or_invalid_pending_deadline_never_automatically_reads(tmp_path, retry):
    args = job(tmp_path, record_shadow=Mock(return_value=pending(retry_at=retry)))
    first = run_actionable_research_promotion(**args)
    Clock.current = datetime(2026, 9, 21, tzinfo=timezone.utc)
    second = run_actionable_research_promotion(**{**args, "evaluation_date": "2026-09-21"})
    assert first["status"] == second["status"] == "deferred"
    args["read_pending_shadow"].assert_not_called()
    assert args["record_shadow"].call_count == 1


def test_not_due_shadow_does_not_poll_or_repeat_admission(tmp_path):
    args = job(tmp_path, admit_new_research=Mock(return_value=True))
    run_actionable_research_promotion(**args)
    run_actionable_research_promotion(**args)
    args["read_pending_shadow"].assert_not_called()
    assert args["admit_new_research"].call_count == 1


@pytest.mark.parametrize("case", ["new", "identity", "incomplete", "gate_failed"])
def test_stale_input_cannot_start_or_resume_unfinished_research(tmp_path, case):
    args = job(tmp_path)
    if case != "new":
        first = run_actionable_research_promotion(**args)
        if case == "identity":
            args["research_identity"] = {**IDENTITY, "input_revision": "changed"}
        else:
            ticket = cycle.load_research_promotion_ticket(first["ticket_path"])
            stages = ticket.research_progress["stages"]
            if case == "incomplete":
                del stages["optimize"]
            else:
                stages["backtest"]["result"]["status"] = "FAIL"
            cycle.save_research_promotion_ticket(ticket, first["ticket_path"])
    before = [args[key].call_count for key in ("diagnose", "optimize", "enforce_backtest_gates", "record_shadow")]
    Clock.current = datetime(2026, 9, 21, tzinfo=timezone.utc)
    result = run_actionable_research_promotion(**{**args, "evaluation_date": "2026-09-21"})
    assert result["status"] == "parked"
    assert [args[key].call_count for key in ("diagnose", "optimize", "enforce_backtest_gates", "record_shadow")] == before
    args["read_pending_shadow"].assert_not_called()


@pytest.mark.parametrize("case", ["exception", "invalid_receipt", "missing_previous", "bare_passed", "live", "incomplete_window"])
def test_unknown_or_invalid_shadow_completion_cannot_reach_console_or_retry(tmp_path, case):
    reader = Mock(return_value=complete())
    if case == "exception":
        reader.side_effect = TimeoutError("private material must not escape")
    elif case == "invalid_receipt":
        reader.return_value["observation"]["forward_observation_receipt"]["receipt_sha256"] = "0" * 64
    elif case == "missing_previous":
        del reader.return_value["observation"]["previous_evidence"]
        del reader.return_value["observation"]["previous_forward_observation_receipt"]
    elif case == "bare_passed":
        reader.return_value = {"status": "complete", "evidence_kind": "paired_shadow", "passed": True}
    elif case == "live":
        reader.return_value = pending(live_authority_granted=True)
    else:
        from dataclasses import replace
        value = reader.return_value["observation"]
        value["policy"] = replace(value["policy"], required_trading_sessions=63)
    args = job(tmp_path, read_pending_shadow=reader)
    run_actionable_research_promotion(**args)
    Clock.current = datetime(2026, 9, 21, tzinfo=timezone.utc)
    for _ in range(2):
        result = run_actionable_research_promotion(**{**args, "evaluation_date": "2026-09-21"})
        assert result["status"] == "parked"
        assert "private material" not in str(result)
    assert reader.call_count == 1
    args["sync_console"].assert_not_called()


def test_shadow_read_uses_existing_directory_lock(tmp_path):
    args = job(tmp_path)
    run_actionable_research_promotion(**args)
    Clock.current = datetime(2026, 9, 21, tzinfo=timezone.utc)
    with cycle._research_directory_lock(tmp_path) as acquired:
        assert acquired
        result = run_actionable_research_promotion(**{**args, "evaluation_date": "2026-09-21"})
    assert result["reason"] == "research_in_progress"
    args["read_pending_shadow"].assert_not_called()


def test_pending_reader_can_wait_again_without_restarting_the_experiment(tmp_path):
    next_retry = datetime(2026, 9, 28, tzinfo=timezone.utc).timestamp()
    reader = Mock(side_effect=[pending(retry_at=next_retry), complete()])
    args = job(tmp_path, read_pending_shadow=reader)
    run_actionable_research_promotion(**args)
    for day, calls in [(21, 1), (22, 1), (29, 2)]:
        Clock.current = datetime(2026, 9, day, tzinfo=timezone.utc)
        result = run_actionable_research_promotion(**{**args, "evaluation_date": f"2026-09-{day}"})
        assert result["status"] == ("awaiting_human" if day == 29 else "deferred")
        assert reader.call_count == calls
    assert args["record_shadow"].call_count == args["optimize"].call_count == 1


def test_missing_reader_never_repeats_first_callback_and_explicit_failure_stays_parked(tmp_path):
    args = job(tmp_path, read_pending_shadow=None)
    run_actionable_research_promotion(**args)
    Clock.current = datetime(2026, 9, 21, tzinfo=timezone.utc)
    result = run_actionable_research_promotion(**{**args, "evaluation_date": "2026-09-21"})
    assert result["reason"] == "shadow_reader_unavailable"
    assert args["record_shadow"].call_count == 1
    reader = Mock(return_value={"status": "failed", "passed": False, "evidence_kind": "paired_shadow",
                                "no_order": True, "live_authority_granted": False})
    for _ in range(2):
        result = run_actionable_research_promotion(**{**args, "evaluation_date": "2026-09-21", "read_pending_shadow": reader})
        assert result["status"] == "parked"
    assert reader.call_count == 1
    args["sync_console"].assert_not_called()


@pytest.mark.parametrize("stage_status", ["pending", "completed"])
def test_interrupt_after_shadow_result_save_resumes_without_repeating_callback(tmp_path, monkeypatch, stage_status):
    args = job(tmp_path)
    save = cycle.save_research_promotion_ticket
    if stage_status == "completed":
        run_actionable_research_promotion(**args)
        Clock.current = datetime(2026, 9, 21, tzinfo=timezone.utc)
        args["evaluation_date"] = "2026-09-21"

    def stop(ticket, path):
        save(ticket, path)
        if ticket.research_progress.get("stages", {}).get("shadow", {}).get("status") == stage_status:
            raise SystemExit("synthetic checkpoint boundary")

    monkeypatch.setattr(cycle, "save_research_promotion_ticket", stop)
    with pytest.raises(SystemExit):
        run_actionable_research_promotion(**args)
    monkeypatch.setattr(cycle, "save_research_promotion_ticket", save)
    Clock.current = datetime(2026, 9, 21, tzinfo=timezone.utc)
    result = run_actionable_research_promotion(**{**args, "evaluation_date": "2026-09-21"})
    assert result["status"] == "awaiting_human"
    assert args["read_pending_shadow"].call_count == args["record_shadow"].call_count == 1
    assert args["optimize"].call_count == args["enforce_backtest_gates"].call_count == 1


def test_normal_auto_pilot_passes_reader_through_expired_observation(tmp_path, monkeypatch):
    from quant_platform_kit.strategy_lifecycle import codex_integration as codex, production_drift_health_probe as probe
    from quant_platform_kit.strategy_lifecycle.contracts import StrategyPerformanceSnapshot
    from tests.test_research_promotion_cycle import _drift

    monkeypatch.setattr(probe, "datetime", Clock)
    monkeypatch.setattr(codex, "_run_monitor_phase", Mock(return_value=[]))
    monkeypatch.setattr(codex, "_run_drift_phase", Mock(return_value=([_drift()], [_drift()])))
    ai = Mock(return_value={"optimization_needed": True})
    monkeypatch.setattr(codex, "call_ai_optimization_decision", ai)
    from quant_platform_kit.strategy_lifecycle import ai_reviewer
    monkeypatch.setattr(ai_reviewer, "review_proposal", Mock(return_value=Mock(verdict="approve", to_dict=lambda: {})))
    store = Mock(local_root=tmp_path)
    store.load_latest_snapshot.return_value = StrategyPerformanceSnapshot(strategy_profile="demo_strategy", domain="us_equity",
        platform="test", as_of=date(2026, 9, 7), source_revision="observation-v1")
    args = job(tmp_path)
    kwargs = {key: args[key] for key in ("research_identity", "optimize", "enforce_backtest_gates", "record_shadow",
                                         "read_pending_shadow", "sync_console", "pull_console")}
    first = codex.run_auto_pilot_cycle("us_equity", store=store, create_issues=False, **kwargs)
    assert first["actions"][0]["research_promotion_state"] == "deferred"
    Clock.current = datetime(2026, 9, 21, tzinfo=timezone.utc)
    second = codex.run_auto_pilot_cycle("us_equity", store=store, create_issues=False, **kwargs)
    assert second["actions"][0]["research_promotion_state"] == "awaiting_human"
    assert ai.call_count == args["optimize"].call_count == args["enforce_backtest_gates"].call_count == 1
    assert args["read_pending_shadow"].call_count == 1


@pytest.mark.parametrize("decision", ["accept", "reject"])
def test_actual_caller_recovers_unknown_console_delivery_and_human_decision_after_sixty_days(tmp_path, decision):
    from tests.test_research_promotion_reconciliation import remote_decision

    args = job(tmp_path, sync_console=Mock(side_effect=TimeoutError("private uncertain write")))
    run_actionable_research_promotion(**args)
    Clock.current = datetime(2026, 9, 21, tzinfo=timezone.utc)
    ready = run_actionable_research_promotion(**{**args, "evaluation_date": "2026-09-21"})
    assert ready["status"] == "awaiting_human" and ready["console_synced"] is False
    local = cycle.load_research_promotion_ticket(ready["ticket_path"])
    args["pull_console"].return_value = remote_decision(local, decision)
    Clock.current = datetime(2026, 11, 21, tzinfo=timezone.utc)
    for _ in range(2):
        recovered = run_actionable_research_promotion(**{**args, "evaluation_date": "2026-11-21"})
        assert recovered["status"] == ("human_accepted" if decision == "accept" else "human_rejected")
        assert recovered["ticket"]["live_authority_granted"] is False
    assert args["pull_console"].call_count == args["sync_console"].call_count == 1
    assert [args[key].call_count for key in ("diagnose", "optimize", "enforce_backtest_gates",
                                            "record_shadow", "read_pending_shadow")] == [1] * 5


@pytest.mark.parametrize("case", ["missing_stage", "changed_candidate"])
def test_stale_awaiting_without_matching_completed_checkpoint_cannot_read_console(tmp_path, case):
    args = job(tmp_path)
    run_actionable_research_promotion(**args)
    Clock.current = datetime(2026, 9, 21, tzinfo=timezone.utc)
    ready = run_actionable_research_promotion(**{**args, "evaluation_date": "2026-09-21"})
    local = cycle.load_research_promotion_ticket(ready["ticket_path"])
    if case == "missing_stage":
        del local.research_progress["stages"]["backtest"]
    else:
        local.proposed_params = {"a": 999}
    cycle.save_research_promotion_ticket(local, ready["ticket_path"])
    result = run_actionable_research_promotion(**{**args, "evaluation_date": "2026-11-21"})
    assert result["status"] == "parked"
    args["pull_console"].assert_not_called()
    assert args["sync_console"].call_count == 1
