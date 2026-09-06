from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from quant_platform_kit.risk.engine import RiskEngine
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
    def _install_fake_schwab_module(self):
        schwab_module = types.ModuleType("schwab")
        client_module = types.ModuleType("schwab.client")
        client_module.Client = types.SimpleNamespace(
            Account=types.SimpleNamespace(
                Fields=types.SimpleNamespace(POSITIONS="POSITIONS")
            )
        )
        return patch.dict(sys.modules, {"schwab": schwab_module, "schwab.client": client_module})

    def _snapshot_with_balances(self, balances):
        payload = FakeClient().get_account("abc123", "POSITIONS").json()
        payload["securitiesAccount"]["currentBalances"] = balances
        with self._install_fake_schwab_module(), patch.object(
            FakeClient, "get_account", return_value=FakeResponse(payload)
        ):
            return fetch_account_snapshot(FakeClient(), strategy_symbols=("TQQQ",))

    def test_cash_available_for_trading_is_required(self) -> None:
        with self.assertRaises(ValueError) as raised:
            self._snapshot_with_balances({"liquidationValue": 2_500.0})
        self.assertEqual("Invalid Schwab balance: cashAvailableForTrading", str(raised.exception))

    def test_explicit_invalid_balances_are_rejected_without_exposing_values(self) -> None:
        invalid_values = {
            "null": None,
            "true": True,
            "false": False,
            "text": "synthetic-invalid-balance",
            "mapping": {},
            "list": [],
            "nan": float("nan"),
            "positive_infinity": float("inf"),
            "negative_infinity": float("-inf"),
            "text_overflow": "1e1000",
            "integer_overflow": 10**400,
        }
        for field in ("cashAvailableForTrading", "cashAvailableForWithdrawal", "liquidationValue"):
            for case, value in invalid_values.items():
                with self.subTest(field=field, case=case):
                    balances = {
                        "cashAvailableForTrading": 1000.0,
                        "cashAvailableForWithdrawal": 800.0,
                        "liquidationValue": 2_500.0,
                    }
                    balances[field] = value
                    with self.assertRaises(ValueError) as raised:
                        self._snapshot_with_balances(balances)
                    self.assertEqual(f"Invalid Schwab balance: {field}", str(raised.exception))
                    self.assertIsNone(raised.exception.__cause__)

    def test_missing_withdrawable_balance_remains_unknown(self) -> None:
        snapshot = self._snapshot_with_balances({"cashAvailableForTrading": 1000.0})
        self.assertIsNone(snapshot.metadata["cash_available_for_withdrawal"])
        self.assertEqual(1210.0, snapshot.total_equity)

    def test_zero_and_negative_balances_remain_observed_facts(self) -> None:
        for value in (0.0, -250.0):
            with self.subTest(value=value):
                snapshot = self._snapshot_with_balances(
                    {
                        "cashAvailableForTrading": value,
                        "cashAvailableForWithdrawal": value,
                        "liquidationValue": value,
                    }
                )
                self.assertEqual(value, snapshot.cash_balance)
                self.assertEqual(value, snapshot.metadata["cash_available_for_trading"])
                self.assertEqual(value, snapshot.metadata["cash_available_for_withdrawal"])
                self.assertEqual(value, snapshot.total_equity)
                self.assertEqual("broker_liquidation_value", snapshot.metadata["total_equity_source"])
                self.assertEqual(0.0, snapshot.buying_power)
                self.assertEqual(("TQQQ",), tuple(position.symbol for position in snapshot.positions))

    def test_missing_liquidation_preserves_legacy_fallback_with_negative_cash(self) -> None:
        snapshot = self._snapshot_with_balances({"cashAvailableForTrading": -250.0})
        self.assertEqual(-250.0, snapshot.cash_balance)
        self.assertEqual(-40.0, snapshot.total_equity)
        self.assertEqual(0.0, snapshot.buying_power)
        self.assertEqual("cash_available_plus_all_position_market_values", snapshot.metadata["total_equity_source"])

    def test_nonpositive_liquidation_reaches_real_risk_rejection(self) -> None:
        for liquidation_value in (0.0, -250.0):
            with self.subTest(liquidation_value=liquidation_value):
                snapshot = self._snapshot_with_balances(
                    {"cashAvailableForTrading": 1000.0, "liquidationValue": liquidation_value}
                )
                self.assertEqual(liquidation_value, snapshot.total_equity)
                assessment = RiskEngine().assess({}, snapshot)
                self.assertEqual("reject", assessment.action)
                self.assertEqual("invalid_portfolio_snapshot", assessment.reason)
                self.assertEqual(0.0, assessment.budget_scalar)
                self.assertEqual(0.0, assessment.leverage_scalar)
                self.assertEqual(0.0, assessment.risk_asset_scalar)

    def test_finite_numeric_strings_remain_compatible(self) -> None:
        snapshot = self._snapshot_with_balances(
            {"cashAvailableForTrading": "1000", "cashAvailableForWithdrawal": "800", "liquidationValue": "2500"}
        )
        self.assertEqual(1000.0, snapshot.cash_balance)
        self.assertEqual(800.0, snapshot.metadata["cash_available_for_withdrawal"])
        self.assertEqual(2500.0, snapshot.total_equity)

    def test_fetch_account_snapshot_filters_to_strategy_symbols(self) -> None:
        with self._install_fake_schwab_module():
            snapshot = fetch_account_snapshot(FakeClient(), strategy_symbols=("TQQQ", "BOXX"))

        self.assertEqual(snapshot.metadata["account_hash"], "abc123")
        self.assertEqual(snapshot.total_equity, 1210.0)
        self.assertEqual(snapshot.buying_power, 1000.0)
        self.assertEqual(snapshot.cash_balance, 1000.0)
        self.assertEqual(snapshot.metadata["cash_available_for_trading"], 1000.0)
        self.assertEqual(snapshot.metadata["cash_available_for_withdrawal"], 800.0)
        self.assertEqual(
            snapshot.metadata["total_equity_source"],
            "cash_available_plus_all_position_market_values",
        )
        self.assertRegex(snapshot.metadata["source_digest_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(len(snapshot.positions), 1)
        self.assertEqual(snapshot.positions[0].symbol, "TQQQ")

    def test_fetch_account_snapshot_requires_selection_for_multiple_accounts(self) -> None:
        class MultiAccountClient(FakeClient):
            def get_account_numbers(self):
                return FakeResponse([{"hashValue": "abc123"}, {"hashValue": "def456"}])

        with self._install_fake_schwab_module(), self.assertRaisesRegex(
            ValueError, "explicit account hash"
        ):
            fetch_account_snapshot(MultiAccountClient(), strategy_symbols=("TQQQ",))

    def test_fetch_account_snapshot_uses_explicit_account_selection(self) -> None:
        class MultiAccountClient(FakeClient):
            def get_account_numbers(self):
                return FakeResponse([{"hashValue": "abc123"}, {"hashValue": "def456"}])

        api_client = MultiAccountClient()
        with self._install_fake_schwab_module():
            snapshot = fetch_account_snapshot(
                api_client,
                strategy_symbols=("TQQQ",),
                expected_account_hash="def456",
            )

        self.assertEqual(snapshot.metadata["account_hash"], "def456")
        self.assertEqual(api_client.args[0], "def456")

    def test_fetch_account_snapshot_prefers_broker_liquidation_value(self) -> None:
        class LiquidationValueClient(FakeClient):
            def get_account(self, account_hash, fields):
                payload = super().get_account(account_hash, fields).json()
                payload["securitiesAccount"]["currentBalances"]["liquidationValue"] = 2_500.0
                return FakeResponse(payload)

        with self._install_fake_schwab_module():
            snapshot = fetch_account_snapshot(
                LiquidationValueClient(), strategy_symbols=("TQQQ",)
            )

        self.assertEqual(snapshot.total_equity, 2_500.0)
        self.assertEqual(snapshot.metadata["total_equity_source"], "broker_liquidation_value")

    def test_fetch_account_snapshot_retries_account_numbers_server_error(self) -> None:
        class FlakyAccountNumbersClient(FakeClient):
            def __init__(self):
                self.account_number_calls = 0

            def get_account_numbers(self):
                self.account_number_calls += 1
                if self.account_number_calls == 1:
                    return FakeResponse({"error": "unavailable"}, status_code=503)
                return super().get_account_numbers()

        api_client = FlakyAccountNumbersClient()
        with self._install_fake_schwab_module(), patch(
            "quant_platform_kit.schwab.market_data.time.sleep"
        ) as sleep_mock:
            snapshot = fetch_account_snapshot(api_client, strategy_symbols=("TQQQ",))

        self.assertEqual(snapshot.metadata["account_hash"], "abc123")
        self.assertEqual(api_client.account_number_calls, 2)
        sleep_mock.assert_called_once_with(1.0)

    def test_fetch_account_snapshot_retries_account_positions_server_error(self) -> None:
        class FlakyAccountPositionsClient(FakeClient):
            def __init__(self):
                self.account_calls = 0

            def get_account(self, account_hash, fields):
                self.account_calls += 1
                if self.account_calls == 1:
                    return FakeResponse({"error": "unavailable"}, status_code=503)
                return super().get_account(account_hash, fields)

        api_client = FlakyAccountPositionsClient()
        with self._install_fake_schwab_module(), patch(
            "quant_platform_kit.schwab.market_data.time.sleep"
        ) as sleep_mock:
            snapshot = fetch_account_snapshot(api_client, strategy_symbols=("TQQQ",))

        self.assertEqual(snapshot.metadata["account_hash"], "abc123")
        self.assertEqual(api_client.account_calls, 2)
        sleep_mock.assert_called_once_with(1.0)


if __name__ == "__main__":
    unittest.main()
