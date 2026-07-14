from __future__ import annotations

import sqlite3
import json
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


def test_constructor_and_ephemeral_are_side_effect_free(tmp_path):
    db = tmp_path / "nested" / "result ?#% 空.sqlite"
    store = SqliteResultStore(db)
    assert not db.exists() and not db.parent.exists()
    with pytest.raises(StoreError):
        store.put(replace(contract(), persist_mode="ephemeral"))
    assert not db.exists() and not db.parent.exists()


def test_exact_write_read_restart_and_idempotent_path_specials(tmp_path):
    db = tmp_path / "result ?#% 空.sqlite"
    item = contract()
    store = SqliteResultStore(db)
    assert store.put(item) == "created"
    assert SqliteResultStore(db).get(item.key) == item
    assert SqliteResultStore(db).put(item) == "idempotent"
    with pytest.raises(StoreError):
        SqliteResultStore(db).put(contract(computed_at="2026-07-16T00:00:00.000000Z"))


def test_concurrent_identical_writers(tmp_path):
    store = SqliteResultStore(tmp_path / "results.sqlite")
    item = contract()
    with ThreadPoolExecutor(max_workers=6) as pool:
        outcomes = list(pool.map(lambda _: store.put(item), range(6)))
    assert outcomes.count("created") == 1
    assert outcomes.count("idempotent") == 5


def test_missing_wrong_schema_and_payload_corruption_fail_closed(tmp_path):
    item = contract()
    missing = SqliteResultStore(tmp_path / "missing.sqlite")
    with pytest.raises(StoreError):
        missing.get(item.key)
    assert not (tmp_path / "missing.sqlite").exists()
    db = tmp_path / "bad.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE other(value TEXT)"); conn.commit(); conn.close()
    before = db.read_bytes()
    with pytest.raises(StoreError):
        SqliteResultStore(db).get(item.key)
    assert db.read_bytes() == before
    good = tmp_path / "good.sqlite"
    store = SqliteResultStore(good); store.put(item)
    conn = sqlite3.connect(good)
    conn.execute("UPDATE results SET payload=? WHERE key=?", ("text", item.key)); conn.commit(); conn.close()
    with pytest.raises(StoreError):
        store.get(item.key)


def test_key_mismatch_and_null_payload_and_rollback(tmp_path):
    db = tmp_path / "results.sqlite"
    item = contract()
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("CREATE TABLE results (key TEXT PRIMARY KEY, payload BLOB)")
    conn.execute("INSERT INTO store_meta(key,value) VALUES ('namespace', 'qpk-vnext/result/v2')")
    conn.execute("INSERT INTO results(key,payload) VALUES (?,NULL)", (item.key,)); conn.commit(); conn.close()
    with pytest.raises(StoreError):
        SqliteResultStore(db).get(item.key)


def test_catalog_constraints_and_unexpected_objects_fail_without_mutation(tmp_path):
    item = contract()
    for suffix, ddl in (
        ("trigger", "CREATE TRIGGER side AFTER INSERT ON results BEGIN SELECT 1; END"),
        ("view", "CREATE VIEW extra AS SELECT 1"),
        ("index", "CREATE INDEX extra_idx ON results(key)"),
    ):
        db = tmp_path / f"{suffix}.sqlite"
        store = SqliteResultStore(db); store.put(item)
        conn = sqlite3.connect(db); conn.execute(ddl); conn.commit(); conn.close()
        before = db.read_bytes()
        with pytest.raises(StoreError):
            store.get(item.key)
        assert db.read_bytes() == before
    forged = tmp_path / "forged.sqlite"
    conn = sqlite3.connect(forged)
    conn.execute("CREATE TABLE store_meta (key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL)")
    conn.execute("CREATE TABLE results (key TEXT PRIMARY KEY, payload BLOB NOT NULL)")
    conn.execute("INSERT INTO store_meta(key,value) VALUES ('namespace', 'qpk-vnext/result/v2')")
    conn.commit(); conn.close()
    with pytest.raises(StoreError):
        SqliteResultStore(forged).get(item.key)


def test_ephemeral_payload_is_rejected_on_durable_get(tmp_path):
    db = tmp_path / "ephemeral.sqlite"
    item = contract(persist_mode="ephemeral")
    payload = json.dumps(item.to_wire(), sort_keys=True, separators=(",", ":")).encode()
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE store_meta (key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL)")
    conn.execute("CREATE TABLE results (key TEXT PRIMARY KEY NOT NULL, payload BLOB NOT NULL)")
    conn.execute("INSERT INTO store_meta(key,value) VALUES ('namespace', 'qpk-vnext/result/v2')")
    conn.execute("INSERT INTO results(key,payload) VALUES (?,?)", (item.key, payload))
    conn.commit(); conn.close()
    with pytest.raises(StoreError):
        SqliteResultStore(db).get(item.key)
