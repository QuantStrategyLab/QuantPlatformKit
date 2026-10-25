from __future__ import annotations

import unittest
from types import SimpleNamespace

from quant_platform_kit.common.models import ExecutionReport
from quant_platform_kit.common.order_status import (
    available_sell_quantity,
    compute_confirmed_sell_release_value,
    normalize_order_status_payload,
)


class OrderStatusHelpersTests(unittest.TestCase):
    def test_available_sell_quantity_deducts_working_sell(self) -> None:
        self.assertEqual(
            available_sell_quantity(10, [{"side": "sell", "status": "working", "quantity": 4}]),
            6.0,
        )

    def test_available_sell_quantity_releases_terminal_orders(self) -> None:
        for status in ("cancelled", "canceled", "rejected", "filled", "expired", " CANCELED "):
            with self.subTest(status=status):
                self.assertEqual(
                    available_sell_quantity(10, [{"side": "sell", "status": status, "quantity": 4}]),
                    10.0,
                )

    def test_available_sell_quantity_partial_fill_then_cancel(self) -> None:
        order = {
            "side": "sell", "status": "partially_filled", "quantity": 4,
            "filled_quantity": 1, "order_id": "partial-1",
        }
        self.assertEqual(available_sell_quantity(9, [order]), 6.0)
        self.assertEqual(
            available_sell_quantity(9, [order, {**order, "status": "cancelled"}]), 9.0,
        )

    def test_available_sell_quantity_uses_last_snapshot_per_id(self) -> None:
        order = {"side": "sell", "status": "working", "quantity": 4, "broker_order_id": "OID-1"}
        self.assertEqual(available_sell_quantity(10, [order, dict(order)]), 6.0)
        cancelled = {**order, "status": "cancelled"}
        self.assertEqual(available_sell_quantity(10, [order, cancelled]), 10.0)
        self.assertEqual(available_sell_quantity(10, [cancelled, order]), 6.0)

    def test_available_sell_quantity_counts_anonymous_orders_separately(self) -> None:
        order = {"side": "sell", "quantity": 4}
        self.assertEqual(available_sell_quantity(10, [order, dict(order)]), 2.0)

    def test_available_sell_quantity_ignores_other_sides(self) -> None:
        self.assertEqual(
            available_sell_quantity(10, [{"side": "buy", "quantity": "invalid"}, {}]), 10.0,
        )

    def test_available_sell_quantity_holds_unknown_or_missing_status(self) -> None:
        for status in ("pending_review", None):
            with self.subTest(status=status):
                self.assertEqual(
                    available_sell_quantity(10, [{"side": "sell", "status": status, "quantity": 4}]),
                    6.0,
                )

    def test_available_sell_quantity_clamps_remainder_and_availability(self) -> None:
        self.assertEqual(available_sell_quantity(2, [{"side": "sell", "quantity": 4}]), 0.0)
        self.assertEqual(
            available_sell_quantity(2, [{"side": "sell", "quantity": 4, "filled": 5}]), 2.0,
        )

    def test_available_sell_quantity_supports_attributes_aliases_and_iterables(self) -> None:
        orders = (
            SimpleNamespace(side=" S-E_L L ", status="working", qty=4, executed_qty=1, order_id="a"),
            {"side": "sell", "order_quantity": 3, "filled": 1, "order_id": "b"},
        )
        self.assertEqual(available_sell_quantity(10, iter(orders)), 5.0)

    def test_available_sell_quantity_uses_first_present_field(self) -> None:
        order = {
            "side": "sell", "quantity": 4, "qty": 9, "order_quantity": 10,
            "filled_quantity": 0, "executed_qty": 2, "filled": 3,
            "broker_order_id": "primary", "order_id": "secondary",
        }
        for snapshot in (order, SimpleNamespace(**order)):
            with self.subTest(snapshot=snapshot):
                self.assertEqual(
                    available_sell_quantity(10, [snapshot, {**order, "order_id": "other"}]), 6.0,
                )
        with self.assertRaisesRegex(ValueError, "^ORDER_AVAILABILITY_INVALID$"):
            available_sell_quantity(10, [{"side": "sell", "quantity": None, "qty": 4}])

    def test_available_sell_quantity_rejects_invalid_position(self) -> None:
        for value in (-1, float("nan"), float("inf"), True, False, None, "10", 10 ** 400):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "^ORDER_AVAILABILITY_INVALID$"):
                    available_sell_quantity(value, None)

    def test_available_sell_quantity_rejects_invalid_order_quantities(self) -> None:
        fill_names = ("filled_quantity", "executed_qty", "filled")
        for name in ("quantity", "qty", "order_quantity", *fill_names):
            values = (-1, float("nan"), float("inf"), True, "invalid")
            if name not in fill_names:
                values += (None,)
            for value in values:
                with self.subTest(name=name, value=value):
                    order = {"side": "sell", "quantity": 4}
                    if name in ("qty", "order_quantity"):
                        del order["quantity"]
                    order[name] = value
                    with self.assertRaisesRegex(ValueError, "^ORDER_AVAILABILITY_INVALID$"):
                        available_sell_quantity(10, [order])
        with self.assertRaisesRegex(ValueError, "^ORDER_AVAILABILITY_INVALID$"):
            available_sell_quantity(10, [{"side": "sell"}])

    def test_available_sell_quantity_without_orders(self) -> None:
        self.assertEqual(available_sell_quantity(10, None), 10.0)
        self.assertEqual(available_sell_quantity(0.5, []), 0.5)

    def test_available_sell_quantity_treats_empty_id_as_anonymous(self) -> None:
        order = {"side": "sell", "status": "working", "quantity": 4, "broker_order_id": " "}
        self.assertEqual(available_sell_quantity(10, [order, dict(order)]), 2.0)

    def test_available_sell_quantity_reads_execution_report_with_unset_fill(self) -> None:
        report = ExecutionReport(symbol="TEST", side="sell", quantity=4, status="working")
        self.assertIsNone(report.filled_quantity)
        self.assertEqual(available_sell_quantity(10, [report]), 6.0)

    def test_available_sell_quantity_rejects_mapping_container(self) -> None:
        order = {"side": "sell", "status": "working", "quantity": 4}
        with self.assertRaisesRegex(ValueError, "^ORDER_AVAILABILITY_INVALID$"):
            available_sell_quantity(10, {"a": order})

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

    def test_normalize_order_status_payload_does_not_treat_submitted_order_values_as_fills(self) -> None:
        normalized = normalize_order_status_payload(
            {
                "status": "ACCEPTED",
                "quantity": 10,
                "limitPrice": 100.0,
            }
        )

        self.assertEqual(normalized["executed_qty"], 0.0)
        self.assertEqual(normalized["executed_price"], 0.0)

    def test_normalize_order_status_payload_aggregates_execution_leg_quantities(self) -> None:
        normalized = normalize_order_status_payload(
            {
                "status": "FILLED",
                "orderActivityCollection": [
                    {
                        "executionLegs": [
                            {"quantity": 1, "price": 100.0},
                            {"quantity": 2, "price": 110.0},
                        ]
                    }
                ],
            }
        )

        self.assertEqual(normalized["executed_qty"], 3.0)
        self.assertAlmostEqual(normalized["executed_price"], 320.0 / 3.0)


if __name__ == "__main__":
    unittest.main()
