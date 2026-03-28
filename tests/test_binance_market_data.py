import unittest
from datetime import datetime, timedelta, timezone

from quant_platform_kit.binance.market_data import fetch_btc_market_snapshot, fetch_daily_indicators


def _make_kline(ts_ms, close):
    return [
        ts_ms,
        str(close),
        str(close * 1.01),
        str(close * 0.99),
        str(close),
        "1000",
    ]


class FakeClient:
    def __init__(self, klines):
        self.klines = klines

    def get_historical_klines(self, symbol, interval, lookback):
        return list(self.klines)


class BinanceMarketDataTests(unittest.TestCase):
    def test_fetch_daily_indicators_returns_snapshot(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        klines = []
        for day in range(420):
            close = 100 + day
            klines.append(_make_kline(int((start + timedelta(days=day)).timestamp() * 1000), close))

        indicators = fetch_daily_indicators(FakeClient(klines), "ETHUSDT")

        self.assertIsNotNone(indicators)
        self.assertIn("close", indicators)
        self.assertIn("sma200", indicators)
        self.assertIn("avg_quote_vol_180", indicators)

    def test_fetch_btc_market_snapshot_returns_none_when_not_enough_history(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        klines = [_make_kline(int((start + timedelta(days=day)).timestamp() * 1000), 50000 + day) for day in range(100)]
        self.assertIsNone(fetch_btc_market_snapshot(FakeClient(klines), 60000.0))

    def test_fetch_btc_market_snapshot_returns_regime_snapshot(self):
        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        klines = [_make_kline(int((start + timedelta(days=day)).timestamp() * 1000), 30000 + day * 50) for day in range(700)]

        snapshot = fetch_btc_market_snapshot(FakeClient(klines), 70000.0)

        self.assertIsNotNone(snapshot)
        self.assertIn("ma200", snapshot)
        self.assertIn("ahr999", snapshot)
        self.assertIn("regime_on", snapshot)


if __name__ == "__main__":
    unittest.main()
