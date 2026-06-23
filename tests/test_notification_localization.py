from __future__ import annotations

import unittest

from quant_platform_kit.common.notification_localization import (
    COMMON_ZH_NOTIFICATION_REPLACEMENTS,
    STRATEGY_PLUGIN_I18N,
    localize_price_source_label,
    localize_notification_text,
    merge_strategy_plugin_i18n,
    translator_uses_zh,
)


def _translator_factory(no_trades_text: str):
    def _translator(key: str, **_kwargs) -> str:
        if key == "no_trades":
            return no_trades_text
        return key

    return _translator


class NotificationLocalizationTests(unittest.TestCase):
    def test_translator_uses_zh_detects_chinese_output(self):
        self.assertTrue(translator_uses_zh(_translator_factory("无需交易")))
        self.assertFalse(translator_uses_zh(_translator_factory("No trades")))

    def test_localize_notification_text_applies_common_replacements(self):
        localized = localize_notification_text(
            "no-op | reason=outside_monthly_execution_window | snapshot=2026-04-16",
            translator=_translator_factory("无需交易"),
        )

        self.assertEqual(
            localized,
            "不执行 | 原因=当前不在月度执行窗口 | 快照日期=2026-04-16",
        )

    def test_localize_notification_text_keeps_english_for_non_zh_translator(self):
        text = "no-op | reason=outside_monthly_execution_window"
        self.assertEqual(
            localize_notification_text(text, translator=_translator_factory("No trades")),
            text,
        )

    def test_localize_notification_text_applies_extra_replacements_after_common_set(self):
        localized = localize_notification_text(
            "fail_reason=same_day_execution_locked",
            translator=_translator_factory("无需交易"),
            extra_replacements=(
                ("fail_reason=", "失败原因="),
                ("same_day_execution_locked", "当日执行锁已存在"),
            ),
        )

        self.assertEqual(localized, "失败原因=当日执行锁已存在")

    def test_common_replacements_include_reason_label(self):
        self.assertIn(("reason=", "原因="), COMMON_ZH_NOTIFICATION_REPLACEMENTS)

    def test_localize_price_source_label_supports_broker_sources(self):
        self.assertEqual(
            localize_price_source_label(
                "schwab_daily_history_with_live_quote_overlay",
                translator=_translator_factory("无需交易"),
            ),
            "Schwab 日线历史",
        )
        self.assertEqual(
            localize_price_source_label(
                "longbridge_candlesticks",
                translator=_translator_factory("No trades"),
            ),
            "LongBridge daily candlesticks",
        )

    def test_strategy_plugin_i18n_has_matching_locale_keys(self):
        self.assertEqual(set(STRATEGY_PLUGIN_I18N["zh"]), set(STRATEGY_PLUGIN_I18N["en"]))
        self.assertIn("strategy_plugin_name_taco_rebound_shadow", STRATEGY_PLUGIN_I18N["zh"])
        self.assertEqual(STRATEGY_PLUGIN_I18N["zh"]["strategy_plugin_name_taco_rebound_shadow"], "TACO 反弹观察通知")

    def test_merge_strategy_plugin_i18n_fills_missing_keys_without_overriding_callers(self):
        merged = merge_strategy_plugin_i18n(
            {
                "zh": {
                    "no_trades": "无需调仓",
                    "strategy_plugin_name_taco_rebound_shadow": "TACO 旧观察通知",
                },
                "en": {"no_trades": "No trades"},
            }
        )

        self.assertEqual(merged["zh"]["no_trades"], "无需调仓")
        self.assertEqual(merged["zh"]["strategy_plugin_name_taco_rebound_shadow"], "TACO 旧观察通知")
        self.assertEqual(merged["en"]["strategy_plugin_name_taco_rebound_shadow"], "TACO Rebound Watch Notice")

    def test_merge_strategy_plugin_i18n_can_prefer_shared_keys(self):
        merged = merge_strategy_plugin_i18n(
            {
                "zh": {
                    "strategy_plugin_name_taco_rebound_shadow": "TACO 旧观察通知",
                },
                "en": {},
            },
            shared_wins=True,
        )

        self.assertEqual(merged["zh"]["strategy_plugin_name_taco_rebound_shadow"], "TACO 反弹观察通知")
        self.assertEqual(merged["en"]["strategy_plugin_route_watch"], "watch")


if __name__ == "__main__":
    unittest.main()
