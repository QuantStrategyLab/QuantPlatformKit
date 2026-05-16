import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_platform_kit.common.cash_sweep import (  # noqa: E402
    estimate_cash_sweep_sale_quantity_to_fund_buy,
    should_sell_cash_sweep_to_fund_whole_share_buy,
)


class CashSweepHelperTests(unittest.TestCase):
    def test_returns_zero_when_buying_power_is_sufficient(self):
        qty = estimate_cash_sweep_sale_quantity_to_fund_buy(
            10,
            100.0,
            1000.0,
            [(500.0, 10.0)],
        )
        self.assertEqual(qty, 0)

    def test_scales_sale_quantity_to_fund_gap(self):
        qty = estimate_cash_sweep_sale_quantity_to_fund_buy(
            10,
            100.0,
            50.0,
            [(500.0, 10.0)],
        )
        self.assertEqual(qty, 5)

    def test_ignores_invalid_funding_needs(self):
        qty = estimate_cash_sweep_sale_quantity_to_fund_buy(
            10,
            100.0,
            50.0,
            [(0.0, 10.0), (500.0, 0.0), (-1.0, -1.0)],
        )
        self.assertEqual(qty, 0)

    def test_detects_when_full_sweep_can_fund_a_whole_share_buy(self):
        should_sell = should_sell_cash_sweep_to_fund_whole_share_buy(
            1,
            100.0,
            100.0,
            [(167.79, 167.79)],
        )
        self.assertTrue(should_sell)

    def test_rejects_when_full_sweep_cannot_fund_a_whole_share_buy(self):
        should_sell = should_sell_cash_sweep_to_fund_whole_share_buy(
            1,
            100.0,
            14.46,
            [(500.0, 504.60)],
        )
        self.assertFalse(should_sell)


if __name__ == "__main__":
    unittest.main()
