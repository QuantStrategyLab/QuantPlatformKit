from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from quant_platform_kit.ibkr.market_data import (
    StrictAdjustedHistoryError,
    StrictAdjustedHistoryRequestOutcome,
    fetch_strict_adjusted_historical_price_candles,
    fetch_historical_price_candles,
    fetch_historical_price_series,
    fetch_option_chain_snapshot,
    fetch_quote_snapshots,
)


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
    @staticmethod
    def _strict_ib(*, bars=None, error: Exception | None = None):
        class StrictIB(FakeIB):
            def __init__(self):
                super().__init__()
                self.history_calls = []
                self.market_data_type_calls = []

            def qualifyContracts(self, contract):
                self.qualified.append(contract)
                return [contract]

            def reqMarketDataType(self, market_data_type):
                self.market_data_type_calls.append(market_data_type)

            def reqHistoricalData(self, contract, **kwargs):
                self.history_calls.append(kwargs)
                if error is not None:
                    raise error
                return bars

        return StrictIB()

    @staticmethod
    def _strict_requester(
        *,
        bars,
        completion_observed: bool,
        provider_error_codes: tuple[int, ...] = (),
    ):
        def requester(_contract, **_kwargs):
            return StrictAdjustedHistoryRequestOutcome(
                bars=bars,
                completion_observed=completion_observed,
                provider_error_codes=provider_error_codes,
            )

        return requester

    def test_strict_adjusted_history_uses_one_exact_request_and_sanitized_provenance(
        self,
    ) -> None:
        bars = [
            FakeBar(date=date(2026, 8, 3), open=100.0, high=101.0, low=99.5, close=100.5, volume=1000.0),
            FakeBar(date=date(2026, 8, 4), open=100.5, high=101.5, low=100.0, close=101.0, volume=1200.0),
        ]
        ib = self._strict_ib(bars=bars)
        cutoff = datetime(2026, 8, 5, 3, 59, 59, tzinfo=timezone.utc)

        result = fetch_strict_adjusted_historical_price_candles(
            ib,
            "SOXL",
            end_datetime=cutoff,
            duration="9 Y",
            expected_sessions=(date(2026, 8, 3), date(2026, 8, 4)),
            stock_factory=FakeContract,
        )

        self.assertEqual(len(ib.history_calls), 1)
        self.assertEqual(
            ib.history_calls[0],
            {
                "endDateTime": cutoff,
                "durationStr": "9 Y",
                "barSizeSetting": "1 day",
                "whatToShow": "ADJUSTED_LAST",
                "useRTH": True,
                "formatDate": 1,
                "keepUpToDate": False,
            },
        )
        self.assertEqual(ib.market_data_type_calls, [])
        self.assertEqual(result.candles[-1].close, 101.0)
        self.assertEqual(result.provenance.symbol, "SOXL")
        self.assertEqual(result.provenance.end_datetime, "2026-08-05T03:59:59Z")
        self.assertEqual(result.provenance.what_to_show, "ADJUSTED_LAST")
        self.assertEqual(result.provenance.returned_row_count, 2)
        self.assertFalse(hasattr(result.provenance, "candles"))
        self.assertEqual(result.diagnostic.to_dict()["classification"], "exact_match")

    def test_strict_adjusted_history_diagnostic_classifies_sanitized_session_failures(
        self,
    ) -> None:
        cutoff = datetime(2026, 8, 5, 3, 59, 59, tzinfo=timezone.utc)
        expected = (date(2026, 8, 1), date(2026, 8, 2))
        valid = FakeBar(
            date=expected[0],
            open=100.0,
            high=101.0,
            low=99.5,
            close=100.5,
            volume=1000.0,
        )
        extra = FakeBar(
            date=date(2026, 8, 3),
            open=101.0,
            high=102.0,
            low=100.5,
            close=101.5,
            volume=900.0,
        )
        cases = (
            ("missing", [valid], {"missing_count": 1, "extra_count": 0, "duplicate_count": 0}),
            ("extra", [valid, FakeBar(**{**extra.__dict__, "date": expected[1]}), extra], {"missing_count": 0, "extra_count": 1, "duplicate_count": 0}),
            ("duplicate", [valid, valid], {"missing_count": 1, "extra_count": 0, "duplicate_count": 1}),
        )

        for name, bars, expected_counts in cases:
            with self.subTest(name=name):
                with self.assertRaises(StrictAdjustedHistoryError) as caught:
                    fetch_strict_adjusted_historical_price_candles(
                        self._strict_ib(bars=[]),
                        "SOXL",
                        end_datetime=cutoff,
                        duration="9 Y",
                        expected_sessions=expected,
                        stock_factory=FakeContract,
                        requester=self._strict_requester(
                            bars=bars,
                            completion_observed=True,
                        ),
                    )

                diagnostic = caught.exception.diagnostic.to_dict()
                self.assertEqual(diagnostic["classification"], "session_contract_mismatch")
                for key, value in expected_counts.items():
                    self.assertEqual(diagnostic["counts"][key], value)
                self.assertEqual(set(diagnostic["commitments"]), {
                    "algorithm",
                    "canonicalization",
                    "missing_sessions_sha256",
                    "extra_sessions_sha256",
                    "duplicate_sessions_sha256",
                })
                serialized = repr(diagnostic)
                for forbidden in ("2026-08-01", "2026-08-02", "2026-08-03", "close", "100.5", "secret"):
                    self.assertNotIn(forbidden, serialized)

    def test_strict_adjusted_history_diagnostic_precedence_is_fail_closed(self) -> None:
        cutoff = datetime(2026, 8, 5, 3, 59, 59, tzinfo=timezone.utc)
        expected = (date(2026, 8, 1), date(2026, 8, 2))
        bar = FakeBar(
            date=expected[0],
            open=100.0,
            high=101.0,
            low=99.5,
            close=100.5,
            volume=1000.0,
        )
        cases = (
            ("provider_error", [bar], False, (10089, 10089, 321)),
            ("completion_not_observed", [bar], False, ()),
            ("empty_response", [], True, ()),
        )

        for classification, bars, completion_observed, provider_error_codes in cases:
            with self.subTest(classification=classification):
                with self.assertRaises(StrictAdjustedHistoryError) as caught:
                    fetch_strict_adjusted_historical_price_candles(
                        self._strict_ib(bars=[]),
                        "SOXL",
                        end_datetime=cutoff,
                        duration="9 Y",
                        expected_sessions=expected,
                        stock_factory=FakeContract,
                        requester=self._strict_requester(
                            bars=bars,
                            completion_observed=completion_observed,
                            provider_error_codes=provider_error_codes,
                        ),
                    )

                diagnostic = caught.exception.diagnostic.to_dict()
                self.assertEqual(diagnostic["classification"], classification)
                self.assertEqual(
                    diagnostic["provider_error_code_counts"],
                    {"321": 1, "10089": 2} if provider_error_codes else {},
                )
                self.assertNotIn("provider failure", repr(diagnostic))

    def test_strict_adjusted_history_never_falls_back_on_empty_or_error(self) -> None:
        cutoff = datetime(2026, 8, 5, 3, 59, 59, tzinfo=timezone.utc)
        cases = (
            self._strict_ib(bars=[]),
            self._strict_ib(error=RuntimeError("provider failure")),
        )

        for ib in cases:
            with self.subTest(error=bool(getattr(ib, "history_calls", None))):
                with self.assertRaises(StrictAdjustedHistoryError):
                    fetch_strict_adjusted_historical_price_candles(
                        ib,
                        "SOXL",
                        end_datetime=cutoff,
                        duration="9 Y",
                        expected_sessions=(date(2026, 8, 4),),
                        stock_factory=FakeContract,
                    )

                self.assertEqual(len(ib.history_calls), 1)
                self.assertEqual(
                    [call["whatToShow"] for call in ib.history_calls],
                    ["ADJUSTED_LAST"],
                )
                self.assertEqual(ib.market_data_type_calls, [])

    def test_strict_adjusted_history_rejects_missing_or_duplicate_sessions(self) -> None:
        cutoff = datetime(2026, 8, 5, 3, 59, 59, tzinfo=timezone.utc)
        valid_bar = FakeBar(
            date=date(2026, 8, 4),
            open=100.0,
            high=101.0,
            low=99.5,
            close=100.5,
            volume=1000.0,
        )
        cases = (
            [valid_bar],
            [valid_bar, valid_bar],
        )

        for bars in cases:
            ib = self._strict_ib(bars=bars)
            with self.subTest(row_count=len(bars)):
                with self.assertRaises(StrictAdjustedHistoryError):
                    fetch_strict_adjusted_historical_price_candles(
                        ib,
                        "SOXL",
                        end_datetime=cutoff,
                        duration="9 Y",
                        expected_sessions=(date(2026, 8, 3), date(2026, 8, 4)),
                        stock_factory=FakeContract,
                    )

                self.assertEqual(len(ib.history_calls), 1)

    def test_strict_adjusted_history_rejects_invalid_fields_without_provider_fallback(
        self,
    ) -> None:
        ib = self._strict_ib(
            bars=[
                SimpleNamespace(
                    date=date(2026, 8, 4),
                    open=100.0,
                    high=101.0,
                    low=99.5,
                    close=float("nan"),
                )
            ]
        )

        with self.assertRaises(StrictAdjustedHistoryError):
            fetch_strict_adjusted_historical_price_candles(
                ib,
                "SOXL",
                end_datetime=datetime(2026, 8, 5, 3, 59, 59, tzinfo=timezone.utc),
                duration="9 Y",
                expected_sessions=(date(2026, 8, 4),),
                stock_factory=FakeContract,
            )

        self.assertEqual(len(ib.history_calls), 1)

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
                if self.market_data_type == 3 and attempt == 0:
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
        self.assertEqual(ib.market_data_attempts[(3, "SPY")], 2)
        self.assertEqual(ib.market_data_type_calls, [3, 1])
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
                if self.market_data_type == 3:
                    return FakeTicker(-1.0, close=float("nan"), bid=None, ask=None)
                if self.market_data_type == 4:
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
        self.assertEqual(ib.market_data_type_calls, [3, 4, 1, 1])

    def test_fetch_option_chain_snapshot_returns_bounded_contract_rows(self) -> None:
        class FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 7, 30, tzinfo=timezone.utc)

        class OptionChainIB(FakeIB):
            def qualifyContracts(self, contract):
                self.qualified.append(contract)
                if not hasattr(contract, "right"):
                    contract.conId = 12345
                return [contract]

            def reqSecDefOptParams(self, symbol, fut_fop_exchange, sec_type, con_id):
                self.option_params_request = (symbol, fut_fop_exchange, sec_type, con_id)
                return [
                    SimpleNamespace(
                        exchange="SMART",
                        expirations={"20280121"},
                        strikes={50.0, 70.0, 90.0, 150.0},
                    )
                ]

            def reqMktData(self, contract, *_args):
                if hasattr(contract, "right"):
                    ticker = FakeTicker(-1.0, close=float("nan"), bid=29.0, ask=31.0)
                    ticker.modelGreeks = SimpleNamespace(delta=0.74)
                    return ticker
                return FakeTicker(102.5, close=101.8, bid=102.4, ask=102.6)

        ib = OptionChainIB()
        with patch("quant_platform_kit.ibkr.market_data.datetime", FrozenDateTime):
            snapshot = fetch_option_chain_snapshot(
                ib,
                "TQQQ",
                rights=("C",),
                min_dte=540,
                max_dte=930,
                target_dte=730,
                wait_seconds=0,
                stock_factory=FakeContract,
                option_factory=FakeOptionContract,
            )

        self.assertEqual(snapshot["underlier"], "TQQQ")
        self.assertEqual(snapshot["spot"], 102.5)
        self.assertEqual(snapshot["contracts"][0]["right"], "C")
        self.assertEqual(snapshot["contracts"][0]["delta"], 0.74)
        self.assertEqual(snapshot["contracts"][0]["mid"], 30.0)
        self.assertEqual(ib.option_params_request, ("TQQQ", "", "STK", 12345))


if __name__ == "__main__":
    unittest.main()
