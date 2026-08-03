"""Tests for quant_platform_kit.position_sizing."""

from __future__ import annotations

import unittest

from quant_platform_kit.position_sizing import (
    KellyResult,
    estimate_kelly,
    risk_budgeted_target_weight,
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


if __name__ == "__main__":
    unittest.main()
