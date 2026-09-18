"""Operational attention classification tests."""

from __future__ import annotations

import unittest

from quant_platform_kit.risk.attention import (
    AttentionAxes,
    AttentionLevel,
    attention_transition_key,
    evaluate_attention,
    render_attention_compact,
)


class AttentionEvaluationTest(unittest.TestCase):
    def test_ok_when_axes_omitted(self) -> None:
        decision = evaluate_attention(AttentionAxes())
        self.assertEqual(decision.level, AttentionLevel.OK)
        self.assertFalse(decision.should_notify)
        self.assertIsNone(decision.dd_ratio)

    def test_leveraged_path_drawdown_below_mandate_stays_ok(self) -> None:
        decision = evaluate_attention(
            AttentionAxes(drawdown_from_peak=0.12, mandate_dd_budget=0.35)
        )
        self.assertEqual(decision.level, AttentionLevel.OK)
        self.assertFalse(decision.should_notify)

    def test_dd_without_budget_is_omitted(self) -> None:
        decision = evaluate_attention(AttentionAxes(drawdown_from_peak=0.25))
        self.assertEqual(decision.level, AttentionLevel.OK)
        self.assertIsNone(decision.dd_ratio)

    def test_dd_watch_and_action_bands(self) -> None:
        watch = evaluate_attention(
            AttentionAxes(drawdown_from_peak=0.28, mandate_dd_budget=0.35)
        )
        self.assertEqual(watch.level, AttentionLevel.WATCH)
        self.assertFalse(watch.should_notify)
        self.assertIn("mandate_dd_elevated", watch.reason_codes)

        action = evaluate_attention(
            AttentionAxes(drawdown_from_peak=0.36, mandate_dd_budget=0.35)
        )
        self.assertEqual(action.level, AttentionLevel.ACTION)
        self.assertTrue(action.should_notify)
        self.assertIn("mandate_dd_exhausted", action.reason_codes)

    def test_new_risk_and_drift_compose_to_highest(self) -> None:
        decision = evaluate_attention(
            {
                "new_risk_prohibited": True,
                "drift_status": "critical",
            }
        )
        self.assertEqual(decision.level, AttentionLevel.HALT)
        self.assertTrue(decision.should_notify)
        self.assertIn("drift_critical", decision.reason_codes)
        self.assertIn("new_risk_prohibited", decision.reason_codes)

    def test_operational_uncertain_is_halt(self) -> None:
        decision = evaluate_attention(AttentionAxes(operational_uncertain=True))
        self.assertEqual(decision.level, AttentionLevel.HALT)
        self.assertEqual(decision.next_step_key, "open_console_resume")

    def test_transition_key_stable_for_dedup(self) -> None:
        key = attention_transition_key(
            platform="ibkr",
            account_alias="U159",
            strategy_profile="soxl_soxx_trend_income",
            level=AttentionLevel.ACTION,
            primary_reason="new_risk_prohibited",
        )
        self.assertEqual(
            key,
            "attention/ibkr/u159/soxl_soxx_trend_income/action/new_risk_prohibited",
        )

    def test_compact_zh_cn_locale_normalizes(self) -> None:
        decision = evaluate_attention(AttentionAxes(new_risk_prohibited=True))
        text = render_attention_compact(
            locale="zh-CN",
            platform="Schwab",
            account_alias="00682",
            strategy_profile="soxl",
            decision=decision,
        )
        self.assertIn("已禁止新增风险", text)
        self.assertIn("原因：已禁止新增风险", text)
        self.assertNotIn("new_risk_prohibited", text)
        self.assertIn("下一步", text)
        self.assertIn("管理站", text)
        self.assertIn("确认意图不等于放行实盘", text)
        self.assertNotIn("accept", text)

    def test_compact_localizes_drift_critical_reason_zh_and_en(self) -> None:
        decision = evaluate_attention(
            AttentionAxes(new_risk_prohibited=True, production_drift_status="critical")
        )
        zh = render_attention_compact(
            locale="zh",
            platform="schwab",
            account_alias="00682",
            strategy_profile="soxl_soxx_trend_income",
            decision=decision,
        )
        en = render_attention_compact(
            locale="en",
            platform="schwab",
            account_alias="00682",
            strategy_profile="soxl_soxx_trend_income",
            decision=decision,
        )
        self.assertIn("原因：生产偏离严重（CRITICAL）", zh)
        self.assertIn("打开管理站处理恢复", zh)
        self.assertNotIn("accept ≠ live", zh)
        self.assertIn("Reason: production drift critical", en)
        self.assertIn("recovery / reset", en)
        self.assertNotIn("accept ≠ live", en)

    def test_resolve_mandate_dd_budget_for_leveraged_profiles(self) -> None:
        from quant_platform_kit.risk.attention import resolve_mandate_dd_budget

        self.assertEqual(resolve_mandate_dd_budget("soxl_soxx_trend_income"), 0.35)
        self.assertEqual(resolve_mandate_dd_budget("tqqq_growth_income"), 0.35)
        self.assertIsNone(resolve_mandate_dd_budget("unknown_profile"))
        self.assertEqual(
            resolve_mandate_dd_budget("soxl_soxx_trend_income", override=0.40),
            0.40,
        )
        self.assertEqual(
            resolve_mandate_dd_budget(
                "other",
                environ={"QSL_MANDATE_DD_BUDGET": "0.25"},
            ),
            0.25,
        )

    def test_publish_attention_transition_dedups(self) -> None:
        from quant_platform_kit.risk.attention_notify import publish_attention_telegram_transition

        decision = evaluate_attention(AttentionAxes(new_risk_prohibited=True))
        sent: list[str] = []
        recorded: list[str] = []
        counts = publish_attention_telegram_transition(
            decision=decision,
            platform="schwab",
            account_alias="00682",
            strategy_profile="soxl_soxx_trend_income",
            locale="zh",
            telegram_sender=lambda **kwargs: sent.append(str(kwargs.get("text") or "")) or True,
            record_sent_key=recorded.append,
        )
        self.assertEqual(counts["sent"], 1)
        self.assertEqual(len(sent), 1)
        counts2 = publish_attention_telegram_transition(
            decision=decision,
            platform="schwab",
            account_alias="00682",
            strategy_profile="soxl_soxx_trend_income",
            already_sent_keys=recorded,
            telegram_sender=lambda **kwargs: sent.append(str(kwargs.get("text") or "")) or True,
            record_sent_key=recorded.append,
        )
        self.assertEqual(counts2["skipped"], 1)
        self.assertEqual(len(sent), 1)


if __name__ == "__main__":
    unittest.main()
