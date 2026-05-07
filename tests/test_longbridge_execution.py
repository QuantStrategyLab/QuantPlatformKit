from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from quant_platform_kit.longbridge.execution import estimate_max_purchase_quantity, fetch_order_status, submit_order


class FakeEstimateResponse:
    def __init__(self, cash_max_qty):
        self.cash_max_qty = cash_max_qty


class FakeOrdersResponse:
    def __init__(self, orders):
        self.orders = orders


class FakeTradeContext:
    def estimate_max_purchase_quantity(self, **kwargs):
        self.estimate_kwargs = kwargs
        return FakeEstimateResponse("12")

    def submit_order(self, symbol, order_type, side, quantity, tif, **kwargs):
        self.submit_args = (symbol, order_type, side, quantity, tif, kwargs)
        return type("SubmitResponse", (), {"order_id": "OID-1"})()

    def today_orders(self, order_id):
        order = type(
            "Order",
            (),
            {
                "status": "Filled",
                "executed_quantity": "10",
                "executed_price": "101.5",
                "msg": "",
            },
        )()
        return FakeOrdersResponse([order])


class LongBridgeExecutionTests(unittest.TestCase):
    def test_estimate_max_purchase_quantity(self) -> None:
        longport_module = types.ModuleType("longport")
        openapi_module = types.ModuleType("longport.openapi")
        openapi_module.OrderSide = types.SimpleNamespace(Buy="Buy")
        openapi_module.OrderType = types.SimpleNamespace(LO="LO", MO="MO")

        ctx = FakeTradeContext()
        with patch.dict(sys.modules, {"longport": longport_module, "longport.openapi": openapi_module}):
            quantity = estimate_max_purchase_quantity(ctx, "SOXL.US", order_kind="limit", ref_price=100.5)

        self.assertEqual(quantity, 12)
        self.assertNotIn("fractional_shares", ctx.estimate_kwargs)

    def test_submit_order(self) -> None:
        longport_module = types.ModuleType("longport")
        openapi_module = types.ModuleType("longport.openapi")
        openapi_module.OrderSide = types.SimpleNamespace(Buy="Buy", Sell="Sell")
        openapi_module.OrderType = types.SimpleNamespace(LO="LO", MO="MO")
        openapi_module.TimeInForceType = types.SimpleNamespace(Day="Day")

        ctx = FakeTradeContext()
        with patch.dict(sys.modules, {"longport": longport_module, "longport.openapi": openapi_module}):
            report = submit_order(ctx, "SOXL.US", order_kind="limit", side="buy", quantity=5, submitted_price=100.25)

        self.assertEqual(report.status, "submitted")
        self.assertEqual(report.broker_order_id, "OID-1")

    def test_submit_order_allows_whole_decimal_quantity(self) -> None:
        longport_module = types.ModuleType("longport")
        openapi_module = types.ModuleType("longport.openapi")
        openapi_module.OrderSide = types.SimpleNamespace(Buy="Buy", Sell="Sell")
        openapi_module.OrderType = types.SimpleNamespace(LO="LO", MO="MO")
        openapi_module.TimeInForceType = types.SimpleNamespace(Day="Day")

        ctx = FakeTradeContext()
        with patch.dict(sys.modules, {"longport": longport_module, "longport.openapi": openapi_module}):
            report = submit_order(ctx, "SOXL.US", order_kind="limit", side="buy", quantity=1.0, submitted_price=100.25)

        self.assertEqual(report.status, "submitted")
        self.assertEqual(str(ctx.submit_args[3]), "1.0")

    def test_submit_order_rejects_quantity_below_one_before_api_call(self) -> None:
        longport_module = types.ModuleType("longport")
        openapi_module = types.ModuleType("longport.openapi")
        openapi_module.OrderSide = types.SimpleNamespace(Buy="Buy", Sell="Sell")
        openapi_module.OrderType = types.SimpleNamespace(LO="LO", MO="MO")
        openapi_module.TimeInForceType = types.SimpleNamespace(Day="Day")

        ctx = FakeTradeContext()
        with patch.dict(sys.modules, {"longport": longport_module, "longport.openapi": openapi_module}):
            report = submit_order(
                ctx,
                "SOXX.US",
                order_kind="limit",
                side="buy",
                quantity=0.4326,
                submitted_price=495.91,
            )

        self.assertEqual(report.status, "rejected")
        self.assertIn("whole-share quantity of at least 1 share", report.raw_payload["detail"])
        self.assertFalse(hasattr(ctx, "submit_args"))

    def test_submit_order_rejects_fractional_quantity_before_api_call(self) -> None:
        longport_module = types.ModuleType("longport")
        openapi_module = types.ModuleType("longport.openapi")
        openapi_module.OrderSide = types.SimpleNamespace(Buy="Buy", Sell="Sell")
        openapi_module.OrderType = types.SimpleNamespace(LO="LO", MO="MO")
        openapi_module.TimeInForceType = types.SimpleNamespace(Day="Day")

        ctx = FakeTradeContext()
        with patch.dict(sys.modules, {"longport": longport_module, "longport.openapi": openapi_module}):
            report = submit_order(
                ctx,
                "SOXX.US",
                order_kind="limit",
                side="buy",
                quantity=1.5,
                submitted_price=495.91,
            )

        self.assertEqual(report.status, "rejected")
        self.assertIn("whole-share quantity of at least 1 share", report.raw_payload["detail"])
        self.assertFalse(hasattr(ctx, "submit_args"))

    def test_submit_order_rejects_fractional_sell_before_api_call(self) -> None:
        longport_module = types.ModuleType("longport")
        openapi_module = types.ModuleType("longport.openapi")
        openapi_module.OrderSide = types.SimpleNamespace(Buy="Buy", Sell="Sell")
        openapi_module.OrderType = types.SimpleNamespace(LO="LO", MO="MO")
        openapi_module.TimeInForceType = types.SimpleNamespace(Day="Day")

        ctx = FakeTradeContext()
        with patch.dict(sys.modules, {"longport": longport_module, "longport.openapi": openapi_module}):
            report = submit_order(ctx, "BOXX.US", order_kind="market", side="sell", quantity=4.6177)

        self.assertEqual(report.status, "rejected")
        self.assertIn("whole-share quantity of at least 1 share", report.raw_payload["detail"])
        self.assertFalse(hasattr(ctx, "submit_args"))

    def test_fetch_order_status(self) -> None:
        status = fetch_order_status(FakeTradeContext(), "OID-1")

        self.assertEqual(status["status"], "Filled")
        self.assertEqual(status["executed_qty"], "10")


if __name__ == "__main__":
    unittest.main()
