from __future__ import annotations

import contextlib
import ctypes
import os
import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd

from quant_platform_kit.longbridge.market_data import (
    _completed_daily_closes,
    calculate_rotation_indicators,
    fetch_last_price,
    fetch_last_prices,
)


class FakeQuote:
    def __init__(self, symbol, last_done):
        self.symbol = symbol
        self.last_done = last_done


class FakeBar:
    def __init__(self, close, timestamp=None):
        self.close = close
        self.timestamp = timestamp


class FakeQuoteContext:
    def quote(self, symbols):
        prices = {"SOXL.US": 123.45, "SOXX.US": 234.56}
        return [FakeQuote(symbol, prices[symbol]) for symbol in symbols]

    def candlesticks(self, symbol, period, count, adjust_type):
        if symbol == "SOXL.US":
            return [FakeBar(100 + i) for i in range(count)]
        return [FakeBar(200.0 + i) for i in range(count)]


@contextlib.contextmanager
def _process_timezone(tz_name: str):
    """Set process-local TZ for naive datetime.astimezone semantics.

    This Python build may omit ``time.tzset``; libc ``tzset`` still applies
    the ``TZ`` environment variable on macOS/Linux.
    """
    previous = os.environ.get("TZ")
    os.environ["TZ"] = tz_name
    ctypes.CDLL(None).tzset()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous
        ctypes.CDLL(None).tzset()


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
        with patch(
            "quant_platform_kit.longbridge.market_data.time.sleep"
        ) as sleep_mock:
            self.assertEqual(fetch_last_price(quote_context, "SOXL.US"), 123.45)

        self.assertEqual(quote_context.calls, 2)
        sleep_mock.assert_called_once_with(1.0)

    def test_calculate_rotation_indicators(self) -> None:
        longport_module = types.ModuleType("longport")
        openapi_module = types.ModuleType("longport.openapi")
        openapi_module.Period = types.SimpleNamespace(Day="Day")
        openapi_module.AdjustType = types.SimpleNamespace(ForwardAdjust="ForwardAdjust")

        with patch.dict(
            sys.modules,
            {"longport": longport_module, "longport.openapi": openapi_module},
        ):
            indicators = calculate_rotation_indicators(
                FakeQuoteContext(), trend_window=150
            )

        self.assertIsNotNone(indicators)
        self.assertEqual(indicators["soxl"]["price"], 519.0)
        self.assertEqual(indicators["soxx"]["price"], 619.0)
        self.assertAlmostEqual(
            indicators["soxx"]["ma20"], sum(200.0 + i for i in range(400, 420)) / 20
        )
        self.assertGreater(indicators["soxx"]["ma20_slope"], 0.0)
        self.assertEqual(indicators["soxx"]["rsi14"], 100.0)
        self.assertGreaterEqual(indicators["soxx"]["rsi14_dynamic_threshold"], 70.0)
        self.assertGreater(indicators["soxx"]["bb_upper"], indicators["soxx"]["price"])
        self.assertLess(indicators["soxx"]["bb_lower"], indicators["soxx"]["price"])
        self.assertIn("realized_volatility_10", indicators["soxx"])
        self.assertIn("realized_volatility_20", indicators["soxx"])
        self.assertEqual(
            indicators["soxx"]["realized_volatility_10_dynamic_threshold"], 0.50
        )
        self.assertEqual(
            indicators["soxx"]["realized_volatility_10_dynamic_sample_count"], 252.0
        )
        self.assertEqual(
            indicators["soxx"]["realized_volatility_10_dynamic_percentile"], 0.95
        )
        self.assertEqual(
            indicators["soxx"]["realized_volatility"],
            indicators["soxx"]["realized_volatility_20"],
        )

    def test_completed_daily_closes_rejects_missing_stale_duplicate_and_timezone_boundary(self) -> None:
        expected = pd.Timestamp("2026-09-16")
        complete = [FakeBar(100.0, pd.Timestamp("2026-09-16 20:00:00+00:00"))]
        self.assertEqual(_completed_daily_closes(complete, expected).iloc[-1]["close"], 100.0)
        self.assertIsNone(_completed_daily_closes([FakeBar(100.0)], expected))
        self.assertIsNone(_completed_daily_closes([FakeBar(float("nan"), pd.Timestamp("2026-09-16 20:00:00+00:00"))], expected))
        self.assertIsNone(_completed_daily_closes([FakeBar(float("inf"), pd.Timestamp("2026-09-16 20:00:00+00:00"))], expected))
        self.assertIsNone(_completed_daily_closes([FakeBar(0.0, pd.Timestamp("2026-09-16 20:00:00+00:00"))], expected))
        self.assertIsNone(_completed_daily_closes([FakeBar(100.0, pd.Timestamp("2026-09-15 20:00:00+00:00"))], expected))
        self.assertIsNone(_completed_daily_closes(complete + [FakeBar(101.0, pd.Timestamp("2026-09-16 21:00:00+00:00"))], expected))
        self.assertEqual(_completed_daily_closes([FakeBar(100.0, pd.Timestamp("2026-09-17 00:30:00+00:00"))], expected).iloc[-1]["session"], expected)

    def test_completed_daily_closes_naive_process_local_dst_and_timezone_matrix(self) -> None:
        # LongPort 3.x emits naive process-local wall times for broker instants.
        # Recover the instant via local semantics, then map to the NY session date.
        # Do not reject naive timestamps, and do not blindly stamp UTC/NY.
        cases = (
            # Summer (EDT): exchange local midnight 2026-06-16 == 04:00 UTC
            ("America/New_York", "2026-06-16 00:00:00", "2026-06-16"),
            ("UTC", "2026-06-16 04:00:00", "2026-06-16"),
            ("Asia/Shanghai", "2026-06-16 12:00:00", "2026-06-16"),
            # Winter (EST): exchange local midnight 2026-01-15 == 05:00 UTC
            ("America/New_York", "2026-01-15 00:00:00", "2026-01-15"),
            ("UTC", "2026-01-15 05:00:00", "2026-01-15"),
            ("Asia/Shanghai", "2026-01-15 13:00:00", "2026-01-15"),
        )
        for process_tz, naive_wall, session_date in cases:
            with self.subTest(process_tz=process_tz, naive_wall=naive_wall):
                expected = pd.Timestamp(session_date)
                with _process_timezone(process_tz):
                    # Sanity: naive wall must equal the process-local view of the
                    # same UTC instant that yields this NY session.
                    local_view = (
                        pd.Timestamp(f"{session_date} 00:00:00", tz="America/New_York")
                        .tz_convert(process_tz)
                        .tz_localize(None)
                    )
                    self.assertEqual(local_view, pd.Timestamp(naive_wall))
                    frame = _completed_daily_closes(
                        [FakeBar(100.0, pd.Timestamp(naive_wall))],
                        expected,
                    )
                self.assertIsNotNone(frame)
                self.assertEqual(frame.iloc[-1]["session"], expected)
                self.assertEqual(frame.iloc[-1]["close"], 100.0)

        # Aware timestamps remain accepted and agree with the NY session calendar.
        aware = FakeBar(
            100.0,
            pd.Timestamp("2026-06-16 00:00:00", tz="America/New_York").tz_convert("UTC"),
        )
        aware_frame = _completed_daily_closes([aware], pd.Timestamp("2026-06-16"))
        self.assertIsNotNone(aware_frame)
        self.assertEqual(aware_frame.iloc[-1]["session"], pd.Timestamp("2026-06-16"))

    def test_completed_session_opt_in_excludes_open_session_bar(self) -> None:
        class TimedContext(FakeQuoteContext):
            def candlesticks(self, symbol, period, count, adjust_type):
                sessions = list(pd.bdate_range(end="2026-09-16", periods=count - 1)) + [pd.Timestamp("2026-09-17")]
                base = 100.0 if symbol == "SOXL.US" else 200.0
                return [
                    FakeBar(
                        base + index,
                        session.tz_localize("America/New_York")
                        .replace(hour=9, minute=30)
                        .tz_convert("UTC"),
                    )
                    for index, session in enumerate(sessions)
                ]

        longport_module = types.ModuleType("longport")
        openapi_module = types.ModuleType("longport.openapi")
        openapi_module.Period = types.SimpleNamespace(Day="Day")
        openapi_module.AdjustType = types.SimpleNamespace(ForwardAdjust="ForwardAdjust")
        with patch.dict(sys.modules, {"longport": longport_module, "longport.openapi": openapi_module}):
            indicators = calculate_rotation_indicators(
                TimedContext(), trend_window=150,
                completed_session_date="2026-09-16",
            )
        self.assertIsNotNone(indicators)
        self.assertEqual(indicators["completed_session"]["date"], "2026-09-16")
        self.assertEqual(indicators["soxl"]["price"], 100.0 + 418)
        self.assertEqual(indicators["soxx"]["price"], 200.0 + 418)

    def test_completed_session_opt_in_rejects_missing_asset_session(self) -> None:
        class MissingSessionContext(FakeQuoteContext):
            def candlesticks(self, symbol, period, count, adjust_type):
                sessions = list(pd.bdate_range(end="2026-09-15", periods=count - 1))
                if symbol == "SOXL.US":
                    sessions.append(pd.Timestamp("2026-09-17"))
                base = 100.0 if symbol == "SOXL.US" else 200.0
                return [
                    FakeBar(
                        base + index,
                        session.tz_localize("America/New_York")
                        .replace(hour=9, minute=30)
                        .tz_convert("UTC"),
                    )
                    for index, session in enumerate(sessions)
                ]

        longport_module = types.ModuleType("longport")
        openapi_module = types.ModuleType("longport.openapi")
        openapi_module.Period = types.SimpleNamespace(Day="Day")
        openapi_module.AdjustType = types.SimpleNamespace(ForwardAdjust="ForwardAdjust")
        with patch.dict(sys.modules, {"longport": longport_module, "longport.openapi": openapi_module}):
            indicators = calculate_rotation_indicators(
                MissingSessionContext(), trend_window=150,
                completed_session_date="2026-09-16",
            )
        self.assertIsNone(indicators)


if __name__ == "__main__":
    unittest.main()
