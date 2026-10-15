"""Tests for QuantRuntimeSettings strategy automation registry guardrails."""

from __future__ import annotations

import unittest

from quant_platform_kit.strategy_lifecycle.watch.strategy_automation_registry import (
    STRATEGY_AUTOMATION_REGISTRY_SCHEMA_VERSION,
    apply_strategy_registry_guard,
    summarize_strategy_registry_context,
)


def _registry() -> dict:
    return {
        "schema_version": STRATEGY_AUTOMATION_REGISTRY_SCHEMA_VERSION,
        "summary": {"strategy_profile_count": 2},
        "profiles": [
            {
                "profile": "live",
                "domain": "us_equity",
                "lifecycle_stage": "runtime_enabled",
                "automation_lane": "live_equivalent_optimization",
                "max_autonomy": "auto_pr_or_trusted_live_equivalent",
                "approval_required": False,
                "can_switch_live": True,
                "position_control_sensitive": False,
            },
            {
                "profile": "candidate",
                "domain": "cn_equity",
                "lifecycle_stage": "live_candidate",
                "automation_lane": "promotion_review",
                "max_autonomy": "human_review_required",
                "approval_required": True,
                "can_switch_live": False,
                "position_control_sensitive": True,
            },
        ],
    }


class StrategyAutomationRegistryTest(unittest.TestCase):
    def test_summarizes_registry_embedded_in_platform_health_report(self) -> None:
        context = summarize_strategy_registry_context({"automation_registry": _registry()}, "live")

        self.assertTrue(context["valid"])
        self.assertTrue(context["matched"])
        self.assertEqual(context["automation_lane"], "live_equivalent_optimization")
        self.assertEqual(context["summary"]["strategy_profile_count"], 2)

    def test_summary_context_is_size_limited_and_scalar_only(self) -> None:
        registry = _registry()
        registry["summary"] = {
            "strategy_profile_count": 2,
            "automation_lane_counts": {"live_equivalent_optimization": 1},
            "large_nested": {"unsafe": ["x" * 1000]},
            "generated_at": "x" * 300,
        }

        context = summarize_strategy_registry_context(registry, "live")

        self.assertEqual(context["summary"]["strategy_profile_count"], 2)
        self.assertEqual(context["summary"]["automation_lane_counts"]["live_equivalent_optimization"], 1)
        self.assertNotIn("large_nested", context["summary"])
        self.assertEqual(len(context["summary"]["generated_at"]), 200)

    def test_registry_guard_caps_promotion_lane_to_escalate(self) -> None:
        context = summarize_strategy_registry_context(_registry(), "candidate")

        guarded = apply_strategy_registry_guard(
            {"final_action": "auto_merge", "human_review_required": False, "reasons": []},
            context,
            profile_binding_trusted=True,
        )

        self.assertEqual(guarded["final_action"], "escalate")
        self.assertTrue(guarded["human_review_required"])
        self.assertIn("strategy_registry_context", guarded)

    def test_registry_guard_does_not_relax_promotion_hard_stop_with_max_autonomy(self) -> None:
        registry = _registry()
        registry["profiles"][1]["max_autonomy"] = "auto_pr_research_only"
        context = summarize_strategy_registry_context(registry, "candidate")

        guarded = apply_strategy_registry_guard(
            {"final_action": "auto_merge", "human_review_required": False, "reasons": []},
            context,
            profile_binding_trusted=True,
        )

        self.assertEqual(guarded["final_action"], "escalate")
        self.assertTrue(guarded["human_review_required"])

    def test_registry_guard_caps_shadow_and_research_lanes_to_escalate(self) -> None:
        for lane in ("shadow_research", "research_backlog"):
            with self.subTest(lane=lane):
                registry = _registry()
                registry["profiles"][0]["automation_lane"] = lane
                context = summarize_strategy_registry_context(registry, "live")

                guarded = apply_strategy_registry_guard(
                    {"final_action": "auto_merge", "human_review_required": False, "reasons": []},
                    context,
                    profile_binding_trusted=True,
                )

                self.assertEqual(guarded["final_action"], "escalate")
                self.assertTrue(guarded["human_review_required"])

    def test_registry_guard_caps_position_sensitive_live_lane_to_auto_pr(self) -> None:
        registry = _registry()
        registry["profiles"][0]["position_control_sensitive"] = True
        context = summarize_strategy_registry_context(registry, "live")

        guarded = apply_strategy_registry_guard(
            {"final_action": "auto_merge", "human_review_required": False, "reasons": []},
            context,
            profile_binding_trusted=True,
        )

        self.assertEqual(guarded["final_action"], "auto_pr")
        self.assertTrue(guarded["human_review_required"])

    def test_registry_guard_caps_position_sensitive_auto_notify_to_escalate(self) -> None:
        registry = _registry()
        registry["profiles"][0]["position_control_sensitive"] = True
        context = summarize_strategy_registry_context(registry, "live")

        guarded = apply_strategy_registry_guard(
            {"final_action": "auto_notify", "human_review_required": False, "reasons": []},
            context,
            profile_binding_trusted=True,
        )

        self.assertEqual(guarded["final_action"], "escalate")
        self.assertTrue(guarded["human_review_required"])

    def test_registry_guard_preserves_position_sensitive_live_lane_with_trusted_proof(self) -> None:
        registry = _registry()
        registry["profiles"][0]["position_control_sensitive"] = True
        context = summarize_strategy_registry_context(registry, "live")

        guarded = apply_strategy_registry_guard(
            {
                "final_action": "auto_merge",
                "human_review_required": False,
                "reasons": [],
                "trusted_position_control_proof": True,
            },
            context,
            profile_binding_trusted=True,
        )

        self.assertEqual(guarded["final_action"], "auto_merge")
        self.assertFalse(guarded["human_review_required"])

    def test_registry_guard_caps_unmatched_profile_to_escalate(self) -> None:
        context = summarize_strategy_registry_context(_registry(), "typo")

        guarded = apply_strategy_registry_guard(
            {"final_action": "auto_merge", "human_review_required": False, "reasons": []},
            context,
        )

        self.assertEqual(guarded["final_action"], "escalate")
        self.assertTrue(guarded["human_review_required"])
        self.assertFalse(guarded["strategy_registry_context"]["matched"])

    def test_registry_guard_caps_untrusted_live_profile_binding_to_auto_pr(self) -> None:
        context = summarize_strategy_registry_context(_registry(), "live")

        guarded = apply_strategy_registry_guard(
            {"final_action": "auto_merge", "human_review_required": False, "reasons": []},
            context,
        )

        self.assertEqual(guarded["final_action"], "auto_pr")
        self.assertTrue(guarded["human_review_required"])

    def test_registry_guard_caps_untrusted_auto_notify_to_escalate(self) -> None:
        context = summarize_strategy_registry_context(_registry(), "live")

        guarded = apply_strategy_registry_guard(
            {"final_action": "auto_notify", "human_review_required": False, "reasons": []},
            context,
        )

        self.assertEqual(guarded["final_action"], "escalate")
        self.assertTrue(guarded["human_review_required"])

    def test_invalid_registry_does_not_modify_authority(self) -> None:
        authority = {"final_action": "auto_merge", "human_review_required": False, "reasons": ["ok"]}

        guarded = apply_strategy_registry_guard(authority, summarize_strategy_registry_context({}, ""))

        self.assertEqual(guarded["final_action"], authority["final_action"])
        self.assertFalse(guarded["human_review_required"])
        self.assertFalse(guarded["strategy_registry_context"]["valid"])

    def test_invalid_registry_with_profile_fails_closed(self) -> None:
        guarded = apply_strategy_registry_guard(
            {"final_action": "auto_merge", "human_review_required": False, "reasons": []},
            summarize_strategy_registry_context({}, "live"),
        )

        self.assertEqual(guarded["final_action"], "escalate")
        self.assertTrue(guarded["human_review_required"])

    def test_blank_profile_without_registry_skips_strategy_registry_guard(self) -> None:
        context = summarize_strategy_registry_context({}, "")

        guarded = apply_strategy_registry_guard(
            {"final_action": "auto_merge", "human_review_required": False, "reasons": []},
            context,
        )

        self.assertEqual(guarded["final_action"], "auto_merge")
        self.assertFalse(guarded["human_review_required"])
        self.assertFalse(guarded["strategy_registry_context"]["valid"])

    def test_blank_profile_with_supplied_registry_fails_closed(self) -> None:
        context = summarize_strategy_registry_context(_registry(), "")

        guarded = apply_strategy_registry_guard(
            {"final_action": "auto_merge", "human_review_required": False, "reasons": []},
            context,
        )

        self.assertEqual(guarded["final_action"], "escalate")
        self.assertTrue(guarded["human_review_required"])
        self.assertTrue(guarded["strategy_registry_context"]["profile_required"])

    def test_blank_profile_with_malformed_registry_fails_closed(self) -> None:
        context = summarize_strategy_registry_context({"schema_version": "stale"}, "")

        guarded = apply_strategy_registry_guard(
            {"final_action": "auto_merge", "human_review_required": False, "reasons": []},
            context,
        )

        self.assertEqual(guarded["final_action"], "escalate")
        self.assertTrue(guarded["human_review_required"])
        self.assertTrue(guarded["strategy_registry_context"]["profile_required"])

    def test_registry_guard_enforces_human_review_max_autonomy(self) -> None:
        registry = _registry()
        registry["profiles"][0]["max_autonomy"] = "human_review_required"
        context = summarize_strategy_registry_context(registry, "live")

        guarded = apply_strategy_registry_guard(
            {"final_action": "auto_merge", "human_review_required": False, "reasons": []},
            context,
            profile_binding_trusted=True,
        )

        self.assertEqual(guarded["final_action"], "escalate")
        self.assertTrue(guarded["human_review_required"])

    def test_registry_guard_caps_auto_notify_for_auto_pr_max_autonomy(self) -> None:
        registry = _registry()
        registry["profiles"][0]["max_autonomy"] = "auto_pr_research_only"
        context = summarize_strategy_registry_context(registry, "live")

        guarded = apply_strategy_registry_guard(
            {"final_action": "auto_notify", "human_review_required": False, "reasons": []},
            context,
            profile_binding_trusted=True,
        )

        self.assertEqual(guarded["final_action"], "escalate")
        self.assertTrue(guarded["human_review_required"])

    def test_registry_guard_enforces_can_switch_live_for_trusted_live_lane(self) -> None:
        registry = _registry()
        registry["profiles"][0]["can_switch_live"] = False
        context = summarize_strategy_registry_context(registry, "live")

        guarded = apply_strategy_registry_guard(
            {"final_action": "auto_merge", "human_review_required": False, "reasons": []},
            context,
            profile_binding_trusted=True,
        )

        self.assertEqual(guarded["final_action"], "escalate")
        self.assertTrue(guarded["human_review_required"])
