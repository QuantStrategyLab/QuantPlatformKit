"""Offline console reconciliation; all remote effects are injected stubs."""

import json
import urllib.error
from copy import deepcopy
from unittest.mock import Mock, patch

import pytest

from quant_platform_kit.strategy_lifecycle import research_promotion_cycle as cycle
from tests.test_research_promotion_cycle import _drift, _proposal, run_research_promotion_cycle


def ticket():
    return run_research_promotion_cycle(
        _drift(), optimize=lambda *_: _proposal(),
        record_shadow=lambda _: {"evidence_kind": "paired_shadow", "passed": True,
                                 "paired_shadow_evidence_sha256": "a" * 64},
        ticket_id="rpt_reconcile",
    )


def sync(post, pull):
    return cycle.make_console_research_promotion_sync(
        endpoint_url="https://console.invalid/api/internal/sync-research-promotion-ticket",
        sync_token="synthetic-test-only", post_json=post, pull_console=pull,
        printer=lambda *_args, **_kwargs: None,
    )


def remote_decision(local, decision="accept"):
    remote = deepcopy(local)
    cycle.apply_human_promotion_decision(
        remote, decision=decision,
        confirmation={"target_platform": "ibkr", "execution_mode": "live",
                      "risk_profile": "CAPITAL_PRESERVATION"} if decision == "accept" else None,
        decided_at="2026-09-08T12:00:00+00:00",
    )
    return remote.to_dict()


def test_http_success_without_readback_is_not_confirmed():
    post, pull = Mock(return_value=200), Mock(return_value=None)
    assert sync(post, pull)(ticket()) is False
    assert post.call_count == 1
    assert pull.call_count == 2


def test_existing_matching_ticket_is_read_without_another_post():
    local = ticket()
    post, pull = Mock(), Mock(return_value=local.to_dict())
    assert sync(post, pull)(local) is True
    post.assert_not_called()


def test_console_number_roundtrip_preserves_candidate_identity():
    local = ticket()
    local.drift_score = 1.0
    local.proposed_params = {"lookback": 20.0, "nested": {"weights": (1.0, 0.5)}}
    local.budget = {**local.budget, "max_search_iterations": 25.0}
    # JSON.stringify(JSON.parse(...)) emits integral JavaScript numbers as ints.
    remote = json.loads(json.dumps(local.to_dict()), parse_float=lambda number: (
        int(number.split(".")[0]) if float(number).is_integer() else float(number)
    ))
    assert remote["drift_score"] == 1 and type(remote["drift_score"]) is int
    assert sync(Mock(), Mock(return_value=remote))(local) is True


@pytest.mark.parametrize("field,value", [("drift_score", True), ("shadow_passed", 1),
                                         ("proposed_params", {"a": True, "b": 3})])
def test_console_numbers_never_equal_booleans(field, value):
    local = ticket()
    local.drift_score = 1.0
    local.proposed_params = {"a": 1, "b": 3}
    remote = {**local.to_dict(), field: value}
    post = Mock()
    assert sync(post, Mock(return_value=remote))(local) is False
    post.assert_not_called()


def test_uncertain_post_is_reconciled_without_repeating_write():
    local = ticket()
    post = Mock(side_effect=TimeoutError("sensitive transport detail"))
    pull = Mock(side_effect=[None, local.to_dict(), local.to_dict()])
    publish = sync(post, pull)
    assert publish(local) is True
    assert publish(local) is True
    assert post.call_count == 1


def test_unavailable_preflight_never_becomes_permission_to_write():
    post = Mock()
    assert sync(post, Mock(side_effect=ValueError("sensitive")))(ticket()) is False
    post.assert_not_called()


def test_unconfirmed_write_is_not_repeated_by_same_sync_callback():
    local = ticket()
    post = Mock(side_effect=TimeoutError("sensitive"))
    publish = sync(post, Mock(return_value=None))
    assert publish(local) is False
    assert publish(local) is False
    assert post.call_count == 1


@pytest.mark.parametrize("field,value", [
    ("proposed_params", {"a": 99}), ("shadow_passed", False),
    ("notes", ["paired_shadow_evidence_sha256=" + "b" * 64]),
    ("budget", {"max_search_iterations": 999}), ("drift_score", 0.1),
    ("state", "human_accepted"), ("live_authority_granted", True),
])
def test_sync_rejects_inconsistent_readback(field, value):
    local = ticket()
    remote = {**local.to_dict(), field: value}
    post = Mock(return_value=200)
    assert sync(post, Mock(side_effect=[None, remote]))(local) is False
    assert post.call_count == 1


@pytest.mark.parametrize("payload", [None, [], {"ok": False},
    {"ok": False, "live_authority_granted": False, "ticket": {"ticket_id": "rpt_reconcile"}},
    {"ok": True, "live_authority_granted": False, "ticket": {"ticket_id": "other", "live_authority_granted": False}},
])
def test_pull_requires_success_and_requested_identity(payload):
    pull = cycle.make_console_research_promotion_pull(
        endpoint_url="https://console.invalid/api/internal/research-promotion-ticket",
        sync_token="synthetic-test-only", get_json=Mock(return_value=payload),
        printer=lambda *_args, **_kwargs: None,
    )
    assert pull("rpt_reconcile") is None


@pytest.mark.parametrize("code", [403, 404, 500])
def test_strict_pull_distinguishes_absence_from_unavailable(code):
    pull = cycle.make_console_research_promotion_pull(
        endpoint_url="https://console.invalid/api/internal/research-promotion-ticket",
        sync_token="synthetic-test-only", raise_on_unavailable=True,
        get_json=Mock(side_effect=urllib.error.HTTPError("synthetic", code, "sensitive", {}, None)),
    )
    if code == 404:
        assert pull("rpt_reconcile") is None
    else:
        with pytest.raises(ValueError, match="^console_read_unavailable$"):
            pull("rpt_reconcile")


@pytest.mark.parametrize("decision", ["accept", "reject"])
def test_saved_decision_is_applied_once_and_remains_intent(tmp_path, decision):
    local = ticket()
    path = tmp_path / "ticket.json"
    cycle.save_research_promotion_ticket(local, path)
    pull = Mock(return_value=remote_decision(local, decision))
    first = cycle.reconcile_saved_research_promotion_ticket(path, pull_console=pull)
    saved = path.read_bytes()
    second = cycle.reconcile_saved_research_promotion_ticket(path, pull_console=pull)
    assert first["status"] == "updated"
    assert first["state"] == ("human_accepted" if decision == "accept" else "human_rejected")
    assert first["live_authority_granted"] is False
    assert second["status"] == "already_terminal"
    assert path.read_bytes() == saved
    assert pull.call_count == 1
    assert cycle.load_research_promotion_ticket(path).live_authority_granted is False


@pytest.mark.parametrize("broken", ["unavailable", "mismatch", "evidence", "live", "permission", "waiting",
                                   "domain", "profile", "confirmation", "decision", "decision_time"])
def test_reconciliation_failure_or_waiting_preserves_local_ticket(tmp_path, broken):
    local = ticket()
    path = tmp_path / "ticket.json"
    cycle.save_research_promotion_ticket(local, path)
    before = path.read_bytes()
    remote = remote_decision(local)
    if broken == "unavailable":
        remote = None
    elif broken == "mismatch":
        remote["proposed_params"] = {"a": 999}
    elif broken == "evidence":
        remote["notes"][0] = "forged evidence"
    elif broken == "live":
        remote["live_authority_granted"] = True
    elif broken == "waiting":
        remote = local.to_dict()
    elif broken == "domain":
        remote["domain"] = "cn_equity"
    elif broken == "profile":
        remote["strategy_profile"] = "other_strategy"
    elif broken == "confirmation":
        remote["confirmation_execution_mode"] = "synthetic"
    elif broken == "decision":
        remote["human_decision"] = "reject"
    elif broken == "decision_time":
        remote["human_decided_at"] = ""
    pull = Mock(side_effect=PermissionError("sensitive")) if broken == "permission" else Mock(return_value=remote)
    result = cycle.reconcile_saved_research_promotion_ticket(path, pull_console=pull)
    assert result["status"] in {"unavailable", "rejected", "awaiting_human"}
    assert path.read_bytes() == before
    assert "sensitive" not in json.dumps(result)


def test_normal_cycle_recovers_saved_decision_without_new_research(tmp_path):
    from quant_platform_kit.strategy_lifecycle.codex_integration import run_auto_pilot_cycle

    local = ticket()
    path = tmp_path / "research_promotion_tickets" / "ticket.json"
    cycle.save_research_promotion_ticket(local, path)
    store = Mock(local_root=tmp_path)
    pull = Mock(return_value=remote_decision(local))
    prefix = "quant_platform_kit.strategy_lifecycle.codex_integration."
    with patch(prefix + "_run_monitor_phase", return_value=[]), patch(prefix + "_run_drift_phase", return_value=([], [])):
        result = run_auto_pilot_cycle("us_equity", store=store, create_issues=False,
                                      trigger_optimization=False, pull_console=pull)
    assert result["research_decisions"][0]["status"] == "updated"
    assert result["actions"] == []
    assert cycle.load_research_promotion_ticket(path).state is cycle.ResearchPromotionState.HUMAN_ACCEPTED


def test_reconciliation_save_failure_keeps_original_and_can_recover(tmp_path):
    local = ticket()
    path = tmp_path / "ticket.json"
    cycle.save_research_promotion_ticket(local, path)
    before = path.read_bytes()
    pull = Mock(return_value=remote_decision(local))
    with patch("os.replace", side_effect=OSError("sensitive filesystem detail")):
        result = cycle.reconcile_saved_research_promotion_ticket(path, pull_console=pull)
    assert result["status"] == "unavailable"
    assert result["reason"] == "local_ticket_save_failed"
    assert path.read_bytes() == before
    assert set(tmp_path.iterdir()) == {path, tmp_path / ".research.lock"}
    assert cycle.reconcile_saved_research_promotion_ticket(path, pull_console=pull)["status"] == "updated"


@pytest.mark.parametrize("decision", [None, "accept", "reject"])
def test_cycle_isolates_bad_and_other_domain_tickets_and_skips_research_for_pending_profile(tmp_path, decision):
    from quant_platform_kit.strategy_lifecycle.codex_integration import run_auto_pilot_cycle

    local = ticket()
    directory = tmp_path / "research_promotion_tickets"
    cycle.save_research_promotion_ticket(local, directory / "02-own.json")
    other = deepcopy(local)
    other.ticket_id, other.domain = "rpt_other", "cn_equity"
    cycle.save_research_promotion_ticket(other, directory / "01-other.json")
    (directory / "00-broken.json").write_text("not json", encoding="utf-8")
    pull = Mock(return_value=remote_decision(local, decision) if decision else local.to_dict())
    prefix = "quant_platform_kit.strategy_lifecycle.codex_integration."
    with patch(prefix + "_run_monitor_phase", return_value=[]), \
            patch(prefix + "_run_drift_phase", return_value=([_drift()], [_drift()])), \
            patch(prefix + "_process_optimization_decision") as optimize:
        result = run_auto_pilot_cycle("us_equity", store=Mock(local_root=tmp_path),
                                      create_issues=False, pull_console=pull)
    assert [r["status"] for r in result["research_decisions"]] == ["rejected", "skipped", "updated" if decision else "awaiting_human"]
    assert result["actions"][0]["reason"] == "saved_research_ticket_pending"
    pull.assert_called_once_with(local.ticket_id)
    optimize.assert_not_called()


@pytest.mark.parametrize("saved_state", ["empty", "terminal", "dry_run"])
def test_cycle_does_not_pull_without_an_awaiting_ticket(tmp_path, saved_state):
    from quant_platform_kit.strategy_lifecycle.codex_integration import run_auto_pilot_cycle

    if saved_state != "empty":
        local = ticket()
        if saved_state == "terminal":
            local = cycle.ResearchPromotionTicket.from_dict(remote_decision(local))
        cycle.save_research_promotion_ticket(local, tmp_path / "research_promotion_tickets" / "ticket.json")
    pull = Mock()
    prefix = "quant_platform_kit.strategy_lifecycle.codex_integration."
    with patch(prefix + "_run_monitor_phase", return_value=[]), patch(prefix + "_run_drift_phase", return_value=([], [])):
        run_auto_pilot_cycle("us_equity", store=Mock(local_root=tmp_path), create_issues=False,
                             trigger_optimization=False, dry_run=saved_state == "dry_run", pull_console=pull)
    pull.assert_not_called()


def test_cli_uses_saved_reconciliation_and_terminal_retry_is_noop(tmp_path, capsys):
    from quant_platform_kit.strategy_lifecycle import cli

    local = ticket()
    path = tmp_path / "ticket.json"
    cycle.save_research_promotion_ticket(local, path)
    pull = Mock(return_value=remote_decision(local))
    with patch.object(cycle, "make_console_research_promotion_pull", return_value=pull):
        assert cli.main(["research-promotion-pull", "--ticket", str(path)]) == 0
        assert cli.main(["research-promotion-pull", "--ticket", str(path)]) == 0
    assert "already_terminal" in capsys.readouterr().out
    pull.assert_called_once()
