import base64
import urllib.parse
from types import SimpleNamespace

from quant_platform_kit.notifications.sms import parse_sms_recipients, send_twilio_sms
from quant_platform_kit.notifications.strategy_plugin_sms import (
    StrategyPluginSmsAlertMarkerStore,
    StrategyPluginSmsSettings,
    publish_strategy_plugin_sms_alerts,
)


def test_parse_sms_recipients_normalizes_and_deduplicates():
    assert parse_sms_recipients("(516) 548-0265;15165480265,+1 516 548 0265\n+8613800000000") == (
        "+15165480265",
        "+8613800000000",
    )


def test_send_twilio_sms_uses_configured_http_request():
    observed = {}

    class FakeResponse:
        status = 201

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

    assert send_twilio_sms(
        body="Crisis alert",
        recipients=("(516) 548-0265",),
        account_sid="AC123",
        auth_token="secret",
        from_number="+15551234567",
        api_base_url="https://twilio.example.test",
        timeout=3.0,
        opener=fake_open,
        printer=lambda *_args, **_kwargs: None,
    )

    assert observed["url"] == "https://twilio.example.test/2010-04-01/Accounts/AC123/Messages.json"
    assert observed["timeout"] == 3.0
    assert observed["headers"]["Authorization"] == (
        "Basic " + base64.b64encode(b"AC123:secret").decode("ascii")
    )
    assert observed["headers"]["Content-type"] == "application/x-www-form-urlencoded"
    assert observed["body"] == {
        "To": ["+15165480265"],
        "Body": ["Crisis alert"],
        "From": ["+15551234567"],
    }


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


def test_publish_strategy_plugin_sms_alerts_skips_missing_config():
    observed = []

    result = publish_strategy_plugin_sms_alerts(
        [_alert_signal()],
        sms_settings=StrategyPluginSmsSettings(),
        strategy_label="TQQQ",
        context_label="ibkr / paper / tqqq",
        send_notification=lambda **_kwargs: observed.append(_kwargs) or True,
        log_message=lambda *_args, **_kwargs: None,
    )

    assert result.sent_count == 0
    assert result.skipped_count == 1
    assert result.deliveries[0].reason == "missing_sms_config"
    assert "CRISIS_ALERT_SMS_RECIPIENTS" in result.deliveries[0].error
    assert "CRISIS_ALERT_SMS_ACCOUNT_ID" in result.deliveries[0].error
    assert "CRISIS_ALERT_SMS_AUTH_TOKEN" in result.deliveries[0].error
    assert "CRISIS_ALERT_SMS_SENDER or CRISIS_ALERT_SMS_MESSAGING_SERVICE_ID" in result.deliveries[0].error
    assert observed == []


def test_publish_strategy_plugin_sms_alerts_sends_and_records_marker(tmp_path):
    observed = []
    store = StrategyPluginSmsAlertMarkerStore(local_dir=tmp_path)

    result = publish_strategy_plugin_sms_alerts(
        [_alert_signal()],
        sms_settings=StrategyPluginSmsSettings(
            recipients=("+15165480265",),
            account_id="AC123",
            auth_token="secret",
            sender="+15551234567",
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
    assert "[ibkr / paper / tqqq]" in observed[0]["body"]
    assert observed[0]["recipients"] == ("+15165480265",)
    assert observed[0]["account_sid"] == "AC123"
    assert observed[0]["auth_token"] == "secret"
    assert observed[0]["from_number"] == "+15551234567"
    assert observed[0]["messaging_service_sid"] is None
    assert observed[0]["api_base_url"] == "https://api.twilio.com"
    assert observed[0]["timeout"] == 10.0
    assert store.has_alert(result.deliveries[0].alert_key)


def test_publish_strategy_plugin_sms_alerts_skips_duplicate_marker(tmp_path):
    store = StrategyPluginSmsAlertMarkerStore(local_dir=tmp_path)
    settings = StrategyPluginSmsSettings(
        recipients=("+15165480265",),
        account_id="AC123",
        auth_token="secret",
        sender="+15551234567",
    )
    first = publish_strategy_plugin_sms_alerts(
        [_alert_signal()],
        sms_settings=settings,
        strategy_label="TQQQ",
        context_label="ibkr / paper / tqqq",
        alert_store=store,
        send_notification=lambda **_kwargs: True,
        log_message=lambda *_args, **_kwargs: None,
    )

    second = publish_strategy_plugin_sms_alerts(
        [_alert_signal()],
        sms_settings=settings,
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


def test_sms_settings_reads_twilio_config_from_object():
    settings = StrategyPluginSmsSettings.from_object(
        SimpleNamespace(
            crisis_alert_sms_recipients="(516) 548-0265",
            crisis_alert_sms_provider="twilio",
            crisis_alert_sms_account_id="AC123",
            crisis_alert_sms_auth_token="secret",
            crisis_alert_sms_messaging_service_id="MG123",
            crisis_alert_sms_api_base_url="https://twilio.example.test",
            crisis_alert_sms_body_max_chars="160",
        )
    )

    assert settings.recipients == ("+15165480265",)
    assert settings.provider == "twilio"
    assert settings.account_id == "AC123"
    assert settings.auth_token == "secret"
    assert settings.messaging_service_id == "MG123"
    assert settings.api_base_url == "https://twilio.example.test"
    assert settings.body_max_chars == 160
    assert settings.missing_fields() == ()
