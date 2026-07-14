"""Descriptor-relative local store for the clean-slate qpk-vnext/result/v2 contract."""
from __future__ import annotations

import errno
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from quant_platform_kit.strategy_lifecycle.qpk_vnext_n1 import (
    NAMESPACE, ContractError, ResultContract, _segment, decode_wire,
)


class StoreError(ValueError):
    """Sanitized isolated-store failure."""


def _fail() -> None:
    raise StoreError("invalid qpk-vnext isolated store operation")


class IsolatedResultStore:
    """Filesystem store using descriptor-relative, no-follow operations only."""

    _DIR_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    _FILE_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)

    def __init__(self, root: str | os.PathLike[str]) -> None:
        if not isinstance(root, (str, os.PathLike)) or not os.name == "posix":
            _fail()
        self.root = Path(root).expanduser()
        if not self.root.is_absolute():
            _fail()

    @staticmethod
    def _fsync(fd: int) -> None:
        try:
            os.fsync(fd)
        except OSError:
            _fail()

    def _root_fd(self) -> int:
        try:
            current = os.open("/", self._DIR_FLAGS)
            for part in self.root.parts[1:]:
                child = os.open(part, self._DIR_FLAGS, dir_fd=current)
                os.close(current)
                current = child
            return current
        except OSError:
            try:
                os.close(current)
            except (OSError, UnboundLocalError):
                pass
            _fail()

    @staticmethod
    def _read_regular(fd: int, limit: int = 10_000_000) -> bytes:
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                _fail()
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(fd, min(1_048_576, limit - total + 1))
                if not chunk:
                    return b"".join(chunks)
                chunks.append(chunk)
                total += len(chunk)
                if total > limit:
                    _fail()
        except OSError:
            _fail()

    @staticmethod
    def _validate_key(key: str) -> list[str]:
        if not isinstance(key, str) or "\\" in key:
            _fail()
        parts = key.split("/")
        if len(parts) != 11 or parts[:3] != NAMESPACE.split("/") or not parts[-1].endswith(".json"):
            _fail()
        if any(not part or part in {".", ".."} for part in parts):
            _fail()
        for part in parts[3:-1]:
            try:
                _segment(part.removeprefix("i").removeprefix("p") if part[:1] in {"i", "p"} else part)
            except ContractError:
                _fail()
        return parts

    @classmethod
    def _open_child_dir(cls, parent: int, name: str, *, create: bool, created: list[int]) -> int:
        try:
            return os.open(name, cls._DIR_FLAGS, dir_fd=parent)
        except FileNotFoundError:
            if not create:
                _fail()
            try:
                os.mkdir(name, mode=0o700, dir_fd=parent)
                cls._fsync(parent)
            except FileExistsError:
                pass
            except OSError:
                _fail()
            try:
                child = os.open(name, cls._DIR_FLAGS, dir_fd=parent)
            except OSError:
                _fail()
            created.append(child)
            return child
        except OSError:
            _fail()

    @classmethod
    def _walk(cls, root_fd: int, parts: list[str], *, create: bool) -> tuple[int, list[int]]:
        current = root_fd
        opened: list[int] = []
        for part in parts:
            current = cls._open_child_dir(current, part, create=create, created=opened)
        return current, opened

    @staticmethod
    def _wire_bytes(contract: ResultContract) -> bytes:
        if not isinstance(contract, ResultContract) or contract.persist_mode != "durable":
            _fail()
        try:
            checked = decode_wire(contract.to_wire())
            return json.dumps(checked.to_wire(), ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"), allow_nan=False).encode("utf-8")
        except (ContractError, TypeError, ValueError, UnicodeError):
            _fail()

    def put(self, contract: ResultContract) -> str:
        payload = self._wire_bytes(contract)
        parts = self._validate_key(contract.key)
        root_fd = self._root_fd()
        parent_fd = None
        created: list[int] = []
        temp_name: str | None = None
        try:
            parent_fd, created = self._walk(root_fd, parts[:-1], create=True)
            target = parts[-1]
            try:
                existing_fd = os.open(target, self._FILE_FLAGS, dir_fd=parent_fd)
            except FileNotFoundError:
                existing_fd = None
            except OSError:
                _fail()
            if existing_fd is not None:
                try:
                    existing = self._read_regular(existing_fd, len(payload))
                finally:
                    os.close(existing_fd)
                if existing == payload:
                    return "idempotent"
                _fail()
            for _ in range(8):
                candidate = f".{target}.{os.getpid()}.{next(tempfile._RandomNameSequence())}.tmp"
                try:
                    fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=parent_fd)
                    temp_name = candidate
                    break
                except FileExistsError:
                    continue
                except OSError:
                    _fail()
            else:
                _fail()
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temp_name, target, src_dir_fd=parent_fd, dst_dir_fd=parent_fd, follow_symlinks=False)
            except FileExistsError:
                try:
                    existing_fd = os.open(target, self._FILE_FLAGS, dir_fd=parent_fd)
                    existing = self._read_regular(existing_fd, len(payload))
                    os.close(existing_fd)
                except OSError:
                    _fail()
                if existing != payload:
                    _fail()
                return "idempotent"
            self._fsync(parent_fd)
            for fd in reversed(created):
                self._fsync(fd)
            os.unlink(temp_name, dir_fd=parent_fd)
            temp_name = None
            self._fsync(parent_fd)
            return "created"
        except (OSError, ValueError):
            _fail()
        finally:
            if temp_name and parent_fd is not None:
                try:
                    os.unlink(temp_name, dir_fd=parent_fd)
                except OSError:
                    pass
            for fd in reversed(created):
                try:
                    os.close(fd)
                except OSError:
                    pass
            os.close(root_fd)

    def get(self, key: str) -> ResultContract:
        parts = self._validate_key(key)
        root_fd = self._root_fd()
        parent_fd = None
        try:
            parent_fd, opened = self._walk(root_fd, parts[:-1], create=False)
            fd = os.open(parts[-1], self._FILE_FLAGS, dir_fd=parent_fd)
            try:
                data: Any = json.loads(self._read_regular(fd).decode("utf-8"))
            finally:
                os.close(fd)
            item = decode_wire(data)
            if item.key != key:
                _fail()
            return item
        except (OSError, UnicodeError, json.JSONDecodeError, ContractError):
            _fail()
        finally:
            for fd in reversed(opened if 'opened' in locals() else []):
                os.close(fd)
            os.close(root_fd)

    def list_keys(self, *, domain: str, profile: str, timing: str) -> tuple[str, ...]:
        try:
            domain, profile = _segment(domain), _segment(profile)
        except ContractError:
            _fail()
        if timing not in {"next_open", "next_close"}:
            _fail()
        root_fd = self._root_fd()
        profile_fd = None
        try:
            profile_fd, opened = self._walk(root_fd, NAMESPACE.split("/") + [domain, profile], create=False)
            found: list[str] = []

            def scan(fd: int, rel: list[str]) -> None:
                try:
                    names = os.listdir(fd)
                except OSError:
                    _fail()
                for name in names:
                    if not name or name in {".", ".."}:
                        continue
                    try:
                        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    except OSError:
                        _fail()
                    if stat.S_ISLNK(info.st_mode):
                        _fail()
                    if stat.S_ISDIR(info.st_mode):
                        child = os.open(name, self._DIR_FLAGS, dir_fd=fd)
                        try:
                            scan(child, rel + [name])
                        finally:
                            os.close(child)
                    elif name.endswith(".json"):
                        key = "/".join(NAMESPACE.split("/") + [domain, profile] + rel + [name])
                        parts = self._validate_key(key)
                        if parts[7] != timing:
                            continue
                        item = self.get(key)
                        found.append(item.key)

            scan(profile_fd, [])
            return tuple(sorted(set(found)))
        finally:
            for fd in reversed(opened if 'opened' in locals() else []):
                os.close(fd)
            os.close(root_fd)
