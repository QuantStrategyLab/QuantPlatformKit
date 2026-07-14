"""Trusted single-process SQLite backend for qpk-vnext/result/v2."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from quant_platform_kit.strategy_lifecycle.qpk_vnext_n1 import (
    NAMESPACE, ContractError, ResultContract, _segment, decode_wire,
)


class StoreError(ValueError):
    """Sanitized isolated-store failure."""


def _fail() -> None:
    raise StoreError("invalid qpk-vnext sqlite store operation")


class SqliteResultStore:
    """Durable trusted local research store; constructor performs no I/O."""

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
    def _configure(conn: sqlite3.Connection, *, initialize: bool) -> None:
        try:
            if initialize:
                conn.execute("BEGIN IMMEDIATE")
                names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                initialize = "store_meta" not in names
            if initialize:
                conn.execute("CREATE TABLE IF NOT EXISTS store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                conn.execute("CREATE TABLE IF NOT EXISTS results ("
                             "key TEXT PRIMARY KEY, payload BLOB NOT NULL, domain TEXT NOT NULL, "
                             "profile TEXT NOT NULL, timing TEXT NOT NULL, strategy_id TEXT NOT NULL, "
                             "run_id TEXT NOT NULL, identity_version INTEGER NOT NULL, "
                             "param_version INTEGER NOT NULL)")
                conn.execute("CREATE INDEX IF NOT EXISTS results_selector ON results(domain, profile, timing, key)")
                conn.execute("INSERT OR IGNORE INTO store_meta(key, value) VALUES (?, ?)", ("namespace", NAMESPACE))
            else:
                names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if "store_meta" not in names or "results" not in names:
                    _fail()
            marker = conn.execute("SELECT value FROM store_meta WHERE key=?", ("namespace",)).fetchone()
            if marker != (NAMESPACE,):
                _fail()
            if conn.in_transaction:
                conn.execute("COMMIT")
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA foreign_keys=ON")
        except sqlite3.Error:
            try:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            _fail()

    def _connect(self, *, write: bool) -> sqlite3.Connection:
        try:
            exists = self.db_path.exists()
            if not write and (not exists or self.db_path.stat().st_size == 0):
                _fail()
            initialize = write and (not exists or self.db_path.stat().st_size == 0)
            if exists and not initialize:
                uri = f"file:{self.db_path}?mode=rw"
                conn = sqlite3.connect(uri, uri=True, timeout=10, isolation_level=None)
            else:
                conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
            self._configure(conn, initialize=initialize)
            return conn
        except (OSError, sqlite3.Error):
            _fail()

    @staticmethod
    def _validate_columns(item: ResultContract, row: tuple[Any, ...]) -> None:
        key, _payload, domain, profile, timing, strategy_id, run_id, identity_version, param_version = row
        if (item.key, item.domain, item.profile, item.timing, item.strategy_id, item.run_id,
                item.identity_version, item.param_version) != (key, domain, profile, timing,
                strategy_id, run_id, identity_version, param_version):
            _fail()

    def put(self, contract: ResultContract) -> str:
        payload = self._payload(contract)
        conn = self._connect(write=True)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT payload FROM results WHERE key=?", (contract.key,)).fetchone()
            if row is not None:
                if bytes(row[0]) == payload:
                    conn.execute("COMMIT")
                    return "idempotent"
                conn.execute("ROLLBACK")
                _fail()
            conn.execute("INSERT INTO results(key,payload,domain,profile,timing,strategy_id,run_id,identity_version,param_version) "
                         "VALUES (?,?,?,?,?,?,?,?,?)", (contract.key, payload, contract.domain,
                         contract.profile, contract.timing, contract.strategy_id, contract.run_id,
                         contract.identity_version, contract.param_version))
            conn.execute("COMMIT")
            return "created"
        except (sqlite3.Error, OSError, ValueError):
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            _fail()
        finally:
            conn.close()

    def get(self, key: str) -> ResultContract:
        if not isinstance(key, str) or not key.startswith(NAMESPACE + "/"):
            _fail()
        conn = self._connect(write=False)
        try:
            row = conn.execute("SELECT key,payload,domain,profile,timing,strategy_id,run_id,identity_version,param_version "
                               "FROM results WHERE key=?", (key,)).fetchone()
            if row is None:
                _fail()
            item = decode_wire(json.loads(bytes(row[1]).decode("utf-8")))
            self._validate_columns(item, row)
            return item
        except (sqlite3.Error, OSError, UnicodeError, json.JSONDecodeError, ContractError):
            _fail()
        finally:
            conn.close()

    def list_keys(self, *, domain: str, profile: str, timing: str) -> tuple[str, ...]:
        try:
            domain, profile = _segment(domain), _segment(profile)
        except ContractError:
            _fail()
        if timing not in {"next_open", "next_close"}:
            _fail()
        conn = self._connect(write=False)
        try:
            rows = conn.execute("SELECT key,payload,domain,profile,timing,strategy_id,run_id,identity_version,param_version "
                                "FROM results WHERE domain=? AND profile=? AND timing=? ORDER BY key",
                                (domain, profile, timing)).fetchall()
            found: list[str] = []
            for row in rows:
                item = decode_wire(json.loads(bytes(row[1]).decode("utf-8")))
                self._validate_columns(item, row)
                found.append(item.key)
            return tuple(found)
        except (sqlite3.Error, OSError, UnicodeError, json.JSONDecodeError, ContractError):
            _fail()
        finally:
            conn.close()
