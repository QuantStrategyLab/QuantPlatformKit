"""Typed runtime-control contract shared by every broker platform.

This module is intentionally *not* wired into any runtime yet.  It defines a
single, broker-neutral description of how a deployed runtime target is
controlled (on/off switch, execution mode, cash policy and a reference to the
reviewed risk-limit policy) together with one resolver that has a fixed,
documented precedence:

1. Safe code defaults (``RuntimeControl.safe_default``): disabled, dry-run,
   cash-only, no reserve beyond the strategy default.
2. A reviewed per-target document (for example a QuantRuntimeSettings target
   file rendered into ``RUNTIME_CONTROL_JSON``).
3. Emergency overrides that may only *tighten* the result (disable, move to a
   safer mode, force cash-only, raise the reserve).  An override that tries to
   loosen a control raises ``RuntimeControlError`` instead of being applied.

All boolean and enum inputs are parsed strictly: an unrecognised value raises
rather than silently falling back to a less safe behaviour.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Mapping

RUNTIME_CONTROL_SCHEMA_VERSION = "qsl.runtime_control.v1"
RUNTIME_CONTROL_ENV = "RUNTIME_CONTROL_JSON"
EMERGENCY_ENABLED_ENV = "RUNTIME_TARGET_ENABLED"
EMERGENCY_MODE_ENV = "RUNTIME_CONTROL_MODE_OVERRIDE"

_TRUE_VALUES = frozenset({"1", "true", "yes", "y", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "n", "off"})


class RuntimeControlError(ValueError):
    """Raised when runtime-control input is malformed or would loosen a control."""


class RuntimeMode(str, Enum):
    """Execution mode ordered from most permissive to safest."""

    LIVE = "live"
    PAPER = "paper"
    DRY_RUN = "dry_run"

    @property
    def safety_rank(self) -> int:
        """Higher rank means fewer real-world side effects."""
        return {RuntimeMode.LIVE: 0, RuntimeMode.PAPER: 1, RuntimeMode.DRY_RUN: 2}[self]

    @property
    def submits_live_orders(self) -> bool:
        return self is RuntimeMode.LIVE

    @classmethod
    def parse(cls, raw: Any, *, name: str = "mode") -> "RuntimeMode":
        text = str(raw if raw is not None else "").strip().lower()
        for member in cls:
            if member.value == text:
                return member
        raise RuntimeControlError(f"{name} must be one of live, paper, dry_run; got {raw!r}")


def parse_strict_bool(raw: Any, *, name: str) -> bool:
    """Parse a boolean flag, raising on empty or unrecognised input.

    Safety flags must never treat a typo or an empty string as ``False``.
    """
    if isinstance(raw, bool):
        return raw
    text = str(raw if raw is not None else "").strip().lower()
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    raise RuntimeControlError(f"{name} must be a boolean (true/false); got {raw!r}")


def parse_optional_strict_bool(raw: Any, *, name: str) -> bool | None:
    """Like ``parse_strict_bool`` but returns ``None`` when the value is unset."""
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None
    return parse_strict_bool(raw, name=name)


def _parse_ratio(raw: Any, *, name: str) -> float:
    if isinstance(raw, bool):
        raise RuntimeControlError(f"{name} must be a number in [0, 1]; got {raw!r}")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeControlError(f"{name} must be a number in [0, 1]; got {raw!r}") from exc
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise RuntimeControlError(f"{name} must be a number in [0, 1]; got {raw!r}")
    return value


def _parse_non_negative(raw: Any, *, name: str) -> float:
    if isinstance(raw, bool):
        raise RuntimeControlError(f"{name} must be a non-negative number; got {raw!r}")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeControlError(f"{name} must be a non-negative number; got {raw!r}") from exc
    if not math.isfinite(value) or value < 0.0:
        raise RuntimeControlError(f"{name} must be a non-negative number; got {raw!r}")
    return value


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    text = str(payload.get(key) or "").strip()
    if not text:
        raise RuntimeControlError(f"runtime control field {key!r} is required")
    return text


@dataclass(frozen=True)
class CashPolicy:
    """Cash handling for one runtime target.

    The effective reserve is ``max(reserved_cash_floor_usd, equity * reserved_cash_ratio)``
    and is combined with the strategy default using ``max`` so configuration can
    only raise, never lower, the strategy's own reserve.
    """

    cash_only: bool = True
    reserved_cash_ratio: float = 0.0
    reserved_cash_floor_usd: float = 0.0

    def __post_init__(self) -> None:
        if type(self.cash_only) is not bool:
            raise RuntimeControlError("cash_policy.cash_only must be a bool")
        _parse_ratio(self.reserved_cash_ratio, name="cash_policy.reserved_cash_ratio")
        _parse_non_negative(self.reserved_cash_floor_usd, name="cash_policy.reserved_cash_floor_usd")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "CashPolicy":
        payload = payload or {}
        if not isinstance(payload, Mapping):
            raise RuntimeControlError("cash_policy must be an object")
        unknown = set(payload) - {"cash_only", "reserved_cash_ratio", "reserved_cash_floor_usd"}
        if unknown:
            raise RuntimeControlError(f"cash_policy has unknown fields: {sorted(unknown)}")
        return cls(
            cash_only=parse_strict_bool(payload.get("cash_only", True), name="cash_policy.cash_only"),
            reserved_cash_ratio=_parse_ratio(
                payload.get("reserved_cash_ratio", 0.0), name="cash_policy.reserved_cash_ratio"
            ),
            reserved_cash_floor_usd=_parse_non_negative(
                payload.get("reserved_cash_floor_usd", 0.0), name="cash_policy.reserved_cash_floor_usd"
            ),
        )

    def effective_reserve_ratio(self, strategy_default_ratio: float = 0.0) -> float:
        """Combine with a strategy default; configuration can only raise the reserve."""
        return max(self.reserved_cash_ratio, _parse_ratio(strategy_default_ratio, name="strategy_default_ratio"))

    def reserved_cash_usd(self, total_equity: float, strategy_default_ratio: float = 0.0) -> float:
        equity = max(0.0, float(total_equity or 0.0))
        return max(self.reserved_cash_floor_usd, equity * self.effective_reserve_ratio(strategy_default_ratio))

    def to_dict(self) -> dict[str, Any]:
        return {
            "cash_only": self.cash_only,
            "reserved_cash_ratio": self.reserved_cash_ratio,
            "reserved_cash_floor_usd": self.reserved_cash_floor_usd,
        }


@dataclass(frozen=True)
class RuntimeControl:
    """Broker-neutral control state for one deployed runtime target."""

    target_id: str
    platform_id: str
    strategy_profile: str
    enabled: bool = False
    mode: RuntimeMode = RuntimeMode.DRY_RUN
    cash_policy: CashPolicy = field(default_factory=CashPolicy)
    risk_limits_ref: str | None = None
    options_enabled: bool = False

    def __post_init__(self) -> None:
        for key in ("target_id", "platform_id", "strategy_profile"):
            if not str(getattr(self, key) or "").strip():
                raise RuntimeControlError(f"runtime control field {key!r} is required")
        if type(self.enabled) is not bool or type(self.options_enabled) is not bool:
            raise RuntimeControlError("enabled and options_enabled must be bools")
        if not isinstance(self.mode, RuntimeMode):
            raise RuntimeControlError("mode must be a RuntimeMode")

    @classmethod
    def safe_default(cls, *, target_id: str, platform_id: str, strategy_profile: str) -> "RuntimeControl":
        """The fail-closed baseline used before any configuration is applied."""
        return cls(target_id=target_id, platform_id=platform_id, strategy_profile=strategy_profile)

    @property
    def may_submit_live_orders(self) -> bool:
        return self.enabled and self.mode.submits_live_orders

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "RuntimeControl":
        if not isinstance(payload, Mapping):
            raise RuntimeControlError("runtime control must be an object")
        version = payload.get("schema_version", RUNTIME_CONTROL_SCHEMA_VERSION)
        if version != RUNTIME_CONTROL_SCHEMA_VERSION:
            raise RuntimeControlError(f"unsupported runtime control schema_version {version!r}")
        allowed = {
            "schema_version", "target_id", "platform_id", "strategy_profile", "enabled", "mode",
            "cash_policy", "risk_limits_ref", "options_enabled", "description",
        }
        unknown = set(payload) - allowed
        if unknown:
            raise RuntimeControlError(f"runtime control has unknown fields: {sorted(unknown)}")
        risk_ref = payload.get("risk_limits_ref")
        return cls(
            target_id=_required_text(payload, "target_id"),
            platform_id=_required_text(payload, "platform_id"),
            strategy_profile=_required_text(payload, "strategy_profile"),
            enabled=parse_strict_bool(payload.get("enabled", False), name="enabled"),
            mode=RuntimeMode.parse(payload.get("mode", RuntimeMode.DRY_RUN.value)),
            cash_policy=CashPolicy.from_mapping(payload.get("cash_policy")),
            risk_limits_ref=str(risk_ref).strip() if risk_ref not in (None, "") else None,
            options_enabled=parse_strict_bool(payload.get("options_enabled", False), name="options_enabled"),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": RUNTIME_CONTROL_SCHEMA_VERSION,
            "target_id": self.target_id,
            "platform_id": self.platform_id,
            "strategy_profile": self.strategy_profile,
            "enabled": self.enabled,
            "mode": self.mode.value,
            "cash_policy": self.cash_policy.to_dict(),
            "options_enabled": self.options_enabled,
        }
        if self.risk_limits_ref is not None:
            payload["risk_limits_ref"] = self.risk_limits_ref
        return payload


@dataclass(frozen=True)
class TighteningOverride:
    """An emergency override.  Every field may only make the target safer."""

    enabled: bool | None = None
    mode: RuntimeMode | None = None
    cash_only: bool | None = None
    reserved_cash_ratio: float | None = None
    source: str = "override"

    def apply(self, control: RuntimeControl) -> RuntimeControl:
        """Return a tightened copy of *control* or raise if this would loosen it."""
        result = control
        if self.enabled is not None:
            if self.enabled and not control.enabled:
                raise RuntimeControlError(f"{self.source} cannot enable a disabled target")
            result = replace(result, enabled=self.enabled)
        if self.mode is not None:
            if self.mode.safety_rank < control.mode.safety_rank:
                raise RuntimeControlError(
                    f"{self.source} cannot move mode from {control.mode.value} to {self.mode.value}"
                )
            result = replace(result, mode=self.mode)
        cash = result.cash_policy
        if self.cash_only is not None:
            if not self.cash_only and cash.cash_only:
                raise RuntimeControlError(f"{self.source} cannot disable cash-only execution")
            cash = replace(cash, cash_only=self.cash_only)
        if self.reserved_cash_ratio is not None:
            ratio = _parse_ratio(self.reserved_cash_ratio, name=f"{self.source}.reserved_cash_ratio")
            if ratio < cash.reserved_cash_ratio:
                raise RuntimeControlError(f"{self.source} cannot lower the reserved cash ratio")
            cash = replace(cash, reserved_cash_ratio=ratio)
        return replace(result, cash_policy=cash)


def resolve_runtime_control(
    *,
    target_id: str,
    platform_id: str,
    strategy_profile: str,
    document: Mapping[str, Any] | None = None,
    overrides: tuple[TighteningOverride, ...] = (),
) -> RuntimeControl:
    """Resolve the effective control with the documented precedence.

    ``document`` replaces the safe default as a whole (it is the reviewed source
    of truth) but must describe the same target, platform and profile.  Each
    override is then applied in order and may only tighten the result.
    """
    control = RuntimeControl.safe_default(
        target_id=target_id, platform_id=platform_id, strategy_profile=strategy_profile
    )
    if document is not None:
        reviewed = RuntimeControl.from_mapping(document)
        for key in ("target_id", "platform_id", "strategy_profile"):
            if getattr(reviewed, key) != getattr(control, key):
                raise RuntimeControlError(
                    f"runtime control {key} {getattr(reviewed, key)!r} does not match {getattr(control, key)!r}"
                )
        control = reviewed
    for override in overrides:
        control = override.apply(control)
    return control


def resolve_runtime_control_from_env(
    env: Mapping[str, str | None],
    *,
    target_id: str,
    platform_id: str,
    strategy_profile: str,
) -> RuntimeControl:
    """Resolve from ``RUNTIME_CONTROL_JSON`` plus tighten-only emergency env vars.

    ``RUNTIME_TARGET_ENABLED=false`` and ``RUNTIME_CONTROL_MODE_OVERRIDE`` act as
    emergency brakes.  Unset values are ignored; malformed values raise.
    """
    raw_document = str(env.get(RUNTIME_CONTROL_ENV) or "").strip()
    document: Mapping[str, Any] | None = None
    if raw_document:
        try:
            document = json.loads(raw_document)
        except json.JSONDecodeError as exc:
            raise RuntimeControlError(f"{RUNTIME_CONTROL_ENV} must contain valid JSON") from exc
    control = resolve_runtime_control(
        target_id=target_id,
        platform_id=platform_id,
        strategy_profile=strategy_profile,
        document=document,
    )
    enabled = parse_optional_strict_bool(env.get(EMERGENCY_ENABLED_ENV), name=EMERGENCY_ENABLED_ENV)
    raw_mode = str(env.get(EMERGENCY_MODE_ENV) or "").strip()
    override = TighteningOverride(
        # An emergency "true" never re-enables; it simply leaves the document value alone.
        enabled=False if enabled is False else None,
        mode=RuntimeMode.parse(raw_mode, name=EMERGENCY_MODE_ENV) if raw_mode else None,
        source="environment",
    )
    return override.apply(control)


__all__ = [
    "CashPolicy",
    "EMERGENCY_ENABLED_ENV",
    "EMERGENCY_MODE_ENV",
    "RUNTIME_CONTROL_ENV",
    "RUNTIME_CONTROL_SCHEMA_VERSION",
    "RuntimeControl",
    "RuntimeControlError",
    "RuntimeMode",
    "TighteningOverride",
    "parse_optional_strict_bool",
    "parse_strict_bool",
    "resolve_runtime_control",
    "resolve_runtime_control_from_env",
]
