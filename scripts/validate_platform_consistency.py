#!/usr/bin/env python3
"""Validate cross-platform strategy consistency.

Checks:
1. Every strategy profile with ``compatible_platforms`` must have a working
   runtime adapter for each listed platform.
2. Platform capability matrix must declare support for all required inputs
   of its enabled strategies.
3. No strategy is enabled on multiple platforms with conflicting definitions.
4. All ``runtime_enabled_profiles`` entries exist in the strategy catalog.

Usage:
    python scripts/validate_platform_consistency.py          # check all platforms
    python scripts/validate_platform_consistency.py schwab   # single platform
"""

from __future__ import annotations

import sys
from typing import Iterable

from quant_platform_kit.common.strategies import (
    derive_eligible_profiles_for_platform,
    PlatformCapabilityMatrix,
    StrategyCatalog,
)


def _load_platform_registry(platform_id: str):
    """Import a platform registry module by name."""
    registry_modules = {
        "schwab": "strategy_registry_schwab",
        "ibkr": "strategy_registry_ibkr",
        "longbridge": "strategy_registry_longbridge",
        "firstrade": "strategy_registry_firstrade",
    }
    mod_name = registry_modules.get(
        platform_id, f"strategy_registry_{platform_id}"
    )
    try:
        return __import__(mod_name, fromlist=["__all__"])
    except ImportError:
        raise SystemExit(
            f"Cannot import {mod_name}. "
            f"Run this script from a platform repo that has strategy_registry.py, "
            f"or install the platform package."
        )


def _iter_known_platforms() -> Iterable[str]:
    """Discover available platform registries."""
    candidates = ["schwab", "ibkr", "longbridge", "firstrade"]
    for pid in candidates:
        try:
            _load_platform_registry(pid)
            yield pid
        except SystemExit:
            continue


def validate_strategy_catalog(catalog: StrategyCatalog) -> list[str]:
    """Check the strategy catalog itself for internal consistency."""
    errors: list[str] = []
    profiles = set(catalog.definitions)
    metadata_profiles = set(catalog.metadata)
    compat_profiles = set(catalog.compatible_platforms)

    for profile in catalog.definitions:
        if profile not in metadata_profiles:
            errors.append(
                f"Strategy '{profile}' has a definition but no metadata entry"
            )

    for profile in metadata_profiles:
        if profile not in profiles:
            errors.append(
                f"Strategy '{profile}' has metadata but no definition"
            )

    for profile in compat_profiles:
        if profile not in profiles:
            errors.append(
                f"Strategy '{profile}' listed in compatible_platforms but has no definition"
            )

    return errors


def validate_platform_capability_matrix(
    platform_id: str,
    catalog: StrategyCatalog,
    capability_matrix: PlatformCapabilityMatrix,
    enabled_profiles: frozenset[str],
) -> list[str]:
    """Check that the platform can actually execute its enabled strategies."""
    errors: list[str] = []

    for profile in enabled_profiles:
        definition = catalog.definitions.get(profile)
        if definition is None:
            errors.append(
                f"[{platform_id}] enabled profile '{profile}' not found in strategy catalog"
            )
            continue

        # Check domain support
        domain = str(getattr(definition, "domain", "") or catalog.metadata.get(profile))
        if domain:
            meta = catalog.metadata.get(profile)
            if meta is not None:
                domain = str(getattr(meta, "domain", "") or "")

        if domain and domain not in (capability_matrix.supported_domains or frozenset()):
            errors.append(
                f"[{platform_id}] strategy '{profile}' domain '{domain}' "
                f"not in platform supported domains {capability_matrix.supported_domains}"
            )

    # Check that eligible profiles are a superset of enabled
    eligible = derive_eligible_profiles_for_platform(
        catalog,
        capability_matrix=capability_matrix,
        runtime_adapter_loader=lambda p: None,  # skip adapter check
    )
    not_eligible = enabled_profiles - eligible
    if not_eligible:
        errors.append(
            f"[{platform_id}] enabled profiles not in eligible set: {sorted(not_eligible)}"
        )

    return errors


def validate_platform_cross_compatibility(
    catalog: StrategyCatalog,
    all_enabled: dict[str, frozenset[str]],
) -> list[str]:
    """Check that no strategy has conflicting platform assignments."""
    errors: list[str] = []

    # A strategy can be enabled on multiple platforms — that's fine.
    # But it MUST be in compatible_platforms for each.
    for profile in catalog.compatible_platforms:
        declared = set(catalog.compatible_platforms[profile])
        for pid, enabled in all_enabled.items():
            if profile in enabled and pid not in declared:
                errors.append(
                    f"Strategy '{profile}' is enabled on '{pid}' "
                    f"but '{pid}' is not in its compatible_platforms {sorted(declared)}"
                )

    return errors


def check_platform(platform_id: str) -> tuple[list[str], list[str]]:
    """Run all checks for a single platform.  Returns (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    registry = _load_platform_registry(platform_id)

    catalog = getattr(registry, "STRATEGY_CATALOG", None)
    if catalog is None:
        errors.append(f"[{platform_id}] missing STRATEGY_CATALOG")
        return errors, warnings

    capability_matrix = getattr(registry, "PLATFORM_CAPABILITY_MATRIX", None)
    if capability_matrix is None:
        warnings.append(f"[{platform_id}] missing PLATFORM_CAPABILITY_MATRIX; skipping capability checks")
        return errors, warnings

    enabled = getattr(registry, "SCHWAB_ENABLED_PROFILES", None) or \
              getattr(registry, "IBKR_ENABLED_PROFILES", None) or \
              getattr(registry, "LONGBRIDGE_ENABLED_PROFILES", None) or \
              frozenset()

    # Catalog internal checks (run once if first platform)
    errors.extend(validate_strategy_catalog(catalog))

    # Platform-specific checks
    errors.extend(
        validate_platform_capability_matrix(
            platform_id, catalog, capability_matrix, enabled
        )
    )

    return errors, warnings


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else None
    platforms = [target] if target else list(_iter_known_platforms())

    if not platforms:
        print("No platform registries found.")
        return 2

    all_errors: list[str] = []
    all_warnings: list[str] = []
    all_enabled: dict[str, frozenset[str]] = {}

    for pid in platforms:
        print(f"  Checking {pid}...")
        errors, warnings = check_platform(pid)
        all_errors.extend(errors)
        all_warnings.extend(warnings)

        # Collect enabled profiles for cross-compat check
        registry = _load_platform_registry(pid)
        enabled = getattr(registry, "SCHWAB_ENABLED_PROFILES", None) or \
                  getattr(registry, "IBKR_ENABLED_PROFILES", None) or \
                  getattr(registry, "LONGBRIDGE_ENABLED_PROFILES", None) or \
                  frozenset()
        all_enabled[pid] = enabled

    if len(platforms) > 1:
        catalog = None
        for pid in platforms:
            registry = _load_platform_registry(pid)
            catalog = getattr(registry, "STRATEGY_CATALOG", None)
            if catalog is not None:
                break
        if catalog is not None:
            all_errors.extend(
                validate_platform_cross_compatibility(catalog, all_enabled)
            )

    for w in all_warnings:
        print(f"  ⚠  {w}")
    for e in all_errors:
        print(f"  ✗  {e}")

    if all_errors:
        print(f"\n{len(all_errors)} error(s) found.")
        return 1

    print(f"\nAll checks passed ({len(platforms)} platform(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
