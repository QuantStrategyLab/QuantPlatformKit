"""Tests for quant_platform_kit.position_sizing."""

from __future__ import annotations

import unittest

from quant_platform_kit.position_sizing import (
    KellyResult,
    estimate_kelly,
    risk_budgeted_target_weight,
    risk_budgeted_target_weights,
    validate_reduce_only_normalization,
)


class PositionSizingTests(unittest.TestCase):
    def test_all_wins(self) -> None:
        result = estimate_kelly([0.10, 0.05, 0.08])

        self.assertEqual(result.win_rate, 1.0)
        self.assertAlmostEqual(result.avg_win, (0.10 + 0.05 + 0.08) / 3)
        self.assertEqual(result.avg_loss, 0.0)
        self.assertEqual(result.kelly_fraction, 1.0)
        self.assertEqual(result.half_kelly, 0.5)
        self.assertEqual(result.max_position_pct, 0.10)

    def test_all_losses(self) -> None:
        result = estimate_kelly([-0.10, -0.05, -0.08])

        self.assertEqual(result.win_rate, 0.0)
        self.assertEqual(result.avg_win, 0.0)
        self.assertAlmostEqual(result.avg_loss, (0.10 + 0.05 + 0.08) / 3)
        self.assertEqual(result.kelly_fraction, 0.0)
        self.assertEqual(result.half_kelly, 0.0)
        self.assertEqual(result.max_position_pct, 0.0)

    def test_break_even(self) -> None:
        result = estimate_kelly([0.10, -0.10])

        self.assertEqual(result.win_rate, 0.5)
        self.assertAlmostEqual(result.avg_win, 0.10)
        self.assertAlmostEqual(result.avg_loss, 0.10)
        self.assertAlmostEqual(result.kelly_fraction, 0.0)
        self.assertAlmostEqual(result.half_kelly, 0.0)
        self.assertAlmostEqual(result.max_position_pct, 0.0)

    def test_positive_edge(self) -> None:
        result = estimate_kelly([0.20, 0.20, -0.10])

        self.assertAlmostEqual(result.win_rate, 2 / 3)
        self.assertAlmostEqual(result.avg_win, 0.20)
        self.assertAlmostEqual(result.avg_loss, 0.10)
        self.assertAlmostEqual(result.kelly_fraction, 0.5)
        self.assertAlmostEqual(result.half_kelly, 0.25)
        self.assertAlmostEqual(result.max_position_pct, 0.10)

    def test_empty_returns(self) -> None:
        result = estimate_kelly([])

        self.assertEqual(
            result,
            KellyResult(
                win_rate=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                kelly_fraction=0.0,
                half_kelly=0.0,
                max_position_pct=0.0,
            ),
        )

    def test_zero_returns_are_neutral(self) -> None:
        result = estimate_kelly([0.0, 0.0])

        self.assertEqual(result.win_rate, 0.0)
        self.assertEqual(result.avg_win, 0.0)
        self.assertEqual(result.avg_loss, 0.0)
        self.assertEqual(result.kelly_fraction, 0.0)

    def test_single_win(self) -> None:
        result = estimate_kelly([0.05])

        self.assertEqual(result.win_rate, 1.0)
        self.assertEqual(result.kelly_fraction, 1.0)
        self.assertEqual(result.max_position_pct, 0.10)

    def test_single_loss(self) -> None:
        result = estimate_kelly([-0.05])

        self.assertEqual(result.win_rate, 0.0)
        self.assertEqual(result.kelly_fraction, 0.0)

    def test_half_kelly_below_cap(self) -> None:
        result = estimate_kelly([0.04, 0.04, -0.02])

        self.assertAlmostEqual(result.kelly_fraction, 0.5)
        self.assertAlmostEqual(result.half_kelly, 0.25)
        self.assertAlmostEqual(result.max_position_pct, 0.10)

    def test_negative_edge_clamped_to_zero(self) -> None:
        result = estimate_kelly([0.05, -0.20, -0.20])

        self.assertGreater(result.avg_loss, result.avg_win)
        self.assertEqual(result.kelly_fraction, 0.0)
        self.assertEqual(result.half_kelly, 0.0)
        self.assertEqual(result.max_position_pct, 0.0)


class RiskBudgetedTargetWeightTests(unittest.TestCase):
    def _approved_inputs(self, **overrides: object) -> dict[str, object]:
        return {
            "risk_mandate_id": "bootstrap_small_account_v2",
            "account_equity": 2_000.0,
            "risk_fraction": 0.01,
            "stop_loss_distance": 0.05,
            "drawdown_scalar": 1.0,
            "available_account_exposure": 0.50,
            "product_leverage_factor": 1,
            "inputs_fresh": True,
            **overrides,
        }

    def test_approved_mandate_matches_one_percent_five_percent_stop_example(
        self,
    ) -> None:
        self.assertAlmostEqual(
            risk_budgeted_target_weight(**self._approved_inputs()), 0.20
        )

    def test_approved_mandate_applies_product_and_effective_exposure_caps(self) -> None:
        self.assertAlmostEqual(
            risk_budgeted_target_weight(
                **self._approved_inputs(product_leverage_factor=2),
            ),
            0.20,
        )
        self.assertEqual(
            risk_budgeted_target_weight(
                **self._approved_inputs(product_leverage_factor=3),
            ),
            0.15,
        )

    def test_approved_mandate_clamps_to_available_single_account_exposure(self) -> None:
        self.assertEqual(
            risk_budgeted_target_weight(
                **self._approved_inputs(available_account_exposure=0.10),
            ),
            0.10,
        )

    def test_without_approved_mandate_cannot_use_leverage_or_exceed_ten_percent(
        self,
    ) -> None:
        inputs = self._approved_inputs(risk_mandate_id=None)
        self.assertEqual(risk_budgeted_target_weight(**inputs), 0.10)
        self.assertEqual(
            risk_budgeted_target_weight(**{**inputs, "product_leverage_factor": 2}),
            0.0,
        )

    def test_invalid_stale_or_over_budget_inputs_fail_closed(self) -> None:
        invalid_cases = (
            {"risk_fraction": 0.0100001},
            {"product_leverage_factor": 4},
            {"drawdown_scalar": 1.01},
            {"available_account_exposure": 0.51},
            {"account_equity": float("nan")},
            {"stop_loss_distance": float("inf")},
            {"inputs_fresh": False},
        )
        for overrides in invalid_cases:
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    risk_budgeted_target_weight(**self._approved_inputs(**overrides)),
                    0.0,
                )


class RiskBudgetedTargetWeightsTests(unittest.TestCase):
    def _approved_inputs(self, **overrides: object) -> dict[str, object]:
        return {
            "raw_target_weights": {"SOXL": 0.70, "SOXX": 0.30},
            "risk_mandate_id": "soxl_p3_research_v1",
            "risk_fraction": 0.01,
            "stop_loss_distances": {"SOXL": 0.05, "SOXX": 0.05},
            "drawdown_scalar": 1.0,
            "available_effective_exposure": 0.50,
            "product_leverage_factors": {"SOXL": 3, "SOXX": 1},
            "inputs_fresh": True,
            **overrides,
        }

    def test_sizes_multi_asset_vector_proportionally_under_all_caps(self) -> None:
        result = risk_budgeted_target_weights(**self._approved_inputs())

        self.assertEqual(set(result), {"SOXL", "SOXX"})
        self.assertAlmostEqual(result["SOXL"], 0.14)
        self.assertAlmostEqual(result["SOXX"], 0.06)
        self.assertAlmostEqual(result["SOXL"] / result["SOXX"], 7 / 3)
        self.assertLessEqual(result["SOXL"], 0.15)
        self.assertLessEqual(result["SOXL"] * 3 + result["SOXX"], 0.50)
        self.assertLessEqual(
            result["SOXL"] * 0.05 + result["SOXX"] * 0.05,
            0.01,
        )

    def test_drawdown_scalar_reduces_aggregate_loss_budget(self) -> None:
        result = risk_budgeted_target_weights(
            **self._approved_inputs(drawdown_scalar=0.50),
        )

        self.assertAlmostEqual(result["SOXL"], 0.07)
        self.assertAlmostEqual(result["SOXX"], 0.03)

    def test_invalid_or_stale_multi_asset_inputs_fail_closed(self) -> None:
        invalid_cases = (
            {"risk_mandate_id": None},
            {"risk_mandate_id": "bootstrap_small_account_v2"},
            {"inputs_fresh": False},
            {"risk_fraction": 0.0100001},
            {"drawdown_scalar": float("nan")},
            {"available_effective_exposure": 0.500001},
            {"product_leverage_factors": {"SOXL": 4, "SOXX": 1}},
            {"product_leverage_factors": {"SOXL": 3}},
            {"stop_loss_distances": {"SOXL": 0.05}},
            {"raw_target_weights": {"SOXL": float("inf"), "SOXX": 0.30}},
            {"raw_target_weights": {"SOXL": -0.10, "SOXX": 0.30}},
        )
        for overrides in invalid_cases:
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    risk_budgeted_target_weights(
                        **self._approved_inputs(**overrides),
                    ),
                    {},
                )


class ReduceOnlyNormalizationTests(unittest.TestCase):
    def test_one_hundred_percent_boxx_can_normalize_to_compliant_boxx_cash(self) -> None:
        self.assertTrue(
            validate_reduce_only_normalization(
                origin_weights={"BOXX": 1.0},
                target_weights={"BOXX": 0.50},
                product_leverage_factors={"BOXX": 1},
                effective_exposure_cap=0.50,
                observed_effective_exposure=1.0,
            )
        )

    def test_normalization_rejects_new_exposure_non_reduction_or_bad_origin(self) -> None:
        invalid_cases = (
            ({"BOXX": 0.40, "SOXX": 0.10}, {"BOXX": 1, "SOXX": 1}, 1.0),
            ({"BOXX": 1.0}, {"BOXX": 1}, 1.0),
            ({"BOXX": 0.60}, {"BOXX": 1}, 1.0),
            ({"BOXX": 0.50}, {"BOXX": 1}, 0.90),
            ({"BOXX": float("nan")}, {"BOXX": 1}, 1.0),
        )
        for target_weights, factors, observed in invalid_cases:
            with self.subTest(
                target_weights=target_weights,
                factors=factors,
                observed=observed,
            ):
                self.assertFalse(
                    validate_reduce_only_normalization(
                        origin_weights={"BOXX": 1.0},
                        target_weights=target_weights,
                        product_leverage_factors=factors,
                        effective_exposure_cap=0.50,
                        observed_effective_exposure=observed,
                    )
                )


if __name__ == "__main__":
    unittest.main()
