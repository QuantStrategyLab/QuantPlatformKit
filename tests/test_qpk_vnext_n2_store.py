from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from quant_platform_kit.strategy_lifecycle.qpk_vnext_n1 import ResultContract
from quant_platform_kit.strategy_lifecycle.qpk_vnext_n2_store import SqliteResultStore, StoreError


def contract(**changes):
    values = dict(domain="us_equity", profile="SOXL", timing="next_open", identity_version=1,
                  persist_mode="durable", strategy_id="strategy", run_id="run-1",
                  param_set_id="baseline", param_version=1, source_revision="rev1",
                  computed_at="2026-07-15T00:00:00.000000Z", params={"x": 1})
    values.update(changes)
    return ResultContract(**values)


def test_constructor_is_side_effect_free_and_ephemeral_zero_side_effect(tmp_path):
    db = tmp_path / "nested" / "results.sqlite"
    store = SqliteResultStore(db)
    assert not db.exists() and not db.parent.exists()
    with pytest.raises(StoreError):
        store.put(replace(contract(), persist_mode="ephemeral"))
    assert not db.exists() and not db.parent.exists()


def test_write_read_idempotent_conflict_and_restart(tmp_path):
    db = tmp_path / "results.sqlite"
    item = contract()
    assert SqliteResultStore(db).put(item) == "created"
    assert SqliteResultStore(db).put(item) == "idempotent"
    assert SqliteResultStore(db).get(item.key) == item
    with pytest.raises(StoreError):
        SqliteResultStore(db).put(contract(computed_at="2026-07-16T00:00:00.000000Z"))


def test_concurrent_identical_writers_and_selector(tmp_path):
    store = SqliteResultStore(tmp_path / "results.sqlite")
    item = contract()
    with ThreadPoolExecutor(max_workers=6) as pool:
        outcomes = list(pool.map(lambda _: store.put(item), range(6)))
    assert outcomes.count("created") == 1
    assert outcomes.count("idempotent") == 5
    other = contract(timing="next_close")
    store.put(other)
    assert store.list_keys(domain="us_equity", profile="SOXL", timing="next_open") == (item.key,)
    assert store.list_keys(domain="us_equity", profile="SOXL", timing="next_close") == (other.key,)
    with pytest.raises(StoreError):
        store.list_keys(domain="us_equity", profile="..", timing="next_open")


def test_corruption_key_mismatch_and_schema_mismatch_fail_closed(tmp_path):
    db = tmp_path / "results.sqlite"
    store = SqliteResultStore(db)
    item = contract()
    store.put(item)
    conn = sqlite3.connect(db)
    conn.execute("UPDATE results SET payload=? WHERE key=?", (b"{}", item.key))
    conn.commit(); conn.close()
    with pytest.raises(StoreError):
        store.get(item.key)
    conn = sqlite3.connect(db)
    conn.execute("UPDATE store_meta SET value='legacy' WHERE key='namespace'")
    conn.commit(); conn.close()
    with pytest.raises(StoreError):
        store.list_keys(domain="us_equity", profile="SOXL", timing="next_open")


def test_reads_do_not_create_or_mutate_unrelated_database(tmp_path):
    missing = SqliteResultStore(tmp_path / "missing.sqlite")
    with pytest.raises(StoreError):
        missing.get("qpk-vnext/result/v2/us_equity/SOXL/strategy/run-1/next_open/i1/p1/x.json")
    assert not (tmp_path / "missing.sqlite").exists()
    unrelated = tmp_path / "unrelated.sqlite"
    conn = sqlite3.connect(unrelated)
    conn.execute("CREATE TABLE other (value TEXT)")
    conn.commit(); conn.close()
    before = unrelated.read_bytes()
    with pytest.raises(StoreError):
        SqliteResultStore(unrelated).list_keys(domain="us_equity", profile="SOXL", timing="next_open")
    assert unrelated.read_bytes() == before


def test_permissions_fail_closed(tmp_path):
    db = tmp_path / "results.sqlite"
    db.parent.chmod(0o500)
    try:
        with pytest.raises(StoreError):
            SqliteResultStore(db).put(contract())
    finally:
        db.parent.chmod(0o700)
