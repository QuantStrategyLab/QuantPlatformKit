from __future__ import annotations

import unittest

from quant_platform_kit.common.strategies import (
    CRYPTO_DOMAIN,
    PlatformStrategyPolicy,
    US_EQUITY_DOMAIN,
    StrategyComponentDefinition,
    StrategyDefinition,
    StrategyMetadata,
    build_platform_profile_matrix,
    build_profile_aliases,
    build_strategy_catalog,
    build_strategy_index_rows,
    get_catalog_compatible_platforms,
    get_catalog_strategy_definition,
    get_catalog_strategy_metadata,
    get_enabled_profiles_for_platform,
    resolve_catalog_profile,
    load_strategy_component_module,
    resolve_platform_strategy_definition,
)


class StrategyContractsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy_definitions = {
            "global_etf_rotation": StrategyDefinition(
                profile="global_etf_rotation",
                domain=US_EQUITY_DOMAIN,
                supported_platforms=frozenset({"ibkr", "schwab", "longbridge"}),
                components=(
                    StrategyComponentDefinition(
                        name="signal_logic",
                        module_path="math",
                    ),
                ),
            ),
            "crypto_leader_rotation": StrategyDefinition(
                profile="crypto_leader_rotation",
                domain=CRYPTO_DOMAIN,
                supported_platforms=frozenset({"binance"}),
                components=(
                    StrategyComponentDefinition(
                        name="core",
                        module_path="math",
                    ),
                ),
            ),
        }
        self.platform_supported_domains = {
            "ibkr": frozenset({US_EQUITY_DOMAIN}),
            "binance": frozenset({CRYPTO_DOMAIN}),
        }
        self.strategy_catalog = build_strategy_catalog(
            strategy_definitions=self.strategy_definitions,
        )
        self.ibkr_policy = PlatformStrategyPolicy(
            platform_id="ibkr",
            supported_domains=self.platform_supported_domains["ibkr"],
            enabled_profiles=frozenset({"global_etf_rotation"}),
            default_profile="global_etf_rotation",
            rollback_profile="global_etf_rotation",
            require_explicit_profile=True,
        )
        self.binance_policy = PlatformStrategyPolicy(
            platform_id="binance",
            supported_domains=self.platform_supported_domains["binance"],
            enabled_profiles=frozenset({"crypto_leader_rotation"}),
            default_profile="crypto_leader_rotation",
            rollback_profile="crypto_leader_rotation",
        )

    def test_get_enabled_profiles_for_platform_reads_platform_policy(self) -> None:
        supported = get_enabled_profiles_for_platform(
            "ibkr",
            policy=self.ibkr_policy,
        )

        self.assertEqual(supported, frozenset({"global_etf_rotation"}))

    def test_resolve_platform_strategy_definition_uses_default_profile_when_allowed(self) -> None:
        definition = resolve_platform_strategy_definition(
            None,
            platform_id="binance",
            strategy_catalog=self.strategy_catalog,
            policy=self.binance_policy,
        )

        self.assertEqual(definition.profile, "crypto_leader_rotation")
        self.assertEqual(definition.domain, CRYPTO_DOMAIN)

    def test_resolve_platform_strategy_definition_requires_explicit_when_requested(self) -> None:
        with self.assertRaisesRegex(EnvironmentError, "STRATEGY_PROFILE is required"):
            resolve_platform_strategy_definition(
                None,
                platform_id="ibkr",
                strategy_catalog=self.strategy_catalog,
                policy=self.ibkr_policy,
            )

    def test_resolve_platform_strategy_definition_rejects_profile_outside_platform_domain(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported STRATEGY_PROFILE"):
            resolve_platform_strategy_definition(
                "crypto_leader_rotation",
                platform_id="ibkr",
                strategy_catalog=self.strategy_catalog,
                policy=self.ibkr_policy,
            )

    def test_load_strategy_component_module_imports_named_component(self) -> None:
        definition = self.strategy_definitions["global_etf_rotation"]

        module = load_strategy_component_module(
            definition,
            component_name="signal_logic",
        )

        self.assertEqual(module.__name__, "math")

    def test_load_strategy_component_module_rejects_unknown_component(self) -> None:
        definition = self.strategy_definitions["global_etf_rotation"]

        with self.assertRaisesRegex(ValueError, "available components: signal_logic"):
            load_strategy_component_module(
                definition,
                component_name="allocation",
            )

    def test_catalog_helpers_resolve_alias_and_metadata(self) -> None:
        catalog = build_strategy_catalog(
            strategy_definitions=self.strategy_definitions,
            metadata={
                "global_etf_rotation": StrategyMetadata(
                    canonical_profile="global_etf_rotation",
                    display_name="Global ETF Rotation Defense",
                    description="rotation",
                    aliases=("global_macro_etf_rotation",),
                    cadence="quarterly",
                    benchmark="VOO",
                )
            },
            compatible_platforms={
                "global_etf_rotation": frozenset({"ibkr"}),
            },
        )

        self.assertEqual(
            resolve_catalog_profile("global_macro_etf_rotation", strategy_catalog=catalog),
            "global_etf_rotation",
        )
        self.assertEqual(
            get_catalog_strategy_definition(catalog, "global_macro_etf_rotation").profile,
            "global_etf_rotation",
        )
        self.assertEqual(
            get_catalog_strategy_metadata(catalog, "global_etf_rotation").display_name,
            "Global ETF Rotation Defense",
        )
        self.assertEqual(
            get_catalog_compatible_platforms(catalog, "global_etf_rotation"),
            frozenset({"ibkr"}),
        )
        rows = build_strategy_index_rows(catalog)
        by_profile = {row["canonical_profile"]: row for row in rows}
        self.assertEqual(by_profile["global_etf_rotation"]["display_name"], "Global ETF Rotation Defense")

    def test_platform_policy_helpers_build_matrix_and_resolve_enabled_profile(self) -> None:
        catalog = build_strategy_catalog(
            strategy_definitions=self.strategy_definitions,
            metadata={
                "global_etf_rotation": StrategyMetadata(
                    canonical_profile="global_etf_rotation",
                    display_name="Global ETF Rotation Defense",
                    description="rotation",
                    aliases=("global_macro_etf_rotation",),
                ),
            },
        )
        policy = PlatformStrategyPolicy(
            platform_id="ibkr",
            supported_domains=frozenset({US_EQUITY_DOMAIN}),
            enabled_profiles=frozenset({"global_etf_rotation"}),
            default_profile="global_etf_rotation",
            rollback_profile="global_etf_rotation",
            require_explicit_profile=True,
        )

        self.assertEqual(
            get_enabled_profiles_for_platform("ibkr", policy=policy),
            frozenset({"global_etf_rotation"}),
        )
        matrix = build_platform_profile_matrix(catalog, policy=policy)
        self.assertEqual(matrix[0]["display_name"], "Global ETF Rotation Defense")
        definition = resolve_platform_strategy_definition(
            "global_macro_etf_rotation",
            platform_id="ibkr",
            strategy_catalog=catalog,
            policy=policy,
        )
        self.assertEqual(definition.profile, "global_etf_rotation")

    def test_build_profile_aliases_rejects_duplicate_alias(self) -> None:
        with self.assertRaisesRegex(ValueError, "Duplicate strategy alias"):
            build_profile_aliases(
                {
                    "one": StrategyMetadata(
                        canonical_profile="one",
                        display_name="One",
                        description="",
                        aliases=("shared",),
                    ),
                    "two": StrategyMetadata(
                        canonical_profile="two",
                        display_name="Two",
                        description="",
                        aliases=("shared",),
                    ),
                }
            )
