from __future__ import annotations

from types import SimpleNamespace
import unittest

from quant_platform_kit.ibkr.portfolio import fetch_portfolio_snapshot


class FakeIB:
    def __init__(self):
        self.req_positions_called = False

    def reqPositions(self):
        self.req_positions_called = True

    def positions(self):
        return [
            SimpleNamespace(
                account="U00000001",
                contract=SimpleNamespace(symbol="TQQQ"),
                position=3,
                avgCost=100.0,
            ),
            SimpleNamespace(
                account="U00000001",
                contract=SimpleNamespace(
                    symbol="TQQQ",
                    secType="OPT",
                    lastTradeDateOrContractMonth="20280121",
                    right="C",
                    strike=70.0,
                    localSymbol="TQQQ  280121C00070000",
                ),
                position=2,
                avgCost=3200.0,
            ),
            SimpleNamespace(
                account="U00000000",
                contract=SimpleNamespace(symbol="AAPL"),
                position=5,
                avgCost=200.0,
            ),
        ]

    def accountValues(self):
        return [
            SimpleNamespace(account="U00000001", tag="NetLiquidation", currency="USD", value="1000"),
            SimpleNamespace(account="U00000001", tag="AvailableFunds", currency="USD", value="250"),
            SimpleNamespace(account="U00000000", tag="NetLiquidation", currency="USD", value="2000"),
            SimpleNamespace(account="U00000000", tag="AvailableFunds", currency="USD", value="500"),
        ]


class IbkrPortfolioTests(unittest.TestCase):
    def test_fetch_portfolio_snapshot_filters_by_account_id(self) -> None:
        ib = FakeIB()

        snapshot = fetch_portfolio_snapshot(ib, account_ids=("U00000001",), wait_seconds=0)

        self.assertTrue(ib.req_positions_called)
        self.assertEqual(snapshot.total_equity, 1000.0)
        self.assertEqual(snapshot.buying_power, 250.0)
        self.assertEqual(tuple(position.symbol for position in snapshot.positions), ("TQQQ",))
        self.assertEqual(snapshot.positions[0].account_id, "U00000001")
        self.assertEqual(snapshot.metadata["account_ids"], ("U00000001",))
        self.assertEqual(snapshot.metadata["total_equity_source"], "broker_net_liquidation")
        self.assertEqual(len(snapshot.metadata["source_digest_sha256"]), 64)
        self.assertEqual(snapshot.metadata["option_positions"][0]["underlier"], "TQQQ")
        self.assertEqual(snapshot.metadata["option_positions"][0]["right"], "C")
        self.assertEqual(snapshot.metadata["option_positions"][0]["strike"], 70.0)

    def test_fetch_portfolio_snapshot_sums_selected_accounts(self) -> None:
        snapshot = fetch_portfolio_snapshot(
            FakeIB(),
            account_ids=("U00000001", "U00000000"),
            wait_seconds=0,
        )

        self.assertEqual(snapshot.total_equity, 3000.0)
        self.assertEqual(snapshot.buying_power, 750.0)
        self.assertEqual(snapshot.metadata["total_equity_source"], "broker_net_liquidation")

    def test_snapshot_without_explicit_account_scope_has_no_strict_capital_evidence(self) -> None:
        snapshot = fetch_portfolio_snapshot(FakeIB(), wait_seconds=0)

        self.assertEqual(snapshot.total_equity, 3000.0)
        self.assertEqual(snapshot.metadata["total_equity_source"], "unverified_net_liquidation")
        self.assertNotIn("source_digest_sha256", snapshot.metadata)
        self.assertEqual(tuple(position.symbol for position in snapshot.positions), ("TQQQ", "AAPL"))
        self.assertEqual(len(snapshot.metadata["option_positions"]), 1)


if __name__ == "__main__":
    unittest.main()
