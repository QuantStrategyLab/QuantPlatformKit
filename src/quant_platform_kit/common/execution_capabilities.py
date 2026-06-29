from __future__ import annotations

from .strategies import PlatformCapabilityMatrix, StrategyCatalog, StrategyDefinition, normalize_profile_name

FRACTIONAL_SHARE_EXECUTION_CAPABILITY = "fractional_share_execution"
FRACTIONAL_SHARE_EXECUTION_SKIP_REASON = "fractional_share_execution_required"

# When a platform does NOT natively support fractional shares, DCA / notional
# strategies can still run by converting each notional buy into a minimum
# 1-share (US) or 1-lot (HK) order.  This compat mode is signalled via
# ``notional_buy_compat_mode_enabled()`` so the execution layer knows to
# floor-up notional amounts instead of placing true fractional orders.
NOTIONAL_TO_WHOLE_SHARE_COMPAT_SKIP_REASON = "notional_to_whole_share_compat"


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
    """Return a reason string if *profile* requires fractional shares but the
    platform does **not** support them natively.

    When the platform lacks ``fractional_share_execution`` but a strategy
    still needs to place notional orders, callers should check
    ``notional_buy_compat_mode_enabled()`` — if that returns ``True`` the
    execution layer should convert each notional buy into a minimum
    whole-share (or whole-lot) order instead of skipping the strategy.
    """
    normalized_profile = normalize_profile_name(profile)
    definition = strategy_catalog.definitions.get(normalized_profile)
    if definition is None:
        return None
    if definition_requires_fractional_share_execution(definition):
        if not platform_supports_fractional_share_execution(capability_matrix=capability_matrix):
            return FRACTIONAL_SHARE_EXECUTION_SKIP_REASON
    return None


def notional_buy_compat_mode_enabled(
    profile: str,
    *,
    strategy_catalog: StrategyCatalog,
    capability_matrix: PlatformCapabilityMatrix,
) -> bool:
    """Return ``True`` when *profile* requires fractional execution but the
    platform does **not** support it natively.

    In compat mode the execution layer should convert each notional buy
    intent into a minimum 1‑share (US) or 1‑lot (HK) order, falling back
    to skipping the order if the notional amount is smaller than one unit.
    """
    normalized_profile = normalize_profile_name(profile)
    definition = strategy_catalog.definitions.get(normalized_profile)
    if definition is None:
        return False
    if not definition_requires_fractional_share_execution(definition):
        return False
    return not platform_supports_fractional_share_execution(capability_matrix=capability_matrix)
