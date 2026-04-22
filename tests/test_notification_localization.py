from __future__ import annotations

import unittest

from quant_platform_kit.common.notification_localization import (
    COMMON_ZH_NOTIFICATION_REPLACEMENTS,
    localize_notification_text,
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


if __name__ == "__main__":
    unittest.main()
