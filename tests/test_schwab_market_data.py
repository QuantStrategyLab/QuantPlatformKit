from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from quant_platform_kit.schwab.market_data import (
    decode_response_json,
    fetch_default_daily_price_history_candles,
    fetch_quotes,
)


class FakeResponse:
    def __init__(self, payload, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}
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
    def _install_fake_schwab_module(self):
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
        return patch.dict(sys.modules, {"schwab": schwab_module, "schwab.client": client_module})

    def test_fetch_default_daily_price_history_candles(self) -> None:
        with self._install_fake_schwab_module():
            candles = fetch_default_daily_price_history_candles(FakeClient(), "QQQ")

        self.assertEqual(len(candles), 2)
        self.assertEqual(candles[-1]["close"], 11.0)

    def test_fetch_default_daily_price_history_retries_rate_limit(self) -> None:
        class RateLimitedClient:
            def __init__(self):
                self.calls = 0

            def get_price_history(self, symbol, **_kwargs):
                self.calls += 1
                if self.calls == 1:
                    return FakeResponse({"error": "rate limited"}, status_code=429, headers={"Retry-After": "0.25"})
                return FakeResponse({"candles": [{"close": 12.0}]})

        rate_limited_client = RateLimitedClient()
        with self._install_fake_schwab_module(), patch(
            "quant_platform_kit.schwab.market_data.time.sleep"
        ) as sleep_mock:
            candles = fetch_default_daily_price_history_candles(rate_limited_client, "SOXL")

        self.assertEqual(candles, [{"close": 12.0}])
        self.assertEqual(rate_limited_client.calls, 2)
        sleep_mock.assert_called_once_with(0.25)

    def test_fetch_quotes_retries_transient_server_error(self) -> None:
        class FlakyQuoteClient:
            def __init__(self):
                self.calls = 0

            def get_quotes(self, symbols):
                self.calls += 1
                if self.calls < 3:
                    return FakeResponse({"error": "unavailable"}, status_code=503)
                return FakeClient().get_quotes(symbols)

        flaky_client = FlakyQuoteClient()
        with patch("quant_platform_kit.schwab.market_data.time.sleep") as sleep_mock:
            snapshots = fetch_quotes(flaky_client, ["TQQQ"])

        self.assertEqual(snapshots["TQQQ"].last_price, 100.0)
        self.assertEqual(flaky_client.calls, 3)
        self.assertEqual([call.args[0] for call in sleep_mock.call_args_list], [1.0, 2.0])

    def test_retry_exhaustion_keeps_original_error_context(self) -> None:
        class AlwaysRateLimitedClient:
            def get_price_history(self, symbol, **_kwargs):
                return FakeResponse({"error": "rate limited"}, status_code=429)

        with self._install_fake_schwab_module(), patch(
            "quant_platform_kit.schwab.market_data.time.sleep"
        ), patch.dict("os.environ", {"QPK_SCHWAB_HTTP_MAX_ATTEMPTS": "2"}):
            with self.assertRaisesRegex(RuntimeError, "SOXL history failed: 429"):
                fetch_default_daily_price_history_candles(AlwaysRateLimitedClient(), "SOXL")

    def test_decode_response_json_still_reports_non_retryable_errors(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Quotes failed: 400"):
            decode_response_json(FakeResponse({"error": "bad request"}, status_code=400), "Quotes")

    def test_fetch_quotes_returns_snapshots(self) -> None:
        snapshots = fetch_quotes(FakeClient(), ["TQQQ", "BOXX"])

        self.assertEqual(snapshots["TQQQ"].last_price, 100.0)
        self.assertEqual(snapshots["BOXX"].ask_price, 101.5)


if __name__ == "__main__":
    unittest.main()
