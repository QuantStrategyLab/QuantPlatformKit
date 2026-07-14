"""Pure R1-S2 capability/request contracts.

This foundation is intentionally not wired into the runtime orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class CapabilityError(ValueError):
    """Raised when a request is not explicitly supported by a capability contract."""


class ExecutionTiming(str, Enum):
    NEXT_OPEN = "next_open"
    NEXT_CLOSE = "next_close"


class PersistMode(str, Enum):
    DURABLE = "durable"
    EPHEMERAL = "ephemeral"


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class BacktestCapabilities:
    """Versioned, explicit capabilities declared by a runner adapter."""

    contract_version: int = field(default=1, kw_only=True)
    execution_timings: frozenset[ExecutionTiming] = field(default_factory=frozenset, kw_only=True)
    ephemeral: bool = field(default=False, kw_only=True)
    persist_modes: frozenset[PersistMode] = field(
        default_factory=lambda: frozenset({PersistMode.DURABLE}), kw_only=True
    )


@dataclass(frozen=True)
class BacktestRequest:
    """Immutable request used by a future capability-aware adapter boundary."""

    profile: str = field(kw_only=True)
    params: Mapping[str, Any] = field(kw_only=True)
    execution_timing: ExecutionTiming | None = field(default=None, kw_only=True)
    persist_mode: PersistMode = field(default=PersistMode.DURABLE, kw_only=True)
    contract_version: int = field(default=1, kw_only=True)

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile", str(self.profile).strip())
        object.__setattr__(self, "params", _freeze(dict(self.params)))
        object.__setattr__(self, "execution_timing", _coerce_timing(self.execution_timing))
        object.__setattr__(self, "persist_mode", PersistMode(self.persist_mode))


class LegacyCapabilityAdapter:
    """Pure declaration for legacy durable/no-timing runners."""

    @staticmethod
    def capabilities() -> BacktestCapabilities:
        return BacktestCapabilities()


def _coerce_timing(value: ExecutionTiming | str | None) -> ExecutionTiming | None:
    return None if value is None else ExecutionTiming(value)


def validate_capability(request: BacktestRequest, capabilities: BacktestCapabilities) -> None:
    """Fail closed unless every requested semantic is explicitly declared."""
    if request.contract_version != capabilities.contract_version:
        raise CapabilityError("contract_version is not supported")
    if request.execution_timing is not None and request.execution_timing not in capabilities.execution_timings:
        raise CapabilityError("execution_timing is not explicitly supported")
    if request.persist_mode is PersistMode.EPHEMERAL and not capabilities.ephemeral:
        raise CapabilityError("ephemeral execution is not explicitly supported")
    if request.persist_mode is PersistMode.DURABLE and request.persist_mode not in capabilities.persist_modes:
        raise CapabilityError(f"persist_mode={request.persist_mode.value} is not supported")


def canonical_profile_id(profile: str) -> str:
    """Pure fixture normalization for the two R1 profiles; no runtime routing."""
    aliases = {
        "SOXL": "SOXL",
        "SOXL_SOXX_TREND_INCOME": "SOXL",
        "TQQQ": "TQQQ",
        "TQQQ_GROWTH_INCOME": "TQQQ",
    }
    try:
        return aliases[str(profile).strip().upper()]
    except KeyError as exc:
        raise CapabilityError(f"unsupported canonical profile: {profile}") from exc


def serialize_request(request: BacktestRequest) -> dict[str, Any]:
    """Return a deterministic, side-effect-free contract fixture."""
    return {
        "contract_version": request.contract_version,
        "profile": request.profile,
        "params": _thaw(request.params),
        "execution_timing": request.execution_timing.value if request.execution_timing else None,
        "persist_mode": request.persist_mode.value,
    }
