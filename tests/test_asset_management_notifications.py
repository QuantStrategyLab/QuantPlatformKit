"""P10 shared entrypoints; fake-only producers, storage and transport."""
from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace

import pytest

from quant_platform_kit.notifications import renderer_base, unified_contract as contract
from quant_platform_kit.notifications.strategy_plugin_telegram import (
    StrategyPluginTelegramSettings, publish_strategy_plugin_telegram_alerts,
)

STAMP = datetime.fromisoformat("2026-11-04T23:00:00+08:00")


def event(kind="real_error", **fields):
    return replace(contract.NotificationEvent(kind, STAMP, "ibkr", "fake-opaque", "fake-target",
                                            "fake-strategy", "fake-run"), **fields)


@pytest.mark.parametrize("kind", ["routine_cycle", "healthy_heartbeat", "order_submitted", "fill",
                                  "recovery", "maintenance_reminder", "research_candidate", "strategy_signal"])
def test_asset_non_errors_persist_without_any_send(kind):
    rows, calls = [], []
    fact = event(kind, order_execution_digest="a" * 64)
    result = contract.route_asset_management_event(fact,
        persist_candidate=lambda row: rows.append(row) or True,
        publish_error=lambda _: calls.append("error"))
    assert result.route == "digest_candidate" and result.candidate_persisted
    assert rows[0]["source_run_id"] == "fake-run" and not calls


@pytest.mark.parametrize("failure", [False, None, "raise"])
def test_asset_deferral_never_swallows_write_failures(failure):
    def persist(_):
        if failure == "raise":
            raise OSError("fake storage outage")
        return failure
    with pytest.raises(contract.CandidatePersistenceError):
        contract.route_asset_management_event(event("recovery"), persist_candidate=persist,
            publish_error=lambda _: pytest.fail("normal message fallback"))


def test_asset_error_still_publishes_when_candidate_write_fails():
    calls = []
    fact = event(incident_reason="empty_position_decision")
    result = contract.route_asset_management_event(fact, persist_candidate=lambda _: False,
        publish_error=lambda item: calls.append(item) or "receipt-pending")
    assert calls == [fact] and result.route == "immediate" and not result.candidate_persisted
    assert result.result == "receipt-pending"


def test_asset_unknown_classification_is_an_error_not_a_healthy_label():
    calls = []
    contract.route_asset_management_event(event("future_unknown"), persist_candidate=lambda _: True,
                                         publish_error=lambda item: calls.append(item))
    assert len(calls) == 1


@pytest.mark.parametrize("locale", ["zh-CN", "en"])
def test_error_format_omits_private_identity_raw_reason_and_unknown_counts(locale):
    fact = event(incident_reason="fake-account secret=FAKE_SECRET")
    text = renderer_base.render_asset_management_error(fact, locale=locale,
        run_url="https://example.test/runs/1?token=FAKE_SECRET", allowed_run_hosts=("example.test",))
    assert "2026-11-04 23:00:00" in text
    assert "https://example.test/runs/1" in text
    assert all(value not in text for value in ("fake-opaque", "fake-target", "fake-strategy", "fake-run",
                                               "fake-account", "FAKE_SECRET", "token="))
    assert ("是否提交订单：未知" if locale == "zh-CN" else "Orders submitted: unknown") in text


@pytest.mark.parametrize("url", ["https://fake-private.test/runs/1", "https://example.test/fake-opaque",
                                  "https://user:pass@example.test/run", "gs://fake-bucket/run"])
def test_unapproved_or_identity_bearing_run_link_is_unavailable(url):
    text = renderer_base.render_asset_management_error(event(), run_url=url,
                                                       allowed_run_hosts=("example.test",))
    assert url not in text and "运行链接不可用" in text


def test_error_formatter_rejects_healthy_envelope_and_keeps_empty_decision_error():
    with pytest.raises(ValueError):
        renderer_base.render_asset_management_error(event("recovery"))
    text = renderer_base.render_asset_management_error(event(incident_reason="empty_position_decision"))
    assert "策略决策不可用" in text and "无需调仓" not in text
    assert "是否提交订单：未知" in text


def signal():
    return SimpleNamespace(strategy="fake-strategy", plugin="market_regime_control", effective_mode="shadow",
        as_of="2026-11-04", canonical_route="opportunity_watch", suggested_action="notify_manual_review",
        would_trade_if_enabled=False, execution_controls={"notification_profile": "shadow_only"})


@pytest.mark.parametrize("mode", ["immediate", "daily_digest", "invalid"])
def test_asset_plugin_entrypoint_uses_structured_route_in_every_mode(monkeypatch, mode):
    monkeypatch.setenv("QSL_ROUTINE_NOTIFICATION_MODE", mode)
    calls, rows = [], []
    result = publish_strategy_plugin_telegram_alerts([signal()],
        telegram_settings=StrategyPluginTelegramSettings(chat_ids=("fake-chat",), bot_token="fake-credential"),
        asset_management_event_factory=lambda _: event("research_candidate"),
        persist_candidate=lambda row: rows.append(row) or True,
        send_notification=lambda **kwargs: calls.append(kwargs) or True, log_message=lambda *a, **k: None)
    assert not calls and len(rows) == 1 and result.sent_count == 0


def test_asset_plugin_error_uses_fixed_body_and_existing_marker_dedupe():
    calls = []
    store = Store()
    kwargs = dict(telegram_settings=StrategyPluginTelegramSettings(chat_ids=("fake-chat",), bot_token="fake-credential"),
        asset_management_event_factory=lambda _: event(incident_reason="empty_position_decision"),
        persist_candidate=lambda _: True, asset_management_incident_tracker=contract.IncidentTracker(store),
        send_notification=lambda **kw: calls.append(kw) or True, log_message=lambda *a, **k: None)
    publish_strategy_plugin_telegram_alerts([signal()], **kwargs)
    publish_strategy_plugin_telegram_alerts([signal()], **kwargs)
    assert len(calls) == 1 and calls[0]["title"] == ""
    assert calls[0]["body"].startswith("【资产管理｜运行错误】")
    assert "无需调仓" not in calls[0]["body"] and "fake-strategy" not in calls[0]["body"]


def test_asset_plugin_requires_persistence_before_sending():
    with pytest.raises(contract.CandidatePersistenceError):
        publish_strategy_plugin_telegram_alerts([signal()], telegram_settings={},
            asset_management_event_factory=lambda _: event("research_candidate"),
            send_notification=lambda **_: pytest.fail("must not send"))


class Store:
    def __init__(self):
        self.rows = {}

    def read(self, key):
        return self.rows.get(key, (None, None))

    def compare_and_set(self, key, version, value):
        current, _ = self.read(key)
        if current != version:
            return False
        self.rows[key] = ((current or 0) + 1, dict(value))
        return True


def test_asset_error_requires_durable_tracker_before_transport():
    with pytest.raises(RuntimeError, match="durable_incident_tracker_required"):
        publish_strategy_plugin_telegram_alerts([signal()],
            telegram_settings=StrategyPluginTelegramSettings(chat_ids=("fake-chat",), bot_token="fake-credential"),
            asset_management_event_factory=lambda _: event(incident_reason="empty_position_decision"),
            persist_candidate=lambda _: True,
            send_notification=lambda **_: pytest.fail("unreserved send"))


@pytest.mark.parametrize("send_result", [False, True, "raise"])
def test_asset_error_restart_never_retries_unknown_transport(send_result):
    calls, store = [], Store()
    def send(**_):
        calls.append("send")
        if send_result == "raise":
            raise TimeoutError("fake timeout")
        return send_result
    for _ in range(2):
        publish_strategy_plugin_telegram_alerts([signal()],
            telegram_settings=StrategyPluginTelegramSettings(chat_ids=("fake-chat",), bot_token="fake-credential"),
            asset_management_event_factory=lambda _: event(incident_reason="empty_position_decision"),
            persist_candidate=lambda _: True,
            asset_management_incident_tracker=contract.IncidentTracker(store), send_notification=send)
    assert calls == ["send"]
    assert next(iter(store.rows.values()))[1]["delivery_status"] == "uncertain"


def test_current_incident_transition_is_not_overwritten_after_sender_await():
    store = Store()
    fact = event(incident_reason="empty_position_decision")
    def send(**_):
        contract.IncidentTracker(store).observe(fact, state="new_failure", severity=2)
        return True
    with pytest.raises(RuntimeError, match="transition_changed"):
        publish_strategy_plugin_telegram_alerts([signal()],
            telegram_settings=StrategyPluginTelegramSettings(chat_ids=("fake-chat",), bot_token="fake-credential"),
            asset_management_event_factory=lambda _: fact, persist_candidate=lambda _: True,
            asset_management_incident_tracker=contract.IncidentTracker(store), send_notification=send)
    row = next(iter(store.rows.values()))[1]
    assert row["state"] == "new_failure" and row["delivery_status"] == "pending"


def test_conflicting_plugin_error_cannot_be_hidden_in_research_candidate():
    item = signal()
    item.error = "fake input failure"
    with pytest.raises(ValueError, match="routine_incident_conflict"):
        publish_strategy_plugin_telegram_alerts([item], telegram_settings={},
            asset_management_event_factory=lambda _: event("research_candidate"),
            persist_candidate=lambda _: pytest.fail("must not archive as healthy"))


def test_overlong_link_does_not_exceed_single_message_budget():
    text = renderer_base.render_asset_management_error(event(),
        run_url="https://example.test/" + "x" * 5000, allowed_run_hosts=("example.test",))
    assert len(text.encode("utf-16-le")) // 2 <= 3900
    assert "运行链接不可用" in text


def test_asset_candidate_unknown_identity_and_conflicting_reason_fail_closed():
    for fact in (event("recovery", source_run_id=None), event("research_candidate", incident_reason="auth_failure")):
        with pytest.raises((contract.CandidatePersistenceError, ValueError)):
            contract.route_asset_management_event(fact,
                persist_candidate=lambda _: pytest.fail("invalid fact must not be persisted"),
                publish_error=lambda _: pytest.fail("invalid fact must not silently route"))


class SQLiteStore:
    """Test-only durable CAS implementation shared by independent processes."""
    def __init__(self, path):
        self.path = path

    def read(self, key):
        import json
        import sqlite3
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT version, value FROM markers WHERE key = ?", (key,)).fetchone()
        return (row[0], json.loads(row[1])) if row else (None, None)

    def compare_and_set(self, key, version, value):
        import json
        import sqlite3
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT version FROM markers WHERE key = ?", (key,)).fetchone()
            current = row[0] if row else None
            if current != version:
                return False
            db.execute("INSERT OR REPLACE INTO markers VALUES (?, ?, ?)",
                       (key, (current or 0) + 1, json.dumps(value)))
        return True


def _asset_worker(path, barrier, queue):
    barrier.wait(timeout=10)
    result = publish_strategy_plugin_telegram_alerts([signal()],
        telegram_settings=StrategyPluginTelegramSettings(chat_ids=("fake-chat",), bot_token="fake-credential"),
        asset_management_event_factory=lambda _: event(incident_reason="empty_position_decision"),
        persist_candidate=lambda _: True,
        asset_management_incident_tracker=contract.IncidentTracker(SQLiteStore(path)),
        send_notification=lambda **_: True)
    queue.put(sum(item.metadata.get("transport_attempted", False) for item in result.deliveries))


def test_asset_error_cross_process_reservation_and_restart(tmp_path):
    import multiprocessing
    import sqlite3
    path = str(tmp_path / "fake-markers.sqlite")
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE markers (key TEXT PRIMARY KEY, version INTEGER, value TEXT)")
    ctx = multiprocessing.get_context("spawn")
    barrier, queue = ctx.Barrier(4), ctx.Queue()
    processes = [ctx.Process(target=_asset_worker, args=(path, barrier, queue)) for _ in range(4)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=20)
        assert process.exitcode == 0
    assert sum(queue.get(timeout=2) for _ in processes) == 1
    # A fresh process after all earlier writers exited cannot resend uncertainty.
    barrier = ctx.Barrier(1)
    process = ctx.Process(target=_asset_worker, args=(path, barrier, queue))
    process.start()
    process.join(timeout=20)
    assert process.exitcode == 0 and queue.get(timeout=2) == 0
    queue.close()


def test_asset_transport_success_without_receipt_is_pending_and_errors_are_private():
    for failure in (False, True):
        def send(**_):
            if failure:
                raise OSError("fake-opaque fake-account fake-project token=FAKE_SECRET")
            return True
        result = publish_strategy_plugin_telegram_alerts([signal()],
            telegram_settings=StrategyPluginTelegramSettings(chat_ids=("fake-chat",), bot_token="fake-credential"),
            asset_management_event_factory=lambda _: event(incident_reason="empty_position_decision"),
            persist_candidate=lambda _: True, asset_management_incident_tracker=contract.IncidentTracker(Store()),
            send_notification=send)
        assert result.sent_count == 0
        assert result.deliveries[0].status == ("failed" if failure else "pending")
        assert all(value not in repr(result) for value in ("fake-opaque", "fake-account", "fake-project", "FAKE_SECRET"))


def test_confirmed_recovery_clears_incident_without_push_and_next_error_is_new():
    store, calls = Store(), []
    for kind in ("real_error", "recovery", "real_error"):
        result = publish_strategy_plugin_telegram_alerts([signal()],
            telegram_settings=StrategyPluginTelegramSettings(chat_ids=("fake-chat",), bot_token="fake-credential"),
            asset_management_event_factory=lambda _, kind=kind: event(kind, incident_reason="empty_position_decision"),
            persist_candidate=lambda _: True, asset_management_incident_tracker=contract.IncidentTracker(store),
            send_notification=lambda **_: calls.append(kind) or True)
        assert result.sent_count == 0
    assert calls == ["real_error", "real_error"]


def test_failed_recovery_persistence_does_not_clear_active_incident():
    store = Store()
    tracker = contract.IncidentTracker(store)
    tracker.observe(event(incident_reason="empty_position_decision"), state="real_error")
    with pytest.raises(contract.CandidatePersistenceError):
        publish_strategy_plugin_telegram_alerts([signal()], telegram_settings={},
            asset_management_event_factory=lambda _: event("recovery", incident_reason="empty_position_decision"),
            persist_candidate=lambda _: False, asset_management_incident_tracker=tracker,
            send_notification=lambda **_: pytest.fail("recovery must not push"))
    assert next(iter(store.rows.values()))[1]["active"] is True


def test_asset_error_candidate_failure_alerts_once_then_propagates_failure():
    calls, store = [], Store()
    for _ in range(2):
        with pytest.raises(contract.CandidatePersistenceError):
            publish_strategy_plugin_telegram_alerts([signal()],
                telegram_settings=StrategyPluginTelegramSettings(chat_ids=("fake-chat",), bot_token="fake-credential"),
                asset_management_event_factory=lambda _: event(incident_reason="empty_position_decision"),
                persist_candidate=lambda _: False, asset_management_incident_tracker=contract.IncidentTracker(store),
                send_notification=lambda **_: calls.append("send") or True)
    assert calls == ["send"]
