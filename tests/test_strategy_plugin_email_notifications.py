from types import SimpleNamespace

from quant_platform_kit.notifications.email import parse_email_recipients, send_smtp_email
from quant_platform_kit.notifications.strategy_plugin_email import (
    StrategyPluginEmailAlertMarkerStore,
    StrategyPluginEmailSettings,
    publish_strategy_plugin_email_alerts,
)


def test_parse_email_recipients_splits_and_deduplicates():
    assert parse_email_recipients("ops@example.com; risk@example.com, ops@example.com\n") == (
        "ops@example.com",
        "risk@example.com",
    )


def test_send_smtp_email_uses_configured_smtp_client():
    observed = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            observed["connect"] = (host, port, timeout)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def starttls(self):
            observed["starttls"] = True

        def login(self, username, password):
            observed["login"] = (username, password)

        def send_message(self, message):
            observed["message"] = message

    class FakeSmtpModule:
        SMTP = FakeSMTP
        SMTP_SSL = FakeSMTP

    assert send_smtp_email(
        subject="Crisis",
        body="body",
        smtp_host="smtp.example.com",
        smtp_port=587,
        sender="bot@example.com",
        recipients=("risk@example.com",),
        username="user",
        password="pass",
        smtp_module=FakeSmtpModule,
    )
    assert observed["connect"] == ("smtp.example.com", 587, 10.0)
    assert observed["starttls"] is True
    assert observed["login"] == ("user", "pass")
    assert observed["message"]["Subject"] == "Crisis"
    assert observed["message"]["To"] == "risk@example.com"


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


def test_publish_strategy_plugin_email_alerts_skips_missing_config():
    observed = []

    result = publish_strategy_plugin_email_alerts(
        [_alert_signal()],
        email_settings=StrategyPluginEmailSettings(),
        strategy_label="TQQQ",
        context_label="ibkr / paper / tqqq",
        send_notification=lambda **_kwargs: observed.append(_kwargs) or True,
        log_message=lambda *_args, **_kwargs: None,
    )

    assert result.sent_count == 0
    assert result.skipped_count == 1
    assert result.deliveries[0].reason == "missing_email_config"
    assert "STRATEGY_PLUGIN_ALERT_EMAIL_RECIPIENTS" in result.deliveries[0].error
    assert "STRATEGY_PLUGIN_ALERT_EMAIL_SENDER_EMAIL" in result.deliveries[0].error
    assert "STRATEGY_PLUGIN_ALERT_EMAIL_SENDER_PASSWORD" in result.deliveries[0].error
    assert observed == []


def test_publish_strategy_plugin_email_alerts_sends_and_records_marker(tmp_path):
    observed = []
    store = StrategyPluginEmailAlertMarkerStore(local_dir=tmp_path)

    result = publish_strategy_plugin_email_alerts(
        [_alert_signal()],
        email_settings=StrategyPluginEmailSettings(
            recipients=("risk@example.com",),
            sender_email="bot@example.com",
            sender_password="app-password",
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
    assert "[ibkr / paper / tqqq]" in observed[0]["subject"]
    assert observed[0]["smtp_host"] == "smtp.gmail.com"
    assert observed[0]["smtp_port"] == 465
    assert observed[0]["sender"] == "bot@example.com"
    assert observed[0]["recipients"] == ("risk@example.com",)
    assert observed[0]["username"] == "bot@example.com"
    assert observed[0]["password"] == "app-password"
    assert observed[0]["use_starttls"] is False
    assert observed[0]["use_ssl"] is True
    assert store.has_alert(result.deliveries[0].alert_key)


def test_publish_strategy_plugin_email_alerts_skips_duplicate_marker(tmp_path):
    store = StrategyPluginEmailAlertMarkerStore(local_dir=tmp_path)
    settings = StrategyPluginEmailSettings(
        recipients=("risk@example.com",),
        sender_email="bot@example.com",
        sender_password="app-password",
    )
    first = publish_strategy_plugin_email_alerts(
        [_alert_signal()],
        email_settings=settings,
        strategy_label="TQQQ",
        context_label="ibkr / paper / tqqq",
        alert_store=store,
        send_notification=lambda **_kwargs: True,
        log_message=lambda *_args, **_kwargs: None,
    )

    second = publish_strategy_plugin_email_alerts(
        [_alert_signal()],
        email_settings=settings,
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


def test_publish_strategy_plugin_email_alerts_uses_transport_overrides():
    observed = []

    result = publish_strategy_plugin_email_alerts(
        [_alert_signal()],
        email_settings=StrategyPluginEmailSettings(
            recipients=("voice@example.com",),
            sender_email="bot@example.com",
            sender_password="secret",
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_security="starttls",
        ),
        strategy_label="TQQQ",
        context_label="ibkr / paper / tqqq",
        send_notification=lambda **kwargs: observed.append(kwargs) or True,
        log_message=lambda *_args, **_kwargs: None,
    )

    assert result.sent_count == 1
    assert observed[0]["smtp_host"] == "smtp.example.com"
    assert observed[0]["smtp_port"] == 587
    assert observed[0]["use_starttls"] is True
    assert observed[0]["use_ssl"] is False


def test_email_settings_reads_sender_and_default_transport_names_only():
    settings = StrategyPluginEmailSettings.from_object(
        SimpleNamespace(
            strategy_plugin_alert_email_recipients="alerts@example.com; voice@example.com",
            strategy_plugin_alert_email_sender_email="sender@example.com",
            strategy_plugin_alert_email_sender_password="app-password",
        )
    )

    assert settings.sender_email == "sender@example.com"
    assert settings.recipients == ("alerts@example.com", "voice@example.com")
    assert settings.sender_password == "app-password"
    assert settings.smtp_host == "smtp.gmail.com"
    assert settings.smtp_port == 465
    assert settings.smtp_security == "ssl"
    assert settings.missing_fields() == ()


def test_email_settings_reads_optional_smtp_transport_overrides():
    settings = StrategyPluginEmailSettings.from_object(
        SimpleNamespace(
            strategy_plugin_alert_email_recipients="voice@example.com",
            strategy_plugin_alert_email_sender_email="sender@example.com",
            strategy_plugin_alert_email_sender_password="secret",
            strategy_plugin_alert_email_smtp_host="smtp.example.com",
            strategy_plugin_alert_email_smtp_port="587",
            strategy_plugin_alert_email_smtp_security="starttls",
        )
    )

    assert settings.smtp_host == "smtp.example.com"
    assert settings.smtp_port == 587
    assert settings.smtp_security == "starttls"
