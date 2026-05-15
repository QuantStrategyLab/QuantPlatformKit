import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quant_platform_kit.common.cash_sweep import estimate_cash_sweep_sale_quantity_to_fund_buy  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
