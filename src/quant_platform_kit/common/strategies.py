from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from types import ModuleType
from typing import Iterable, Mapping

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


@dataclass(frozen=True)
class StrategyMetadata:
    canonical_profile: str
    display_name: str
    description: str
    aliases: tuple[str, ...] = ()
    cadence: str | None = None
    asset_scope: str | None = None
    benchmark: str | None = None
    role: str | None = None
    status: str | None = None


@dataclass(frozen=True)
class StrategyCatalog:
    definitions: Mapping[str, StrategyDefinition]
    metadata: Mapping[str, StrategyMetadata] = field(default_factory=dict)
    compatible_platforms: Mapping[str, frozenset[str]] = field(default_factory=dict)
    profile_aliases: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PlatformStrategyPolicy:
    platform_id: str
    supported_domains: frozenset[str]
    enabled_profiles: frozenset[str]
    default_profile: str
    rollback_profile: str
    require_explicit_profile: bool = False


def normalize_profile_name(profile: str | None) -> str:
    return str(profile or "").strip().lower()


def build_profile_aliases(metadata_map: Mapping[str, StrategyMetadata]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for canonical_profile, metadata in metadata_map.items():
        canonical = normalize_profile_name(canonical_profile)
        if not canonical:
            continue
        for alias in metadata.aliases:
            normalized_alias = normalize_profile_name(alias)
            if not normalized_alias:
                continue
            existing = aliases.get(normalized_alias)
            if existing is not None and existing != canonical:
                raise ValueError(
                    f"Duplicate strategy alias {alias!r}; already assigned to {existing!r}"
                )
            if normalized_alias in metadata_map and normalized_alias != canonical:
                raise ValueError(
                    f"Strategy alias {alias!r} collides with canonical profile {normalized_alias!r}"
                )
            aliases[normalized_alias] = canonical
    return aliases


def build_strategy_catalog(
    *,
    strategy_definitions: Mapping[str, StrategyDefinition],
    metadata: Mapping[str, StrategyMetadata] | None = None,
    compatible_platforms: Mapping[str, frozenset[str]] | None = None,
    profile_aliases: Mapping[str, str] | None = None,
) -> StrategyCatalog:
    definitions = {normalize_profile_name(profile): definition for profile, definition in strategy_definitions.items()}
    metadata_map = {
        normalize_profile_name(profile): value for profile, value in (metadata or {}).items()
    }
    compatibility_map = {
        normalize_profile_name(profile): frozenset(platforms)
        for profile, platforms in (compatible_platforms or {}).items()
    }
    missing_metadata = sorted(set(metadata_map) - set(definitions))
    if missing_metadata:
        raise ValueError(f"Metadata provided for unknown profiles: {', '.join(missing_metadata)}")
    missing_compatibility = sorted(set(compatibility_map) - set(definitions))
    if missing_compatibility:
        raise ValueError(
            f"Compatibility provided for unknown profiles: {', '.join(missing_compatibility)}"
        )
    aliases = {
        normalize_profile_name(alias): normalize_profile_name(canonical)
        for alias, canonical in (
            profile_aliases.items() if profile_aliases is not None else build_profile_aliases(metadata_map).items()
        )
    }
    return StrategyCatalog(
        definitions=definitions,
        metadata=metadata_map,
        compatible_platforms=compatibility_map,
        profile_aliases=aliases,
    )


def _unsupported_profile_error(*, profile: str | None, supported: Iterable[str], aliases: Iterable[str]) -> ValueError:
    supported_text = ", ".join(sorted(supported)) or "<none>"
    alias_text = ", ".join(sorted(aliases)) or "<none>"
    return ValueError(
        f"Unknown strategy profile={profile!r}; supported canonical values: {supported_text}; aliases: {alias_text}"
    )


def resolve_catalog_profile(profile: str | None, *, strategy_catalog: StrategyCatalog) -> str:
    normalized = normalize_profile_name(profile)
    if not normalized:
        return normalized
    return str(strategy_catalog.profile_aliases.get(normalized, normalized))


def get_catalog_strategy_definition(
    strategy_catalog: StrategyCatalog,
    profile: str,
) -> StrategyDefinition:
    canonical = resolve_catalog_profile(profile, strategy_catalog=strategy_catalog)
    definition = strategy_catalog.definitions.get(canonical)
    if definition is None:
        raise _unsupported_profile_error(
            profile=profile,
            supported=strategy_catalog.definitions,
            aliases=strategy_catalog.profile_aliases,
        )
    return definition


def get_catalog_strategy_metadata(
    strategy_catalog: StrategyCatalog,
    profile: str,
) -> StrategyMetadata:
    canonical = resolve_catalog_profile(profile, strategy_catalog=strategy_catalog)
    metadata = strategy_catalog.metadata.get(canonical)
    if metadata is None:
        raise _unsupported_profile_error(
            profile=profile,
            supported=strategy_catalog.metadata,
            aliases=strategy_catalog.profile_aliases,
        )
    return metadata


def get_catalog_compatible_platforms(
    strategy_catalog: StrategyCatalog,
    profile: str,
) -> frozenset[str]:
    canonical = resolve_catalog_profile(profile, strategy_catalog=strategy_catalog)
    platforms = strategy_catalog.compatible_platforms.get(canonical)
    if platforms is not None:
        return frozenset(platforms)
    definition = strategy_catalog.definitions.get(canonical)
    if definition is None:
        raise _unsupported_profile_error(
            profile=profile,
            supported=strategy_catalog.definitions,
            aliases=strategy_catalog.profile_aliases,
        )
    return definition.supported_platforms


def build_strategy_index_rows(strategy_catalog: StrategyCatalog) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for canonical_profile in sorted(strategy_catalog.definitions):
        definition = strategy_catalog.definitions[canonical_profile]
        metadata = strategy_catalog.metadata.get(canonical_profile)
        rows.append(
            {
                "canonical_profile": canonical_profile,
                "display_name": metadata.display_name if metadata else canonical_profile,
                "aliases": metadata.aliases if metadata else (),
                "description": metadata.description if metadata else "",
                "cadence": metadata.cadence if metadata else None,
                "asset_scope": metadata.asset_scope if metadata else None,
                "benchmark": metadata.benchmark if metadata else None,
                "role": metadata.role if metadata else None,
                "status": metadata.status if metadata else None,
                "component_names": tuple(component.name for component in definition.components),
                "compatible_platforms": get_catalog_compatible_platforms(
                    strategy_catalog,
                    canonical_profile,
                ),
            }
        )
    return rows


def get_enabled_profiles_for_platform(
    platform_id: str,
    *,
    policy: PlatformStrategyPolicy,
) -> frozenset[str]:
    if platform_id != policy.platform_id:
        return frozenset()
    return policy.enabled_profiles


def build_platform_profile_matrix(
    strategy_catalog: StrategyCatalog,
    *,
    policy: PlatformStrategyPolicy,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for profile in sorted(policy.enabled_profiles):
        definition = get_catalog_strategy_definition(strategy_catalog, profile)
        metadata = strategy_catalog.metadata.get(definition.profile)
        rows.append(
            {
                "platform": policy.platform_id,
                "canonical_profile": definition.profile,
                "display_name": metadata.display_name if metadata else definition.profile,
                "aliases": metadata.aliases if metadata else (),
                "enabled": True,
                "is_default": definition.profile == policy.default_profile,
                "is_rollback": definition.profile == policy.rollback_profile,
                "domain": definition.domain,
            }
        )
    return rows


def resolve_platform_strategy_definition(
    raw_value: str | None,
    *,
    platform_id: str,
    strategy_catalog: StrategyCatalog,
    policy: PlatformStrategyPolicy,
) -> StrategyDefinition:
    if platform_id != policy.platform_id:
        raise ValueError(f"Unsupported platform_id={platform_id!r}")

    normalized = normalize_profile_name(raw_value)
    if policy.require_explicit_profile and not normalized:
        raise EnvironmentError("STRATEGY_PROFILE is required")

    candidate = normalized or normalize_profile_name(policy.default_profile)
    if not candidate:
        raise EnvironmentError("STRATEGY_PROFILE is required")

    canonical = resolve_catalog_profile(candidate, strategy_catalog=strategy_catalog)
    supported = ", ".join(sorted(policy.enabled_profiles)) or "<none>"
    if canonical not in policy.enabled_profiles:
        raise ValueError(
            f"Unsupported STRATEGY_PROFILE={raw_value!r}; supported values: {supported}"
        )

    definition = get_catalog_strategy_definition(strategy_catalog, canonical)
    if definition.domain not in policy.supported_domains:
        raise ValueError(
            f"Unsupported strategy domain {definition.domain!r} for platform {platform_id!r}"
        )
    return definition


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
