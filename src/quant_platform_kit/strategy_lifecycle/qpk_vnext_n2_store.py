"""Filesystem-only store for the clean-slate qpk-vnext/result/v2 contract.

This module deliberately has no legacy fallback, listing-by-latest semantics,
cloud client, or caller integration.  Keys are validated and contained below
the explicitly supplied root before any filesystem operation.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from quant_platform_kit.strategy_lifecycle.qpk_vnext_n1 import (
    NAMESPACE,
    ContractError,
    ResultContract,
    decode_wire,
)


class StoreError(ValueError):
    """Sanitized isolated-store failure."""


def _fail() -> None:
    raise StoreError("invalid qpk-vnext isolated store operation")


class IsolatedResultStore:
    """Write-once local store rooted at an explicit directory."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        if not isinstance(root, (str, os.PathLike)):
            _fail()
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_absolute():
            _fail()

    def _path_for_key(self, key: str) -> Path:
        if not isinstance(key, str) or not key or "\\" in key:
            _fail()
        parts = key.split("/")
        if len(parts) != 11 or parts[:3] != NAMESPACE.split("/") or not parts[-1].endswith(".json"):
            _fail()
        if any(not part or part in {".", ".."} for part in parts):
            _fail()
        candidate = (self.root.joinpath(*parts)).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            _fail()
        return candidate

    @staticmethod
    def _bytes(contract: ResultContract) -> bytes:
        if contract.persist_mode != "durable":
            _fail()
        try:
            wire = contract.to_wire()
            checked = decode_wire(wire)
            return json.dumps(checked.to_wire(), ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"), allow_nan=False).encode("utf-8")
        except (ContractError, TypeError, ValueError, UnicodeError):
            _fail()

    def put(self, contract: ResultContract) -> str:
        """Atomically create the contract; repeat identical writes are no-ops."""
        if not isinstance(contract, ResultContract):
            _fail()
        payload = self._bytes(contract)
        path = self._path_for_key(contract.key)
        if path.exists():
            try:
                existing = path.read_bytes()
            except OSError:
                _fail()
            if existing == payload:
                return "idempotent"
            _fail()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            temporary = None
            return "created"
        except (OSError, ValueError):
            _fail()
        finally:
            if temporary:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    def get(self, key: str) -> ResultContract:
        path = self._path_for_key(key)
        if not path.is_file():
            _fail()
        try:
            data: Any = json.loads(path.read_text(encoding="utf-8"))
            contract = decode_wire(data)
        except (OSError, UnicodeError, json.JSONDecodeError, ContractError):
            _fail()
        if contract.key != key:
            _fail()
        return contract

    def list_keys(self, *, domain: str, profile: str, timing: str) -> tuple[str, ...]:
        """List exact selector matches; no implicit latest or legacy scan."""
        prefix = f"{NAMESPACE}/{domain}/{profile}/"
        base = (self.root / NAMESPACE / domain / profile).resolve()
        try:
            base.relative_to(self.root)
        except ValueError:
            _fail()
        if not base.is_dir():
            return ()
        found: list[str] = []
        for path in base.rglob("*.json"):
            try:
                key = path.resolve().relative_to(self.root).as_posix()
                if f"/{timing}/" in key:
                    found.append(key)
            except ValueError:
                continue
        return tuple(sorted(found))
