"""Reporting retains the existing account response; strategy inputs stay filtered."""
from copy import deepcopy
import hashlib
import json
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pytest

from quant_platform_kit.schwab.portfolio import fetch_account_snapshot


class Response:
    status_code = 200
    def __init__(self, payload): self.payload = payload
    def json(self): return self.payload


class Client:
    def __init__(self, account):
        self.payload = {"securitiesAccount": account}
        self.numbers_calls = self.account_calls = 0
    def get_account_numbers(self):
        self.numbers_calls += 1
        return Response([{"hashValue": "synthetic"}])
    def get_account(self, account_hash, fields):
        assert (account_hash, fields) == ("synthetic", "POSITIONS")
        self.account_calls += 1
        return Response(self.payload)


def read(account):
    account = {"currentBalances": {"cashAvailableForTrading": 1000, "liquidationValue": 1210}, **account}
    sdk, sdk_client = ModuleType("schwab"), ModuleType("schwab.client")
    sdk_client.Client = SimpleNamespace(Account=SimpleNamespace(Fields=SimpleNamespace(POSITIONS="POSITIONS")))
    client = Client(account)
    with patch.dict(sys.modules, {"schwab": sdk, "schwab.client": sdk_client}):
        snapshot = fetch_account_snapshot(client, strategy_symbols=("TQQQ",), expected_account_hash="synthetic")
    return snapshot, client


def row(symbol="OTHER", **changes):
    return {"instrument": {"assetType": "EQUITY", "symbol": symbol, "description": "omit"},
            "longQuantity": "1.12345678", "shortQuantity": "0", "marketValue": "10.001", **changes}


def test_same_response_preserves_non_strategy_fields_without_extra_reads():
    rows = [row("TQQQ", longQuantity="5", marketValue="200"), row()]
    snapshot, client = read({"positions": rows, "accountNumber": "must-not-copy"})
    native = snapshot.metadata["broker_stock_inventory"]
    assert (client.numbers_calls, client.account_calls) == (1, 1)
    assert [(p.symbol, p.quantity, p.market_value) for p in snapshot.positions] == [("TQQQ", 5.0, 200.0)]
    assert (snapshot.total_equity, snapshot.cash_balance, snapshot.buying_power) == (1210, 1000, 1000)
    expected_digest = hashlib.sha256(json.dumps(client.payload, sort_keys=True, separators=(",", ":"),
                                              ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    assert snapshot.metadata["source_digest_sha256"] == expected_digest
    assert native["positions_field_present"] is True and native["native_positions_count"] == 2
    assert native["positions"][1]["longQuantity"] == "1.12345678"
    assert native["positions"][1]["instrument"] == {"assetType": "EQUITY", "symbol": "OTHER"}
    assert "accountNumber" not in native and "description" not in str(native)
    original = deepcopy(client.payload)
    native["positions"][0]["instrument"]["symbol"] = "EDIT"
    assert client.payload == original


@pytest.mark.parametrize("account,present,count,positions", [({}, False, None, None), ({"positions": []}, True, 0, [])])
def test_missing_and_real_empty_keep_distinct_native_presence(account, present, count, positions):
    snapshot, client = read(account)
    native = snapshot.metadata["broker_stock_inventory"]
    assert snapshot.positions == () and snapshot.total_equity == 1210
    assert native["positions_field_present"] is present
    assert native["native_positions_count"] == count
    assert native.get("positions") == positions
    assert client.account_calls == 1


def test_reporting_copy_is_bounded_without_changing_strategy_result():
    snapshot, _ = read({"positions": [row()] * 513})
    native = snapshot.metadata["broker_stock_inventory"]
    assert snapshot.positions == () and snapshot.total_equity == 1210
    assert native == {"positions_field_present": True, "native_positions_count": 513, "positions": None}


def test_missing_or_invalid_native_fields_are_not_filled_with_zero():
    bad = row(shortQuantity=None)
    del bad["marketValue"]
    snapshot, _ = read({"positions": [bad]})
    copied = snapshot.metadata["broker_stock_inventory"]["positions"][0]
    assert copied["shortQuantity"] is None and "marketValue" not in copied
    assert snapshot.positions == ()
