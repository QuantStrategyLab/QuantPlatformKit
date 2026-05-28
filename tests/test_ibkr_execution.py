from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
import unittest

from quant_platform_kit.common.models import OrderIntent
from quant_platform_kit.ibkr.execution import submit_order_intent


@dataclass
class FakeContract:
    symbol: str
    exchange: str
    currency: str


@dataclass
class FakeOptionContract:
    symbol: str
    lastTradeDateOrContractMonth: str
    strike: float
    right: str
    exchange: str
    currency: str


class FakeMarketOrder:
    def __init__(self, side, quantity):
        self.side = side
        self.quantity = quantity
        self.tif = None


class FakeLimitOrder:
    def __init__(self, side, quantity, limit_price):
        self.side = side
        self.quantity = quantity
        self.limit_price = limit_price
        self.tif = None


class FakeComboLeg:
    def __init__(self, conId, ratio, action, exchange):
        self.conId = conId
        self.ratio = ratio
        self.action = action
        self.exchange = exchange


class FakeTrade:
    def __init__(self, status="Submitted", filled=0, avg_fill_price=0, order_id=123):
        self.orderStatus = type(
            "OrderStatus",
            (),
            {"status": status, "filled": filled, "avgFillPrice": avg_fill_price},
        )()
        self.order = type("Order", (), {"orderId": order_id})()


class FakeIB:
    def __init__(self):
        self.orders = []

    def qualifyContracts(self, contract):
        self.qualified_contract = contract

    def placeOrder(self, contract, order):
        self.orders.append((contract, order))
        return FakeTrade(status="Submitted", filled=0, avg_fill_price=0, order_id=321)


class IbkrExecutionTests(unittest.TestCase):
    def test_submit_market_order_intent_returns_execution_report(self) -> None:
        ib = FakeIB()
        report = submit_order_intent(
            ib,
            OrderIntent(symbol="SPY", side="sell", quantity=5),
            wait_seconds=0,
            stock_factory=FakeContract,
            market_order_factory=FakeMarketOrder,
        )

        self.assertEqual(report.symbol, "SPY")
        self.assertEqual(report.status, "Submitted")
        self.assertEqual(report.broker_order_id, "321")
        self.assertEqual(ib.orders[0][1].side, "SELL")

    def test_submit_limit_order_sets_time_in_force(self) -> None:
        ib = FakeIB()
        report = submit_order_intent(
            ib,
            OrderIntent(
                symbol="SPY",
                side="buy",
                quantity=5,
                order_type="limit",
                limit_price=100.5,
                time_in_force="DAY",
            ),
            wait_seconds=0,
            stock_factory=FakeContract,
            limit_order_factory=FakeLimitOrder,
        )

        self.assertEqual(report.raw_payload["time_in_force"], "DAY")
        self.assertEqual(ib.orders[0][1].tif, "DAY")

    def test_submit_order_intent_sets_account_when_provided(self) -> None:
        ib = FakeIB()
        report = submit_order_intent(
            ib,
            OrderIntent(symbol="SPY", side="buy", quantity=5, account_id="U18308207"),
            wait_seconds=0,
            stock_factory=FakeContract,
            market_order_factory=FakeMarketOrder,
        )

        self.assertEqual(ib.orders[0][1].account, "U18308207")
        self.assertEqual(report.raw_payload["account_id"], "U18308207")

    def test_submit_order_intent_rejects_conflicting_account_id(self) -> None:
        ib = FakeIB()

        with self.assertRaises(ValueError):
            submit_order_intent(
                ib,
                OrderIntent(symbol="SPY", side="buy", quantity=5, account_id="U18308207"),
                account_id="U15998061",
                wait_seconds=0,
                stock_factory=FakeContract,
                market_order_factory=FakeMarketOrder,
            )

    def test_submit_order_intent_builds_single_leg_option_contract(self) -> None:
        ib = FakeIB()

        report = submit_order_intent(
            ib,
            OrderIntent(
                symbol="TQQQ",
                side="buy_to_open",
                quantity=2,
                order_type="limit",
                limit_price=32.5,
                time_in_force="DAY",
                metadata={
                    "asset_class": "option",
                    "intent_type": "single_leg_option",
                    "underlier": "TQQQ",
                    "right": "C",
                    "expiration": "2028-01-21",
                    "strike": 70.0,
                },
            ),
            wait_seconds=0,
            option_factory=FakeOptionContract,
            limit_order_factory=FakeLimitOrder,
        )

        contract, order = ib.orders[0]
        self.assertEqual(contract.symbol, "TQQQ")
        self.assertEqual(contract.lastTradeDateOrContractMonth, "20280121")
        self.assertEqual(contract.right, "C")
        self.assertEqual(contract.strike, 70.0)
        self.assertEqual(order.side, "BUY")
        self.assertEqual(report.raw_payload["asset_class"], "option")

    def test_submit_order_intent_builds_option_combo_contract(self) -> None:
        class ComboIB(FakeIB):
            def __init__(self):
                super().__init__()
                self.next_con_id = 100

            def qualifyContracts(self, contract):
                if hasattr(contract, "right"):
                    contract.conId = self.next_con_id
                    self.next_con_id += 1
                self.qualified_contract = contract
                return [contract]

        ib = ComboIB()
        report = submit_order_intent(
            ib,
            OrderIntent(
                symbol="SOXX",
                side="sell",
                quantity=1,
                order_type="limit",
                limit_price=1.25,
                time_in_force="DAY",
                metadata={
                    "asset_class": "option",
                    "intent_type": "multi_leg_option",
                    "underlier": "SOXX",
                    "expiration": "2026-07-17",
                    "legs": (
                        {
                            "action": "sell_to_open",
                            "right": "P",
                            "expiration": "2026-07-17",
                            "strike": 200.0,
                            "ratio": 1,
                        },
                        {
                            "action": "buy_to_open",
                            "right": "P",
                            "expiration": "2026-07-17",
                            "strike": 180.0,
                            "ratio": 1,
                        },
                    ),
                },
            ),
            wait_seconds=0,
            option_factory=FakeOptionContract,
            combo_contract_factory=SimpleNamespace,
            combo_leg_factory=FakeComboLeg,
            limit_order_factory=FakeLimitOrder,
        )

        contract, order = ib.orders[0]
        self.assertEqual(contract.secType, "BAG")
        self.assertEqual(contract.symbol, "SOXX")
        self.assertEqual([leg.action for leg in contract.comboLegs], ["SELL", "BUY"])
        self.assertEqual(order.side, "SELL")
        self.assertEqual(report.raw_payload["intent_type"], "multi_leg_option")


if __name__ == "__main__":
    unittest.main()
