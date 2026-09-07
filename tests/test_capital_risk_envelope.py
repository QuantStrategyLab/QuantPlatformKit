"""Capital risk envelope D1: equity bands, vol/DD scales, shrink-only combine."""

from __future__ import annotations

import unittest

from quant_platform_kit.risk.capital_risk_envelope import (
    DEFAULT_TARGET_VOL_ANNUAL,
    CapitalRiskEnvelope,
    apply_envelope_to_sized_weight,
    evaluate_capital_risk_envelope,
)
from quant_platform_kit.risk.promotion_sizing import size_target_weight


class EquityBandBoundaryTests(unittest.TestCase):
    def test_under_50k_full_capital_scale(self) -> None:
        env = evaluate_capital_risk_envelope(49_999.99)
        self.assertEqual(env.band_id, "under_50k")
        self.assertEqual(env.capital_scale, 1.0)
        self.assertEqual(env.dd_brake, 0.15)
        self.assertTrue(env.new_risk_allowed)
        self.assertFalse(env.live_authority_granted)

    def test_exact_50k_enters_mid_band(self) -> None:
        env = evaluate_capital_risk_envelope(50_000.0)
        self.assertEqual(env.band_id, "from_50k_to_250k")
        self.assertEqual(env.capital_scale, 0.85)
        self.assertEqual(env.dd_brake, 0.10)

    def test_just_under_250k_stays_mid(self) -> None:
        env = evaluate_capital_risk_envelope(249_999.99)
        self.assertEqual(env.band_id, "from_50k_to_250k")
        self.assertEqual(env.capital_scale, 0.85)

    def test_exact_250k_enters_upper_band(self) -> None:
        env = evaluate_capital_risk_envelope(250_000.0)
        self.assertEqual(env.band_id, "from_250k_to_1m")
        self.assertEqual(env.capital_scale, 0.65)
        self.assertEqual(env.dd_brake, 0.075)

    def test_exact_1m_stays_upper_band(self) -> None:
        env = evaluate_capital_risk_envelope(1_000_000.0)
        self.assertEqual(env.band_id, "from_250k_to_1m")
        self.assertEqual(env.capital_scale, 0.65)

    def test_above_1m_conservative_band(self) -> None:
        env = evaluate_capital_risk_envelope(1_000_000.01)
        self.assertEqual(env.band_id, "above_1m")
        self.assertEqual(env.capital_scale, 0.50)
        self.assertEqual(env.dd_brake, 0.05)
        self.assertEqual(env.leverage_product_cap.max_3x_etf_weight, 0.0)
        self.assertTrue(env.leverage_product_cap.new_leverage_requires_hitl)


class VolScaleTests(unittest.TestCase):
    def test_missing_vol_defaults_to_one(self) -> None:
        env = evaluate_capital_risk_envelope(40_000.0)
        self.assertEqual(env.vol_scale, 1.0)

    def test_zero_or_negative_realized_vol_is_neutral_or_fail_closed(self) -> None:
        self.assertEqual(
            evaluate_capital_risk_envelope(40_000.0, realized_vol=0.0).vol_scale,
            1.0,
        )
        bad = evaluate_capital_risk_envelope(40_000.0, realized_vol=-0.1)
        self.assertEqual(bad.vol_scale, 0.0)
        self.assertIn("INVALID_REALIZED_VOL_FAIL_CLOSED", bad.reasons)

    def test_vol_scale_caps_at_one_and_shrinks_when_hot(self) -> None:
        cool = evaluate_capital_risk_envelope(
            40_000.0, realized_vol=0.10, target_vol=DEFAULT_TARGET_VOL_ANNUAL
        )
        self.assertEqual(cool.vol_scale, 1.0)
        hot = evaluate_capital_risk_envelope(
            40_000.0, realized_vol=0.40, target_vol=DEFAULT_TARGET_VOL_ANNUAL
        )
        self.assertAlmostEqual(hot.vol_scale, 0.5)
        self.assertIn("VOL_SCALE_REDUCED", hot.reasons)


class DrawdownBrakeTests(unittest.TestCase):
    def test_half_brake_halves_dd_scale(self) -> None:
        # mid band brake 0.10 → half at 0.05
        env = evaluate_capital_risk_envelope(
            100_000.0, drawdown_from_peak=0.05
        )
        self.assertEqual(env.dd_scale, 0.5)
        self.assertTrue(env.new_risk_allowed)
        self.assertIn("DRAWDOWN_HALF_BRAKE", env.reasons)

    def test_full_brake_zeros_scale_and_blocks_new_risk(self) -> None:
        env = evaluate_capital_risk_envelope(
            100_000.0, drawdown_from_peak=0.10
        )
        self.assertEqual(env.dd_scale, 0.0)
        self.assertFalse(env.new_risk_allowed)
        self.assertIn("DRAWDOWN_BRAKE_TRIPPED", env.reasons)
        self.assertEqual(env.combined_scale, 0.0)

    def test_small_band_uses_wider_brake(self) -> None:
        # under_50k brake 0.15; 0.10 is below half? half=0.075, so 0.10 ≥ half → 0.5
        env = evaluate_capital_risk_envelope(20_000.0, drawdown_from_peak=0.10)
        self.assertEqual(env.dd_brake, 0.15)
        self.assertEqual(env.dd_scale, 0.5)
        self.assertTrue(env.new_risk_allowed)


class CombinedProductTests(unittest.TestCase):
    def test_combined_is_product_clamped_to_unit(self) -> None:
        env = evaluate_capital_risk_envelope(
            100_000.0,
            realized_vol=0.40,
            drawdown_from_peak=0.05,
        )
        # capital 0.85 * vol 0.5 * dd 0.5 = 0.2125
        self.assertAlmostEqual(env.capital_scale, 0.85)
        self.assertAlmostEqual(env.vol_scale, 0.5)
        self.assertAlmostEqual(env.dd_scale, 0.5)
        self.assertAlmostEqual(env.combined_scale, 0.85 * 0.5 * 0.5)

    def test_invalid_equity_fail_closed(self) -> None:
        env = evaluate_capital_risk_envelope(float("nan"))
        self.assertEqual(env.combined_scale, 0.0)
        self.assertFalse(env.new_risk_allowed)
        self.assertIn("INVALID_EQUITY_FAIL_CLOSED", env.reasons)


class ApplyEnvelopeToSizedWeightTests(unittest.TestCase):
    def test_only_shrinks_after_promotion_and_plugin(self) -> None:
        sized = size_target_weight(
            1.0,
            risk_profile="GROWTH_COMPOUNDING",
            plugin_scalar=1.0,
        )
        self.assertAlmostEqual(sized, 1.0)
        env = evaluate_capital_risk_envelope(100_000.0)  # capital_scale 0.85
        applied = apply_envelope_to_sized_weight(sized, env)
        self.assertAlmostEqual(applied, 0.85)
        self.assertLessEqual(applied, sized)
        self.assertLessEqual(applied, 1.0)

    def test_envelope_after_plugin_never_exceeds_one(self) -> None:
        sized = size_target_weight(
            0.80,
            risk_profile="BALANCED_COMPOUNDING",  # 0.75
            plugin_scalar=0.90,
        )
        # 0.80 * 0.75 * 0.90 = 0.54
        self.assertAlmostEqual(sized, 0.54)
        env = evaluate_capital_risk_envelope(40_000.0)  # combined 1.0
        applied = apply_envelope_to_sized_weight(sized, env)
        self.assertAlmostEqual(applied, 0.54)
        self.assertLessEqual(applied, 1.0)

    def test_rejects_non_envelope_fail_closed(self) -> None:
        self.assertEqual(apply_envelope_to_sized_weight(0.5, object()), 0.0)

    def test_result_is_capital_risk_envelope_dataclass(self) -> None:
        env = evaluate_capital_risk_envelope(10_000.0)
        self.assertIsInstance(env, CapitalRiskEnvelope)


if __name__ == "__main__":
    unittest.main()
