import tempfile
import unittest
from types import SimpleNamespace

from quant_platform_kit.notifications.strategy_plugin_alerts import (
    StrategyPluginAlertStateSettings,
    publish_strategy_plugin_alerts,
)
from quant_platform_kit.notifications.strategy_plugin_email import StrategyPluginEmailSettings
from quant_platform_kit.notifications.strategy_plugin_push import StrategyPluginPushSettings
from quant_platform_kit.notifications.strategy_plugin_sms import StrategyPluginSmsSettings
from quant_platform_kit.notifications.strategy_plugin_telegram import StrategyPluginTelegramSettings


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


class _NotificationSettings:
    crisis_alert_email_recipients = "risk@example.com"
    crisis_alert_email_sender_email = "bot@example.com"
    crisis_alert_email_sender_password = "app-password"
    crisis_alert_sms_recipients = "+15165480265"
    crisis_alert_sms_account_id = "AC123"
    crisis_alert_sms_auth_token = "secret"
    crisis_alert_sms_sender = "+15551234567"
    crisis_alert_push_provider = "ntfy"
    crisis_alert_push_recipients = "risk-topic"
    crisis_alert_push_priority = "5"
    crisis_alert_telegram_chat_ids = "123456"
    crisis_alert_telegram_bot_token = "bot-token"


class StrategyPluginAlertDispatcherTests(unittest.TestCase):
    def test_publish_strategy_plugin_alerts_dispatches_enabled_channels(self):
        emails = []
        sms_messages = []
        push_messages = []
        telegram_messages = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = publish_strategy_plugin_alerts(
                [_alert_signal()],
                notification_settings=_NotificationSettings(),
                strategy_label="TQQQ",
                context_label="schwab / tqqq",
                state_settings=StrategyPluginAlertStateSettings(local_dir=tmp_dir),
                send_email_notification=lambda **kwargs: emails.append(kwargs) or True,
                send_sms_notification=lambda **kwargs: sms_messages.append(kwargs) or True,
                send_push_notification=lambda **kwargs: push_messages.append(kwargs) or True,
                send_telegram_notification=lambda **kwargs: telegram_messages.append(kwargs) or True,
                log_message=lambda *_args, **_kwargs: None,
            )

        self.assertEqual(result.sent_count, 4)
        self.assertEqual(result.failed_count, 0)
        self.assertIsNotNone(result.email_result)
        self.assertIsNotNone(result.sms_result)
        self.assertIsNotNone(result.push_result)
        self.assertIsNotNone(result.telegram_result)
        self.assertEqual(result.email_result.sent_count, 1)
        self.assertEqual(result.sms_result.sent_count, 1)
        self.assertEqual(result.push_result.sent_count, 1)
        self.assertEqual(result.telegram_result.sent_count, 1)
        self.assertEqual(emails[0]["recipients"], ("risk@example.com",))
        self.assertEqual(sms_messages[0]["recipients"], ("+15165480265",))
        self.assertEqual(push_messages[0]["recipients"], ("risk-topic",))
        self.assertEqual(telegram_messages[0]["chat_ids"], ("123456",))

    def test_publish_strategy_plugin_alerts_records_channel_dedupe_independently(self):
        settings = _NotificationSettings()

        with tempfile.TemporaryDirectory() as tmp_dir:
            state_settings = StrategyPluginAlertStateSettings(local_dir=tmp_dir)
            first = publish_strategy_plugin_alerts(
                [_alert_signal()],
                notification_settings=settings,
                strategy_label="TQQQ",
                context_label="schwab / tqqq",
                state_settings=state_settings,
                send_email_notification=lambda **_kwargs: True,
                send_sms_notification=lambda **_kwargs: True,
                send_push_notification=lambda **_kwargs: True,
                send_telegram_notification=lambda **_kwargs: True,
                log_message=lambda *_args, **_kwargs: None,
            )
            second = publish_strategy_plugin_alerts(
                [_alert_signal()],
                notification_settings=settings,
                strategy_label="TQQQ",
                context_label="schwab / tqqq",
                state_settings=state_settings,
                send_email_notification=lambda **_kwargs: True,
                send_sms_notification=lambda **_kwargs: True,
                send_push_notification=lambda **_kwargs: True,
                send_telegram_notification=lambda **_kwargs: True,
                log_message=lambda *_args, **_kwargs: None,
            )

        self.assertEqual(first.sent_count, 4)
        self.assertEqual(second.sent_count, 0)
        self.assertEqual(second.skipped_count, 4)
        self.assertIsNotNone(second.email_result)
        self.assertEqual(second.email_result.deliveries[0].reason, "duplicate_alert")
        self.assertIsNotNone(second.sms_result)
        self.assertEqual(second.sms_result.deliveries[0].reason, "duplicate_alert")
        self.assertIsNotNone(second.push_result)
        self.assertEqual(second.push_result.deliveries[0].reason, "duplicate_alert")
        self.assertIsNotNone(second.telegram_result)
        self.assertEqual(second.telegram_result.deliveries[0].reason, "duplicate_alert")

    def test_publish_strategy_plugin_alerts_can_target_one_channel(self):
        sms_messages = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = publish_strategy_plugin_alerts(
                [_alert_signal()],
                notification_settings=StrategyPluginSmsSettings(
                    recipients=("+15165480265",),
                    account_id="AC123",
                    auth_token="secret",
                    sender="+15551234567",
                ),
                channels=("sms",),
                strategy_label="TQQQ",
                context_label="schwab / tqqq",
                state_settings=StrategyPluginAlertStateSettings(local_dir=tmp_dir),
                send_email_notification=lambda **_kwargs: self.fail("email should not run"),
                send_sms_notification=lambda **kwargs: sms_messages.append(kwargs) or True,
                send_telegram_notification=lambda **_kwargs: self.fail("telegram should not run"),
                log_message=lambda *_args, **_kwargs: None,
            )

        self.assertIsNone(result.email_result)
        self.assertIsNotNone(result.sms_result)
        self.assertEqual(result.sent_count, 1)
        self.assertTrue(sms_messages)

    def test_publish_strategy_plugin_alerts_can_target_push_channel(self):
        push_messages = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = publish_strategy_plugin_alerts(
                [_alert_signal()],
                notification_settings=StrategyPluginPushSettings(
                    provider="ntfy",
                    recipients=("risk-topic",),
                    priority="5",
                ),
                channels=("push",),
                strategy_label="TQQQ",
                context_label="schwab / tqqq",
                state_settings=StrategyPluginAlertStateSettings(local_dir=tmp_dir),
                send_email_notification=lambda **_kwargs: self.fail("email should not run"),
                send_sms_notification=lambda **_kwargs: self.fail("sms should not run"),
                send_push_notification=lambda **kwargs: push_messages.append(kwargs) or True,
                log_message=lambda *_args, **_kwargs: None,
            )

        self.assertIsNone(result.email_result)
        self.assertIsNone(result.sms_result)
        self.assertIsNotNone(result.push_result)
        self.assertIsNone(result.telegram_result)
        self.assertEqual(result.sent_count, 1)
        self.assertEqual(push_messages[0]["provider"], "ntfy")

    def test_publish_strategy_plugin_alerts_can_target_telegram_channel(self):
        telegram_messages = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = publish_strategy_plugin_alerts(
                [_alert_signal()],
                notification_settings=StrategyPluginTelegramSettings(
                    chat_ids=("123456",),
                    bot_token="bot-token",
                ),
                channels=("telegram",),
                strategy_label="TQQQ",
                context_label="ibkr / live-slot-a",
                state_settings=StrategyPluginAlertStateSettings(local_dir=tmp_dir),
                send_email_notification=lambda **_kwargs: self.fail("email should not run"),
                send_sms_notification=lambda **_kwargs: self.fail("sms should not run"),
                send_push_notification=lambda **_kwargs: self.fail("push should not run"),
                send_telegram_notification=lambda **kwargs: telegram_messages.append(kwargs) or True,
                log_message=lambda *_args, **_kwargs: None,
            )

        self.assertIsNone(result.email_result)
        self.assertIsNone(result.sms_result)
        self.assertIsNone(result.push_result)
        self.assertIsNotNone(result.telegram_result)
        self.assertEqual(result.sent_count, 1)
        self.assertEqual(telegram_messages[0]["chat_ids"], ("123456",))

    def test_publish_strategy_plugin_alerts_reads_channels_from_settings(self):
        settings = _NotificationSettings()
        settings.crisis_alert_channels = "email,telegram"
        emails = []
        telegram_messages = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = publish_strategy_plugin_alerts(
                [_alert_signal()],
                notification_settings=settings,
                strategy_label="TQQQ",
                context_label="schwab / tqqq",
                state_settings=StrategyPluginAlertStateSettings(local_dir=tmp_dir),
                send_email_notification=lambda **kwargs: emails.append(kwargs) or True,
                send_sms_notification=lambda **_kwargs: self.fail("sms should not run"),
                send_push_notification=lambda **_kwargs: self.fail("push should not run"),
                send_telegram_notification=lambda **kwargs: telegram_messages.append(kwargs) or True,
                log_message=lambda *_args, **_kwargs: None,
            )

        self.assertEqual(result.sent_count, 2)
        self.assertIsNotNone(result.email_result)
        self.assertIsNone(result.sms_result)
        self.assertIsNone(result.push_result)
        self.assertIsNotNone(result.telegram_result)
        self.assertEqual(len(emails), 1)
        self.assertEqual(len(telegram_messages), 1)

    def test_publish_strategy_plugin_alerts_attach_to_report(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = publish_strategy_plugin_alerts(
                [_alert_signal()],
                notification_settings=StrategyPluginEmailSettings(
                    recipients=("risk@example.com",),
                    sender_email="bot@example.com",
                    sender_password="app-password",
                ),
                channels=("email",),
                strategy_label="TQQQ",
                context_label="schwab / tqqq",
                state_settings=StrategyPluginAlertStateSettings(local_dir=tmp_dir),
                send_email_notification=lambda **_kwargs: True,
                log_message=lambda *_args, **_kwargs: None,
            )
        report = {}

        result.attach_to_report(report)

        self.assertEqual(report["summary"]["strategy_plugin_alert_sent_count"], 1)
        self.assertEqual(report["summary"]["strategy_plugin_alert_email_sent_count"], 1)
        self.assertEqual(report["diagnostics"]["strategy_plugin_alert_sent_count"], 1)
        self.assertEqual(report["diagnostics"]["strategy_plugin_alert_email_sent_count"], 1)
        self.assertNotIn("strategy_plugin_alert_sms_sent_count", report["summary"])
        self.assertNotIn("strategy_plugin_alert_telegram_sent_count", report["summary"])

    def test_publish_strategy_plugin_alerts_rejects_unknown_channel(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaisesRegex(ValueError, "unsupported strategy plugin alert channel"):
                publish_strategy_plugin_alerts(
                    [_alert_signal()],
                    notification_settings=_NotificationSettings(),
                    channels=("pager",),
                    state_settings=StrategyPluginAlertStateSettings(local_dir=tmp_dir),
                    log_message=lambda *_args, **_kwargs: None,
                )

    def test_strategy_plugin_alert_state_settings_reads_env_with_fallback(self):
        values = {
            "STRATEGY_PLUGIN_ALERT_STATE_DIR": "/tmp/custom-alerts",
            "EXECUTION_REPORT_GCS_URI": "gs://reports/runtime",
        }

        settings = StrategyPluginAlertStateSettings.from_env(
            env_reader=lambda name, default=None: values.get(name, default),
            gcp_project_id="project-a",
            fallback_gcs_prefix_uri="gs://state/fallback",
        )

        self.assertEqual(settings.local_dir, "/tmp/custom-alerts")
        self.assertEqual(settings.gcs_prefix_uri, "gs://reports/runtime")
        self.assertEqual(settings.gcp_project_id, "project-a")


if __name__ == "__main__":
    unittest.main()
