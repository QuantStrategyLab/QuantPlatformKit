from __future__ import annotations

from unittest.mock import patch
import unittest

from quant_platform_kit.longbridge.portfolio import fetch_strategy_account_state


class FakeCashInfo:
    def __init__(self, currency, available_cash):
        self.currency = currency
        self.available_cash = available_cash


class FakeBalanceAccount:
    def __init__(self):
        self.buy_power = 1000.0
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
    def __init__(self):
        self.quote_calls = []

    def quote(self, symbols):
        self.quote_calls.append(tuple(symbols))
        prices = {"SOXL.US": 50.0, "QQQI.US": 20.0}
        return [
            type("Quote", (), {"symbol": symbol, "last_done": prices[symbol]})()
            for symbol in symbols
        ]


class FakeTradeContext:
    def account_balance(self):
        return [FakeBalanceAccount()]

    def stock_positions(self):
        return FakePositionsResponse()


class LongBridgePortfolioTests(unittest.TestCase):
    def test_fetch_strategy_account_state(self) -> None:
        quote_context = FakeQuoteContext()
        state = fetch_strategy_account_state(
            quote_context,
            FakeTradeContext(),
            ["SOXL", "QQQI", "SPYI"],
        )

        self.assertEqual(state["available_cash"], 1000.0)
        self.assertEqual(state["cash_by_currency"], {"USD": 1000.0, "SGD": 350.0})
        self.assertEqual(state["market_values"]["SOXL"], 150.0)
        self.assertEqual(state["quantities"]["QQQI"], 2)
        self.assertEqual(state["sellable_quantities"]["QQQI"], 1)
        self.assertEqual(state["total_strategy_equity"], 1190.0)
        self.assertEqual(quote_context.quote_calls, [("SOXL.US", "QQQI.US")])

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

    def test_fetch_strategy_account_state_falls_back_when_account_balance_fails(self) -> None:
        class BalanceFailingTradeContext(FakeTradeContext):
            def account_balance(self):
                raise RuntimeError("boom")

        warnings = []
        state = fetch_strategy_account_state(
            FakeQuoteContext(),
            BalanceFailingTradeContext(),
            ["SOXL", "QQQI", "SPYI"],
            warning_log_fn=warnings.append,
        )

        self.assertEqual(state["available_cash"], 0.0)
        self.assertEqual(state["cash_by_currency"], {})
        self.assertEqual(state["market_values"]["SOXL"], 150.0)
        self.assertEqual(state["quantities"]["QQQI"], 2)
        self.assertEqual(state["sellable_quantities"]["QQQI"], 1)
        self.assertEqual(state["total_strategy_equity"], 190.0)
        self.assertTrue(any("longbridge_account_balance_failed" in warning for warning in warnings))

    def test_fetch_strategy_account_state_uses_currency_retry_when_unfiltered_balance_fails(self) -> None:
        class RetryTradeContext(FakeTradeContext):
            def account_balance(self, currency=None):
                if currency is None:
                    raise RuntimeError("boom")
                if currency == "USD":
                    return [FakeBalanceAccount()]
                return []

        warnings = []
        state = fetch_strategy_account_state(
            FakeQuoteContext(),
            RetryTradeContext(),
            ["SOXL", "QQQI", "SPYI"],
            warning_log_fn=warnings.append,
        )

        self.assertEqual(state["available_cash"], 1000.0)
        self.assertEqual(state["cash_by_currency"], {"USD": 1000.0, "SGD": 350.0})
        self.assertTrue(any("longbridge_account_balance_retry_succeeded" in warning for warning in warnings))

    def test_fetch_strategy_account_state_retries_transient_balance_and_position_errors(self) -> None:
        class FlakyTradeContext(FakeTradeContext):
            def __init__(self):
                self.balance_calls = 0
                self.position_calls = 0

            def account_balance(self, currency=None):
                self.balance_calls += 1
                if self.balance_calls == 1:
                    raise RuntimeError("temporary balance failure")
                if currency is None:
                    return [FakeBalanceAccount()]
                if currency == "USD":
                    return [FakeBalanceAccount()]
                return []

            def stock_positions(self):
                self.position_calls += 1
                if self.position_calls == 1:
                    raise RuntimeError("temporary position failure")
                return FakeTradeContext().stock_positions()

        warnings = []
        with patch("quant_platform_kit.longbridge.portfolio.time.sleep", lambda _seconds: None):
            state = fetch_strategy_account_state(
                FakeQuoteContext(),
                FlakyTradeContext(),
                ["SOXL", "QQQI", "SPYI"],
                warning_log_fn=warnings.append,
            )

        self.assertEqual(state["available_cash"], 1000.0)
        self.assertEqual(state["market_values"]["SOXL"], 150.0)
        self.assertGreaterEqual(len([warning for warning in warnings if "retrying" in warning]), 1)


if __name__ == "__main__":
    unittest.main()
