from __future__ import annotations

from .strategies import StrategyCatalog, StrategyDefinition, StrategyMetadata


def merge_strategy_catalogs(*catalogs: StrategyCatalog) -> StrategyCatalog:
    """Merge catalogs in order without mutating their mappings.

    Equal duplicate values are accepted; conflicting values raise ValueError.
    Keys and values are preserved without normalization or extra validation.
    """
    definitions: dict[str, StrategyDefinition] = {}
    metadata: dict[str, StrategyMetadata] = {}
    compatible_platforms: dict[str, frozenset[str]] = {}
    profile_aliases: dict[str, str] = {}
    for catalog in catalogs:
        for profile, definition in catalog.definitions.items():
            if profile in definitions and definitions[profile] != definition:
                raise ValueError(f"Duplicate strategy definition for profile {profile!r}")
            definitions[profile] = definition
        for profile, value in catalog.metadata.items():
            if profile in metadata and metadata[profile] != value:
                raise ValueError(f"Duplicate strategy metadata for profile {profile!r}")
            metadata[profile] = value
        for profile, platforms in catalog.compatible_platforms.items():
            if profile in compatible_platforms and compatible_platforms[profile] != platforms:
                raise ValueError(f"Duplicate strategy platform compatibility for profile {profile!r}")
            compatible_platforms[profile] = platforms
        for alias, profile in catalog.profile_aliases.items():
            if alias in profile_aliases and profile_aliases[alias] != profile:
                raise ValueError(f"Duplicate strategy alias {alias!r}")
            profile_aliases[alias] = profile
    return StrategyCatalog(
        definitions=definitions,
        metadata=metadata,
        compatible_platforms=compatible_platforms,
        profile_aliases=profile_aliases,
    )
