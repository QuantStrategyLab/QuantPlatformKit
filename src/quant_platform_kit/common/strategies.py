from __future__ import annotations

from dataclasses import dataclass

US_EQUITY_DOMAIN = "us_equity"
CRYPTO_DOMAIN = "crypto"


@dataclass(frozen=True)
class StrategyDefinition:
    profile: str
    domain: str
    supported_platforms: frozenset[str]


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
