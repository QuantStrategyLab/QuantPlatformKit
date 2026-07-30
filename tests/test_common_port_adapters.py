from __future__ import annotations

from datetime import datetime, timezone
import unittest

from quant_platform_kit.common.models import PricePoint, PriceSeries, QuoteSnapshot
from quant_platform_kit.common.port_adapters import CallableMarketDataPort, CallableNotificationPort


class CallableMarketDataPortTests(unittest.TestCase):
    def test_get_quote_delegates_to_loader(self) -> None:
        port = CallableMarketDataPort(
            quote_loader=lambda symbol: QuoteSnapshot(
                symbol=symbol,
                as_of=datetime(2026, 4, 21, tzinfo=timezone.utc),
                last_price=123.45,
            )
        )

        snapshot = port.get_quote("SOXL")

        self.assertEqual(snapshot.symbol, "SOXL")
        self.assertEqual(snapshot.last_price, 123.45)

    def test_get_price_series_delegates_when_loader_is_available(self) -> None:
        expected = PriceSeries(
            symbol="SOXX",
            currency="USD",
            points=(
                PricePoint(
                    as_of=datetime(2026, 4, 21, tzinfo=timezone.utc),
                    close=200.0,
                ),
            ),
        )
        port = CallableMarketDataPort(
            quote_loader=lambda symbol: QuoteSnapshot(
                symbol=symbol,
                as_of=datetime(2026, 4, 21, tzinfo=timezone.utc),
                last_price=123.45,
            ),
            price_series_loader=lambda symbol: expected,
        )

        series = port.get_price_series("SOXX")

        self.assertEqual(series, expected)

    def test_get_price_series_raises_when_not_configured(self) -> None:
        port = CallableMarketDataPort(
            quote_loader=lambda symbol: QuoteSnapshot(
                symbol=symbol,
                as_of=datetime(2026, 4, 21, tzinfo=timezone.utc),
                last_price=123.45,
            )
        )

        with self.assertRaises(NotImplementedError):
            port.get_price_series("SOXL")


class CallableNotificationPortTests(unittest.TestCase):
    def test_send_text_propagates_delivery_result(self) -> None:
        port = CallableNotificationPort(lambda _message: False)

        self.assertIs(port.send_text("rebalance"), False)


if __name__ == "__main__":
    unittest.main()
