from __future__ import annotations

import unittest

from quant_platform_kit.common.notification_localization import (
    COMMON_ZH_NOTIFICATION_REPLACEMENTS,
    STRATEGY_PLUGIN_I18N,
    localize_price_source_label,
    localize_notification_text,
    format_notification_account_label,
    humanize_notification_line,
    humanize_notification_lines,
    resolve_notification_locale,
    merge_strategy_plugin_i18n,
    translator_uses_zh,
)
from quant_platform_kit.common.operational_notification_localization import (
    format_operational_alert,
    format_operational_heartbeat_status,
    localize_attention_reason_code,
    localize_operational_activity,
    operational_notification_text,
    resolve_operational_notification_locale,
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

    def test_resolve_notification_locale_defaults_to_english_and_normalizes_chinese(self):
        self.assertEqual(resolve_notification_locale(None), "en")
        self.assertEqual(resolve_notification_locale("fr"), "en")
        self.assertEqual(resolve_notification_locale("zh-CN"), "zh")
        self.assertEqual(resolve_notification_locale("zh_Hans"), "zh")

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

    def test_humanize_control_plane_lines_for_zh_operator_message(self):
        translator = _translator_factory("无需交易")
        self.assertEqual(
            humanize_notification_line(
                "[Account new-risk gate] disposition=ALLOW_NEW_RISK observation=COMPLETE reconciliation=VERIFIED breaker=CLOSED reasons=-",
                translator=translator,
            ),
            "✅ 账户风险检查通过：允许新增风险",
        )
        self.assertIsNone(
            humanize_notification_line(
                "[Attention notify] sent=0 skipped=1 failed=0",
                translator=translator,
            )
        )

    def test_allow_new_risk_does_not_hide_incomplete_verification_state(self):
        self.assertEqual(
            humanize_notification_line(
                "[Account new-risk gate] disposition=ALLOW_NEW_RISK observation=PARTIAL reconciliation=UNKNOWN breaker=OPEN reasons=-",
                translator=_translator_factory("无需交易"),
            ),
            "⚠️ 账户风险检查：允许新增风险，但验证状态未完成（观测=PARTIAL，对账=UNKNOWN，熔断=OPEN）",
        )

    def test_duplicate_trade_events_are_preserved_but_duplicate_status_is_compacted(self):
        translator = _translator_factory("无需交易")
        order_event = "订单已提交：卖出 SOXL 1 股，成交状态未知"
        self.assertEqual(
            humanize_notification_lines((order_event, order_event), translator=translator),
            [order_event, order_event],
        )
        # Generic 状态: trade copy must keep count (not prefix-compacted).
        status_order = "状态：订单已提交，成交未知"
        self.assertEqual(
            humanize_notification_lines((status_order, status_order), translator=translator),
            [status_order, status_order],
        )
        self.assertEqual(
            humanize_notification_lines(
                ("Status: Order submitted, fill unknown",) * 2,
                translator=_translator_factory("No trades"),
            ),
            ["Status: Order submitted, fill unknown", "Status: Order submitted, fill unknown"],
        )
        # Exact known no-trade copy may compact; control-plane parser lines may too.
        status_line = "状态：本轮无新增提醒"
        self.assertEqual(
            humanize_notification_lines((status_line, status_line), translator=translator),
            [status_line],
        )
        gate = (
            "[Account new-risk gate] disposition=ALLOW_NEW_RISK "
            "observation=COMPLETE reconciliation=VERIFIED breaker=CLOSED reasons=-"
        )
        self.assertEqual(
            humanize_notification_lines((gate, gate), translator=translator),
            ["✅ 账户风险检查通过：允许新增风险"],
        )
        self.assertIsNone(
            humanize_notification_line(
                "[Envelope scale] combined_scale=1.0 applied_to_allocation_targets",
                translator=translator,
            )
        )

    def test_unknown_duplicate_alerts_keep_count_without_keyword_guessing(self):
        translator = _translator_factory("无需交易")
        unknown = "broker latency spike: SOXL lane"
        self.assertEqual(
            humanize_notification_lines((unknown, unknown, unknown), translator=translator),
            [unknown, unknown, unknown],
        )
        opaque_fill = "SOXL qty=1 @ 41.25 lane=A"
        self.assertEqual(
            humanize_notification_lines(
                (opaque_fill, "状态：本轮无新增提醒", opaque_fill, "状态：本轮无新增提醒"),
                translator=translator,
            ),
            [opaque_fill, "状态：本轮无新增提醒", opaque_fill],
        )

    def test_allow_new_risk_english_incomplete_is_not_marked_passed(self):
        self.assertEqual(
            humanize_notification_line(
                "[Account new-risk gate] disposition=ALLOW_NEW_RISK observation=PARTIAL reconciliation=UNKNOWN breaker=OPEN reasons=-",
                translator=_translator_factory("No trades"),
            ),
            "⚠️ Account risk check: new risk is allowed, but verification is incomplete"
            " (observation=PARTIAL, reconciliation=UNKNOWN, breaker=OPEN)",
        )

    def test_humanize_lines_preserves_unknown_warning_and_deduplicates(self):
        # reason= is not a control-plane parser / exact no-trade line: keep duplicates.
        lines = humanize_notification_lines(
            ("reason=insufficient_buying_power", "reason=insufficient_buying_power"),
            translator=_translator_factory("无需交易"),
        )
        self.assertEqual(lines, ["原因=购买力不足", "原因=购买力不足"])
        # Unknown alert text must still surface (not dropped to None).
        self.assertEqual(
            humanize_notification_line(
                "unexpected reconciliation drift marker",
                translator=_translator_factory("无需交易"),
            ),
            "unexpected reconciliation drift marker",
        )
    def test_long_account_label_is_hidden_but_short_alias_is_kept(self):
        translator = _translator_factory("无需交易")
        self.assertEqual(
            format_notification_account_label("a" * 64, translator=translator),
            "已隐藏",
        )
        self.assertEqual(
            format_notification_account_label("Schwab 主账户", translator=translator),
            "Schwab 主账户",
        )

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

    def test_operational_alert_renderer_keeps_technical_detail_separate_from_zh_summary(self):
        message = format_operational_alert(
            locale="zh-CN",
            alert_type="runtime_guard",
            name="LongBridge SG",
            context={"project": "longbridgequant", "lookback_minutes": 180},
            issues=[
                operational_notification_text(
                    "zh",
                    "runtime_guard_cloud_run_log_query_failed",
                    service="longbridge-quant-sg-service",
                )
            ],
            technical_details=["HttpError: INTERNAL"],
            workflow_url="https://example.test/run/1",
        )

        self.assertIn("[运行守卫] LongBridge SG", message)
        self.assertIn("问题：", message)
        self.assertIn("Cloud Run 日志查询失败", message)
        self.assertIn("技术详情（原文）：", message)
        self.assertIn("HttpError: INTERNAL", message)
        self.assertIn("工作流：https://example.test/run/1", message)

    def test_operational_locale_and_normal_heartbeat_are_bilingual(self):
        self.assertEqual(resolve_operational_notification_locale("zh_TW"), "zh")
        self.assertEqual(resolve_operational_notification_locale("fr"), "en")
        self.assertEqual(localize_operational_activity("zh", "no trade"), "无交易")
        self.assertEqual(
            operational_notification_text("zh", "heartbeat_no_enabled_target"),
            "没有与当前心跳匹配的可执行运行目标；未提交订单。",
        )
        self.assertEqual(
            operational_notification_text("zh", "workflow_heartbeat_query_failed"),
            "GitHub Actions 运行记录查询失败",
        )
        self.assertEqual(
            format_operational_heartbeat_status(
                locale="zh",
                name="LongBridge SG",
                detail=operational_notification_text("zh", "heartbeat_runtime_target_disabled"),
            ),
            "[执行回执心跳] LongBridge SG\n状态：正常\n运行目标已停用；未提交订单。",
        )

    def test_attention_reason_codes_are_localized(self):
        self.assertEqual(
            localize_attention_reason_code("zh", "new_risk_prohibited"),
            "已禁止新增风险",
        )
        self.assertEqual(
            localize_attention_reason_code("zh", "drift_critical"),
            "生产偏离严重（CRITICAL）",
        )
        self.assertEqual(
            localize_attention_reason_code("en", "PRODUCTION_DRIFT_REVIEW"),
            "production drift review",
        )
        self.assertEqual(
            localize_attention_reason_code("zh", "unknown_future_code"),
            "unknown_future_code",
        )
        self.assertIn(
            "确认意图不等于放行实盘",
            operational_notification_text("zh", "attention_next_open_console_confirm"),
        )
        self.assertNotIn(
            "accept",
            operational_notification_text("zh", "attention_next_open_console_confirm"),
        )


if __name__ == "__main__":
    unittest.main()
