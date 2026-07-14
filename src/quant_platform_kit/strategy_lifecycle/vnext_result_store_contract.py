"""Strict side-by-side vNext result/store contract foundation.

Pure validation and deterministic wire/key generation only; this module performs
no store, cache, publish, runner, or filesystem I/O and never reads legacy data.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from quant_platform_kit.strategy_lifecycle.capabilities import ExecutionTiming, PersistMode

VNEXT_NAMESPACE = "qpk-vnext/result/v1"
_SCHEMA_VERSION = "qpk.vnext.result.v1"
_MAX_SEGMENT = 100
_PROFILES = frozenset({"SOXL", "TQQQ"})
_WIRE_FIELDS = frozenset({
    "namespace", "schema_version", "domain", "canonical_profile", "execution_timing",
    "result_identity_version", "persist_mode", "strategy_id", "run_id", "param_set_id",
    "param_version", "computed_at", "source_revision", "params", "identity_digest",
})


class VNextContractError(ValueError):
    """Sanitized validation error for all vNext contract failures."""

    def __init__(self) -> None:
        super().__init__("invalid vNext result/store contract")


def _segment(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > _MAX_SEGMENT:
        raise VNextContractError()
    if value in {".", ".."} or "/" in value or "\\" in value or value.startswith("/"):
        raise VNextContractError()
    if value != value.strip() or value != value.strip("-._"):
        raise VNextContractError()
    if any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for char in value):
        raise VNextContractError()
    return value


def _param_value(value: Any) -> Any:
    if value is None:
        raise VNextContractError()
    if isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    if isinstance(value, tuple):
        return [_param_value(item) for item in value]
    raise VNextContractError()


def _params(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) or not key for key in value):
        raise VNextContractError()
    return {key: _param_value(value[key]) for key in sorted(value)}


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > _MAX_SEGMENT:
        raise VNextContractError()
    if any(ord(char) < 32 or char in "/\\" for char in value):
        raise VNextContractError()
    return value


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


@dataclass(frozen=True)
class VNextResultContract:
    domain: str
    canonical_profile: str
    execution_timing: ExecutionTiming
    result_identity_version: int
    persist_mode: PersistMode
    strategy_id: str
    run_id: str
    param_set_id: str
    param_version: int
    computed_at: str
    source_revision: str
    params: Mapping[str, Any]

    def __post_init__(self) -> None:
        _segment(self.domain)
        if self.canonical_profile not in _PROFILES:
            raise VNextContractError()
        try:
            object.__setattr__(self, "execution_timing", ExecutionTiming(self.execution_timing))
            object.__setattr__(self, "persist_mode", PersistMode(self.persist_mode))
        except Exception as exc:
            raise VNextContractError() from exc
        for value in (self.strategy_id, self.run_id, self.param_set_id, self.source_revision):
            _segment(value)
        if not isinstance(self.result_identity_version, int) or isinstance(self.result_identity_version, bool) or self.result_identity_version < 1:
            raise VNextContractError()
        if not isinstance(self.param_version, int) or isinstance(self.param_version, bool) or self.param_version < 1:
            raise VNextContractError()
        _text(self.computed_at)
        object.__setattr__(self, "params", MappingProxyType(_params(self.params)))

    def _payload(self) -> dict[str, Any]:
        return {
            "namespace": VNEXT_NAMESPACE,
            "schema_version": _SCHEMA_VERSION,
            "domain": self.domain,
            "canonical_profile": self.canonical_profile,
            "execution_timing": self.execution_timing.value,
            "result_identity_version": self.result_identity_version,
            "persist_mode": self.persist_mode.value,
            "strategy_id": self.strategy_id,
            "run_id": self.run_id,
            "param_set_id": self.param_set_id,
            "param_version": self.param_version,
            "computed_at": self.computed_at,
            "source_revision": self.source_revision,
            "params": dict(self.params),
        }

    def to_wire(self) -> dict[str, Any]:
        payload = self._payload()
        return {**payload, "identity_digest": _digest(payload)}

    @property
    def key(self) -> str:
        return f"{VNEXT_NAMESPACE}/{self.domain}/{self.canonical_profile}/{self.strategy_id}/{self.run_id}/{self.execution_timing.value}/i{self.result_identity_version}/p{self.param_version}/{_digest(self._payload())}.json"


def decode_vnext_wire(data: Mapping[str, Any]) -> VNextResultContract:
    try:
        if not isinstance(data, Mapping) or set(data) != _WIRE_FIELDS:
            raise VNextContractError()
        if data["namespace"] != VNEXT_NAMESPACE or data["schema_version"] != _SCHEMA_VERSION:
            raise VNextContractError()
        payload = {key: data[key] for key in _WIRE_FIELDS if key != "identity_digest"}
        if not isinstance(data["identity_digest"], str) or _digest(payload) != data["identity_digest"]:
            raise VNextContractError()
        contract = VNextResultContract(
            domain=data["domain"], canonical_profile=data["canonical_profile"],
            execution_timing=data["execution_timing"], result_identity_version=data["result_identity_version"],
            persist_mode=data["persist_mode"], strategy_id=data["strategy_id"], run_id=data["run_id"],
            param_set_id=data["param_set_id"], param_version=data["param_version"],
            computed_at=data["computed_at"], source_revision=data["source_revision"], params=data["params"],
        )
        if contract.to_wire() != dict(data):
            raise VNextContractError()
        return contract
    except VNextContractError:
        raise
    except Exception as exc:
        raise VNextContractError() from exc
