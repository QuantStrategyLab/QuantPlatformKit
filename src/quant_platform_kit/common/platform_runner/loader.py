"""Shared strategy-loader pattern for QuantStrategyLab execution platforms.

Every Cloud Run–based platform repo (IBKR, LongBridge, Schwab, Firstrade)
previously replicated this 3-function pattern.  New platform implementations
should import from here and customise via the platform-specific registry.
"""

from __future__ import annotations

from typing import Any

from quant_platform_kit.common.strategies import (
    PlatformStrategyPolicy,
    StrategyCatalog,
    StrategyDefinition,
    resolve_platform_strategy_definition,
)
from quant_platform_kit.common.strategies import (
    load_strategy_entrypoint,
)
from quant_platform_kit.common.strategy_contracts import (
    StrategyEntrypoint,
    StrategyRuntimeAdapter,
)


def load_strategy_definition(
    raw_profile: str | None,
    *,
    platform_id: str,
    strategy_catalog: StrategyCatalog,
    policy: PlatformStrategyPolicy,
) -> StrategyDefinition:
    """Resolve a raw profile string to a validated *StrategyDefinition*.

    Parameters
    ----------
    raw_profile :
        Profile name supplied by the caller (may be ``None`` to use the
        platform default).
    platform_id :
        Platform identifier (e.g. ``"ibkr"``, ``"schwab"``).
    strategy_catalog :
        Merged catalog (typically combining domain + combo definitions).
    policy :
        Platform strategy policy (defines the rollout allowlist, default,
        rollback profile).

    Returns
    -------
    StrategyDefinition

    Raises
    ------
    EnvironmentError
        When the profile is required but missing.
    ValueError
        When the profile is unknown or unsupported.
    """
    return resolve_platform_strategy_definition(
        raw_profile,
        platform_id=platform_id,
        strategy_catalog=strategy_catalog,
        policy=policy,
    )


def load_strategy_entrypoint_for_profile(
    raw_profile: str | None,
    *,
    platform_id: str,
    strategy_catalog: StrategyCatalog,
    policy: PlatformStrategyPolicy,
    runtime_adapter: StrategyRuntimeAdapter | None = None,
) -> StrategyEntrypoint:
    """Load the entrypoint (``evaluate``) for a profile.

    Parameters
    ----------
    raw_profile :
        Profile name (may be ``None``, see
        :func:`load_strategy_definition`).
    platform_id, strategy_catalog, policy :
        Forwarded to :func:`load_strategy_definition`.
    runtime_adapter :
        Optional runtime adapter that provides ``available_inputs`` and
        ``available_capabilities`` for entrypoint validation.

    Returns
    -------
    StrategyEntrypoint
    """
    definition = load_strategy_definition(
        raw_profile,
        platform_id=platform_id,
        strategy_catalog=strategy_catalog,
        policy=policy,
    )
    kwargs: dict[str, Any] = {}
    if runtime_adapter is not None:
        kwargs["platform_id"] = platform_id
        kwargs["available_inputs"] = runtime_adapter.available_inputs
        kwargs["available_capabilities"] = runtime_adapter.available_capabilities
    return load_strategy_entrypoint(definition, **kwargs)


def load_strategy_runtime_adapter_for_profile(
    raw_profile: str | None,
    *,
    platform_id: str,
    strategy_catalog: StrategyCatalog,
    policy: PlatformStrategyPolicy,
    adapter_loader: Any,
) -> StrategyRuntimeAdapter:
    """Load the runtime adapter for a profile.

    Parameters
    ----------
    raw_profile :
        Profile name (may be ``None``).
    platform_id, strategy_catalog, policy :
        Forwarded to :func:`load_strategy_definition`.
    adapter_loader :
        Callable that accepts a profile string and returns a
        *StrategyRuntimeAdapter*.  Must be supplied by the platform‐specific
        registry (e.g. ``get_platform_runtime_adapter``).

    Returns
    -------
    StrategyRuntimeAdapter
    """
    definition = load_strategy_definition(
        raw_profile,
        platform_id=platform_id,
        strategy_catalog=strategy_catalog,
        policy=policy,
    )
    return adapter_loader(definition.profile)
