from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, asdict
from typing import Any, Mapping


@dataclass(frozen=True)
class RuntimeTarget:
    platform_id: str
    strategy_profile: str
    dry_run_only: bool
    deployment_selector: str | None = None
    account_selector: tuple[str, ...] = ()
    account_scope: str | None = None
    service_name: str | None = None

    @property
    def execution_mode(self) -> str:
        return "paper" if self.dry_run_only else "live"

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
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


def build_runtime_target(
    *,
    platform_id: str,
    strategy_profile: str,
    dry_run_only: bool,
    deployment_selector: str | None = None,
    account_selector: Iterable[str] | str | None = None,
    account_scope: str | None = None,
    service_name: str | None = None,
) -> RuntimeTarget:
    return RuntimeTarget(
        platform_id=str(platform_id).strip(),
        strategy_profile=str(strategy_profile).strip(),
        dry_run_only=bool(dry_run_only),
        deployment_selector=_normalize_optional_string(deployment_selector),
        account_selector=_normalize_account_selector(account_selector),
        account_scope=_normalize_optional_string(account_scope),
        service_name=_normalize_optional_string(service_name),
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
    raw_payload = _normalize_optional_string(env.get("RUNTIME_TARGET_JSON"))
    if raw_payload is None:
        raise EnvironmentError("RUNTIME_TARGET_JSON is required")

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

    return build_runtime_target(
        platform_id=resolved_platform_id,
        strategy_profile=resolved_strategy_profile,
        dry_run_only=resolved_dry_run_only,
        deployment_selector=payload.get("deployment_selector"),
        account_selector=payload.get("account_selector"),
        account_scope=payload.get("account_scope"),
        service_name=payload.get("service_name"),
    )
