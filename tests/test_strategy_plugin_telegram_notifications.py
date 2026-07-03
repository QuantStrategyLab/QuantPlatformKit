import json
import tempfile
import unittest
from types import SimpleNamespace

from quant_platform_kit.common.notification_localization import STRATEGY_PLUGIN_I18N
from quant_platform_kit.notifications.strategy_plugin_telegram import (
    StrategyPluginTelegramSettings,
    publish_strategy_plugin_telegram_alerts,
)
from quant_platform_kit.notifications.telegram import (
    parse_telegram_chat_ids,
    send_strategy_plugin_telegram,
    send_telegram_message,
)


def _alert_signal():
    return SimpleNamespace(
        strategy="tqqq_growth_income",
        plugin="market_regime_control",
        effective_mode="shadow",
        as_of="2026-05-24",
        canonical_route="opportunity_watch",
        suggested_action="notify_manual_review",
        would_trade_if_enabled=False,
        execution_controls={"notification_profile": "shadow_only"},
    )


def _auto_consumable_signal():
    return SimpleNamespace(
        strategy="tqqq_growth_income",
        plugin="market_regime_control",
        effective_mode="shadow",
        as_of="2026-05-24",
        canonical_route="risk_off",
        suggested_action="defend",
        would_trade_if_enabled=True,
        execution_controls={
            "strategy_runtime_metadata_allowed": True,
            "position_control_allowed": True,
            "consumption_evidence_status": "automation_approved",
        },
    )


class _FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class StrategyPluginTelegramNotificationTests(unittest.TestCase):
    def test_parse_telegram_chat_ids_accepts_common_separators(self):
        self.assertEqual(
            parse_telegram_chat_ids("123; -456\n@risk_channel,123"),
            ("123", "-456", "@risk_channel"),
        )

    def test_send_telegram_message_posts_json_for_each_chat(self):
        requests = []

        def opener(request, timeout):
            requests.append((request, timeout))
            return _FakeResponse()

        sent = send_telegram_message(
            text="危机通知",
            chat_ids=("123", "@risk_channel"),
            bot_token="123456:ABC",
            api_base_url="https://telegram.example.test",
            timeout=3.0,
            opener=opener,
        )

        self.assertTrue(sent)
        self.assertEqual(len(requests), 2)
        first_request, timeout = requests[0]
        self.assertEqual(timeout, 3.0)
        self.assertEqual(
            first_request.full_url,
            "https://telegram.example.test/bot123456:ABC/sendMessage",
        )
        payload = json.loads(first_request.data.decode("utf-8"))
        self.assertEqual(payload["chat_id"], "123")
        self.assertEqual(payload["text"], "危机通知")
        self.assertTrue(payload["disable_web_page_preview"])

    def test_send_telegram_message_breaks_market_symbol_auto_links(self):
        requests = []

        def opener(request, timeout):
            requests.append((request, timeout))
            return _FakeResponse()

        sent = send_telegram_message(
            text="SOXL.US 预计；00700.HK 持仓；https://example.com 保持原样",
            chat_ids=("123",),
            bot_token="123456:ABC",
            api_base_url="https://telegram.example.test",
            opener=opener,
        )

        self.assertTrue(sent)
        payload = json.loads(requests[0][0].data.decode("utf-8"))
        self.assertEqual(
            payload["text"],
            "SOXL.\u2060US 预计；00700.\u2060HK 持仓；https://example.com 保持原样",
        )

    def test_send_strategy_plugin_telegram_combines_title_and_body(self):
        requests = []

        def opener(request, timeout):
            requests.append(request)
            return _FakeResponse()

        sent = send_strategy_plugin_telegram(
            title="标题",
            body="正文",
            chat_ids=("123",),
            bot_token="token",
            api_base_url="https://telegram.example.test",
            opener=opener,
        )

        self.assertTrue(sent)
        payload = json.loads(requests[0].data.decode("utf-8"))
        self.assertEqual(payload["text"], "标题\n\n正文")

    def test_strategy_plugin_telegram_settings_from_object(self):
        settings = StrategyPluginTelegramSettings.from_object(
            SimpleNamespace(
                strategy_plugin_alert_telegram_chat_ids="123; @risk",
                strategy_plugin_alert_telegram_bot_token="bot-token",
                strategy_plugin_alert_telegram_api_base_url="https://telegram.example.test",
                strategy_plugin_alert_telegram_parse_mode="HTML",
                strategy_plugin_alert_telegram_disable_web_page_preview="false",
                strategy_plugin_alert_telegram_body_max_chars="500",
            )
        )

        self.assertEqual(settings.chat_ids, ("123", "@risk"))
        self.assertEqual(settings.bot_token, "bot-token")
        self.assertEqual(settings.api_base_url, "https://telegram.example.test")
        self.assertEqual(settings.parse_mode, "HTML")
        self.assertFalse(settings.disable_web_page_preview)
        self.assertEqual(settings.body_max_chars, 500)
        self.assertEqual(settings.missing_fields(), ())

    def test_publish_strategy_plugin_telegram_alerts_sends_and_dedupes(self):
        calls = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            settings = StrategyPluginTelegramSettings(
                chat_ids=("123",),
                bot_token="bot-token",
            )
            first = publish_strategy_plugin_telegram_alerts(
                [_alert_signal()],
                telegram_settings=settings,
                strategy_label="TQQQ",
                context_label="ibkr / live-slot-a",
                alert_store=SimpleNamespace(
                    has_alert=lambda _key: False,
                    record_alert=lambda _key, **_kwargs: None,
                ),
                send_notification=lambda **kwargs: calls.append(kwargs) or True,
                log_message=lambda *_args, **_kwargs: None,
            )
            second = publish_strategy_plugin_telegram_alerts(
                [_alert_signal()],
                telegram_settings=settings,
                strategy_label="TQQQ",
                context_label="ibkr / live-slot-a",
                alert_store=SimpleNamespace(
                    has_alert=lambda _key: True,
                    record_alert=lambda _key, **_kwargs: self.fail("duplicate should not record"),
                ),
                send_notification=lambda **_kwargs: self.fail("duplicate should not send"),
                log_message=lambda *_args, **_kwargs: None,
            )

        self.assertEqual(first.sent_count, 1)
        self.assertEqual(second.skipped_count, 1)
        self.assertEqual(second.deliveries[0].reason, "duplicate_alert")
        self.assertEqual(calls[0]["chat_ids"], ("123",))
        self.assertIn("Unified manual-review signal", calls[0]["body"])
        self.assertNotIn("ibkr / live-slot-a", calls[0]["body"])
        self.assertTrue(tmp_dir)

    def test_publish_strategy_plugin_telegram_alerts_skips_auto_consumable_signals(self):
        calls = []

        result = publish_strategy_plugin_telegram_alerts(
            [_auto_consumable_signal()],
            telegram_settings=StrategyPluginTelegramSettings(
                chat_ids=("123",),
                bot_token="bot-token",
            ),
            send_notification=lambda **kwargs: calls.append(kwargs) or True,
            log_message=lambda *_args, **_kwargs: None,
        )

        self.assertEqual(result.attempted_count, 0)
        self.assertEqual(result.sent_count, 0)
        self.assertEqual(calls, [])

    def test_publish_strategy_plugin_telegram_alerts_compacts_market_regime_body(self):
        calls = []
        translations = STRATEGY_PLUGIN_I18N["zh"]
        signal = SimpleNamespace(
            strategy="tqqq_growth_income",
            plugin="market_regime_control",
            effective_mode="shadow",
            as_of="2026-06-19",
            canonical_route="opportunity_watch",
            suggested_action="notify_manual_review",
            would_trade_if_enabled=False,
            execution_controls={"notification_profile": "shadow_only"},
            payload={
                "localized_messages": {
                    "default_locale": "zh-CN",
                    "labels": {"reason_codes": {"zh-CN": ["价格反弹待确认"]}},
                },
            },
        )

        result = publish_strategy_plugin_telegram_alerts(
            [signal],
            telegram_settings=StrategyPluginTelegramSettings(
                chat_ids=("123",),
                bot_token="bot-token",
            ),
            translator=lambda key, **kwargs: translations.get(key, key).format(**kwargs)
            if kwargs
            else translations.get(key, key),
            alert_store=SimpleNamespace(
                has_alert=lambda _key: False,
                record_alert=lambda _key, **_kwargs: None,
            ),
            send_notification=lambda **kwargs: calls.append(kwargs) or True,
            log_message=lambda *_args, **_kwargs: None,
        )

        self.assertEqual(result.sent_count, 1)
        self.assertEqual(calls[0]["title"], "")
        self.assertEqual(
            calls[0]["body"],
            "\n".join(
                (
                    "统一人工复核信号",
                    "日期：2026-06-19",
                    "市场状态：抄底机会",
                    "背景情况：机会观察：出现可能的反弹或低吸窗口，当前证据只够人工复核。",
                    "建议操作：人工核对反弹质量、成交/趋势确认和失效条件；确认前只作为低吸候选，不直接转成自动买入。",
                )
            ),
        )
        self.assertNotIn("策略插件提醒", calls[0]["body"])
        self.assertNotIn("插件：", calls[0]["body"])

    def test_publish_strategy_plugin_telegram_alerts_skips_when_missing_config(self):
        result = publish_strategy_plugin_telegram_alerts(
            [_alert_signal()],
            telegram_settings=SimpleNamespace(),
            log_message=lambda *_args, **_kwargs: None,
        )

        self.assertEqual(result.sent_count, 0)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(result.deliveries[0].reason, "missing_telegram_config")
        self.assertIn("STRATEGY_PLUGIN_ALERT_TELEGRAM_CHAT_IDS", result.deliveries[0].error)
        self.assertIn("STRATEGY_PLUGIN_ALERT_TELEGRAM_BOT_TOKEN", result.deliveries[0].error)


if __name__ == "__main__":
    unittest.main()
