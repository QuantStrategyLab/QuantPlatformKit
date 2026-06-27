from __future__ import annotations

from .strategies import PlatformCapabilityMatrix, StrategyCatalog, StrategyDefinition, normalize_profile_name

FRACTIONAL_SHARE_EXECUTION_CAPABILITY = "fractional_share_execution"
FRACTIONAL_SHARE_EXECUTION_SKIP_REASON = "fractional_share_execution_required"


def definition_requires_fractional_share_execution(definition: StrategyDefinition) -> bool:
    return FRACTIONAL_SHARE_EXECUTION_CAPABILITY in frozenset(definition.compatible_capabilities)


def platform_supports_fractional_share_execution(*, capability_matrix: PlatformCapabilityMatrix) -> bool:
    return FRACTIONAL_SHARE_EXECUTION_CAPABILITY in frozenset(capability_matrix.supported_capabilities)


def fractional_share_execution_unsupported_reason(
    profile: str,
    *,
    strategy_catalog: StrategyCatalog,
    capability_matrix: PlatformCapabilityMatrix,
) -> str | None:
    normalized_profile = normalize_profile_name(profile)
    definition = strategy_catalog.definitions.get(normalized_profile)
    if definition is None:
        return None
    if definition_requires_fractional_share_execution(definition):
        if not platform_supports_fractional_share_execution(capability_matrix=capability_matrix):
            return FRACTIONAL_SHARE_EXECUTION_SKIP_REASON
    return None
