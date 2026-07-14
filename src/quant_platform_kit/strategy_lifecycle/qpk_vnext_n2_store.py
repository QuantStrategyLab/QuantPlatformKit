"""Exact durable put/get foundation for the trusted qpk-vnext/result/v2 store."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from quant_platform_kit.strategy_lifecycle.qpk_vnext_n1 import NAMESPACE, ContractError, ResultContract, decode_wire


class StoreError(ValueError):
    """Sanitized store failure."""


def _fail() -> None:
    raise StoreError("invalid qpk-vnext sqlite store operation")


class SqliteResultStore:
    """Trusted single-process local store with no selector/latest API."""

    def __init__(self, db_path: str | os.PathLike[str]) -> None:
        if not isinstance(db_path, (str, os.PathLike)) or os.name != "posix":
            _fail()
        self.db_path = Path(db_path).expanduser()
        if not self.db_path.is_absolute() or self.db_path.name in {"", ".", ".."}:
            _fail()

    @staticmethod
    def _payload(contract: ResultContract) -> bytes:
        if not isinstance(contract, ResultContract) or contract.persist_mode != "durable":
            _fail()
        try:
            checked = decode_wire(contract.to_wire())
            return json.dumps(checked.to_wire(), ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"), allow_nan=False).encode("utf-8")
        except (ContractError, TypeError, ValueError, UnicodeError):
            _fail()

    @staticmethod
    def _schema_names(conn: sqlite3.Connection) -> set[str]:
        try:
            return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        except sqlite3.Error:
            _fail()

    @staticmethod
    def _validate_schema(conn: sqlite3.Connection) -> None:
        try:
            objects = {(row[0], row[1]) for row in conn.execute(
                "SELECT name,type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
            if objects != {("store_meta", "table"), ("results", "table")}:
                _fail()
            marker = conn.execute("SELECT value FROM store_meta WHERE key=?", ("namespace",)).fetchone()
            if marker != (NAMESPACE,):
                _fail()
            meta_cols = [(row[1], row[2], row[3], row[5]) for row in conn.execute("PRAGMA table_info(store_meta)")]
            result_cols = [(row[1], row[2], row[3], row[5]) for row in conn.execute("PRAGMA table_info(results)")]
            if meta_cols != [("key", "TEXT", 1, 1), ("value", "TEXT", 1, 0)]:
                _fail()
            if result_cols != [("key", "TEXT", 1, 1), ("payload", "BLOB", 1, 0)]:
                _fail()
        except sqlite3.Error:
            _fail()

    @staticmethod
    def _configure(conn: sqlite3.Connection, *, initialize: bool) -> None:
        try:
            if initialize:
                conn.execute("BEGIN IMMEDIATE")
                if SqliteResultStore._schema_names(conn):
                    SqliteResultStore._validate_schema(conn)
                else:
                    conn.execute("CREATE TABLE store_meta (key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL)")
                    conn.execute("CREATE TABLE results (key TEXT PRIMARY KEY NOT NULL, payload BLOB NOT NULL)")
                    conn.execute("INSERT INTO store_meta(key,value) VALUES (?,?)", ("namespace", NAMESPACE))
                conn.execute("COMMIT")
            else:
                SqliteResultStore._validate_schema(conn)
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("PRAGMA synchronous=FULL")
        except (sqlite3.Error, StoreError):
            try:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise

    def _connect(self, *, write: bool) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = None
        try:
            exists = self.db_path.exists()
            if not write and (not exists or self.db_path.stat().st_size == 0):
                _fail()
            initialize = write and (not exists or self.db_path.stat().st_size == 0)
            conn = sqlite3.connect(str(self.db_path), timeout=10, isolation_level=None)
            self._configure(conn, initialize=initialize)
            return conn
        except (OSError, sqlite3.Error, StoreError):
            if conn is not None:
                conn.close()
            _fail()

    @staticmethod
    def _key(key: Any) -> str:
        if not isinstance(key, str) or not key.startswith(NAMESPACE + "/") or "\\" in key:
            _fail()
        return key

    @staticmethod
    def _blob(value: Any) -> bytes:
        if not isinstance(value, (bytes, bytearray, memoryview)):
            _fail()
        return bytes(value)

    def put(self, contract: ResultContract) -> str:
        payload = self._payload(contract)
        conn = self._connect(write=True)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT payload FROM results WHERE key=?", (contract.key,)).fetchone()
            if row is not None:
                if self._blob(row[0]) == payload:
                    conn.execute("COMMIT")
                    return "idempotent"
                conn.execute("ROLLBACK")
                _fail()
            conn.execute("INSERT INTO results(key,payload) VALUES (?,?)", (contract.key, payload))
            conn.execute("COMMIT")
            return "created"
        except (sqlite3.Error, StoreError):
            try:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            _fail()
        finally:
            conn.close()

    def get(self, key: str) -> ResultContract:
        key = self._key(key)
        conn = self._connect(write=False)
        try:
            row = conn.execute("SELECT payload FROM results WHERE key=?", (key,)).fetchone()
            if row is None:
                _fail()
            data = json.loads(self._blob(row[0]).decode("utf-8"))
            item = decode_wire(data)
            if item.key != key:
                _fail()
            if item.persist_mode != "durable":
                _fail()
            return item
        except (sqlite3.Error, StoreError, TypeError, UnicodeError, json.JSONDecodeError):
            _fail()
        finally:
            conn.close()
