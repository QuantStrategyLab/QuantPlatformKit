from __future__ import annotations

from dataclasses import dataclass
import unittest

from quant_platform_kit.ibkr.portfolio import fetch_portfolio_snapshot


@dataclass
class FakeContract:
    symbol: str


@dataclass
class FakePosition:
    contract: FakeContract
    position: int
    avgCost: float


@dataclass
class FakeAccountValue:
    tag: str
    currency: str
    value: str


class FakeIB:
    def reqPositions(self):
        self.positions_requested = True

    def positions(self):
        return [
            FakePosition(contract=FakeContract("SPY"), position=10, avgCost=99.0),
            FakePosition(contract=FakeContract("AGG"), position=0, avgCost=100.0),
        ]

    def accountValues(self):
        return [
            FakeAccountValue(tag="NetLiquidation", currency="USD", value="100000"),
            FakeAccountValue(tag="AvailableFunds", currency="USD", value="25000"),
        ]


class IbkrPortfolioTests(unittest.TestCase):
    def test_fetch_portfolio_snapshot_returns_equity_and_positions(self) -> None:
        snapshot = fetch_portfolio_snapshot(FakeIB(), wait_seconds=0)

        self.assertEqual(snapshot.total_equity, 100000.0)
        self.assertEqual(snapshot.buying_power, 25000.0)
        self.assertEqual(len(snapshot.positions), 1)
        self.assertEqual(snapshot.positions[0].symbol, "SPY")
        self.assertEqual(snapshot.positions[0].market_value, 990.0)


if __name__ == "__main__":
    unittest.main()
