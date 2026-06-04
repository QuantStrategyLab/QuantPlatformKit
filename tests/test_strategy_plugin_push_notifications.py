import urllib.parse
from types import SimpleNamespace

from quant_platform_kit.notifications.push import (
    parse_push_recipients,
    send_ntfy_push,
    send_pushover_push,
)
from quant_platform_kit.notifications.strategy_plugin_push import (
    StrategyPluginPushAlertMarkerStore,
    StrategyPluginPushSettings,
    publish_strategy_plugin_push_alerts,
)


def test_parse_push_recipients_splits_and_deduplicates():
    assert parse_push_recipients("topic-a; topic-b,topic-a\nhttps://ntfy.example/risk") == (
        "topic-a",
        "topic-b",
        "https://ntfy.example/risk",
    )


def test_send_pushover_push_uses_configured_http_request():
    observed = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def fake_open(request, timeout):
        observed["url"] = request.full_url
        observed["timeout"] = timeout
        observed["headers"] = dict(request.header_items())
        observed["body"] = urllib.parse.parse_qs(request.data.decode("utf-8"))
        return FakeResponse()

    assert send_pushover_push(
        title="Crisis alert",
        body="危机插件告警",
        recipients=("user-key",),
        app_token="app-token",
        api_base_url="https://pushover.example.test",
        device="iphone",
        priority=1,
        timeout=3.0,
        opener=fake_open,
        printer=lambda *_args, **_kwargs: None,
    )

    assert observed["url"] == "https://pushover.example.test/1/messages.json"
    assert observed["timeout"] == 3.0
    assert observed["headers"]["Content-type"] == "application/x-www-form-urlencoded"
    assert observed["body"] == {
        "token": ["app-token"],
        "user": ["user-key"],
        "title": ["Crisis alert"],
        "message": ["危机插件告警"],
        "device": ["iphone"],
        "priority": ["1"],
    }


def test_send_ntfy_push_uses_configured_http_request_and_encodes_chinese_title():
    observed = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def fake_open(request, timeout):
        observed["url"] = request.full_url
        observed["timeout"] = timeout
        observed["headers"] = dict(request.header_items())
        observed["body"] = request.data.decode("utf-8")
        return FakeResponse()

    assert send_ntfy_push(
        title="危机插件告警",
        body="TQQQ 防守",
        recipients=("risk/topic",),
        access_token="access-token",
        api_base_url="https://ntfy.example.test",
        priority=5,
        tags="warning",
        timeout=4.0,
        opener=fake_open,
        printer=lambda *_args, **_kwargs: None,
    )

    assert observed["url"] == "https://ntfy.example.test/risk/topic"
    assert observed["timeout"] == 4.0
    assert observed["headers"]["Content-type"] == "text/plain; charset=utf-8"
    assert observed["headers"]["Title"].startswith("=?utf-8?")
    assert observed["headers"]["Priority"] == "5"
    assert observed["headers"]["Tags"] == "warning"
    assert observed["headers"]["Authorization"] == "Bearer access-token"
    assert observed["body"] == "TQQQ 防守"


def _alert_signal():
    return SimpleNamespace(
        strategy="tqqq_growth_income",
        plugin="crisis_response_shadow",
        effective_mode="shadow",
        as_of="2026-05-24",
        canonical_route="true_crisis",
        suggested_action="defend",
        would_trade_if_enabled=True,
    )


def test_publish_strategy_plugin_push_alerts_skips_missing_config():
    observed = []

    result = publish_strategy_plugin_push_alerts(
        [_alert_signal()],
        push_settings=StrategyPluginPushSettings(),
        strategy_label="TQQQ",
        context_label="ibkr / paper / tqqq",
        send_notification=lambda **_kwargs: observed.append(_kwargs) or True,
        log_message=lambda *_args, **_kwargs: None,
    )

    assert result.sent_count == 0
    assert result.skipped_count == 1
    assert result.deliveries[0].reason == "missing_push_config"
    assert "STRATEGY_PLUGIN_ALERT_PUSH_RECIPIENTS" in result.deliveries[0].error
    assert "STRATEGY_PLUGIN_ALERT_PUSH_APP_TOKEN" in result.deliveries[0].error
    assert observed == []


def test_publish_strategy_plugin_push_alerts_sends_and_records_marker(tmp_path):
    observed = []
    store = StrategyPluginPushAlertMarkerStore(local_dir=tmp_path)

    result = publish_strategy_plugin_push_alerts(
        [_alert_signal()],
        push_settings=StrategyPluginPushSettings(
            provider="ntfy",
            recipients=("risk-topic",),
            priority="5",
        ),
        strategy_label="TQQQ",
        context_label="ibkr / paper / tqqq",
        alert_store=store,
        send_notification=lambda **kwargs: observed.append(kwargs) or True,
        log_message=lambda *_args, **_kwargs: None,
    )

    assert result.sent_count == 1
    assert result.failed_count == 0
    assert result.deliveries[0].alert_key
    assert observed[0]["provider"] == "ntfy"
    assert observed[0]["recipients"] == ("risk-topic",)
    assert observed[0]["priority"] == "5"
    assert "Strategy plugin alert" in observed[0]["title"]
    assert store.has_alert(result.deliveries[0].alert_key)


def test_publish_strategy_plugin_push_alerts_skips_duplicate_marker(tmp_path):
    store = StrategyPluginPushAlertMarkerStore(local_dir=tmp_path)
    settings = StrategyPluginPushSettings(provider="ntfy", recipients=("risk-topic",))
    first = publish_strategy_plugin_push_alerts(
        [_alert_signal()],
        push_settings=settings,
        strategy_label="TQQQ",
        context_label="ibkr / paper / tqqq",
        alert_store=store,
        send_notification=lambda **_kwargs: True,
        log_message=lambda *_args, **_kwargs: None,
    )

    second = publish_strategy_plugin_push_alerts(
        [_alert_signal()],
        push_settings=settings,
        strategy_label="TQQQ",
        context_label="ibkr / paper / tqqq",
        alert_store=store,
        send_notification=lambda **_kwargs: True,
        log_message=lambda *_args, **_kwargs: None,
    )

    assert first.sent_count == 1
    assert second.sent_count == 0
    assert second.skipped_count == 1
    assert second.deliveries[0].reason == "duplicate_alert"


def test_push_settings_reads_pushover_and_ntfy_config_from_object():
    pushover = StrategyPluginPushSettings.from_object(
        SimpleNamespace(
            strategy_plugin_alert_push_recipients="user-key",
            strategy_plugin_alert_push_provider="pushover",
            strategy_plugin_alert_push_app_token="app-token",
            strategy_plugin_alert_push_device="iphone",
            strategy_plugin_alert_push_priority="1",
        )
    )
    ntfy = StrategyPluginPushSettings.from_object(
        SimpleNamespace(
            strategy_plugin_alert_push_recipients="risk-topic",
            strategy_plugin_alert_push_provider="ntfy",
            strategy_plugin_alert_push_access_token="access-token",
            strategy_plugin_alert_push_api_base_url="https://ntfy.example.test",
            strategy_plugin_alert_push_priority="5",
            strategy_plugin_alert_push_tags="warning",
            strategy_plugin_alert_push_body_max_chars="300",
        )
    )

    assert pushover.recipients == ("user-key",)
    assert pushover.provider == "pushover"
    assert pushover.app_token == "app-token"
    assert pushover.device == "iphone"
    assert pushover.priority == "1"
    assert pushover.missing_fields() == ()
    assert ntfy.recipients == ("risk-topic",)
    assert ntfy.provider == "ntfy"
    assert ntfy.access_token == "access-token"
    assert ntfy.api_base_url == "https://ntfy.example.test"
    assert ntfy.priority == "5"
    assert ntfy.tags == "warning"
    assert ntfy.body_max_chars == 300
    assert ntfy.missing_fields() == ()
