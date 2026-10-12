"""A2: synthetic, offline contracts for labeled fills and costs."""
import math
import random
import unittest

from quant_platform_kit.research_stats.execution_models import CostModel, FillModel


class FillModelTests(unittest.TestCase):
    def test_three_timings_are_explicit_and_repeatable(self):
        for timing, expected in (("same_close", (1, "close")),
                                 ("next_close", (2, "close")),
                                 ("next_open", (2, "open"))):
            model = FillModel(timing)
            fill = model.resolve(signal_index=1, available_index=1, bar_count=3)
            self.assertEqual((fill.index, fill.price_field), expected)
            self.assertEqual(fill, model.resolve(signal_index=1, available_index=1, bar_count=3))
            self.assertEqual(fill.timing, timing)

    def test_unavailable_or_out_of_window_does_not_fill(self):
        with self.assertRaisesRegex(ValueError, "SIGNAL_NOT_AVAILABLE"):
            FillModel("same_close").resolve(signal_index=1, available_index=2, bar_count=4)
        self.assertIsNone(FillModel("next_close").resolve(signal_index=2, available_index=2, bar_count=3))

    def test_invalid_modes_and_indices_fail_closed(self):
        for timing in ("today", "", None):
            with self.assertRaises(ValueError):
                FillModel(timing)
        for index in (-1, True, 1.1):
            with self.assertRaises(ValueError):
                FillModel("next_open").resolve(signal_index=index, available_index=0, bar_count=3)


class CostModelTests(unittest.TestCase):
    def test_start_order_matches_existing_cost_stress_bitwise(self):
        from quant_platform_kit.research_stats.cost_stress import cost_stress_recompute
        rng = random.Random(2)
        gross = [rng.uniform(-.4, .4) for _ in range(100)]
        turnover = [rng.uniform(0, 2) for _ in gross]
        expected = cost_stress_recompute(gross, turnover, cost_bps_per_side=5).scenario(1).net_returns
        actual = tuple(CostModel(2, 3).net_return(r, t) for r, t in zip(gross, turnover))
        self.assertEqual(actual, expected)

    def test_entry_exit_and_multiplier_charge_each_security_side(self):
        model = CostModel(commission_bps=2, slippage_bps=3, multiplier=2)
        self.assertEqual(model.total_bps_per_side, 10)
        self.assertAlmostEqual(model.fraction(1), .001)
        self.assertAlmostEqual(model.fraction(2), .002)
        self.assertEqual(model.fraction(0), 0)

    def test_start_vs_end_cost_order_is_explicit(self):
        model = CostModel(commission_bps=100)
        self.assertAlmostEqual(model.net_return(.1, 1, charge_at="start"), .089)
        self.assertAlmostEqual(model.net_return(.1, 1, charge_at="end"), .09)

    def test_invalid_and_ruin_inputs_fail_closed(self):
        for value in (-1, math.inf, math.nan, True):
            with self.assertRaises(ValueError):
                CostModel(slippage_bps=value)
        for turnover in (-1, math.nan, True, 100):
            with self.assertRaises(ValueError):
                CostModel(commission_bps=100).net_return(.01, turnover)
        with self.assertRaises(ValueError):
            CostModel().net_return(-1, 0)
        with self.assertRaises(ValueError):
            CostModel().net_return(0, 0, charge_at="unknown")


if __name__ == "__main__":
    unittest.main()
