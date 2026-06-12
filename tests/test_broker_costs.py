import unittest

from quant_platform_kit.common.broker_costs import (
    BrokerCostProfile,
    minimum_economic_order_notional_usd,
)


class BrokerCostTests(unittest.TestCase):
    def test_zero_fixed_fee_keeps_explicit_floor(self):
        self.assertEqual(
            minimum_economic_order_notional_usd(
                BrokerCostProfile(explicit_min_order_notional_usd=25.0)
            ),
            25.0,
        )

    def test_minimum_order_fee_sets_economic_floor(self):
        self.assertEqual(
            minimum_economic_order_notional_usd(
                BrokerCostProfile(minimum_order_fee_usd=0.35, max_fixed_fee_bps=50.0)
            ),
            70.0,
        )

    def test_longbridge_like_fixed_fee_uses_bps_limit(self):
        self.assertEqual(
            minimum_economic_order_notional_usd(
                BrokerCostProfile(fixed_order_fee_usd=0.99, max_fixed_fee_bps=100.0)
            ),
            99.0,
        )

    def test_explicit_floor_can_be_more_conservative_than_fee_floor(self):
        self.assertEqual(
            minimum_economic_order_notional_usd(
                BrokerCostProfile(
                    fixed_order_fee_usd=0.99,
                    max_fixed_fee_bps=100.0,
                    explicit_min_order_notional_usd=150.0,
                )
            ),
            150.0,
        )


if __name__ == "__main__":
    unittest.main()
