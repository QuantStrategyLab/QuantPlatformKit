from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from quant_platform_kit.risk.engine import RiskEngine
from quant_platform_kit.schwab.portfolio import _optional_decimal_text, fetch_account_snapshot


_MISSING = object()


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

    def _snapshot_with_balances(self, balances, *, account_type=_MISSING, cash_balance=_MISSING):
        payload = FakeClient().get_account("abc123", "POSITIONS").json()
        payload["securitiesAccount"]["currentBalances"] = balances
        if account_type is not _MISSING:
            payload["securitiesAccount"]["type"] = account_type
        if cash_balance is not _MISSING:
            payload["securitiesAccount"]["currentBalances"]["cashBalance"] = cash_balance
        with self._install_fake_schwab_module(), patch.object(
            FakeClient, "get_account", return_value=FakeResponse(payload)
        ):
            return fetch_account_snapshot(FakeClient(), strategy_symbols=("TQQQ",))

    def test_optional_native_facts_come_from_the_same_account_response(self) -> None:
        class CountingClient(FakeClient):
            def __init__(self):
                self.account_number_calls = 0
                self.account_calls = 0

            def get_account_numbers(self):
                self.account_number_calls += 1
                return super().get_account_numbers()

            def get_account(self, account_hash, fields):
                self.account_calls += 1
                payload = super().get_account(account_hash, fields).json()
                payload["securitiesAccount"]["type"] = "MARGIN_UNKNOWN"
                payload["securitiesAccount"]["currentBalances"].update(
                    {"cashBalance": "1234.5600", "buyingPower": 5000.0}
                )
                return FakeResponse(payload)

        api_client = CountingClient()
        with self._install_fake_schwab_module():
            snapshot = fetch_account_snapshot(api_client, strategy_symbols=("TQQQ",))

        self.assertEqual((1, 1), (api_client.account_number_calls, api_client.account_calls))
        self.assertEqual("MARGIN_UNKNOWN", snapshot.metadata["broker_account_type"])
        self.assertEqual("securitiesAccount.type", snapshot.metadata["broker_account_type_source"])
        self.assertEqual("1234.5600", snapshot.metadata["broker_cash_balance"])
        self.assertEqual("cashBalance", snapshot.metadata["broker_cash_balance_source"])
        self.assertEqual(1000.0, snapshot.cash_balance)
        self.assertEqual(5000.0, snapshot.buying_power)
        self.assertEqual(1210.0, snapshot.total_equity)
        self.assertEqual(("TQQQ",), tuple(position.symbol for position in snapshot.positions))

    def test_raw_broker_account_type_is_preserved_only_as_a_bounded_token(self) -> None:
        for raw, expected in (
            ("CASH", "CASH"),
            ("MARGIN", "MARGIN"),
            ("PROVIDER_UNKNOWN", "PROVIDER_UNKNOWN"),
            (None, None),
            ("", None),
            ("contains space", None),
            ("type-1", None),
            ("é", None),
            ("X" * 33, None),
            (42, None),
            (True, None),
        ):
            with self.subTest(raw=raw):
                snapshot = self._snapshot_with_balances(
                    {"cashAvailableForTrading": 1000.0}, account_type=raw
                )
                if expected is None:
                    self.assertNotIn("broker_account_type", snapshot.metadata)
                    self.assertNotIn("broker_account_type_source", snapshot.metadata)
                else:
                    self.assertEqual(expected, snapshot.metadata["broker_account_type"])
                    self.assertEqual(
                        "securitiesAccount.type",
                        snapshot.metadata["broker_account_type_source"],
                    )

    def test_native_cash_balance_is_canonical_decimal_text_without_fallback(self) -> None:
        for raw, expected in (
            ("123.4500", "123.4500"),
            (123, "123"),
            (12.5, "12.5"),
            (0, "0"),
            ("-25.125", "-25.125"),
        ):
            with self.subTest(raw=raw):
                snapshot = self._snapshot_with_balances(
                    {"cashAvailableForTrading": 1000.0}, cash_balance=raw
                )
                self.assertEqual(expected, snapshot.metadata["broker_cash_balance"])
                self.assertEqual("cashBalance", snapshot.metadata["broker_cash_balance_source"])
                self.assertEqual(1000.0, snapshot.cash_balance)
                self.assertEqual(1000.0, snapshot.buying_power)

        for raw in (None, True, False, "NaN", "Infinity", "-Infinity", "bad", {}, []):
            with self.subTest(invalid_raw=repr(raw)):
                snapshot = self._snapshot_with_balances(
                    {"cashAvailableForTrading": 1000.0}, cash_balance=raw
                )
                self.assertNotIn("broker_cash_balance", snapshot.metadata)
                self.assertNotIn("broker_cash_balance_source", snapshot.metadata)

        for raw in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(non_finite_number=repr(raw)):
                self.assertIsNone(_optional_decimal_text(raw))

        missing = self._snapshot_with_balances({"cashAvailableForTrading": 1000.0})
        self.assertNotIn("broker_cash_balance", missing.metadata)
        self.assertNotIn("broker_cash_balance_source", missing.metadata)

    def test_cash_balance_formatting_is_bounded_before_fixed_point_expansion(self) -> None:
        for raw in ("1e1000", "1e-1000", "1e999999999", "1e-999999999", "9" * 129):
            with self.subTest(raw_prefix=raw[:20], raw_length=len(raw)):
                self.assertIsNone(_optional_decimal_text(raw))
                snapshot = self._snapshot_with_balances(
                    {"cashAvailableForTrading": 1000.0}, cash_balance=raw
                )
                self.assertNotIn("broker_cash_balance", snapshot.metadata)
                self.assertNotIn("broker_cash_balance_source", snapshot.metadata)
                self.assertEqual(1000.0, snapshot.cash_balance)
                self.assertEqual(1000.0, snapshot.buying_power)
                self.assertEqual(1210.0, snapshot.total_equity)

        self.assertEqual("125", _optional_decimal_text("1.25e2"))
        self.assertEqual("0.0125", _optional_decimal_text("1.25e-2"))
        self.assertEqual("0", _optional_decimal_text("0"))
        self.assertEqual("-1.25", _optional_decimal_text("-1.25"))
        self.assertEqual(
            "123456789012345.12345678",
            _optional_decimal_text("123456789012345.12345678"),
        )
        self.assertIsNone(_optional_decimal_text("1234567890123456"))
        self.assertIsNone(_optional_decimal_text("0.123456789"))

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

    def test_buying_power_prefers_broker_buying_power(self) -> None:
        snapshot = self._snapshot_with_balances(
            {
                "cashAvailableForTrading": 1000.0,
                "buyingPower": 2500.0,
                "availableFunds": 1800.0,
            }
        )
        self.assertEqual(1000.0, snapshot.cash_balance)
        self.assertEqual(2500.0, snapshot.buying_power)
        self.assertEqual("broker_buying_power", snapshot.metadata["buying_power_source"])

    def test_buying_power_uses_available_funds_when_buying_power_absent(self) -> None:
        snapshot = self._snapshot_with_balances(
            {
                "cashAvailableForTrading": 1000.0,
                "availableFunds": 1800.0,
            }
        )
        self.assertEqual(1800.0, snapshot.buying_power)
        self.assertEqual("broker_available_funds", snapshot.metadata["buying_power_source"])

    def test_buying_power_falls_back_to_cash_without_leverage_invention(self) -> None:
        snapshot = self._snapshot_with_balances({"cashAvailableForTrading": 1000.0})
        self.assertEqual(1000.0, snapshot.buying_power)
        self.assertEqual(
            "cash_available_for_trading_fallback",
            snapshot.metadata["buying_power_source"],
        )

    def test_invalid_optional_buying_power_fields_fail_closed(self) -> None:
        for field in ("buyingPower", "availableFunds"):
            with self.subTest(field=field):
                balances = {"cashAvailableForTrading": 1000.0, field: float("nan")}
                with self.assertRaises(ValueError) as raised:
                    self._snapshot_with_balances(balances)
                self.assertEqual(f"Invalid Schwab balance: {field}", str(raised.exception))

if __name__ == "__main__":
    unittest.main()
