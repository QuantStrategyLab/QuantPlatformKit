"""Promotion sizing chain: target × risk-profile scale × plugin scalar → RiskEngine."""

from __future__ import annotations

import unittest

from quant_platform_kit.risk.contracts import ROUTE_BLOCKED, RiskSignal
from quant_platform_kit.risk.engine import RiskEngine
from quant_platform_kit.risk.promotion_sizing import (
    DEFAULT_RISK_PROFILE_SCALES,
    PromotionSizingResult,
    assess_promotion_sized_target,
    normalize_plugin_scalar,
    resolve_risk_profile_scale,
    size_target_weight,
)


class _BlockingPlugin:
    plugin_name = "blocking"
    schema_version = "test.v1"

    def evaluate(self, market_data):  # noqa: ANN001
        return RiskSignal(
            plugin=self.plugin_name,
            schema_version=self.schema_version,
            route=ROUTE_BLOCKED,
            confidence=1.0,
            suggested_action="blocked",
            reason_codes=("forced_block",),
        )


class NormalizePluginScalarTests(unittest.TestCase):
    def test_default_and_valid_range(self) -> None:
        self.assertEqual(normalize_plugin_scalar(None), 1.0)
        self.assertEqual(normalize_plugin_scalar(0.5), 0.5)
        self.assertEqual(normalize_plugin_scalar(0.0), 0.0)
        self.assertEqual(normalize_plugin_scalar(1.0), 1.0)

    def test_rejects_raise_and_invalid_fail_closed(self) -> None:
        self.assertEqual(normalize_plugin_scalar(1.25), 1.0)
        self.assertEqual(normalize_plugin_scalar(-0.1), 0.0)
        self.assertEqual(normalize_plugin_scalar(float("nan")), 0.0)
        self.assertEqual(normalize_plugin_scalar("0.5"), 0.0)


class RiskProfileScaleTests(unittest.TestCase):
    def test_default_envelopes(self) -> None:
        self.assertEqual(
            resolve_risk_profile_scale("CAPITAL_PRESERVATION"),
            DEFAULT_RISK_PROFILE_SCALES["CAPITAL_PRESERVATION"],
        )
        self.assertEqual(resolve_risk_profile_scale("GROWTH_COMPOUNDING"), 1.0)

    def test_scale_bps_override(self) -> None:
        self.assertEqual(resolve_risk_profile_scale("GROWTH_COMPOUNDING", scale_bps=2500), 0.25)

    def test_unknown_profile_fails(self) -> None:
        with self.assertRaises(ValueError):
            resolve_risk_profile_scale("YOLO")


class SizeTargetWeightTests(unittest.TestCase):
    def test_multiplies_profile_and_plugin(self) -> None:
        # 0.40 × 0.50 × 0.50 = 0.10
        sized = size_target_weight(
            0.40,
            risk_profile="CAPITAL_PRESERVATION",
            plugin_scalar=0.50,
        )
        self.assertAlmostEqual(sized, 0.10)

    def test_plugin_cannot_raise_above_one(self) -> None:
        sized = size_target_weight(
            0.40,
            risk_profile="GROWTH_COMPOUNDING",
            plugin_scalar=2.0,
        )
        self.assertAlmostEqual(sized, 0.40)

    def test_invalid_target_fail_closed(self) -> None:
        self.assertEqual(
            size_target_weight(float("nan"), risk_profile="CAPITAL_PRESERVATION"),
            0.0,
        )


class AssessPromotionSizedTargetTests(unittest.TestCase):
    def test_approve_preserves_sized_weight(self) -> None:
        result = assess_promotion_sized_target(
            target_weight=0.40,
            risk_profile="BALANCED_COMPOUNDING",
            plugin_scalar=0.80,
            symbol="QQQ",
            portfolio_snapshot={"total_equity": 100_000.0},
            engine=RiskEngine(),
        )
        self.assertIsInstance(result, PromotionSizingResult)
        self.assertAlmostEqual(result.sized_weight, 0.40 * 0.75 * 0.80)
        self.assertEqual(result.risk_action, "approve")
        self.assertAlmostEqual(result.final_weight, result.sized_weight)
        self.assertFalse(result.live_authority_granted)
        self.assertEqual(result.decision.positions[0].symbol, "QQQ")
        self.assertAlmostEqual(result.decision.positions[0].target_weight or 0.0, result.sized_weight)

    def test_reject_zeros_final_weight(self) -> None:
        result = assess_promotion_sized_target(
            target_weight=0.40,
            risk_profile="GROWTH_COMPOUNDING",
            plugin_scalar=1.0,
            portfolio_snapshot={"total_equity": 100_000.0},
            engine=RiskEngine(plugins=(_BlockingPlugin(),)),
        )
        self.assertEqual(result.risk_action, "reject")
        self.assertEqual(result.final_weight, 0.0)
        self.assertFalse(result.live_authority_granted)

    def test_missing_snapshot_rejects(self) -> None:
        result = assess_promotion_sized_target(
            target_weight=0.20,
            risk_profile="CAPITAL_PRESERVATION",
            portfolio_snapshot=None,
            engine=RiskEngine(),
        )
        self.assertEqual(result.risk_action, "reject")
        self.assertEqual(result.final_weight, 0.0)



class DualScaleAndPromotionScopeTests(unittest.TestCase):
    def test_default_scales_never_exceed_one(self) -> None:
        for profile, scale in DEFAULT_RISK_PROFILE_SCALES.items():
            self.assertLessEqual(scale, 1.0, profile)
            self.assertGreater(scale, 0.0, profile)
        self.assertEqual(DEFAULT_RISK_PROFILE_SCALES["CAPITAL_PRESERVATION"], 0.50)
        self.assertEqual(DEFAULT_RISK_PROFILE_SCALES["BALANCED_COMPOUNDING"], 0.75)
        self.assertEqual(DEFAULT_RISK_PROFILE_SCALES["GROWTH_COMPOUNDING"], 1.00)

    def test_growth_scale_is_not_composer_mdd_ceiling(self) -> None:
        # Composer GROWTH_COMPOUNDING MDD ceiling is 1.50; promotion scale stays 1.00.
        self.assertEqual(resolve_risk_profile_scale("GROWTH_COMPOUNDING"), 1.00)
        self.assertNotEqual(resolve_risk_profile_scale("GROWTH_COMPOUNDING"), 1.50)

    def test_live_authority_never_granted_on_approve(self) -> None:
        result = assess_promotion_sized_target(
            target_weight=0.20,
            risk_profile="GROWTH_COMPOUNDING",
            plugin_scalar=1.0,
            portfolio_snapshot={"total_equity": 100_000.0},
            engine=RiskEngine(),
        )
        self.assertEqual(result.risk_action, "approve")
        self.assertFalse(result.live_authority_granted)


if __name__ == "__main__":
    unittest.main()
