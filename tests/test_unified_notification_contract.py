"""Offline contract tests; all transport/storage/broker effects are fakes."""
import copy
from dataclasses import replace
from datetime import datetime

import pytest

from quant_platform_kit.notifications.unified_contract import (
    EVENT_KINDS, CandidatePersistenceError, IncidentTracker, NotificationEvent,
    effective_notification_mode, order_identity_digest, route_notification_event,
    routine_dedupe_key, select_notification_route, sgt_business_window,
    unified_notification_enabled,
)

FLAGS = ["IBKR_UNIFIED_NOTIFICATION_ENABLED", "SCHWAB_UNIFIED_NOTIFICATION_ENABLED",
         "LONGBRIDGE_UNIFIED_NOTIFICATION_ENABLED", "BINANCE_UNIFIED_NOTIFICATION_ENABLED",
         "FIRSTRADE_UNIFIED_NOTIFICATION_ENABLED", "QRS_UNIFIED_NOTIFICATION_ENABLED"]
FLAG = FLAGS[0]
STAMP = datetime.fromisoformat("2026-10-17T05:59:59+08:00")


def event(**values):
    return replace(NotificationEvent("routine_cycle", STAMP, "platform", "opaque-a", "target", "strategy", "run-a"), **values)


class MemoryStore:
    """Test-only CAS fake; multiple tracker instances share the same durable view."""
    def __init__(self):
        self.rows = {}
        self.conflict_once = False

    def read(self, key):
        return copy.deepcopy(self.rows.get(key, (None, None)))

    def compare_and_set(self, key, version, value):
        if self.conflict_once:
            self.conflict_once = False
            return False
        current, _ = self.read(key)
        if current != version:
            return False
        self.rows[key] = ((current or 0) + 1, copy.deepcopy(value))
        return True


@pytest.mark.parametrize("flag", FLAGS)
@pytest.mark.parametrize("value", [None, "", "false", "FALSE", "invalid", "1", "yes", 1, False])
def test_flags_unset_empty_invalid_are_false_and_legacy(flag, value):
    env = {} if value is None else {flag: value}
    assert not unified_notification_enabled(env, flag)
    for kind in EVENT_KINDS | {"future_unknown_event"}:
        assert select_notification_route(event_kind=kind, env=env, flag_key=flag) == "legacy"


@pytest.mark.parametrize("mode", [None, "immediate", "daily_digest", "invalid"])
def test_flag_maps_to_single_existing_mode_and_orders_default_immediate(mode):
    env = {FLAG: "true", "QSL_ROUTINE_NOTIFICATION_MODE": mode}
    assert effective_notification_mode(env, FLAG) == "daily_digest"
    for kind in EVENT_KINDS | {"pending_order", "future_unknown_event"}:
        expected = "digest_candidate" if kind in {"routine_cycle", "healthy_heartbeat"} else "immediate"
        assert select_notification_route(event_kind=kind, env=env, flag_key=FLAG) == expected
    env["QSL_DIGEST_ROUTINE_ORDERS"] = "true"
    assert select_notification_route(event_kind="fill", env=env, flag_key=FLAG) == "digest_candidate"
    assert select_notification_route(event_kind="order_status_unknown", env=env, flag_key=FLAG) == "immediate"


def test_run_event_keys_multi_account_multi_run_and_duplicate_observations():
    first = event()
    assert routine_dedupe_key(first) == routine_dedupe_key(replace(first))
    variants = [first, event(opaque_account_uid="opaque-b"), event(source_run_id="run-b"),
                event(target_id="target-b"), event(platform_id="other"),
                event(strategy_profile="other"), event(event_kind="healthy_heartbeat")]
    assert len({routine_dedupe_key(row) for row in variants}) == len(variants)
    order = event(event_kind="order_submitted", order_execution_digest=order_identity_digest("order-a"))
    other = replace(order, order_execution_digest=order_identity_digest("order-b"))
    assert routine_dedupe_key(order) != routine_dedupe_key(other)
    assert routine_dedupe_key(order) != routine_dedupe_key(replace(order, event_kind="fill"))
    assert "order-a" not in str(order.to_candidate())


@pytest.mark.parametrize("missing", ["opaque_account_uid", "target_id", "platform_id", "source_run_id", "strategy_profile"])
def test_unknown_identity_is_coverage_unknown_never_zero_filled(missing):
    unknown = event(**{missing: None}, order_count=0, fill_count=0)
    candidate = unknown.to_candidate()
    assert candidate["coverage_status"] == "unknown"
    assert candidate["dedupe_key"] is None
    assert candidate["order_count"] is candidate["fill_count"] is None
    with pytest.raises(CandidatePersistenceError):
        route_notification_event(unknown, env={FLAG: "true"}, flag_key=FLAG,
                                 persist_candidate=lambda _: True, legacy=lambda: None, immediate=lambda: None)


def test_order_missing_identity_and_unknown_counts_stay_unknown():
    assert event(event_kind="fill").coverage_status == "unknown"
    assert event().to_candidate()["order_count"] is None
    assert event().to_candidate()["fill_count"] is None
    with pytest.raises(ValueError):
        event(event_kind="expected_block_observed")
    proven = event(event_kind="expected_block_observed", expected_block_evidence="proof-reference")
    assert select_notification_route(event_kind=proven.event_kind, env={FLAG: "true"}, flag_key=FLAG) == "immediate"


def test_business_window_half_open_boundaries_and_equivalent_utc():
    before = sgt_business_window(STAMP)
    at = sgt_business_window(datetime.fromisoformat("2026-10-17T06:00:00+08:00"))
    assert before.business_day.isoformat() == "2026-10-16"
    assert before.report_date.isoformat() == "2026-10-17"
    assert before.end == at.start
    assert at.report_date.isoformat() == "2026-10-18"
    assert at.window_id == "sgt-0600:2026-10-17"
    assert before == sgt_business_window(datetime.fromisoformat("2026-10-16T21:59:59+00:00"))
    with pytest.raises(ValueError):
        sgt_business_window(datetime(2026, 10, 17, 6))


def test_candidate_write_precedes_deferral_and_never_just_silences():
    calls = []
    result = route_notification_event(event(), env={FLAG: "true"}, flag_key=FLAG,
        persist_candidate=lambda payload: calls.append(payload) or True,
        legacy=lambda: pytest.fail("legacy"), immediate=lambda: pytest.fail("immediate"))
    assert result.route == "digest_candidate" and result.candidate_persisted
    assert len(calls) == 1 and calls[0]["source_run_id"] == "run-a"
    for unconfirmed in (False, None, "deferred"):
        with pytest.raises(CandidatePersistenceError):
            route_notification_event(event(), env={FLAG: "true"}, flag_key=FLAG,
                persist_candidate=lambda _: unconfirmed, legacy=lambda: None, immediate=lambda: None)


def test_real_orders_counted_but_immediate_even_if_candidate_store_fails():
    order = event(event_kind="fill", order_execution_digest=order_identity_digest("execution-a"), fill_count=1)
    calls = []
    def failing_write(payload):
        calls.append(("candidate", payload["fill_count"]))
        raise OSError("fake storage failure")
    result = route_notification_event(order, env={FLAG: "true"}, flag_key=FLAG,
        persist_candidate=failing_write, legacy=lambda: pytest.fail("legacy"), immediate=lambda: calls.append("send"))
    assert calls == [("candidate", 1), "send"]
    assert result.route == "immediate" and result.candidate_persisted is False


def test_incident_duplicate_across_runs_workers_and_separate_accounts():
    store = MemoryStore()
    incident = event(event_kind="receipt_unacceptable", incident_reason="blocked")
    first = IncidentTracker(store).observe(incident, state="blocked")
    assert first.action == "send"
    second = IncidentTracker(store).observe(replace(incident, source_run_id="run-b"), state="blocked")
    assert second.action == "duplicate" and second.transition_key == first.transition_key
    assert IncidentTracker(store).observe(replace(incident, opaque_account_uid="opaque-b"), state="blocked").action == "send"
    assert IncidentTracker(store).observe(replace(incident, target_id="target-b"), state="blocked").action == "send"
    assert IncidentTracker(store).observe(replace(incident, strategy_profile="other"), state="blocked").action == "send"
    assert IncidentTracker(store).observe(replace(incident, incident_reason="auth"), state="blocked").action == "send"


def test_recovery_then_reworsen_and_severity_up_are_new_transitions():
    store = MemoryStore()
    tracker = IncidentTracker(store)
    incident = event(event_kind="risk_escalation", incident_reason="risk")
    first = tracker.observe(incident, state="ACTION", severity=1)
    higher = tracker.observe(incident, state="HALT", severity=2)
    assert first.action == higher.action == "send"
    assert first.transition_key != higher.transition_key
    assert tracker.observe(incident, state="HALT", severity=2).action == "duplicate"
    assert tracker.observe(incident, state="OK", severity=0, recovered=True).action == "recovered"
    again = IncidentTracker(store).observe(incident, state="ACTION", severity=1)
    assert again.action == "send" and again.transition_key not in {first.transition_key, higher.transition_key}
    with pytest.raises(RuntimeError):
        tracker.record_delivery(first, receipt_id="late-ack")


def test_send_uncertain_or_crashed_before_ack_never_blind_resend():
    store = MemoryStore()
    incident = event(event_kind="auth_failure", incident_reason="auth")
    tracker = IncidentTracker(store)
    decision = tracker.observe(incident, state="failed")
    assert store.rows[decision.incident_key][1]["delivery_status"] == "pending"
    assert IncidentTracker(store).observe(incident, state="failed").action == "duplicate"
    tracker.record_delivery(decision)
    assert store.rows[decision.incident_key][1]["delivery_status"] == "uncertain"
    assert IncidentTracker(store).observe(incident, state="failed").action == "duplicate"
    tracker.record_delivery(decision, receipt_id="confirmed-transport-ack")
    assert store.rows[decision.incident_key][1]["delivery_status"] == "delivered"


def test_atomic_claim_loser_and_missing_history_do_not_send():
    store = MemoryStore()
    store.conflict_once = True
    incident = event(event_kind="real_error", incident_reason="error")
    assert IncidentTracker(store).observe(incident, state="failed").action == "send"
    class BrokenStore(MemoryStore):
        def read(self, key):
            raise OSError("history unavailable")
    with pytest.raises(OSError):
        IncidentTracker(BrokenStore()).observe(incident, state="failed")
    assert IncidentTracker(store).observe(replace(incident, opaque_account_uid=None), state="failed").action == "coverage_unknown"
