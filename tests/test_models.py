from __future__ import annotations

from datetime import datetime, timezone
import unittest

from quant_platform_kit.common.models import OrderIntent, PricePoint, PriceSeries, StrategyDecision


class ModelsTests(unittest.TestCase):
    def test_price_series_latest_returns_last_point(self) -> None:
        points = (
            PricePoint(as_of=datetime(2026, 3, 1, tzinfo=timezone.utc), close=100.0),
            PricePoint(as_of=datetime(2026, 3, 2, tzinfo=timezone.utc), close=101.5),
        )
        series = PriceSeries(symbol="SPY", currency="USD", points=points)

        self.assertEqual(series.latest.close, 101.5)

    def test_price_series_latest_rejects_empty_series(self) -> None:
        series = PriceSeries(symbol="SPY", currency="USD", points=())

        with self.assertRaises(ValueError):
            _ = series.latest

    def test_strategy_decision_keeps_order_intents(self) -> None:
        order = OrderIntent(symbol="SPY", side="buy", quantity=10)
        decision = StrategyDecision(
            as_of_date=datetime(2026, 3, 29, tzinfo=timezone.utc).date(),
            summary="rotate into SPY",
            target_weights={"SPY": 1.0},
            order_intents=(order,),
        )

        self.assertEqual(decision.order_intents[0].symbol, "SPY")
        self.assertEqual(decision.target_weights["SPY"], 1.0)
