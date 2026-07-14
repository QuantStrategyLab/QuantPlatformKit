"""Pure clean-slate qpk-vnext/result/v2 contract.

Identity subset (and only this subset) is namespace, schema_version, domain,
profile, timing, identity_version, strategy_id, run_id, param_set_id,
param_version, source_revision and canonical params.  persist_mode and
computed_at are wire metadata and never affect identity.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

MAX_SAFE_JSON_INTEGER = 2**53 - 1
NAMESPACE = "qpk-vnext/result/v2"
SCHEMA_VERSION = 2
_WIRE_FIELDS = frozenset({
    "namespace", "schema_version", "domain", "profile", "timing",
    "identity_version", "persist_mode", "strategy_id", "run_id",
    "param_set_id", "param_version", "source_revision", "computed_at",
    "params", "identity_digest", "wire_digest",
})
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
_TIMINGS = frozenset({"next_open", "next_close"})
_MODES = frozenset({"durable", "ephemeral"})
_MAX_DEPTH = 16
_MAX_SEQUENCE = 128


class ContractError(ValueError):
    """Sanitized contract validation failure."""


def _fail() -> None:
    raise ContractError("invalid qpk-vnext contract")


def _text(value: Any, *, bounded: bool = True) -> str:
    if not isinstance(value, str):
        _fail()
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        _fail()
    if any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        _fail()
    if bounded and (not value or len(value) > 256):
        _fail()
    return value


def _segment(value: Any) -> str:
    value = _text(value)
    if not _SAFE_SEGMENT.fullmatch(value) or value in {".", ".."}:
        _fail()
    return value


def _integer(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_SAFE_JSON_INTEGER:
        _fail()
    return value


def _timestamp(value: Any) -> str:
    value = _text(value)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z", value):
        _fail()
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        _fail()
    return value


def _freeze(value: Any, depth: int, *, wire: bool = False) -> Any:
    if depth > _MAX_DEPTH:
        _fail()
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_JSON_INTEGER:
            _fail()
        return value
    if isinstance(value, str):
        return _text(value)
    if isinstance(value, float) or value is None:
        _fail()
    if isinstance(value, tuple) or (wire and isinstance(value, list)):
        if len(value) > _MAX_SEQUENCE:
            _fail()
        return tuple(_freeze(item, depth + 1, wire=wire) for item in value)
    if isinstance(value, Mapping):
        _fail()
    _fail()


def _params(value: Any, *, wire: bool = False) -> MappingProxyType:
    if not isinstance(value, Mapping):
        _fail()
    if len(value) > _MAX_SEQUENCE:
        _fail()
    result: dict[str, Any] = {}
    for key, item in value.items():
        key = _text(key)
        result[key] = _freeze(item, 1, wire=wire)
    return MappingProxyType(dict(sorted(result.items())))


def _thaw(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    return value


def _canonical(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError):
        _fail()


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class ResultContract:
    domain: str
    profile: str
    timing: str
    identity_version: int
    persist_mode: str
    strategy_id: str
    run_id: str
    param_set_id: str
    param_version: int
    source_revision: str
    computed_at: str
    params: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "domain", _segment(self.domain))
        profile = _segment(self.profile)
        if profile != profile.upper():
            _fail()
        object.__setattr__(self, "profile", profile)
        if self.timing not in _TIMINGS or self.persist_mode not in _MODES:
            _fail()
        object.__setattr__(self, "identity_version", _integer(self.identity_version))
        object.__setattr__(self, "param_version", _integer(self.param_version))
        for name in ("strategy_id", "run_id"):
            object.__setattr__(self, name, _segment(getattr(self, name)))
        for name in ("param_set_id", "source_revision"):
            object.__setattr__(self, name, _text(getattr(self, name)))
        object.__setattr__(self, "computed_at", _timestamp(self.computed_at))
        object.__setattr__(self, "params", _params(self.params))

    def _identity(self) -> dict[str, Any]:
        return {
            "namespace": NAMESPACE, "schema_version": SCHEMA_VERSION,
            "domain": self.domain, "profile": self.profile, "timing": self.timing,
            "identity_version": self.identity_version, "strategy_id": self.strategy_id,
            "run_id": self.run_id, "param_set_id": self.param_set_id,
            "param_version": self.param_version, "source_revision": self.source_revision,
            "params": _thaw(self.params),
        }

    def to_wire(self) -> dict[str, Any]:
        payload = {**self._identity(), "persist_mode": self.persist_mode, "computed_at": self.computed_at}
        payload["identity_digest"] = _digest(self._identity())
        payload["wire_digest"] = _digest(payload)
        return payload

    @property
    def key(self) -> str:
        return "/".join((NAMESPACE, self.domain, self.profile, self.strategy_id,
                          self.run_id, self.timing, f"i{self.identity_version}",
                          f"p{self.param_version}", f"{_digest(self._identity())}.json"))


def decode_wire(data: Any) -> ResultContract:
    try:
        if not isinstance(data, Mapping) or set(data) != _WIRE_FIELDS:
            _fail()
        if data["namespace"] != NAMESPACE or data["schema_version"] != SCHEMA_VERSION:
            _fail()
        params = _params(data["params"], wire=True)
        item = ResultContract(domain=data["domain"], profile=data["profile"], timing=data["timing"],
                              identity_version=data["identity_version"], persist_mode=data["persist_mode"],
                              strategy_id=data["strategy_id"], run_id=data["run_id"],
                              param_set_id=data["param_set_id"], param_version=data["param_version"],
                              source_revision=data["source_revision"], computed_at=data["computed_at"], params=params)
        if data["identity_digest"] != _digest(item._identity()):
            _fail()
        expected = item.to_wire()
        if data != expected:
            _fail()
        return item
    except ContractError:
        raise
    except Exception:
        raise ContractError("invalid qpk-vnext contract") from None
