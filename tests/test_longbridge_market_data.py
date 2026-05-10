from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from quant_platform_kit.longbridge.market_data import calculate_rotation_indicators, fetch_last_price, fetch_last_prices


class FakeQuote:
    def __init__(self, symbol, last_done):
        self.symbol = symbol
        self.last_done = last_done


class FakeBar:
    def __init__(self, close):
        self.close = close


class FakeQuoteContext:
    def quote(self, symbols):
        prices = {"SOXL.US": 123.45, "SOXX.US": 234.56}
        return [FakeQuote(symbol, prices[symbol]) for symbol in symbols]

    def candlesticks(self, symbol, period, count, adjust_type):
        if symbol == "SOXL.US":
            return [FakeBar(100 + i) for i in range(count)]
        return [FakeBar(200.0 + i) for i in range(count)]


class LongBridgeMarketDataTests(unittest.TestCase):
    def test_fetch_last_price(self) -> None:
        self.assertEqual(fetch_last_price(FakeQuoteContext(), "SOXL.US"), 123.45)

    def test_fetch_last_prices_batches_symbols(self) -> None:
        self.assertEqual(
            fetch_last_prices(FakeQuoteContext(), ["SOXL.US", "SOXX.US", "SOXL.US"]),
            {"SOXL.US": 123.45, "SOXX.US": 234.56},
        )

    def test_fetch_last_price_retries_rate_limit(self) -> None:
        class RateLimitError(Exception):
            code = 301606

        class RateLimitedQuoteContext(FakeQuoteContext):
            def __init__(self):
                self.calls = 0

            def quote(self, symbols):
                self.calls += 1
                if self.calls == 1:
                    raise RateLimitError("request rate limit")
                return super().quote(symbols)

        quote_context = RateLimitedQuoteContext()
        with patch("quant_platform_kit.longbridge.market_data.time.sleep") as sleep_mock:
            self.assertEqual(fetch_last_price(quote_context, "SOXL.US"), 123.45)

        self.assertEqual(quote_context.calls, 2)
        sleep_mock.assert_called_once_with(1.0)

    def test_calculate_rotation_indicators(self) -> None:
        longport_module = types.ModuleType("longport")
        openapi_module = types.ModuleType("longport.openapi")
        openapi_module.Period = types.SimpleNamespace(Day="Day")
        openapi_module.AdjustType = types.SimpleNamespace(ForwardAdjust="ForwardAdjust")

        with patch.dict(sys.modules, {"longport": longport_module, "longport.openapi": openapi_module}):
            indicators = calculate_rotation_indicators(FakeQuoteContext(), trend_window=150)

        self.assertIsNotNone(indicators)
        self.assertEqual(indicators["soxl"]["price"], 379.0)
        self.assertEqual(indicators["soxx"]["price"], 479.0)
        self.assertAlmostEqual(indicators["soxx"]["ma20"], sum(200.0 + i for i in range(260, 280)) / 20)
        self.assertGreater(indicators["soxx"]["ma20_slope"], 0.0)
        self.assertEqual(indicators["soxx"]["rsi14"], 100.0)
        self.assertGreaterEqual(indicators["soxx"]["rsi14_dynamic_threshold"], 70.0)
        self.assertGreater(indicators["soxx"]["bb_upper"], indicators["soxx"]["price"])
        self.assertLess(indicators["soxx"]["bb_lower"], indicators["soxx"]["price"])
        self.assertIn("realized_volatility_20", indicators["soxx"])
        self.assertEqual(
            indicators["soxx"]["realized_volatility"],
            indicators["soxx"]["realized_volatility_20"],
        )


if __name__ == "__main__":
    unittest.main()
