from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from quant_platform_kit.common.models import OrderIntent
from quant_platform_kit.schwab.execution import fetch_order_status, submit_equity_order


class FakeResponse:
    def __init__(self, status_code=201, text="", headers=None, json_payload=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self._json_payload = json_payload

    def json(self):
        if self._json_payload is None:
            raise ValueError("no json payload")
        return self._json_payload


class FakeClient:
    def __init__(self, response):
        self.response = response

    def place_order(self, account_hash, order):
        self.last_call = (account_hash, order)
        return self.response

    def get_order(self, order_id, account_hash):
        self.last_order_lookup = (order_id, account_hash)
        return self.response


class SchwabExecutionTests(unittest.TestCase):
    def test_submit_limit_buy_returns_accepted_report(self) -> None:
        equities_module = types.ModuleType("schwab.orders.equities")
        equities_module.equity_buy_limit = lambda symbol, quantity, price: ("buy_limit", symbol, quantity, price)
        equities_module.equity_buy_market = lambda symbol, quantity: ("buy_market", symbol, quantity)
        equities_module.equity_sell_market = lambda symbol, quantity: ("sell_market", symbol, quantity)

        client = FakeClient(FakeResponse(201, headers={"Location": "/orders/456"}))
        with patch.dict(sys.modules, {"schwab.orders.equities": equities_module}):
            report = submit_equity_order(
                client,
                "acct-hash",
                OrderIntent(symbol="TQQQ", side="buy", quantity=2, order_type="limit", limit_price=50.25),
            )

        self.assertEqual(report.status, "accepted")
        self.assertEqual(report.broker_order_id, "456")
        self.assertEqual(client.last_call[0], "acct-hash")

    def test_submit_sell_market_returns_rejected_report(self) -> None:
        equities_module = types.ModuleType("schwab.orders.equities")
        equities_module.equity_buy_limit = lambda symbol, quantity, price: ("buy_limit", symbol, quantity, price)
        equities_module.equity_buy_market = lambda symbol, quantity: ("buy_market", symbol, quantity)
        equities_module.equity_sell_market = lambda symbol, quantity: ("sell_market", symbol, quantity)

        client = FakeClient(FakeResponse(400, text="bad request"))
        with patch.dict(sys.modules, {"schwab.orders.equities": equities_module}):
            report = submit_equity_order(
                client,
                "acct-hash",
                OrderIntent(symbol="TQQQ", side="sell", quantity=2),
            )

        self.assertEqual(report.status, "rejected")
        self.assertIn("bad request", report.raw_payload["detail"])

    def test_submit_dollar_buy_market_uses_quantity_type_dollars(self) -> None:
        client = FakeClient(FakeResponse(201, headers={"Location": "/orders/789"}))
        report = submit_equity_order(
            client,
            "acct-hash",
            OrderIntent(
                symbol="QQQM",
                side="buy",
                quantity=0.0,
                order_type="market",
                metadata={"notional_usd": 50.0},
            ),
        )

        self.assertEqual(report.status, "accepted")
        self.assertEqual(report.quantity, 50.0)
        order = client.last_call[1]
        self.assertEqual(order["orderType"], "MARKET")
        self.assertEqual(order["orderLegCollection"][0]["quantityType"], "DOLLARS")
        self.assertEqual(order["orderLegCollection"][0]["quantity"], 50.0)
        self.assertEqual(order["orderLegCollection"][0]["instrument"]["symbol"], "QQQM")

    def test_fetch_order_status_reads_execution_legs(self) -> None:
        client = FakeClient(
            FakeResponse(
                200,
                json_payload={
                    "status": "FILLED",
                    "filledQuantity": 3,
                    "orderActivityCollection": [
                        {
                            "executionLegs": [
                                {"quantity": 1, "price": 100.0},
                                {"quantity": 2, "price": 101.0},
                            ]
                        }
                    ],
                },
            )
        )

        status = fetch_order_status(client, "acct-hash", "OID-123")

        self.assertEqual(client.last_order_lookup, ("OID-123", "acct-hash"))
        self.assertEqual(status["status"], "FILLED")
        self.assertEqual(status["executed_qty"], 3.0)
        self.assertAlmostEqual(status["executed_price"], (1 * 100.0 + 2 * 101.0) / 3)
        self.assertEqual(status["broker_order_id"], "OID-123")


if __name__ == "__main__":
    unittest.main()
