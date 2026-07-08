"""Tests for quant_platform_kit.position_sizing."""

from __future__ import annotations

import unittest

from quant_platform_kit.position_sizing import KellyResult, estimate_kelly


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


if __name__ == "__main__":
    unittest.main()
