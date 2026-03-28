from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from quant_platform_kit.longbridge.market_data import calculate_rotation_indicators, fetch_last_price


class FakeQuote:
    def __init__(self, last_done):
        self.last_done = last_done


class FakeBar:
    def __init__(self, close):
        self.close = close


class FakeQuoteContext:
    def quote(self, symbols):
        return [FakeQuote(123.45)]

    def candlesticks(self, symbol, period, count, adjust_type):
        if symbol == "SOXL.US":
            return [FakeBar(100 + i) for i in range(count)]
        return [FakeBar(200.0) for _ in range(20)]


class LongBridgeMarketDataTests(unittest.TestCase):
    def test_fetch_last_price(self) -> None:
        self.assertEqual(fetch_last_price(FakeQuoteContext(), "SOXL.US"), 123.45)

    def test_calculate_rotation_indicators(self) -> None:
        longport_module = types.ModuleType("longport")
        openapi_module = types.ModuleType("longport.openapi")
        openapi_module.Period = types.SimpleNamespace(Day="Day")
        openapi_module.AdjustType = types.SimpleNamespace(ForwardAdjust="ForwardAdjust")

        with patch.dict(sys.modules, {"longport": longport_module, "longport.openapi": openapi_module}):
            indicators = calculate_rotation_indicators(FakeQuoteContext(), trend_window=150)

        self.assertIsNotNone(indicators)
        self.assertEqual(indicators["soxl"]["price"], 319.0)
        self.assertEqual(indicators["soxx"]["price"], 200.0)


if __name__ == "__main__":
    unittest.main()
