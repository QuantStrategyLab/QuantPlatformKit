from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from types import ModuleType
from typing import Any, Iterable, Mapping

from .strategy_contracts import (
    CallableStrategyEntrypoint,
    StrategyContractValidationError,
    StrategyEntrypoint,
    StrategyManifest,
    validate_strategy_manifest,
)

US_EQUITY_DOMAIN = "us_equity"
CRYPTO_DOMAIN = "crypto"


@dataclass(frozen=True)
class StrategyComponentDefinition:
    name: str
    module_path: str


@dataclass(frozen=True)
class StrategyEntrypointDefinition:
    module_path: str
    attribute_name: str = "entrypoint"


@dataclass(frozen=True)
class StrategyDefinition:
    profile: str
    domain: str
    supported_platforms: frozenset[str]
    components: tuple[StrategyComponentDefinition, ...] = field(default_factory=tuple)
    entrypoint: StrategyEntrypointDefinition | None = None
    required_inputs: frozenset[str] = frozenset()
    compatible_capabilities: frozenset[str] = frozenset()
    default_config: Mapping[str, Any] = field(default_factory=dict)


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
    definitions = {
        normalize_profile_name(profile): definition
        for profile, definition in strategy_definitions.items()
    }
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
            profile_aliases.items()
            if profile_aliases is not None
            else build_profile_aliases(metadata_map).items()
        )
    }
    return StrategyCatalog(
        definitions=definitions,
        metadata=metadata_map,
        compatible_platforms=compatibility_map,
        profile_aliases=aliases,
    )


def _unsupported_profile_error(
    *,
    profile: str | None,
    supported: Iterable[str],
    aliases: Iterable[str],
) -> ValueError:
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
                "has_entrypoint": definition.entrypoint is not None
                or "entrypoint" in {component.name for component in definition.components},
                "required_inputs": definition.required_inputs,
                "compatible_capabilities": definition.compatible_capabilities,
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


def build_strategy_manifest(
    definition: StrategyDefinition,
    *,
    metadata: StrategyMetadata | None = None,
) -> StrategyManifest:
    manifest = StrategyManifest(
        profile=definition.profile,
        domain=definition.domain,
        display_name=(metadata.display_name if metadata else definition.profile.replace("_", " ").title()),
        description=(
            metadata.description
            if metadata
            else f"Legacy entrypoint adapter for strategy profile {definition.profile}."
        ),
        aliases=metadata.aliases if metadata else (),
        required_inputs=definition.required_inputs,
        compatible_capabilities=definition.compatible_capabilities,
        default_config=dict(definition.default_config),
    )
    return validate_strategy_manifest(manifest)


def _coerce_entrypoint_candidate(
    candidate: object,
    *,
    source: str,
) -> StrategyEntrypoint:
    manifest = getattr(candidate, "manifest", None)
    evaluate = getattr(candidate, "evaluate", None)
    if manifest is None or not callable(evaluate):
        raise StrategyContractValidationError(
            f"{source} must expose manifest and callable evaluate(ctx)"
        )
    return CallableStrategyEntrypoint(
        manifest=validate_strategy_manifest(manifest),
        _evaluate=evaluate,
    )


def _module_entrypoint_candidate(
    module: ModuleType,
    *,
    module_ref: StrategyEntrypointDefinition,
    definition: StrategyDefinition,
    metadata: StrategyMetadata | None,
) -> StrategyEntrypoint | None:
    attribute_name = module_ref.attribute_name.strip()
    if attribute_name:
        explicit = getattr(module, attribute_name, None)
        if explicit is not None:
            return _coerce_entrypoint_candidate(
                explicit,
                source=f"{module.__name__}.{attribute_name}",
            )

    factory = getattr(module, "build_entrypoint", None)
    if callable(factory):
        return _coerce_entrypoint_candidate(factory(), source=f"{module.__name__}.build_entrypoint()")

    evaluate = getattr(module, "evaluate", None)
    if not callable(evaluate):
        return None

    manifest = getattr(module, "manifest", None)
    if manifest is None:
        manifest = build_strategy_manifest(definition, metadata=metadata)
    else:
        validate_strategy_manifest(manifest)
    return CallableStrategyEntrypoint(manifest=manifest, _evaluate=evaluate)


def _iter_entrypoint_candidates(
    definition: StrategyDefinition,
) -> tuple[StrategyEntrypointDefinition, ...]:
    candidates: list[StrategyEntrypointDefinition] = []
    seen: set[tuple[str, str]] = set()

    def append_candidate(module_path: str, attribute_name: str = "entrypoint") -> None:
        key = (module_path, attribute_name)
        if key in seen:
            return
        seen.add(key)
        candidates.append(
            StrategyEntrypointDefinition(module_path=module_path, attribute_name=attribute_name)
        )

    if definition.entrypoint is not None:
        append_candidate(
            definition.entrypoint.module_path,
            definition.entrypoint.attribute_name,
        )

    component_map = get_strategy_component_map(definition)
    entrypoint_component = component_map.get("entrypoint")
    if entrypoint_component is not None:
        append_candidate(entrypoint_component.module_path)

    for component in definition.components:
        append_candidate(component.module_path)

    return tuple(candidates)


def _validate_entrypoint_compatibility(
    entrypoint: StrategyEntrypoint,
    definition: StrategyDefinition,
    *,
    platform_id: str | None,
    available_inputs: Iterable[str] | None,
    available_capabilities: Iterable[str] | None,
) -> None:
    manifest = validate_strategy_manifest(entrypoint.manifest)

    if available_inputs is not None and manifest.required_inputs:
        missing_inputs = manifest.required_inputs - frozenset(available_inputs)
        if missing_inputs:
            raise StrategyContractValidationError(
                "Strategy manifest requires missing inputs: "
                f"{', '.join(sorted(missing_inputs))}"
            )

    if manifest.compatible_capabilities:
        capabilities = frozenset(available_capabilities or ())
        missing_capabilities = manifest.compatible_capabilities - capabilities
        if missing_capabilities:
            raise StrategyContractValidationError(
                "Strategy manifest requires missing capabilities: "
                f"{', '.join(sorted(missing_capabilities))}"
            )
        return

    if platform_id is not None and platform_id not in definition.supported_platforms:
        supported = ", ".join(sorted(definition.supported_platforms)) or "<none>"
        raise StrategyContractValidationError(
            f"Strategy profile {definition.profile!r} is not compatible with platform "
            f"{platform_id!r}; supported_platforms={supported}"
        )


def load_strategy_entrypoint(
    definition: StrategyDefinition,
    *,
    metadata: StrategyMetadata | None = None,
    platform_id: str | None = None,
    available_inputs: Iterable[str] | None = None,
    available_capabilities: Iterable[str] | None = None,
) -> StrategyEntrypoint:
    candidates = _iter_entrypoint_candidates(definition)
    if not candidates:
        raise ValueError(f"Strategy profile {definition.profile!r} has no entrypoint candidates")

    for module_ref in candidates:
        module = import_module(module_ref.module_path)
        entrypoint = _module_entrypoint_candidate(
            module,
            module_ref=module_ref,
            definition=definition,
            metadata=metadata,
        )
        if entrypoint is None:
            continue
        _validate_entrypoint_compatibility(
            entrypoint,
            definition,
            platform_id=platform_id,
            available_inputs=available_inputs,
            available_capabilities=available_capabilities,
        )
        return entrypoint

    candidate_modules = ", ".join(module_ref.module_path for module_ref in candidates)
    raise ValueError(
        f"Strategy profile {definition.profile!r} does not expose a unified entrypoint; "
        f"checked modules: {candidate_modules}"
    )
