"""Durable research stages, using synthetic evidence and no external services."""

from dataclasses import replace
from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

import pytest

from quant_platform_kit.strategy_lifecycle import research_promotion_cycle as cycle
from tests.test_research_promotion_cycle import _drift, _proposal, _promotion_backtest_evidence
from tests.test_research_promotion_reconciliation import remote_decision


IDENTITY = {
    "code_revision": "frozen-code-v1",
    "input_revision": "frozen-input-v1",
    "param_space_revision": "bounded-space-v1",
    "cost_model_revision": "cost-v1",
    "validator_revision": "strict-validator-v1",
}


def invoke(tmp_path, **overrides):
    kwargs = dict(
        research_identity=IDENTITY, ticket_dir=tmp_path,
        optimize=Mock(return_value=_proposal()),
        enforce_backtest_gates=Mock(return_value=_promotion_backtest_evidence()),
        record_shadow=Mock(return_value={"evidence_kind": "paired_shadow", "passed": True,
                                        "paired_shadow_evidence_sha256": "a" * 64}),
        sync_console=Mock(return_value=True), pull_console=Mock(return_value=None),
        evaluation_date=date(2026, 9, 8),
    )
    kwargs.update(overrides)
    drift = kwargs.pop("drift", replace(_drift(), source_revision="observation-v1"))
    return cycle.run_saved_research_promotion_cycle(drift, **kwargs)


def test_same_frozen_input_does_not_repeat_completed_stages_or_console_post(tmp_path):
    optimize, gates, shadow, sync = (Mock(return_value=value) for value in
        (_proposal(), _promotion_backtest_evidence(),
         {"evidence_kind": "paired_shadow", "passed": True}, True))
    first = invoke(tmp_path, optimize=optimize, enforce_backtest_gates=gates,
                   record_shadow=shadow, sync_console=sync)
    second = invoke(tmp_path, optimize=optimize, enforce_backtest_gates=gates,
                    record_shadow=shadow, sync_console=sync)
    assert first["status"] == second["status"] == "awaiting_human"
    assert first["ticket"]["ticket_id"] == second["ticket"]["ticket_id"]
    assert second["resumed"] is True
    assert [fn.call_count for fn in (optimize, gates, shadow, sync)] == [1, 1, 1, 1]
    assert "research_progress" not in first["ticket"]  # local state is never QRT material


@pytest.mark.parametrize("field", list(IDENTITY))
def test_changed_binding_starts_a_new_experiment(tmp_path, field):
    first = invoke(tmp_path)
    second = invoke(tmp_path, research_identity={**IDENTITY, field: "changed-v2"})
    assert first["research_key"] != second["research_key"]
    assert first["ticket"]["ticket_id"] != second["ticket"]["ticket_id"]


def test_restart_after_saved_proposal_resumes_gate_without_optimizer(tmp_path):
    save = cycle.save_research_promotion_ticket

    def stop_after_proposal(ticket, path):
        result = save(ticket, path)
        if ticket.research_progress.get("stages", {}).get("optimize", {}).get("status") == "completed":
            raise SystemExit("synthetic process stop between stages")
        return result

    optimize = Mock(return_value=_proposal())
    gates = Mock(return_value=_promotion_backtest_evidence())
    with patch.object(cycle, "save_research_promotion_ticket", side_effect=stop_after_proposal):
        with pytest.raises(SystemExit):
            invoke(tmp_path, optimize=optimize, enforce_backtest_gates=gates)
    result = invoke(tmp_path, optimize=optimize, enforce_backtest_gates=gates)
    assert result["status"] == "awaiting_human"
    assert optimize.call_count == gates.call_count == 1


@pytest.mark.parametrize("stage", ["optimize", "enforce_backtest_gates", "record_shadow", "diagnose"])
def test_unknown_stage_outcome_is_not_retried(tmp_path, stage):
    callback = Mock(side_effect=TimeoutError("private data must not escape"))
    first = invoke(tmp_path, **{stage: callback})
    second = invoke(tmp_path, **{stage: callback})
    assert first["reason"] == second["reason"] == "research_outcome_unknown"
    assert callback.call_count == 1
    assert "private data" not in str(first) + str(second)


def test_unknown_console_write_recovers_only_by_get(tmp_path):
    sync = Mock(side_effect=TimeoutError("sensitive"))
    first = invoke(tmp_path, sync_console=sync)
    local = cycle.load_research_promotion_ticket(first["ticket_path"])
    pull = Mock(return_value=remote_decision(local, "reject"))
    second = invoke(tmp_path, sync_console=sync, pull_console=pull)
    third = invoke(tmp_path, sync_console=sync, pull_console=pull)
    assert second["status"] == third["status"] == "human_rejected"
    assert sync.call_count == pull.call_count == 1
    assert second["ticket"]["live_authority_granted"] is False
    assert cycle.load_research_promotion_ticket(first["ticket_path"]).research_progress


def test_same_evidence_rejected_candidate_does_not_restart_ai(tmp_path):
    diagnose = Mock(return_value={"optimization_needed": False})
    first = invoke(tmp_path, diagnose=diagnose)
    second = invoke(tmp_path, diagnose=diagnose)
    assert first["status"] == second["status"] == "parked"
    assert diagnose.call_count == 1


@pytest.mark.parametrize("overrides", [
    {"enforce_backtest_gates": None}, {"record_shadow": None},
    {"research_identity": {}}, {"evaluation_date": date(2026, 9, 20)},
    {"drift": replace(_drift(), source_revision="")},
])
def test_invalid_or_stale_input_and_missing_bindings_reject_before_ai(tmp_path, overrides):
    diagnose, optimize = Mock(), Mock()
    result = invoke(tmp_path, diagnose=diagnose, optimize=optimize, **overrides)
    assert result["status"] == "parked"
    diagnose.assert_not_called()
    optimize.assert_not_called()


def test_wrong_proposal_target_never_reaches_gate_or_shadow(tmp_path):
    gates, shadow = Mock(), Mock()
    result = invoke(tmp_path, optimize=Mock(return_value=replace(_proposal(), domain="cn_equity")),
                    enforce_backtest_gates=gates, record_shadow=shadow)
    assert result["status"] == "parked"
    gates.assert_not_called()
    shadow.assert_not_called()


def test_shared_directory_limits_concurrency_before_ai(tmp_path):
    nested = []

    def optimize(*_):
        nested.append(invoke(tmp_path, research_identity={**IDENTITY, "input_revision": "next"}))
        return _proposal()

    invoke(tmp_path, optimize=optimize)
    assert nested[0]["status"] == "deferred"
    assert nested[0]["reason"] == "research_in_progress"


def test_actionable_runner_uses_saved_cycle(tmp_path):
    from quant_platform_kit.strategy_lifecycle.promotion_actionable_runner import run_actionable_research_promotion

    optimize = Mock(return_value=_proposal())
    kwargs = dict(strategy_profile="demo_strategy", domain="us_equity", as_of="2026-09-07",
                  drift_score=0.8, source_revision="observation-v1", evaluation_date="2026-09-08",
                  optimize=optimize, enforce_backtest_gates=Mock(return_value=_promotion_backtest_evidence()),
                  record_shadow=Mock(return_value={"evidence_kind": "paired_shadow", "passed": True}),
                  sync_console=Mock(return_value=True), pull_console=Mock(return_value=None),
                  ticket_dir=tmp_path, research_identity=IDENTITY)
    first = run_actionable_research_promotion(**kwargs)
    second = run_actionable_research_promotion(**kwargs)
    assert first["status"] == second["status"] == "awaiting_human"
    assert optimize.call_count == 1


def test_normal_cycle_reuses_declined_diagnosis_across_runs(tmp_path):
    from quant_platform_kit.strategy_lifecycle.codex_integration import run_auto_pilot_cycle
    from quant_platform_kit.strategy_lifecycle.contracts import StrategyPerformanceSnapshot

    store = Mock(local_root=tmp_path)
    store.load_latest_snapshot.return_value = StrategyPerformanceSnapshot(
        strategy_profile="demo_strategy", domain="us_equity", platform="test", as_of=date(2026, 9, 7),
        source_revision="observation-v1")
    prefix = "quant_platform_kit.strategy_lifecycle.codex_integration."
    with patch(prefix + "_run_monitor_phase", return_value=[]), \
            patch(prefix + "_run_drift_phase", return_value=([_drift()], [_drift()])), \
            patch(prefix + "_drift_freshness_reason", return_value=None), \
            patch(prefix + "call_ai_optimization_decision", return_value={"optimization_needed": False}) as ai:
        for _ in range(2):
            result = run_auto_pilot_cycle("us_equity", store=store, create_issues=False,
                research_identity=IDENTITY, optimize=Mock(), enforce_backtest_gates=Mock(),
                record_shadow=Mock(), pull_console=Mock(return_value=None))
            assert result["actions"][0]["research_promotion_state"] == "parked"
    assert ai.call_count == 1


def test_automatic_cycle_missing_frozen_identity_does_not_call_ai(tmp_path):
    from quant_platform_kit.strategy_lifecycle.codex_integration import _process_optimization_decision
    from quant_platform_kit.strategy_lifecycle.contracts import StrategyPerformanceSnapshot

    store = Mock(local_root=tmp_path)
    store.load_latest_snapshot.return_value = StrategyPerformanceSnapshot(
        strategy_profile="demo_strategy", domain="us_equity", platform="test", as_of=date(2026, 9, 7),
        source_revision="observation-v1")
    prefix = "quant_platform_kit.strategy_lifecycle.codex_integration."
    with patch(prefix + "_drift_freshness_reason", return_value=None), \
            patch(prefix + "call_ai_optimization_decision", return_value={"optimization_needed": False}) as ai:
        result = _process_optimization_decision(_drift(), store, False,
            optimize=Mock(), enforce_backtest_gates=Mock(), record_shadow=Mock())
    assert result["reason"] == "research_identity_unavailable"
    ai.assert_not_called()


def test_monitor_bookkeeping_does_not_change_frozen_research_identity(tmp_path):
    optimize = Mock(return_value=_proposal())
    drift = replace(_drift(), source_revision="observation-v1")
    first = invoke(tmp_path, drift=drift, optimize=optimize)
    second = invoke(tmp_path, drift=replace(drift, escalated=True, cooldown_active=True), optimize=optimize)
    assert first["research_key"] == second["research_key"]
    assert optimize.call_count == 1


def test_full_proposal_survives_checkpoint_without_losing_cost_or_validation_identity(tmp_path):
    from quant_platform_kit.strategy_lifecycle.contracts import BacktestResult, BacktestValidationIdentity

    metrics = BacktestResult(strategy_profile="demo_strategy", domain="us_equity", param_set_id="candidate",
        params={"a": 2}, start_date=date(2025, 1, 1), end_date=date(2025, 12, 31),
        cost_inputs={"commission_bps": 1.0, "minimum_commission": 5.0},
        validation_identity=BacktestValidationIdentity(protocol="purged_walk_forward.v1", fold_id="fold1",
            fold_role="walk_forward", train_start=date(2022, 1, 1), train_end=date(2022, 12, 31),
            test_start=date(2023, 1, 2), test_end=date(2023, 6, 30), locked_oos_start=date(2024, 1, 1),
            locked_oos_end=date(2025, 1, 1), purge_days=1, embargo_days=1))
    proposal = replace(_proposal(), current_metrics=metrics, proposed_metrics=metrics,
                       search_iterations=7, winning_dimensions=("sharpe",), walk_forward_passed=True)
    seen = []

    def gate(restored):
        seen.append(restored)
        assert restored == proposal
        return _promotion_backtest_evidence()

    result = invoke(tmp_path, optimize=Mock(return_value=proposal), enforce_backtest_gates=gate)
    assert result["status"] == "awaiting_human"
    assert len(seen) == 1


def test_deferral_waits_until_admitted_retry_time_then_rechecks_once(tmp_path):
    retry = datetime(2026, 9, 8, 12, tzinfo=timezone.utc).timestamp()
    diagnose = Mock(side_effect=[{"optimization_needed": False, "reason": "codex_research_deferred", "retry_at": retry},
                                {"optimization_needed": False}])
    with patch.object(cycle, "datetime") as clock:
        clock.now.return_value = datetime(2026, 9, 8, 11, tzinfo=timezone.utc)
        first = invoke(tmp_path, diagnose=diagnose)
        second = invoke(tmp_path, diagnose=diagnose)
        assert first["status"] == second["status"] == "deferred"
        assert diagnose.call_count == 1
        clock.now.return_value = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
        third = invoke(tmp_path, diagnose=diagnose)
        assert third["status"] == "parked"
        assert diagnose.call_count == 2


def test_damaged_checkpoint_does_not_rerun_or_block_a_different_identity(tmp_path):
    import json

    first = invoke(tmp_path)
    path = cycle.Path(first["ticket_path"])
    raw = json.loads(path.read_text())
    raw["research_progress"]["identity"]["revisions"]["input_revision"] = "mismatch"
    path.write_text(json.dumps(raw))
    optimize = Mock()
    bad = invoke(tmp_path, optimize=optimize)
    assert bad["reason"] == "research_checkpoint_mismatch"
    optimize.assert_not_called()
    assert invoke(tmp_path, research_identity={**IDENTITY, "input_revision": "next"})["status"] == "awaiting_human"


def test_console_decision_recovery_does_not_race_an_active_directory_owner(tmp_path):
    first = invoke(tmp_path)
    path = cycle.Path(first["ticket_path"])
    local = cycle.load_research_promotion_ticket(path)
    pull = Mock(return_value=remote_decision(local, "reject"))
    before = path.read_bytes()
    with cycle._research_directory_lock(tmp_path):
        result = cycle.reconcile_saved_research_promotion_ticket(path, pull_console=pull)
    assert result["status"] == "deferred"
    assert result["reason"] == "research_in_progress"
    assert path.read_bytes() == before
    pull.assert_not_called()
    assert cycle.reconcile_saved_research_promotion_ticket(path, pull_console=pull)["status"] == "updated"


def test_manual_decision_cli_uses_the_same_directory_lock(tmp_path, capsys):
    from quant_platform_kit.strategy_lifecycle import cli

    first = invoke(tmp_path)
    path = cycle.Path(first["ticket_path"])
    before = path.read_bytes()
    with cycle._research_directory_lock(tmp_path):
        assert cli.main(["research-promotion-decide", "--ticket", str(path), "--decision", "reject"]) == 1
    assert path.read_bytes() == before
    assert "research_in_progress" in capsys.readouterr().err
    assert cli.main(["research-promotion-decide", "--ticket", str(path), "--decision", "reject"]) == 0
    assert cycle.load_research_promotion_ticket(path).research_progress


def test_process_stop_during_stage_leaves_unknown_not_an_implicit_retry(tmp_path):
    optimize = Mock(side_effect=SystemExit("synthetic process interruption"))
    with pytest.raises(SystemExit):
        invoke(tmp_path, optimize=optimize)
    result = invoke(tmp_path, optimize=optimize)
    assert result["reason"] == "research_outcome_unknown"
    assert optimize.call_count == 1


def test_checkpointed_strict_gate_is_revalidated_before_shadow(tmp_path):
    import json

    save = cycle.save_research_promotion_ticket
    path = None

    def stop_after_gate(ticket, target):
        nonlocal path
        path = target
        result = save(ticket, target)
        if ticket.research_progress.get("stages", {}).get("backtest", {}).get("status") == "completed":
            raise SystemExit("synthetic process stop")
        return result

    optimize, gates, shadow = Mock(return_value=_proposal()), Mock(return_value=_promotion_backtest_evidence()), Mock()
    with patch.object(cycle, "save_research_promotion_ticket", side_effect=stop_after_gate):
        with pytest.raises(SystemExit):
            invoke(tmp_path, optimize=optimize, enforce_backtest_gates=gates, record_shadow=shadow)
    raw = json.loads(path.read_text())
    raw["research_progress"]["stages"]["backtest"]["result"]["locked_independent_oos"]["reused_for_selection"] = True
    path.write_text(json.dumps(raw))
    result = invoke(tmp_path, optimize=optimize, enforce_backtest_gates=gates, record_shadow=shadow)
    assert result["status"] == "parked"
    assert "locked_independent_oos_failed" in result["ticket"]["notes"]
    assert optimize.call_count == gates.call_count == 1
    shadow.assert_not_called()


def test_operating_system_lock_blocks_another_process_and_releases_on_exit(tmp_path):
    import os
    import subprocess
    import sys

    script = "from pathlib import Path; from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import _research_directory_lock\nimport sys\nwith _research_directory_lock(Path(sys.argv[1])) as owned:\n print(owned, flush=True)\n sys.stdin.readline()\n"
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(cycle.Path(cycle.__file__).parents[2]),
           "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.Popen([sys.executable, "-c", script, str(tmp_path)], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    try:
        assert proc.stdout.readline().strip() == "True"
        diagnose = Mock()
        result = invoke(tmp_path, diagnose=diagnose)
        assert result["reason"] == "research_in_progress"
        diagnose.assert_not_called()
    finally:
        proc.communicate("\n", timeout=10)
    assert invoke(tmp_path)["status"] == "awaiting_human"


def test_restart_before_first_console_attempt_delivers_the_saved_ticket_once(tmp_path):
    save = cycle.save_research_promotion_ticket
    sync = Mock(return_value=True)

    def stop_before_delivery(ticket, path):
        result = save(ticket, path)
        if ticket.state is cycle.ResearchPromotionState.AWAITING_HUMAN:
            raise SystemExit("synthetic process stop before first delivery")
        return result

    with patch.object(cycle, "save_research_promotion_ticket", side_effect=stop_before_delivery):
        with pytest.raises(SystemExit):
            invoke(tmp_path, sync_console=sync)
    sync.assert_not_called()
    optimize = Mock()
    result = invoke(tmp_path, sync_console=sync, optimize=optimize)
    assert result["status"] == "awaiting_human"
    assert result["console_synced"] is True
    sync.assert_called_once()
    optimize.assert_not_called()


def test_optional_diagnosis_does_not_create_a_second_experiment_for_same_evidence(tmp_path):
    first = invoke(tmp_path)
    diagnose, optimize = Mock(), Mock()
    second = invoke(tmp_path, diagnose=diagnose, optimize=optimize)
    assert first["research_key"] == second["research_key"]
    diagnose.assert_not_called()
    optimize.assert_not_called()


@pytest.mark.parametrize("field,value", [("live_authority_granted", True), ("proposed_params", {"a": 999})])
def test_console_callback_cannot_mutate_saved_authority_or_candidate(tmp_path, field, value):
    def bad_sync(ticket):
        setattr(ticket, field, value)
        return True

    result = invoke(tmp_path, sync_console=bad_sync)
    assert result["ticket"]["live_authority_granted"] is False
    assert result["ticket"]["proposed_params"] == _proposal().proposed_params
    assert result["console_synced"] is False
    saved = cycle.load_research_promotion_ticket(result["ticket_path"])
    assert saved.live_authority_granted is False


@pytest.mark.parametrize("retry", [0, -1, 1000])
def test_already_expired_deferral_does_not_create_a_retry_loop(tmp_path, retry):
    diagnose = Mock(return_value={"optimization_needed": False, "reason": "codex_research_deferred",
                                 "retry_at": retry})
    first = invoke(tmp_path, diagnose=diagnose)
    second = invoke(tmp_path, diagnose=diagnose)
    assert first["status"] == second["status"] == "deferred"
    assert first["retry_at"] is None
    assert diagnose.call_count == 1


@pytest.mark.parametrize("delivery,identity_changes,expected_syncs", [
    (None, False, 1), (None, True, 0), ("running", False, 0), ("unconfirmed", False, 0),
])
def test_normal_auto_pilot_resumes_only_matching_unstarted_console_delivery(
    tmp_path, delivery, identity_changes, expected_syncs,
):
    from types import SimpleNamespace
    from quant_platform_kit.strategy_lifecycle.codex_integration import run_auto_pilot_cycle
    from quant_platform_kit.strategy_lifecycle.contracts import StrategyPerformanceSnapshot
    from quant_platform_kit.strategy_lifecycle.promotion_actionable_runner import run_actionable_research_promotion

    directory = tmp_path / "research_promotion_tickets"
    save = cycle.save_research_promotion_ticket
    before_sync = Mock()

    def stop_before_delivery(ticket, path):
        if ticket.state is cycle.ResearchPromotionState.AWAITING_HUMAN:
            if delivery is not None:
                ticket.research_progress["console_delivery"] = delivery
            save(ticket, path)
            raise SystemExit("synthetic crash before delivery acknowledgement")
        return save(ticket, path)

    with patch.object(cycle, "save_research_promotion_ticket", side_effect=stop_before_delivery):
        with pytest.raises(SystemExit):
            run_actionable_research_promotion(
                strategy_profile="demo_strategy", domain="us_equity", as_of="2026-09-07",
                drift_score=0.8, source_revision="observation-v1", evaluation_date="2026-09-08",
                research_identity=IDENTITY, ticket_dir=directory, optimize=Mock(return_value=_proposal()),
                enforce_backtest_gates=Mock(return_value=_promotion_backtest_evidence()),
                record_shadow=Mock(return_value={"evidence_kind": "paired_shadow", "passed": True}),
                sync_console=before_sync,
            )
    before_sync.assert_not_called()
    original_files = list(directory.glob("*.json"))
    store = SimpleNamespace(local_root=tmp_path, load_latest_snapshot=lambda *_: StrategyPerformanceSnapshot(
        strategy_profile="demo_strategy", domain="us_equity", platform="test", as_of=date(2026, 9, 7),
        source_revision="observation-v1"))
    sync, optimize, gates, shadow = Mock(return_value=True), Mock(), Mock(), Mock()
    prefix = "quant_platform_kit.strategy_lifecycle.codex_integration."
    identity = {**IDENTITY, "input_revision": "new-input"} if identity_changes else IDENTITY
    with patch(prefix + "_run_monitor_phase", return_value=[]), \
            patch(prefix + "_run_drift_phase", return_value=([_drift()], [_drift()])), \
            patch(prefix + "call_ai_optimization_decision") as ai:
        run_auto_pilot_cycle("us_equity", store=store, create_issues=False, research_identity=identity,
            optimize=optimize, enforce_backtest_gates=gates, record_shadow=shadow,
            sync_console=sync, pull_console=Mock(return_value=None))
    assert sync.call_count == expected_syncs
    ai.assert_not_called()
    optimize.assert_not_called()
    gates.assert_not_called()
    shadow.assert_not_called()
    assert list(directory.glob("*.json")) == original_files


@pytest.mark.parametrize("decision", [False, None, 1, "true", RuntimeError("private admission detail")])
def test_new_experiment_admission_rejects_before_ticket_or_model(tmp_path, decision):
    admission = Mock(side_effect=decision) if isinstance(decision, Exception) else Mock(return_value=decision)
    diagnose, optimize = Mock(), Mock()
    result = invoke(tmp_path, admit_new_research=admission, diagnose=diagnose, optimize=optimize)
    assert result["status"] in {"parked", "deferred"}
    assert result["reason"] in {"new_research_not_admitted", "research_admission_unavailable"}
    assert not list(tmp_path.glob("*.json"))
    assert "private admission detail" not in str(result)
    admission.assert_called_once()
    diagnose.assert_not_called()
    optimize.assert_not_called()


def test_admission_runs_under_directory_lock_and_binds_the_persisted_utc_clock(tmp_path):
    admitted_times = []

    def admit(directory, created_at):
        assert directory == tmp_path
        assert not list(directory.glob("*.json"))
        with cycle._research_directory_lock(directory) as acquired:
            assert acquired is False
        assert datetime.fromisoformat(created_at).utcoffset().total_seconds() == 0
        admitted_times.append(created_at)
        return True

    result = invoke(tmp_path, admit_new_research=admit)
    assert result["ticket"]["created_at"] == admitted_times[0]


@pytest.mark.parametrize("outcome", ["awaiting", "terminal", "unknown"])
def test_saved_experiments_never_require_a_second_new_experiment_admission(tmp_path, outcome):
    admission = Mock(return_value=True)
    kwargs = {"admit_new_research": admission}
    if outcome == "terminal":
        kwargs["diagnose"] = Mock(return_value={"optimization_needed": False})
    if outcome == "unknown":
        kwargs["optimize"] = Mock(side_effect=TimeoutError("synthetic unknown"))
    first = invoke(tmp_path, **kwargs)
    admission.return_value = False
    second = invoke(tmp_path, **kwargs)
    assert first["research_key"] == second["research_key"]
    assert admission.call_count == 1


def test_actual_auto_pilot_passes_new_admission_before_ai(tmp_path):
    from types import SimpleNamespace
    from quant_platform_kit.strategy_lifecycle.codex_integration import run_auto_pilot_cycle
    from quant_platform_kit.strategy_lifecycle.contracts import StrategyPerformanceSnapshot

    store = SimpleNamespace(local_root=tmp_path, load_latest_snapshot=lambda *_: StrategyPerformanceSnapshot(
        strategy_profile="demo_strategy", domain="us_equity", platform="test", as_of=date(2026, 9, 7),
        source_revision="observation-v1"))
    admission = Mock(return_value=False)
    prefix = "quant_platform_kit.strategy_lifecycle.codex_integration."
    with patch(prefix + "_run_monitor_phase", return_value=[]), \
            patch(prefix + "_run_drift_phase", return_value=([_drift()], [_drift()])), \
            patch(prefix + "call_ai_optimization_decision") as ai:
        result = run_auto_pilot_cycle("us_equity", store=store, create_issues=False, research_identity=IDENTITY,
            optimize=Mock(), enforce_backtest_gates=Mock(), record_shadow=Mock(), admit_new_research=admission)
    assert result["actions"][0]["reason"] == "new_research_not_admitted"
    assert admission.call_count == 1
    ai.assert_not_called()
    assert not list((tmp_path / "research_promotion_tickets").glob("*.json"))
