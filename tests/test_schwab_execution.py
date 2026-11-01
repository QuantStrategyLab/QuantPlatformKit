from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

import pytest

from quant_platform_kit.common.execution_state import (
    AccountSubmissionError,
    AccountSubmissionSession,
    ExecutionMarkerStore,
)
from quant_platform_kit.common.models import ExecutionReport, OrderIntent
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


@pytest.mark.parametrize("status_code", [408, 500, 502, 503, 504, 302, 202, None, "500", True])
def test_ambiguous_http_response_is_not_a_rejection(status_code):
    client = FakeClient(FakeResponse(status_code, text="synthetic transport detail"))
    report = submit_equity_order(
        client, "synthetic-account",
        OrderIntent(symbol="TQQQ", side="buy", quantity=1,
                    metadata={"notional_usd": 50.0}),
    )
    assert report.status == "unknown"
    assert report.broker_order_id is None
    assert report.raw_payload["status_code"] == status_code


@pytest.mark.parametrize("status_code", [408, 500, 502, 503, 504])
def test_ambiguous_http_response_remains_blocking_after_restart(tmp_path, status_code):
    account = "synthetic-account"
    store = ExecutionMarkerStore(local_dir=tmp_path)
    session = AccountSubmissionSession(
        store, broker="schwab", account_id=account, owner_id="synthetic-owner",
        profile="tqqq_growth_income", intent_id="a" * 64, release_id="b" * 64,
    )
    order = OrderIntent(symbol="TQQQ", side="buy", quantity=1,
                        account_id=account, metadata={"notional_usd": 50.0})
    client = FakeClient(FakeResponse(status_code))
    grant = session.reserve(order)
    session.dispatch(grant, order, lambda: submit_equity_order(client, account, order))
    reopened = AccountSubmissionSession(
        ExecutionMarkerStore(local_dir=tmp_path), broker="schwab", account_id=account,
        owner_id="synthetic-owner", profile="soxl_soxx_trend_income",
        intent_id="c" * 64, release_id="b" * 64,
    )
    assert reopened.read_state()["attempts"][grant.attempt_id]["certainty"] == "UNKNOWN"
    with pytest.raises(AccountSubmissionError, match="UNKNOWN"):
        reopened.reserve(OrderIntent(symbol="SOXL", side="buy", quantity=1, account_id=account))
    with pytest.raises(AccountSubmissionError):
        session.dispatch(grant, order, lambda: pytest.fail("duplicate broker submission"))


@pytest.mark.parametrize("headers", [
    {}, {"Location": ""}, {"Location": "/orders/"}, {"Location": "/orders"},
    {"Location": "bogus"}, {"Location": "https://api.schwabapi.com/trader/v1/accounts/synthetic/orders"},
    {"Location": "/orders/not-an-id"}, {"Location": "/orders/123?unverified=true"},
])
def test_success_response_without_order_identity_is_unknown(headers):
    report = submit_equity_order(
        FakeClient(FakeResponse(201, headers=headers)), "synthetic-account",
        OrderIntent(symbol="TQQQ", side="buy", quantity=1,
                    metadata={"notional_usd": 50.0}),
    )
    assert report.status == "unknown"
    assert report.broker_order_id is None
    assert report.raw_payload["status_code"] == 201


@pytest.mark.parametrize("location", [
    "/orders/456",
    "https://api.schwabapi.com/trader/v1/accounts/synthetic-account/orders/456",
])
def test_success_response_preserves_valid_order_identity(location):
    report = submit_equity_order(
        FakeClient(FakeResponse(201, headers={"Location": location})), "synthetic-account",
        OrderIntent(symbol="TQQQ", side="buy", quantity=1,
                    metadata={"notional_usd": 50.0}),
    )
    assert report.status == "accepted"
    assert report.broker_order_id == "456"


def test_unidentified_acceptance_cannot_return_success_from_dispatch(tmp_path):
    account = "synthetic-account"
    session = AccountSubmissionSession(
        ExecutionMarkerStore(local_dir=tmp_path), broker="schwab", account_id=account,
        owner_id="synthetic-owner", profile="tqqq_growth_income",
        intent_id="a" * 64, release_id="b" * 64,
    )
    order = OrderIntent(symbol="TQQQ", side="buy", quantity=1, account_id=account)
    grant = session.reserve(order)
    report = ExecutionReport(symbol="TQQQ", side="buy", quantity=1, status="accepted")
    with pytest.raises(AccountSubmissionError, match="uncertain"):
        session.dispatch(grant, order, lambda: report)
    assert session.read_state()["attempts"][grant.attempt_id]["certainty"] == "UNKNOWN"


if __name__ == "__main__":
    unittest.main()
