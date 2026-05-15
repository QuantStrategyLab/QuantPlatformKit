from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from quant_platform_kit.schwab.portfolio import fetch_account_snapshot


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload


class FakeClient:
    def get_account_numbers(self):
        return FakeResponse([{"hashValue": "abc123"}])

    def get_account(self, account_hash, fields):
        self.args = (account_hash, fields)
        return FakeResponse(
            {
                "securitiesAccount": {
                        "currentBalances": {
                            "cashAvailableForTrading": 1000.0,
                            "cashAvailableForWithdrawal": 800.0,
                        },
                    "positions": [
                        {
                            "instrument": {"symbol": "TQQQ"},
                            "longQuantity": 5,
                            "marketValue": 200.0,
                        },
                        {
                            "instrument": {"symbol": "XYZ"},
                            "longQuantity": 1,
                            "marketValue": 10.0,
                        },
                    ],
                }
            }
        )


class SchwabPortfolioTests(unittest.TestCase):
    def test_fetch_account_snapshot_filters_to_strategy_symbols(self) -> None:
        schwab_module = types.ModuleType("schwab")
        client_module = types.ModuleType("schwab.client")
        client_module.Client = types.SimpleNamespace(
            Account=types.SimpleNamespace(
                Fields=types.SimpleNamespace(POSITIONS="POSITIONS")
            )
        )

        with patch.dict(sys.modules, {"schwab": schwab_module, "schwab.client": client_module}):
            snapshot = fetch_account_snapshot(FakeClient(), strategy_symbols=("TQQQ", "BOXX"))

        self.assertEqual(snapshot.metadata["account_hash"], "abc123")
        self.assertEqual(snapshot.total_equity, 1200.0)
        self.assertEqual(snapshot.buying_power, 1000.0)
        self.assertEqual(snapshot.cash_balance, 1000.0)
        self.assertEqual(snapshot.metadata["cash_available_for_trading"], 1000.0)
        self.assertEqual(snapshot.metadata["cash_available_for_withdrawal"], 800.0)
        self.assertEqual(len(snapshot.positions), 1)
        self.assertEqual(snapshot.positions[0].symbol, "TQQQ")


if __name__ == "__main__":
    unittest.main()
