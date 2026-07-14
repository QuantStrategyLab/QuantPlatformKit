"""Clean-slate qpk-vnext/result/v2 JSON contract; no legacy or I/O fallback.

Identity fields are namespace/schema, domain, canonical_profile, execution_timing,
result_identity_version, strategy_id, run_id, param_set_id, param_version,
source_revision, and canonical params. persist_mode and computed_at are wire-only
metadata. Higher layers own profile allowlists and persistence side effects.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

MAX_SAFE_JSON_INTEGER = 2**53 - 1
NAMESPACE = "qpk-vnext/result/v2"
SCHEMA = "qpk.vnext.result.v2"
_MAX_SEGMENT = 100
_MAX_DEPTH = 16
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
_FIELDS = frozenset({"namespace", "schema_version", "domain", "canonical_profile", "execution_timing", "result_identity_version", "persist_mode", "strategy_id", "run_id", "param_set_id", "param_version", "source_revision", "computed_at", "params", "identity_digest", "wire_digest"})


class VNextContractError(ValueError):
    def __init__(self) -> None:
        super().__init__("invalid qpk-vnext result contract")


def _unicode(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise VNextContractError() from None
    return value


def _segment(value: Any, *, uppercase: bool = False) -> str:
    if not isinstance(value, str) or not value or len(value) > _MAX_SEGMENT or value != value.strip() or value != value.strip("-._"):
        raise VNextContractError()
    _unicode(value)
    if value in {".", ".."} or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for c in value):
        raise VNextContractError()
    if uppercase and value != value.upper():
        raise VNextContractError()
    return value


def _integer(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > MAX_SAFE_JSON_INTEGER:
        raise VNextContractError()
    return value


def _freeze(value: Any, depth: int = 0, *, wire: bool = False) -> Any:
    if depth > _MAX_DEPTH or value is None:
        raise VNextContractError()
    if isinstance(value, str):
        _unicode(value)
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_JSON_INTEGER:
            raise VNextContractError()
        return value
    if isinstance(value, float):
        raise VNextContractError()
    if isinstance(value, tuple) or (wire and isinstance(value, list)):
        return tuple(_freeze(item, depth + 1, wire=wire) for item in value)
    raise VNextContractError()


def _params(value: Any, *, wire: bool = False) -> MappingProxyType:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) or not key for key in value):
        raise VNextContractError()
    for key in value:
        _unicode(key)
    return MappingProxyType({key: _freeze(value[key], wire=wire) for key in sorted(value)})


def _thaw(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _json(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (UnicodeEncodeError, ValueError):
        raise VNextContractError() from None


def _hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


def _timestamp(value: Any) -> str:
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value):
        raise VNextContractError()
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise VNextContractError() from exc
    return value


@dataclass(frozen=True)
class VNextResult:
    domain: str
    canonical_profile: str
    execution_timing: str
    result_identity_version: int
    persist_mode: str
    strategy_id: str
    run_id: str
    param_set_id: str
    param_version: int
    source_revision: str
    computed_at: str
    params: Mapping[str, Any]

    def __post_init__(self) -> None:
        _segment(self.domain)
        _segment(self.canonical_profile, uppercase=True)
        if self.execution_timing not in {"next_open", "next_close"} or self.persist_mode not in {"durable", "ephemeral"}:
            raise VNextContractError()
        for value in (self.strategy_id, self.run_id, self.param_set_id, self.source_revision):
            _segment(value)
        object.__setattr__(self, "result_identity_version", _integer(self.result_identity_version))
        object.__setattr__(self, "param_version", _integer(self.param_version))
        object.__setattr__(self, "computed_at", _timestamp(self.computed_at))
        object.__setattr__(self, "params", _params(self.params))

    def _identity(self) -> dict[str, Any]:
        return {"namespace": NAMESPACE, "schema_version": SCHEMA, "domain": self.domain, "canonical_profile": self.canonical_profile, "execution_timing": self.execution_timing, "result_identity_version": self.result_identity_version, "strategy_id": self.strategy_id, "run_id": self.run_id, "param_set_id": self.param_set_id, "param_version": self.param_version, "source_revision": self.source_revision, "params": {key: _thaw(self.params[key]) for key in sorted(self.params)}}

    def _wire_payload(self) -> dict[str, Any]:
        return {**self._identity(), "persist_mode": self.persist_mode, "computed_at": self.computed_at}

    def to_wire(self) -> dict[str, Any]:
        payload = self._wire_payload()
        return {**payload, "identity_digest": _hash(self._identity()), "wire_digest": _hash(payload)}

    @property
    def key(self) -> str:
        return f"{NAMESPACE}/{self.domain}/{self.canonical_profile}/{self.strategy_id}/{self.run_id}/{self.execution_timing}/i{self.result_identity_version}/p{self.param_version}/{_hash(self._identity())}.json"


def decode_wire(data: Mapping[str, Any]) -> VNextResult:
    try:
        if not isinstance(data, Mapping) or set(data) != _FIELDS or data["namespace"] != NAMESPACE or data["schema_version"] != SCHEMA:
            raise VNextContractError()
        params = _params(data["params"], wire=True)
        item = VNextResult(domain=data["domain"], canonical_profile=data["canonical_profile"], execution_timing=data["execution_timing"], result_identity_version=data["result_identity_version"], persist_mode=data["persist_mode"], strategy_id=data["strategy_id"], run_id=data["run_id"], param_set_id=data["param_set_id"], param_version=data["param_version"], source_revision=data["source_revision"], computed_at=data["computed_at"], params=params)
        if data["identity_digest"] != _hash(item._identity()) or data["wire_digest"] != _hash(item._wire_payload()) or item.to_wire() != dict(data):
            raise VNextContractError()
        return item
    except VNextContractError:
        raise
    except Exception as exc:
        raise VNextContractError() from exc
