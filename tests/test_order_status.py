from __future__ import annotations

import unittest

from quant_platform_kit.common.order_status import compute_confirmed_sell_release_value


class OrderStatusHelpersTests(unittest.TestCase):
    def test_compute_confirmed_sell_release_value_supports_single_argument_fetcher(self) -> None:
        released = compute_confirmed_sell_release_value(
            submitted_sell_orders=(
                {
                    "symbol": "BOXX",
                    "side": "sell",
                    "quantity": 8.0,
                    "broker_order_id": "OID-1",
                    "status": "accepted",
                },
            ),
            fetch_order_status=lambda order_id: {
                "broker_order_id": order_id,
                "status": "Filled",
                "executed_qty": 8.0,
                "executed_price": 100.0,
            },
        )

        self.assertEqual(released, 800.0)

    def test_compute_confirmed_sell_release_value_supports_contextual_fetcher(self) -> None:
        observed = {}

        def fetch_order_status(context, order_id):
            observed["call"] = (context, order_id)
            return {
                "status": "PartiallyFilled",
                "executed_qty": 2.0,
                "executed_price": 50.0,
            }

        released = compute_confirmed_sell_release_value(
            submitted_sell_orders=(
                {
                    "symbol": "TQQQ",
                    "side": "sell",
                    "quantity": 4.0,
                    "broker_order_id": "OID-2",
                    "status": "submitted",
                },
            ),
            fetch_order_status=fetch_order_status,
            order_status_context="ctx-1",
        )

        self.assertEqual(observed["call"], ("ctx-1", "OID-2"))
        self.assertEqual(released, 100.0)


if __name__ == "__main__":
    unittest.main()
