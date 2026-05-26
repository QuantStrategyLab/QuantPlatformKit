from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import unittest

from quant_platform_kit.ibkr.market_data import (
    fetch_historical_price_candles,
    fetch_historical_price_series,
    fetch_quote_snapshots,
)


@dataclass
class FakeContract:
    symbol: str
    exchange: str
    currency: str


@dataclass
class FakeBar:
    date: date
    close: float
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: float = 0.0


class FakeTicker:
    def __init__(
        self,
        market_price: float,
        close: float,
        bid: float | None = None,
        ask: float | None = None,
        *,
        last: float | None = None,
    ):
        self._market_price = market_price
        self.close = close
        self.bid = bid
        self.ask = ask
        self.last = last

    def marketPrice(self) -> float:
        return self._market_price


class FakeIB:
    def __init__(self):
        self.qualified: list[FakeContract] = []
        self.cancelled: list[FakeContract] = []

    def qualifyContracts(self, contract):
        self.qualified.append(contract)

    def reqHistoricalData(self, contract, **kwargs):
        self.last_history_contract = contract
        self.last_history_kwargs = kwargs
        return [
            FakeBar(date=date(2026, 3, 27), open=100.0, high=101.0, low=99.5, close=100.5, volume=1000.0),
            FakeBar(date=date(2026, 3, 28), open=100.5, high=101.5, low=100.0, close=101.0, volume=1200.0),
        ]

    def reqMktData(self, contract, *_args):
        self.last_market_data_contract = contract
        return FakeTicker(102.5, close=101.8, bid=102.4, ask=102.6)

    def cancelMktData(self, contract):
        self.cancelled.append(contract)


class IbkrMarketDataTests(unittest.TestCase):
    def test_fetch_historical_price_series_builds_price_points(self) -> None:
        ib = FakeIB()
        series = fetch_historical_price_series(
            ib,
            "SPY",
            stock_factory=FakeContract,
        )

        self.assertEqual(series.symbol, "SPY")
        self.assertEqual(series.points[-1].close, 101.0)
        self.assertEqual(ib.last_history_contract.symbol, "SPY")
        self.assertEqual(ib.last_history_kwargs["durationStr"], "2 Y")
        self.assertEqual(ib.last_history_kwargs["whatToShow"], "ADJUSTED_LAST")

    def test_fetch_historical_price_series_converts_long_day_duration_to_years(self) -> None:
        ib = FakeIB()
        fetch_historical_price_series(
            ib,
            "SOXL",
            duration="420 D",
            stock_factory=FakeContract,
        )

        self.assertEqual(ib.last_history_kwargs["durationStr"], "2 Y")

    def test_fetch_historical_price_series_falls_back_to_trades_when_adjusted_last_is_empty(self) -> None:
        class AdjustedLastEmptyIB(FakeIB):
            def __init__(self):
                super().__init__()
                self.history_calls = []

            def reqHistoricalData(self, contract, **kwargs):
                self.history_calls.append(kwargs)
                if kwargs["whatToShow"] == "ADJUSTED_LAST":
                    return []
                return super().reqHistoricalData(contract, **kwargs)

        ib = AdjustedLastEmptyIB()
        series = fetch_historical_price_series(
            ib,
            "QQQ",
            stock_factory=FakeContract,
        )

        self.assertEqual(series.points[-1].close, 101.0)
        self.assertEqual([call["whatToShow"] for call in ib.history_calls], ["ADJUSTED_LAST", "TRADES"])

    def test_fetch_historical_price_candles_exposes_ohlc_fields(self) -> None:
        ib = FakeIB()
        candles = fetch_historical_price_candles(
            ib,
            "QQQ",
            stock_factory=FakeContract,
        )

        self.assertEqual(candles[-1]["close"], 101.0)
        self.assertEqual(candles[-1]["open"], 100.5)
        self.assertEqual(candles[-1]["high"], 101.5)
        self.assertEqual(candles[-1]["low"], 100.0)
        self.assertEqual(candles[-1]["volume"], 1200.0)

    def test_fetch_quote_snapshots_returns_last_price(self) -> None:
        ib = FakeIB()
        snapshots = fetch_quote_snapshots(
            ib,
            {"SPY"},
            wait_seconds=0,
            stock_factory=FakeContract,
        )

        self.assertIn("SPY", snapshots)
        self.assertEqual(snapshots["SPY"].last_price, 102.5)
        self.assertEqual(len(ib.cancelled), 1)


    def test_fetch_quote_snapshots_falls_back_to_close_when_market_price_is_negative(self) -> None:
        class NegativePriceIB(FakeIB):
            def reqMktData(self, contract, *_args):
                self.last_market_data_contract = contract
                return FakeTicker(-1.0, close=101.8, bid=None, ask=None)

        ib = NegativePriceIB()
        snapshots = fetch_quote_snapshots(
            ib,
            {"SPY"},
            wait_seconds=0,
            stock_factory=FakeContract,
        )

        self.assertEqual(snapshots["SPY"].last_price, 101.8)

    def test_fetch_quote_snapshots_falls_back_to_bid_ask_mid_when_last_and_close_missing(self) -> None:
        class BidAskOnlyIB(FakeIB):
            def reqMktData(self, contract, *_args):
                self.last_market_data_contract = contract
                return FakeTicker(-1.0, close=float("nan"), bid=102.4, ask=102.6)

        ib = BidAskOnlyIB()
        snapshots = fetch_quote_snapshots(
            ib,
            {"SPY"},
            wait_seconds=0,
            stock_factory=FakeContract,
        )

        self.assertEqual(snapshots["SPY"].last_price, 102.5)




    def test_fetch_quote_snapshots_uses_ib_sleep_when_available(self) -> None:
        class DeferredTicker(FakeTicker):
            def __init__(self):
                super().__init__(-1.0, close=float("nan"), bid=None, ask=None)

        class SleepAwareIB(FakeIB):
            def __init__(self):
                super().__init__()
                self.tickers = []
                self.sleep_calls = []

            def reqMktData(self, contract, *_args):
                ticker = DeferredTicker()
                self.tickers.append(ticker)
                return ticker

            def sleep(self, seconds):
                self.sleep_calls.append(seconds)
                for ticker in self.tickers:
                    ticker.last = 101.8
                    ticker.close = 101.8
                    ticker.bid = 101.7
                    ticker.ask = 101.9

        ib = SleepAwareIB()
        snapshots = fetch_quote_snapshots(
            ib,
            {"SPY"},
            wait_seconds=0.1,
            retry_wait_seconds=0,
            attempts_per_data_type=1,
            stock_factory=FakeContract,
        )

        self.assertEqual(snapshots["SPY"].last_price, 101.8)
        self.assertEqual(ib.sleep_calls, [0.1])

    def test_fetch_quote_snapshots_retries_same_market_data_type_before_fallback(self) -> None:
        class RetrySameTypeIB(FakeIB):
            def __init__(self):
                super().__init__()
                self.market_data_type = 1
                self.market_data_type_calls = []
                self.market_data_attempts = {}

            def reqMarketDataType(self, market_data_type):
                self.market_data_type = market_data_type
                self.market_data_type_calls.append(market_data_type)

            def reqMktData(self, contract, *_args):
                self.last_market_data_contract = contract
                key = (self.market_data_type, contract.symbol)
                attempt = self.market_data_attempts.get(key, 0)
                self.market_data_attempts[key] = attempt + 1
                if self.market_data_type == 1 and attempt == 0:
                    return FakeTicker(-1.0, close=float("nan"), bid=None, ask=None)
                return FakeTicker(101.8, close=101.8, bid=101.7, ask=101.9)

        ib = RetrySameTypeIB()
        snapshots = fetch_quote_snapshots(
            ib,
            {"SPY"},
            wait_seconds=0,
            retry_wait_seconds=0,
            attempts_per_data_type=2,
            stock_factory=FakeContract,
        )

        self.assertEqual(snapshots["SPY"].last_price, 101.8)
        self.assertEqual(ib.market_data_attempts[(1, "SPY")], 2)
        self.assertNotIn(2, ib.market_data_type_calls)
        self.assertNotIn(4, ib.market_data_type_calls)

    def test_fetch_quote_snapshots_retries_with_market_data_fallbacks(self) -> None:
        class FallbackMarketDataIB(FakeIB):
            def __init__(self):
                super().__init__()
                self.market_data_type = 1
                self.market_data_type_calls = []

            def reqMarketDataType(self, market_data_type):
                self.market_data_type = market_data_type
                self.market_data_type_calls.append(market_data_type)

            def reqMktData(self, contract, *_args):
                self.last_market_data_contract = contract
                if self.market_data_type == 1:
                    return FakeTicker(-1.0, close=float("nan"), bid=None, ask=None)
                if self.market_data_type == 2:
                    return FakeTicker(-1.0, close=float("nan"), bid=None, ask=None)
                return FakeTicker(-1.0, close=101.8, bid=None, ask=None)

        ib = FallbackMarketDataIB()
        snapshots = fetch_quote_snapshots(
            ib,
            {"SPY"},
            wait_seconds=0,
            stock_factory=FakeContract,
        )

        self.assertEqual(snapshots["SPY"].last_price, 101.8)
        self.assertEqual(ib.market_data_type_calls, [1, 2, 4, 1])


if __name__ == "__main__":
    unittest.main()
