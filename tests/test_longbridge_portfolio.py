from __future__ import annotations

import unittest

from quant_platform_kit.longbridge.portfolio import fetch_strategy_account_state


class FakeCashInfo:
    def __init__(self, currency, available_cash):
        self.currency = currency
        self.available_cash = available_cash


class FakeBalanceAccount:
    def __init__(self):
        self.cash_infos = [
            FakeCashInfo("USD", 1000.0),
            FakeCashInfo("SGD", 350.0),
        ]


class FakePosition:
    def __init__(self, symbol, quantity, available_quantity=None):
        self.symbol = symbol
        self.quantity = quantity
        self.available_quantity = available_quantity if available_quantity is not None else quantity


class FakeChannel:
    def __init__(self, positions):
        self.positions = positions


class FakePositionsResponse:
    def __init__(self):
        self.channels = [FakeChannel([FakePosition("SOXL.US", 3), FakePosition("QQQI.US", 2, 1)])]


class FakeQuoteContext:
    def quote(self, symbols):
        prices = {"SOXL.US": 50.0, "QQQI.US": 20.0}
        return [type("Quote", (), {"last_done": prices[symbols[0]]})()]


class FakeTradeContext:
    def account_balance(self):
        return [FakeBalanceAccount()]

    def stock_positions(self):
        return FakePositionsResponse()


class LongBridgePortfolioTests(unittest.TestCase):
    def test_fetch_strategy_account_state(self) -> None:
        state = fetch_strategy_account_state(
            FakeQuoteContext(),
            FakeTradeContext(),
            ["SOXL", "QQQI", "SPYI"],
        )

        self.assertEqual(state["available_cash"], 1000.0)
        self.assertEqual(state["cash_by_currency"], {"USD": 1000.0, "SGD": 350.0})
        self.assertEqual(state["market_values"]["SOXL"], 150.0)
        self.assertEqual(state["quantities"]["QQQI"], 2)
        self.assertEqual(state["sellable_quantities"]["QQQI"], 1)
        self.assertEqual(state["total_strategy_equity"], 1190.0)

    def test_fetch_strategy_account_state_includes_all_positions_when_assets_empty(self) -> None:
        state = fetch_strategy_account_state(
            FakeQuoteContext(),
            FakeTradeContext(),
            [],
        )

        self.assertEqual(state["market_values"], {"SOXL": 150.0, "QQQI": 40.0})
        self.assertEqual(state["quantities"], {"SOXL": 3, "QQQI": 2})
        self.assertEqual(state["sellable_quantities"], {"SOXL": 3, "QQQI": 1})
        self.assertEqual(state["total_strategy_equity"], 1190.0)

    def test_fetch_strategy_account_state_preserves_fractional_position_quantity(self) -> None:
        class FractionalPositionsResponse:
            def __init__(self):
                self.channels = [FakeChannel([FakePosition("SOXL.US", 1.999999)])]

        class FractionalTradeContext(FakeTradeContext):
            def stock_positions(self):
                return FractionalPositionsResponse()

        position_logs = []
        state = fetch_strategy_account_state(
            FakeQuoteContext(),
            FractionalTradeContext(),
            ["SOXL"],
            position_log_fn=position_logs.append,
        )

        self.assertEqual(state["quantities"]["SOXL"], 1.999999)
        self.assertEqual(state["sellable_quantities"]["SOXL"], 1.999999)
        self.assertAlmostEqual(state["market_values"]["SOXL"], 99.99995)
        self.assertEqual(
            position_logs,
            [
                "[position_snapshot] raw symbol=SOXL full_symbol=SOXL.US quantity=1.999999 "
                "available_quantity=1.999999",
                "[position_snapshot] aggregate symbol=SOXL quantity=1.999999 "
                "sellable_quantity=1.999999 market_value=100.00",
            ],
        )


if __name__ == "__main__":
    unittest.main()
