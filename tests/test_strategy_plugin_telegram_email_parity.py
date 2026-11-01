"""Exercise channel eligibility through the public publishers with fake transports."""

from itertools import product
from types import SimpleNamespace

import pytest

from quant_platform_kit.notifications import strategy_plugin_telegram as telegram
from quant_platform_kit.notifications.strategy_plugin_email import (
    StrategyPluginEmailSettings,
    publish_strategy_plugin_email_alerts,
)


def _signal(**overrides):
    values = dict(
        strategy="example_strategy",
        plugin="example_plugin",
        effective_mode="shadow",
        as_of="2026-06-19",
        canonical_route="no_action",
        suggested_action="blocked",
        target_type="strategy",
        would_trade_if_enabled=False,
        execution_controls={},
        payload={},
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _publish(signal, *, telegram_settings=None, alert_store=None):
    email_calls, telegram_calls = [], []
    email = publish_strategy_plugin_email_alerts(
        [signal],
        email_settings=StrategyPluginEmailSettings(
            recipients=("alerts@example.test",),
            sender_email="sender@example.test",
            sender_password="synthetic-test-password",
        ),
        send_notification=lambda **kwargs: email_calls.append(kwargs) or True,
        log_message=lambda *_args, **_kwargs: None,
    )
    result = telegram.publish_strategy_plugin_telegram_alerts(
        [signal],
        telegram_settings=telegram_settings or telegram.StrategyPluginTelegramSettings(
            chat_ids=("123",), bot_token="synthetic-test-token",
        ),
        alert_store=alert_store,
        send_notification=lambda **kwargs: telegram_calls.append(kwargs) or True,
        log_message=lambda *_args, **_kwargs: None,
    )
    assert email.sent_count == len(email_calls)
    assert result.sent_count == len(telegram_calls)
    return email, result, telegram_calls


@pytest.mark.parametrize("mode", ["immediate", "daily_digest"])
@pytest.mark.parametrize(
    "action",
    ["defend", "delever", "blocked", "notify_manual_review", "watch", "observe",
     "hold", "unknown", None],
)
def test_email_eligible_signals_reach_telegram_or_routine_digest(monkeypatch, mode, action):
    monkeypatch.setenv("QSL_ROUTINE_NOTIFICATION_MODE", mode)
    evidence = (
        ({}, {}),
        ({"consumption_evidence_status": "notification_only"}, {}),
        ({"notification_profile": "shadow_only"}, {}),
        ({}, {"consumption_policy": {"evidence_status": "notification_only"}}),
        ({}, {"consumption_policy": {"capital_impact": "shadow_only"}}),
    )
    cases = product(
        ("no_action", "watch", "opportunity_watch", "panic_reversal", "taco_rebound",
         "crisis", "risk_off", "unknown_route"),
        ("strategy", "notification_target"),
        (False, True),
        evidence,
        (None, "error", "errors", "risk_halt", "auth_expired"),
    )
    for route, target, would_trade, (controls, payload), failure in cases:
        signal = _signal(
            suggested_action=action, canonical_route=route, target_type=target,
            would_trade_if_enabled=would_trade, execution_controls=controls,
            payload=payload, **({failure: True} if failure else {}),
        )
        email, result, _calls = _publish(signal)
        deferred = (
            mode == "daily_digest"
            and route in {"watch", "opportunity_watch", "panic_reversal", "taco_rebound"}
            and action in {"notify_manual_review", "watch", "observe"}
            and failure is None
        )
        case = (mode, action, route, target, would_trade, controls, payload, failure)
        assert result.sent_count == (email.sent_count if not deferred else 0), case
        assert result.failed_count == 0, case


def test_blocked_without_notification_evidence_reaches_telegram(monkeypatch):
    monkeypatch.setenv("QSL_ROUTINE_NOTIFICATION_MODE", "immediate")
    email, result, calls = _publish(_signal())
    assert email.sent_count == result.sent_count == len(calls) == 1


def test_routine_watch_stays_deferred_in_daily_digest(monkeypatch):
    monkeypatch.setenv("QSL_ROUTINE_NOTIFICATION_MODE", "daily_digest")
    email, result, calls = _publish(_signal(
        canonical_route="watch", suggested_action="watch",
        execution_controls={"notification_profile": "shadow_only"},
    ))
    assert email.sent_count == 1
    assert result.attempted_count == 0
    assert calls == []


@pytest.mark.parametrize("target", ["strategy", "notification_target"])
def test_delegated_review_exclusion_stays_shared(monkeypatch, target):
    monkeypatch.setenv("QSL_ROUTINE_NOTIFICATION_MODE", "immediate")
    email, result, _calls = _publish(_signal(
        target_type=target,
        execution_controls={
            "manual_review_notification_delegated": True,
            "manual_review_notification_target": "example_notification_target",
        },
    ))
    assert email.sent_count == result.sent_count == (target == "notification_target")


@pytest.mark.parametrize("action", ["defend", "delever"])
@pytest.mark.parametrize("policy_source", ["execution_controls", "payload"])
def test_auto_consumable_exclusion_is_preserved(monkeypatch, action, policy_source):
    monkeypatch.setenv("QSL_ROUTINE_NOTIFICATION_MODE", "immediate")
    controls = {"consumption_evidence_status": "automation_approved",
                "position_control_allowed": True}
    payload = {"consumption_policy": {"evidence_status": "automation_approved",
                                      "position_control_allowed": True}}
    signal = _signal(
        suggested_action=action, canonical_route="risk_off",
        target_type="notification_target",
        execution_controls=controls if policy_source == "execution_controls" else {},
        payload=payload if policy_source == "payload" else {},
    )
    # The current sidecar policy disables direct position control: still alert.
    monkeypatch.setattr(telegram, "STRATEGY_PLUGIN_DIRECT_POSITION_CONTROL_ALLOWED", False)
    email, result, _calls = _publish(signal)
    assert email.sent_count == result.sent_count == 1
    # Preserve the historical exclusion if that policy is ever enabled again.
    monkeypatch.setattr(telegram, "STRATEGY_PLUGIN_DIRECT_POSITION_CONTROL_ALLOWED", True)
    email, result, calls = _publish(signal)
    assert email.sent_count == 1
    assert result.attempted_count == 0
    assert calls == []


def test_new_alert_keeps_marker_namespace_dedupe_and_body_limit(monkeypatch):
    monkeypatch.setenv("QSL_ROUTINE_NOTIFICATION_MODE", "immediate")
    recorded = []
    settings = telegram.StrategyPluginTelegramSettings(
        chat_ids=("123",), bot_token="synthetic-test-token", body_max_chars=120,
    )
    store = SimpleNamespace(
        has_alert=lambda key: key in recorded,
        record_alert=lambda key, **_kwargs: recorded.append(key),
    )
    signal = _signal()
    _email, first, calls = _publish(signal, telegram_settings=settings, alert_store=store)
    assert first.sent_count == 1
    assert len(calls[0]["body"]) <= 120
    assert len(recorded) == 1
    assert recorded[0].startswith("strategy_plugin_telegram_alert/")
    _email, second, calls = _publish(signal, telegram_settings=settings, alert_store=store)
    assert second.skipped_count == 1
    assert second.deliveries[0].reason == "duplicate_alert"
    assert calls == []
    assert len(recorded) == 1


def test_new_alert_keeps_missing_config_skip(monkeypatch):
    monkeypatch.setenv("QSL_ROUTINE_NOTIFICATION_MODE", "immediate")
    _email, result, calls = _publish(
        _signal(), telegram_settings=telegram.StrategyPluginTelegramSettings(),
    )
    assert result.skipped_count == 1
    assert result.deliveries[0].reason == "missing_telegram_config"
    assert calls == []
