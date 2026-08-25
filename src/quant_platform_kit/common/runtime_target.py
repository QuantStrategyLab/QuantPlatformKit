from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, asdict
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .strategy_release import StrategyReleaseIdentity, build_strategy_release_identity


@dataclass(frozen=True)
class RuntimeTarget:
    platform_id: str
    strategy_profile: str
    dry_run_only: bool
    deployment_selector: str | None = None
    account_selector: tuple[str, ...] = ()
    account_scope: str | None = None
    service_name: str | None = None
    execution_windows: dict[str, Any] | None = None
    market: str | None = None
    market_calendar: str | None = None
    market_timezone: str | None = None
    scheduler: dict[str, Any] | None = None
    strategy_release: StrategyReleaseIdentity | None = None
    account_identity: dict[str, Any] | None = None

    @property
    def execution_mode(self) -> str:
        return "paper" if self.dry_run_only else "live"

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for field in (
            "market",
            "market_calendar",
            "market_timezone",
            "scheduler",
            "strategy_release",
            "account_identity",
        ):
            if payload.get(field) is None:
                payload.pop(field, None)
        payload["execution_mode"] = self.execution_mode
        return payload


def build_runtime_context_fields(
    extra_context_fields: Mapping[str, Any] | None = None,
    *,
    runtime_target: RuntimeTarget | None = None,
) -> dict[str, Any]:
    fields = dict(extra_context_fields or {})
    if runtime_target is not None:
        fields["runtime_target"] = runtime_target.to_dict()
    return fields


def _normalize_optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_account_selector(value: Iterable[str] | str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        normalized = _normalize_optional_string(value)
        return (normalized,) if normalized is not None else ()
    normalized: list[str] = []
    for item in value:
        text = _normalize_optional_string(item)
        if text is not None:
            normalized.append(text)
    return tuple(normalized)


def _normalize_market_metadata(
    *,
    market: str | None,
    market_calendar: str | None,
    market_timezone: str | None,
) -> tuple[str | None, str | None, str | None]:
    values = (
        _normalize_optional_string(market),
        _normalize_optional_string(market_calendar),
        _normalize_optional_string(market_timezone),
    )
    if any(values) and not all(values):
        raise ValueError(
            "market metadata must include market, market_calendar, and market_timezone together"
        )
    if values[2] is not None:
        try:
            ZoneInfo(values[2])
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"invalid market_timezone: {values[2]!r}") from exc
    return values


def build_runtime_target(
    *,
    platform_id: str,
    strategy_profile: str,
    dry_run_only: bool,
    deployment_selector: str | None = None,
    account_selector: Iterable[str] | str | None = None,
    account_scope: str | None = None,
    service_name: str | None = None,
    market: str | None = None,
    market_calendar: str | None = None,
    market_timezone: str | None = None,
    scheduler: Mapping[str, Any] | None = None,
    execution_windows: Mapping[str, Any] | None = None,
    strategy_release: StrategyReleaseIdentity | Mapping[str, object] | None = None,
    account_identity: Mapping[str, Any] | None = None,
) -> RuntimeTarget:
    normalized_market, normalized_calendar, normalized_timezone = _normalize_market_metadata(
        market=market,
        market_calendar=market_calendar,
        market_timezone=market_timezone,
    )
    return RuntimeTarget(
        platform_id=str(platform_id).strip(),
        strategy_profile=str(strategy_profile).strip(),
        dry_run_only=bool(dry_run_only),
        deployment_selector=_normalize_optional_string(deployment_selector),
        account_selector=_normalize_account_selector(account_selector),
        account_scope=_normalize_optional_string(account_scope),
        service_name=_normalize_optional_string(service_name),
        market=normalized_market,
        market_calendar=normalized_calendar,
        market_timezone=normalized_timezone,
        scheduler=dict(scheduler) if scheduler is not None else None,
        execution_windows=dict(execution_windows) if execution_windows is not None else None,
        strategy_release=(
            build_strategy_release_identity(strategy_release)
            if strategy_release is not None
            else None
        ),
        account_identity=dict(account_identity) if account_identity is not None else None,
    )


def _coerce_optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def resolve_runtime_target_from_env(
    *,
    env: Mapping[str, str | None],
    expected_platform_id: str | None = None,
) -> RuntimeTarget:
    raw_payload = _normalize_optional_string(
        env.get("QSL_RUNTIME_TARGET_JSON") or env.get("RUNTIME_TARGET_JSON")
    )
    if raw_payload is None:
        raise EnvironmentError("RUNTIME_TARGET_JSON (or QSL_RUNTIME_TARGET_JSON) is required")

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise ValueError("RUNTIME_TARGET_JSON must contain valid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("RUNTIME_TARGET_JSON must decode to an object")

    resolved_platform_id = _normalize_optional_string(payload.get("platform_id"))
    if resolved_platform_id is None:
        raise ValueError("RUNTIME_TARGET_JSON.platform_id is required")
    if expected_platform_id is not None and resolved_platform_id != expected_platform_id:
        raise ValueError(
            "RUNTIME_TARGET_JSON.platform_id does not match the runtime platform"
        )
    resolved_strategy_profile = _normalize_optional_string(
        payload.get("strategy_profile")
    )
    if resolved_strategy_profile is None:
        raise ValueError("RUNTIME_TARGET_JSON.strategy_profile is required")
    resolved_dry_run_only = _coerce_optional_bool(payload.get("dry_run_only"))
    if resolved_dry_run_only is None:
        raise ValueError("RUNTIME_TARGET_JSON.dry_run_only is required")

    execution_mode = payload.get("execution_mode")
    if execution_mode is not None and str(execution_mode).strip():
        expected_execution_mode = "paper" if resolved_dry_run_only else "live"
        if str(execution_mode).strip().lower() != expected_execution_mode:
            raise ValueError(
                "RUNTIME_TARGET_JSON.execution_mode does not match dry_run_only"
            )

    execution_windows = payload.get("execution_windows")
    if execution_windows is not None and not isinstance(execution_windows, dict):
        raise ValueError("RUNTIME_TARGET_JSON.execution_windows must be an object when present")
    scheduler = payload.get("scheduler")
    if scheduler is not None and not isinstance(scheduler, dict):
        raise ValueError("RUNTIME_TARGET_JSON.scheduler must be an object when present")
    strategy_release = payload.get("strategy_release")
    if strategy_release is not None and not isinstance(strategy_release, dict):
        raise ValueError("RUNTIME_TARGET_JSON.strategy_release must be an object when present")
    account_identity = payload.get("account_identity")
    if account_identity is not None and not isinstance(account_identity, dict):
        raise ValueError("RUNTIME_TARGET_JSON.account_identity must be an object when present")

    return build_runtime_target(
        platform_id=resolved_platform_id,
        strategy_profile=resolved_strategy_profile,
        dry_run_only=resolved_dry_run_only,
        deployment_selector=payload.get("deployment_selector"),
        account_selector=payload.get("account_selector"),
        account_scope=payload.get("account_scope"),
        service_name=payload.get("service_name"),
        market=payload.get("market"),
        market_calendar=payload.get("market_calendar"),
        market_timezone=payload.get("market_timezone"),
        scheduler=scheduler,
        execution_windows=execution_windows,
        strategy_release=strategy_release,
        account_identity=account_identity,
    )
