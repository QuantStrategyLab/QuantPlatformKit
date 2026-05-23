import unittest

from quant_platform_kit.common.small_account_compatibility import (
    project_unbuyable_value_targets_to_cash,
)


class SmallAccountCompatibilityTests(unittest.TestCase):
    def test_projects_value_targets_below_one_share_to_cash(self):
        adjusted, substituted = project_unbuyable_value_targets_to_cash(
            {"SOXL": 541.58, "SOXX": 154.74, "BOXX": 0.0},
            {"SOXL": 191.15, "SOXX": 536.88, "BOXX": 100.0},
        )

        self.assertEqual(adjusted["SOXL"], 541.58)
        self.assertEqual(adjusted["SOXX"], 0.0)
        self.assertEqual(adjusted["BOXX"], 0.0)
        self.assertEqual(substituted, ("SOXX",))

    def test_keeps_targets_that_can_buy_one_quantity_step(self):
        adjusted, substituted = project_unbuyable_value_targets_to_cash(
            {"AAA": 100.0, "BBB": 99.99},
            {"AAA": 50.0, "BBB": 50.0},
            quantity_step=2.0,
        )

        self.assertEqual(adjusted["AAA"], 100.0)
        self.assertEqual(adjusted["BBB"], 0.0)
        self.assertEqual(substituted, ("BBB",))


if __name__ == "__main__":
    unittest.main()
