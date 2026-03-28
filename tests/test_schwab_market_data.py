from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from quant_platform_kit.schwab.market_data import fetch_default_daily_price_history_candles, fetch_quotes


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload


class FakeClient:
    def get_price_history(self, symbol, **_kwargs):
        return FakeResponse({"candles": [{"close": 10.0}, {"close": 11.0}]})

    def get_quotes(self, symbols):
        return FakeResponse(
            {
                symbol: {"quote": {"lastPrice": 100.0 + i, "bidPrice": 99.5 + i, "askPrice": 100.5 + i}}
                for i, symbol in enumerate(symbols)
            }
        )


class SchwabMarketDataTests(unittest.TestCase):
    def test_fetch_default_daily_price_history_candles(self) -> None:
        schwab_module = types.ModuleType("schwab")
        client_module = types.ModuleType("schwab.client")
        client_module.Client = types.SimpleNamespace(
            PriceHistory=types.SimpleNamespace(
                PeriodType=types.SimpleNamespace(YEAR="YEAR"),
                Period=types.SimpleNamespace(TWO_YEARS="TWO_YEARS"),
                FrequencyType=types.SimpleNamespace(DAILY="DAILY"),
                Frequency=types.SimpleNamespace(DAILY="DAILY"),
            )
        )

        with patch.dict(sys.modules, {"schwab": schwab_module, "schwab.client": client_module}):
            candles = fetch_default_daily_price_history_candles(FakeClient(), "QQQ")

        self.assertEqual(len(candles), 2)
        self.assertEqual(candles[-1]["close"], 11.0)

    def test_fetch_quotes_returns_snapshots(self) -> None:
        snapshots = fetch_quotes(FakeClient(), ["TQQQ", "BOXX"])

        self.assertEqual(snapshots["TQQQ"].last_price, 100.0)
        self.assertEqual(snapshots["BOXX"].ask_price, 101.5)


if __name__ == "__main__":
    unittest.main()
