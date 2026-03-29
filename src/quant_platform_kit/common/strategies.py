from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from types import ModuleType
from typing import Iterable

US_EQUITY_DOMAIN = "us_equity"
CRYPTO_DOMAIN = "crypto"


@dataclass(frozen=True)
class StrategyComponentDefinition:
    name: str
    module_path: str


@dataclass(frozen=True)
class StrategyDefinition:
    profile: str
    domain: str
    supported_platforms: frozenset[str]
    components: tuple[StrategyComponentDefinition, ...] = field(default_factory=tuple)


def get_strategy_component_map(
    definition: StrategyDefinition,
) -> dict[str, StrategyComponentDefinition]:
    return {component.name: component for component in definition.components}


def load_strategy_component_module(
    definition: StrategyDefinition,
    *,
    component_name: str,
) -> ModuleType:
    component_map = get_strategy_component_map(definition)
    component = component_map.get(component_name)
    if component is None:
        available = ", ".join(sorted(component_map)) or "<none>"
        raise ValueError(
            f"Strategy profile {definition.profile!r} does not expose component "
            f"{component_name!r}; available components: {available}"
        )
    return import_module(component.module_path)


def load_strategy_component_modules(
    definition: StrategyDefinition,
    *,
    component_names: Iterable[str],
) -> dict[str, ModuleType]:
    return {
        component_name: load_strategy_component_module(
            definition,
            component_name=component_name,
        )
        for component_name in component_names
    }


def get_supported_profiles_for_platform(
    strategy_definitions: dict[str, StrategyDefinition],
    platform_supported_domains: dict[str, frozenset[str]],
    *,
    platform_id: str,
) -> frozenset[str]:
    return frozenset(
        profile
        for profile, definition in strategy_definitions.items()
        if platform_id in definition.supported_platforms
        and definition.domain in platform_supported_domains.get(platform_id, frozenset())
    )


def resolve_strategy_definition(
    raw_value: str | None,
    *,
    platform_id: str,
    strategy_definitions: dict[str, StrategyDefinition],
    platform_supported_domains: dict[str, frozenset[str]],
    default_profile: str | None = None,
    require_explicit: bool = False,
) -> StrategyDefinition:
    if require_explicit and not str(raw_value or "").strip():
        raise EnvironmentError("STRATEGY_PROFILE is required")

    profile = (raw_value or default_profile or "").strip().lower()
    if not profile:
        raise EnvironmentError("STRATEGY_PROFILE is required")

    supported_profiles = get_supported_profiles_for_platform(
        strategy_definitions,
        platform_supported_domains,
        platform_id=platform_id,
    )
    supported = ", ".join(sorted(supported_profiles))

    definition = strategy_definitions.get(profile)
    if definition is None or platform_id not in definition.supported_platforms:
        raise ValueError(
            f"Unsupported STRATEGY_PROFILE={raw_value!r}; supported values: {supported}"
        )

    if definition.domain not in platform_supported_domains.get(platform_id, frozenset()):
        raise ValueError(
            f"Unsupported strategy domain {definition.domain!r} for platform {platform_id!r}"
        )

    return definition
