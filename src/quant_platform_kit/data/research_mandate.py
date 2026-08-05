"""Crash-safe, single-use lifecycle guard for bounded research mandates."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
from typing import Any


MANDATE_SCHEMA_VERSION = "research_mandate.v1"
RECEIPT_SCHEMA_VERSION = "research_mandate_consumption_receipt.v1"
MANDATE_LIFETIME = timedelta(hours=2)
_DENIED = "research mandate authority denied"
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_NONCE_RE = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
_MANDATE_FIELDS = frozenset(
    {
        "schema_version",
        "candidate_id",
        "mandate_id",
        "config_digest",
        "input_digest",
        "authority_id",
        "nonce",
        "issued_at",
        "expires_at",
        "mandate_digest",
    }
)
_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "mandate_digest",
        "candidate_identity_digest",
        "mandate_identity_digest",
        "config_digest",
        "input_digest",
        "authority_identity_digest",
        "consumed_at",
        "terminal_state",
        "receipt_digest",
    }
)
_ROW_FIELDS = (
    "schema_version",
    "mandate_digest",
    "mandate_id",
    "candidate_id",
    "config_digest",
    "input_digest",
    "authority_id",
    "nonce_digest",
    "issued_at",
    "expires_at",
    "status",
    "consumed_at",
    "receipt_json",
    "receipt_digest",
    "state_digest",
)
_SCHEMA_DESCRIPTION = {
    "schema_version": 1,
    "tables": {
        "metadata": ("key", "value"),
        "mandates": _ROW_FIELDS,
    },
}
_SCHEMA_DIGEST = hashlib.sha256(
    json.dumps(
        _SCHEMA_DESCRIPTION,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
).hexdigest()
_CREATE_SCHEMA = """
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE mandates (
    schema_version TEXT NOT NULL,
    mandate_digest TEXT PRIMARY KEY,
    mandate_id TEXT NOT NULL UNIQUE,
    candidate_id TEXT NOT NULL,
    config_digest TEXT NOT NULL,
    input_digest TEXT NOT NULL,
    authority_id TEXT NOT NULL,
    nonce_digest TEXT NOT NULL UNIQUE,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ISSUED', 'CONSUMED')),
    consumed_at TEXT,
    receipt_json TEXT,
    receipt_digest TEXT,
    state_digest TEXT NOT NULL,
    CHECK (
        (status = 'ISSUED' AND consumed_at IS NULL AND receipt_json IS NULL AND receipt_digest IS NULL)
        OR
        (status = 'CONSUMED' AND consumed_at IS NOT NULL AND receipt_json IS NOT NULL AND receipt_digest IS NOT NULL)
    )
);
PRAGMA user_version = 1;
"""

__all__ = [
    "MANDATE_LIFETIME",
    "MandateConsumptionReceipt",
    "ResearchMandate",
    "ResearchMandateAuthorityError",
    "ResearchMandateAuthorityGuard",
]


class ResearchMandateAuthorityError(ValueError):
    """Sanitized rejection for invalid authority or damaged authority state."""


def _deny() -> None:
    raise ResearchMandateAuthorityError(_DENIED)


def _canonical(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        _deny()


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _identity_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _require_digest(value: object) -> str:
    if not isinstance(value, str) or not _DIGEST_RE.fullmatch(value):
        _deny()
    return value


def _require_identity(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or value != value.strip()
        or any(0xD800 <= ord(character) <= 0xDFFF for character in value)
    ):
        _deny()
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        _deny()
    return value


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not _TIMESTAMP_RE.fullmatch(value):
        _deny()
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        _deny()


def _timestamp(value: datetime) -> str:
    try:
        if not isinstance(value, datetime) or value.tzinfo is None:
            _deny()
        offset = value.utcoffset()
        if offset is None:
            _deny()
        value = value.astimezone(timezone.utc)
        return value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    except (OverflowError, ValueError):
        _deny()


def _strict_mapping(value: object, fields: frozenset[str]) -> dict[str, object]:
    if (
        not isinstance(value, Mapping)
        or any(not isinstance(key, str) for key in value)
        or set(value) != fields
    ):
        _deny()
    return dict(value)


def _mandate_identity_payload(values: Mapping[str, object]) -> dict[str, object]:
    return {
        "schema_version": values["schema_version"],
        "candidate_id": values["candidate_id"],
        "mandate_id": values["mandate_id"],
        "config_digest": values["config_digest"],
        "input_digest": values["input_digest"],
        "authority_id": values["authority_id"],
        "nonce": values["nonce"],
        "issued_at": values["issued_at"],
        "expires_at": values["expires_at"],
    }


@dataclass(frozen=True)
class ResearchMandate:
    """Immutable two-hour authority with a fresh single-use nonce."""

    schema_version: str
    candidate_id: str
    mandate_id: str
    config_digest: str
    input_digest: str
    authority_id: str
    nonce: str
    issued_at: str
    expires_at: str
    mandate_digest: str

    def __post_init__(self) -> None:
        try:
            if self.schema_version != MANDATE_SCHEMA_VERSION:
                _deny()
            for field in ("candidate_id", "mandate_id", "authority_id"):
                _require_identity(getattr(self, field))
            _require_digest(self.config_digest)
            _require_digest(self.input_digest)
            if not isinstance(self.nonce, str) or not _NONCE_RE.fullmatch(self.nonce):
                _deny()
            issued_at = _parse_timestamp(self.issued_at)
            expires_at = _parse_timestamp(self.expires_at)
            if expires_at - issued_at != MANDATE_LIFETIME:
                _deny()
            _require_digest(self.mandate_digest)
            if self.mandate_digest != _digest(
                _mandate_identity_payload(self.to_dict(include_digest=False))
            ):
                _deny()
        except ResearchMandateAuthorityError:
            raise
        except Exception:
            _deny()

    def to_dict(self, *, include_digest: bool = True) -> dict[str, object]:
        payload = {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "mandate_id": self.mandate_id,
            "config_digest": self.config_digest,
            "input_digest": self.input_digest,
            "authority_id": self.authority_id,
            "nonce": self.nonce,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
        }
        if include_digest:
            payload["mandate_digest"] = self.mandate_digest
        return payload

    @classmethod
    def from_dict(cls, value: object) -> ResearchMandate:
        try:
            return cls(**_strict_mapping(value, _MANDATE_FIELDS))  # type: ignore[arg-type]
        except ResearchMandateAuthorityError:
            raise
        except Exception:
            _deny()


@dataclass(frozen=True)
class MandateConsumptionReceipt:
    """Sanitized proof that a mandate entered its terminal consumed state."""

    schema_version: str
    mandate_digest: str
    candidate_identity_digest: str
    mandate_identity_digest: str
    config_digest: str
    input_digest: str
    authority_identity_digest: str
    consumed_at: str
    terminal_state: str
    receipt_digest: str

    def __post_init__(self) -> None:
        if (
            self.schema_version != RECEIPT_SCHEMA_VERSION
            or self.terminal_state != "CONSUMED"
        ):
            _deny()
        for field in (
            "mandate_digest",
            "candidate_identity_digest",
            "mandate_identity_digest",
            "config_digest",
            "input_digest",
            "authority_identity_digest",
            "receipt_digest",
        ):
            _require_digest(getattr(self, field))
        _parse_timestamp(self.consumed_at)
        if self.receipt_digest != _digest(self.to_dict(include_digest=False)):
            _deny()

    def to_dict(self, *, include_digest: bool = True) -> dict[str, str]:
        payload = {
            "schema_version": self.schema_version,
            "mandate_digest": self.mandate_digest,
            "candidate_identity_digest": self.candidate_identity_digest,
            "mandate_identity_digest": self.mandate_identity_digest,
            "config_digest": self.config_digest,
            "input_digest": self.input_digest,
            "authority_identity_digest": self.authority_identity_digest,
            "consumed_at": self.consumed_at,
            "terminal_state": self.terminal_state,
        }
        if include_digest:
            payload["receipt_digest"] = self.receipt_digest
        return payload

    @classmethod
    def from_dict(cls, value: object) -> MandateConsumptionReceipt:
        try:
            return cls(**_strict_mapping(value, _RECEIPT_FIELDS))  # type: ignore[arg-type]
        except ResearchMandateAuthorityError:
            raise
        except Exception:
            _deny()


def _new_receipt(mandate: ResearchMandate, consumed_at: str) -> MandateConsumptionReceipt:
    payload = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "mandate_digest": mandate.mandate_digest,
        "candidate_identity_digest": _identity_digest(mandate.candidate_id),
        "mandate_identity_digest": _identity_digest(mandate.mandate_id),
        "config_digest": mandate.config_digest,
        "input_digest": mandate.input_digest,
        "authority_identity_digest": _identity_digest(mandate.authority_id),
        "consumed_at": consumed_at,
        "terminal_state": "CONSUMED",
    }
    return MandateConsumptionReceipt(**payload, receipt_digest=_digest(payload))


def _state_digest(row: Mapping[str, object]) -> str:
    return _digest({field: row[field] for field in _ROW_FIELDS if field != "state_digest"})


def _decode_receipt(payload: str) -> MandateConsumptionReceipt:
    try:
        parsed = json.loads(payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        _deny()
    return MandateConsumptionReceipt.from_dict(parsed)


def _validate_row(row: Mapping[str, object]) -> None:
    if set(row) != set(_ROW_FIELDS) or row["schema_version"] != MANDATE_SCHEMA_VERSION:
        _deny()
    for field in ("candidate_id", "mandate_id", "authority_id"):
        _require_identity(row[field])
    for field in ("mandate_digest", "config_digest", "input_digest", "nonce_digest"):
        _require_digest(row[field])
    issued_at = _parse_timestamp(row["issued_at"])
    expires_at = _parse_timestamp(row["expires_at"])
    if expires_at - issued_at != MANDATE_LIFETIME:
        _deny()
    if row["status"] not in {"ISSUED", "CONSUMED"}:
        _deny()
    _require_digest(row["state_digest"])
    if row["state_digest"] != _state_digest(row):
        _deny()

    terminal_values = (row["consumed_at"], row["receipt_json"], row["receipt_digest"])
    if row["status"] == "ISSUED":
        if terminal_values != (None, None, None):
            _deny()
        return
    if not all(isinstance(value, str) for value in terminal_values):
        _deny()
    receipt = _decode_receipt(row["receipt_json"])  # type: ignore[arg-type]
    if (
        receipt.receipt_digest != row["receipt_digest"]
        or receipt.consumed_at != row["consumed_at"]
        or receipt.mandate_digest != row["mandate_digest"]
        or receipt.candidate_identity_digest
        != _identity_digest(row["candidate_id"])  # type: ignore[arg-type]
        or receipt.mandate_identity_digest
        != _identity_digest(row["mandate_id"])  # type: ignore[arg-type]
        or receipt.config_digest != row["config_digest"]
        or receipt.input_digest != row["input_digest"]
        or receipt.authority_identity_digest
        != _identity_digest(row["authority_id"])  # type: ignore[arg-type]
    ):
        _deny()


class ResearchMandateAuthorityGuard:
    """Dedicated SQLite guard; not a generic state or locking abstraction."""

    def __init__(
        self,
        database: str | os.PathLike[str],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        try:
            self._database = Path(database)
        except (TypeError, ValueError):
            _deny()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def issue(
        self,
        *,
        candidate_id: str,
        mandate_id: str,
        config_digest: str,
        input_digest: str,
        authority_id: str,
    ) -> ResearchMandate:
        try:
            candidate_id = _require_identity(candidate_id)
            mandate_id = _require_identity(mandate_id)
            config_digest = _require_digest(config_digest)
            input_digest = _require_digest(input_digest)
            authority_id = _require_identity(authority_id)
            issued = self._now()
            expires = issued + MANDATE_LIFETIME
            payload = {
                "schema_version": MANDATE_SCHEMA_VERSION,
                "candidate_id": candidate_id,
                "mandate_id": mandate_id,
                "config_digest": config_digest,
                "input_digest": input_digest,
                "authority_id": authority_id,
                "nonce": secrets.token_hex(32),
                "issued_at": _timestamp(issued),
                "expires_at": _timestamp(expires),
            }
            mandate = ResearchMandate(
                **payload,
                mandate_digest=_digest(payload),
            )
            row = {
                "schema_version": mandate.schema_version,
                "mandate_digest": mandate.mandate_digest,
                "mandate_id": mandate.mandate_id,
                "candidate_id": mandate.candidate_id,
                "config_digest": mandate.config_digest,
                "input_digest": mandate.input_digest,
                "authority_id": mandate.authority_id,
                "nonce_digest": _identity_digest(mandate.nonce),
                "issued_at": mandate.issued_at,
                "expires_at": mandate.expires_at,
                "status": "ISSUED",
                "consumed_at": None,
                "receipt_json": None,
                "receipt_digest": None,
            }
            row["state_digest"] = _state_digest(row)
            with self._transaction(allow_create=True) as connection:
                placeholders = ",".join("?" for _ in _ROW_FIELDS)
                connection.execute(
                    f"INSERT INTO mandates ({','.join(_ROW_FIELDS)}) VALUES ({placeholders})",
                    tuple(row[field] for field in _ROW_FIELDS),
                )
            return mandate
        except ResearchMandateAuthorityError:
            raise
        except Exception:
            _deny()

    def consume(
        self,
        mandate: ResearchMandate,
        *,
        candidate_id: str,
        mandate_id: str,
        config_digest: str,
        input_digest: str,
        authority_id: str,
    ) -> MandateConsumptionReceipt:
        try:
            if type(mandate) is not ResearchMandate:
                _deny()
            expected = {
                "candidate_id": _require_identity(candidate_id),
                "mandate_id": _require_identity(mandate_id),
                "config_digest": _require_digest(config_digest),
                "input_digest": _require_digest(input_digest),
                "authority_id": _require_identity(authority_id),
            }
            if any(getattr(mandate, field) != value for field, value in expected.items()):
                _deny()

            with self._transaction(allow_create=False) as connection:
                selected = connection.execute(
                    f"SELECT {','.join(_ROW_FIELDS)} FROM mandates WHERE mandate_digest = ?",
                    (mandate.mandate_digest,),
                ).fetchone()
                if selected is None:
                    _deny()
                row = dict(zip(_ROW_FIELDS, selected, strict=True))
                _validate_row(row)
                for field in (
                    "schema_version",
                    "mandate_digest",
                    "mandate_id",
                    "candidate_id",
                    "config_digest",
                    "input_digest",
                    "authority_id",
                    "issued_at",
                    "expires_at",
                ):
                    if row[field] != getattr(mandate, field):
                        _deny()
                if row["nonce_digest"] != _identity_digest(mandate.nonce):
                    _deny()
                if row["status"] != "ISSUED":
                    _deny()

                now = self._now()
                if not _parse_timestamp(mandate.issued_at) <= now < _parse_timestamp(
                    mandate.expires_at
                ):
                    _deny()
                receipt = _new_receipt(mandate, _timestamp(now))
                receipt_json = _canonical(receipt.to_dict()).decode("ascii")
                updated = dict(row)
                updated.update(
                    status="CONSUMED",
                    consumed_at=receipt.consumed_at,
                    receipt_json=receipt_json,
                    receipt_digest=receipt.receipt_digest,
                )
                updated["state_digest"] = _state_digest(updated)
                result = connection.execute(
                    """
                    UPDATE mandates
                    SET status = ?, consumed_at = ?, receipt_json = ?,
                        receipt_digest = ?, state_digest = ?
                    WHERE mandate_digest = ? AND status = 'ISSUED' AND state_digest = ?
                    """,
                    (
                        updated["status"],
                        updated["consumed_at"],
                        updated["receipt_json"],
                        updated["receipt_digest"],
                        updated["state_digest"],
                        mandate.mandate_digest,
                        row["state_digest"],
                    ),
                )
                if result.rowcount != 1:
                    _deny()
            return receipt
        except ResearchMandateAuthorityError:
            raise
        except Exception:
            _deny()

    def _now(self) -> datetime:
        try:
            value = self._clock()
            _timestamp(value)
            return value.astimezone(timezone.utc)
        except ResearchMandateAuthorityError:
            raise
        except Exception:
            _deny()

    def _open(self, *, allow_create: bool) -> sqlite3.Connection:
        created = False
        try:
            metadata = os.lstat(self._database)
        except FileNotFoundError:
            if not allow_create:
                _deny()
            try:
                descriptor = os.open(
                    self._database,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
                os.close(descriptor)
                created = True
                metadata = os.lstat(self._database)
            except OSError:
                _deny()
        except OSError:
            _deny()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISREG(metadata.st_mode)
            or (os.name == "posix" and stat.S_IMODE(metadata.st_mode) != 0o600)
        ):
            _deny()
        try:
            connection = sqlite3.connect(
                self._database,
                timeout=30.0,
                isolation_level=None,
            )
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA trusted_schema = OFF")
            connection.execute("PRAGMA synchronous = FULL")
            if created:
                connection.executescript(_CREATE_SCHEMA)
                connection.executemany(
                    "INSERT INTO metadata (key, value) VALUES (?, ?)",
                    (
                        ("schema_digest", _SCHEMA_DIGEST),
                        ("schema_version", "1"),
                    ),
                )
            return connection
        except (OSError, sqlite3.Error):
            _deny()

    def _validate_store(self, connection: sqlite3.Connection) -> None:
        try:
            if connection.execute("PRAGMA journal_mode").fetchone() != ("delete",):
                _deny()
            if connection.execute("PRAGMA synchronous").fetchone() != (2,):
                _deny()
            if connection.execute("PRAGMA user_version").fetchone() != (1,):
                _deny()
            if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                _deny()
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            if tables != {"metadata", "mandates"}:
                _deny()
            if connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('view', 'trigger')"
            ).fetchall():
                _deny()
            metadata = connection.execute(
                "SELECT key, value FROM metadata ORDER BY key"
            ).fetchall()
            if metadata != [
                ("schema_digest", _SCHEMA_DIGEST),
                ("schema_version", "1"),
            ]:
                _deny()
            columns = tuple(
                row[1] for row in connection.execute("PRAGMA table_info(mandates)")
            )
            if columns != _ROW_FIELDS:
                _deny()
            for selected in connection.execute(
                f"SELECT {','.join(_ROW_FIELDS)} FROM mandates"
            ):
                _validate_row(dict(zip(_ROW_FIELDS, selected, strict=True)))
        except ResearchMandateAuthorityError:
            raise
        except Exception:
            _deny()

    class _Transaction:
        def __init__(
            self,
            guard: ResearchMandateAuthorityGuard,
            allow_create: bool,
        ) -> None:
            self.guard = guard
            self.allow_create = allow_create
            self.connection: sqlite3.Connection | None = None

        def __enter__(self) -> sqlite3.Connection:
            self.connection = self.guard._open(allow_create=self.allow_create)
            try:
                self.connection.execute("BEGIN IMMEDIATE")
                self.guard._validate_store(self.connection)
                return self.connection
            except Exception:
                self.connection.rollback()
                self.connection.close()
                raise

        def __exit__(self, exception_type, exception, traceback) -> bool:
            assert self.connection is not None
            try:
                if exception_type is None:
                    self.connection.commit()
                else:
                    self.connection.rollback()
            except sqlite3.Error:
                self.connection.close()
                _deny()
            self.connection.close()
            return False

    def _transaction(self, *, allow_create: bool) -> _Transaction:
        return self._Transaction(self, allow_create)
