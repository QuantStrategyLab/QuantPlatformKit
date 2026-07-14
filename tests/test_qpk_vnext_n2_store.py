from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from quant_platform_kit.strategy_lifecycle.qpk_vnext_n1 import ContractError, ResultContract
from quant_platform_kit.strategy_lifecycle.qpk_vnext_n2_store import IsolatedResultStore, StoreError


def contract(**changes):
    values = dict(domain="us_equity", profile="SOXL", timing="next_open", identity_version=1,
                  persist_mode="durable", strategy_id="strategy", run_id="run-1",
                  param_set_id="baseline", param_version=1, source_revision="rev1",
                  computed_at="2026-07-15T00:00:00.000000Z", params={"x": 1})
    values.update(changes)
    return ResultContract(**values)


def test_durable_write_read_and_idempotent(tmp_path):
    store = IsolatedResultStore(tmp_path)
    item = contract()
    assert store.put(item) == "created"
    assert store.put(item) == "idempotent"
    assert store.get(item.key) == item
    assert list(tmp_path.rglob("*.json"))


def test_ephemeral_has_no_side_effect(tmp_path):
    store = IsolatedResultStore(tmp_path)
    with pytest.raises(StoreError):
        store.put(replace(contract(), persist_mode="ephemeral"))
    assert not list(tmp_path.rglob("*"))


def test_conflict_corrupt_missing_and_traversal_fail_closed(tmp_path):
    store = IsolatedResultStore(tmp_path)
    item = contract()
    store.put(item)
    path = tmp_path / item.key
    path.write_bytes(b"conflict")
    with pytest.raises(StoreError):
        store.put(item)
    with pytest.raises(StoreError):
        store.get(item.key)
    for key in ("../x.json", "/tmp/x.json", item.key.replace("strategy", "../x")):
        with pytest.raises(StoreError):
            store.get(key)
    with pytest.raises(StoreError):
        store.get(item.key + ".missing")


def test_selector_listing_is_explicit_and_ignores_legacy(tmp_path):
    store = IsolatedResultStore(tmp_path)
    first = contract()
    second = contract(timing="next_close")
    store.put(first)
    store.put(second)
    (tmp_path / "legacy" / "result.json").parent.mkdir()
    (tmp_path / "legacy" / "result.json").write_text("{}")
    assert store.list_keys(domain="us_equity", profile="SOXL", timing="next_open") == (first.key,)
    assert store.list_keys(domain="us_equity", profile="SOXL", timing="next_close") == (second.key,)
    with pytest.raises(StoreError):
        store.list_keys(domain="us_equity", profile="..", timing="next_open")
    with pytest.raises(StoreError):
        store.list_keys(domain="us_equity", profile="SOXL/..", timing="next_open")
    with pytest.raises(StoreError):
        store.list_keys(domain="us_equity", profile="SOXL", timing="next_openx")


def test_atomic_failure_cleans_temp(tmp_path, monkeypatch):
    store = IsolatedResultStore(tmp_path)
    def fail_replace(*_args):
        raise OSError("injected")
    monkeypatch.setattr("quant_platform_kit.strategy_lifecycle.qpk_vnext_n2_store.os.link", fail_replace)
    with pytest.raises(StoreError):
        store.put(contract())
    assert not list(tmp_path.rglob("*.tmp"))


def test_concurrent_put_is_create_only(tmp_path):
    store = IsolatedResultStore(tmp_path)
    item = contract()
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda _: store.put(item), range(8)))
    assert outcomes.count("created") == 1
    assert outcomes.count("idempotent") == 7
    assert store.get(item.key) == item
