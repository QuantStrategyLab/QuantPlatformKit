from __future__ import annotations

import unittest

from quant_platform_kit.common.strategies import (
    CRYPTO_DOMAIN,
    PlatformCapabilityMatrix,
    PlatformStrategyPolicy,
    US_EQUITY_DOMAIN,
    StrategyArtifactPaths,
    StrategyComponentDefinition,
    StrategyDefinition,
    StrategyMetadata,
    build_platform_profile_matrix,
    build_platform_profile_status_matrix,
    build_profile_aliases,
    build_strategy_catalog,
    derive_eligible_profiles_for_platform,
    derive_enabled_profiles_for_platform,
    build_strategy_index_rows,
    derive_strategy_artifact_paths,
    get_catalog_compatible_platforms,
    get_catalog_strategy_definition,
    get_catalog_strategy_metadata,
    get_catalog_target_mode,
    get_enabled_profiles_for_platform,
    resolve_catalog_profile,
    load_strategy_component_module,
    resolve_platform_strategy_definition,
)
from quant_platform_kit.common.strategy_contracts import StrategyRuntimeAdapter


class StrategyContractsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy_definitions = {
            "global_etf_rotation": StrategyDefinition(
                profile="global_etf_rotation",
                domain=US_EQUITY_DOMAIN,
                supported_platforms=frozenset({"ibkr", "schwab", "longbridge"}),
                target_mode="weight",
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
                target_mode="weight",
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
        self.assertEqual(by_profile["global_etf_rotation"]["target_mode"], "weight")

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
        status_matrix = build_platform_profile_status_matrix(
            catalog,
            policy=policy,
            eligible_profiles=frozenset({"global_etf_rotation"}),
        )
        self.assertEqual(status_matrix[0]["eligible"], True)
        self.assertEqual(status_matrix[0]["enabled"], True)

    def test_catalog_helpers_expose_target_mode_and_artifact_paths(self) -> None:
        catalog = build_strategy_catalog(
            strategy_definitions={
                "feature_snapshot_strategy": StrategyDefinition(
                    profile="feature_snapshot_strategy",
                    domain=US_EQUITY_DOMAIN,
                    supported_platforms=frozenset({"ibkr"}),
                    required_inputs=frozenset({"feature_snapshot"}),
                    target_mode="weight",
                    bundled_config_relpath="research/configs/example.json",
                )
            }
        )

        self.assertEqual(
            get_catalog_target_mode(catalog, "feature_snapshot_strategy"),
            "weight",
        )
        paths = derive_strategy_artifact_paths(
            catalog,
            "feature_snapshot_strategy",
            artifact_root="/var/strategy-artifacts",
            repo_root="/workspace/runtime",
        )
        self.assertEqual(
            paths,
            StrategyArtifactPaths(
                artifact_root=paths.artifact_root,
                artifact_dir=paths.artifact_dir,
                bundled_config_path=paths.bundled_config_path,
                feature_snapshot_path=paths.feature_snapshot_path,
                feature_snapshot_manifest_path=paths.feature_snapshot_manifest_path,
                reconciliation_output_dir=paths.reconciliation_output_dir,
            ),
        )
        self.assertEqual(
            str(paths.feature_snapshot_path),
            "/var/strategy-artifacts/feature_snapshot_strategy/feature_snapshot_strategy_feature_snapshot_latest.csv",
        )
        self.assertEqual(
            str(paths.feature_snapshot_manifest_path),
            "/var/strategy-artifacts/feature_snapshot_strategy/feature_snapshot_strategy_feature_snapshot_latest.csv.manifest.json",
        )
        self.assertEqual(
            str(paths.bundled_config_path),
            "/workspace/runtime/research/configs/example.json",
        )
        self.assertEqual(
            str(paths.reconciliation_output_dir),
            "/var/strategy-artifacts/feature_snapshot_strategy/reconciliation",
        )

    def test_platform_capability_matrix_derives_eligible_profiles(self) -> None:
        catalog = build_strategy_catalog(
            strategy_definitions={
                "global_etf_rotation": StrategyDefinition(
                    profile="global_etf_rotation",
                    domain=US_EQUITY_DOMAIN,
                    supported_platforms=frozenset({"ibkr"}),
                    required_inputs=frozenset({"historical_close_loader"}),
                    target_mode="weight",
                ),
                "hybrid_growth_income": StrategyDefinition(
                    profile="hybrid_growth_income",
                    domain=US_EQUITY_DOMAIN,
                    supported_platforms=frozenset({"schwab"}),
                    required_inputs=frozenset({"qqq_history", "snapshot"}),
                    target_mode="value",
                ),
                "tech_pullback_cash_buffer": StrategyDefinition(
                    profile="tech_pullback_cash_buffer",
                    domain=US_EQUITY_DOMAIN,
                    supported_platforms=frozenset({"ibkr"}),
                    required_inputs=frozenset({"feature_snapshot"}),
                    target_mode="weight",
                ),
                "schwab_only_weight": StrategyDefinition(
                    profile="schwab_only_weight",
                    domain=US_EQUITY_DOMAIN,
                    supported_platforms=frozenset({"schwab"}),
                    required_inputs=frozenset({"feature_snapshot"}),
                    target_mode="weight",
                ),
            }
        )
        ibkr_matrix = PlatformCapabilityMatrix(
            platform_id="ibkr",
            supported_domains=frozenset({US_EQUITY_DOMAIN}),
            supported_target_modes=frozenset({"weight"}),
            supported_inputs=frozenset({"historical_close_loader", "feature_snapshot"}),
            supported_capabilities=frozenset({"broker_client"}),
        )
        adapters = {
            "global_etf_rotation": StrategyRuntimeAdapter(
                available_inputs=frozenset({"historical_close_loader"}),
                available_capabilities=frozenset({"broker_client"}),
            ),
            "hybrid_growth_income": StrategyRuntimeAdapter(
                available_inputs=frozenset({"qqq_history", "snapshot"}),
            ),
            "tech_pullback_cash_buffer": StrategyRuntimeAdapter(
                available_inputs=frozenset({"feature_snapshot"}),
            ),
            "schwab_only_weight": StrategyRuntimeAdapter(
                available_inputs=frozenset({"feature_snapshot"}),
            ),
        }

        eligible = derive_eligible_profiles_for_platform(
            catalog,
            capability_matrix=ibkr_matrix,
            runtime_adapter_loader=lambda profile: adapters[profile],
        )

        self.assertEqual(
            eligible,
            frozenset({"global_etf_rotation", "tech_pullback_cash_buffer"}),
        )

    def test_platform_capability_matrix_applies_rollout_allowlist(self) -> None:
        catalog = build_strategy_catalog(
            strategy_definitions={
                "global_etf_rotation": StrategyDefinition(
                    profile="global_etf_rotation",
                    domain=US_EQUITY_DOMAIN,
                    supported_platforms=frozenset({"ibkr"}),
                    required_inputs=frozenset({"historical_close_loader"}),
                    target_mode="weight",
                ),
                "tech_pullback_cash_buffer": StrategyDefinition(
                    profile="tech_pullback_cash_buffer",
                    domain=US_EQUITY_DOMAIN,
                    supported_platforms=frozenset({"ibkr"}),
                    required_inputs=frozenset({"feature_snapshot"}),
                    target_mode="weight",
                ),
            }
        )
        ibkr_matrix = PlatformCapabilityMatrix(
            platform_id="ibkr",
            supported_domains=frozenset({US_EQUITY_DOMAIN}),
            supported_target_modes=frozenset({"weight"}),
            supported_inputs=frozenset({"historical_close_loader", "feature_snapshot"}),
            supported_capabilities=frozenset({"broker_client"}),
        )
        adapters = {
            "global_etf_rotation": StrategyRuntimeAdapter(
                available_inputs=frozenset({"historical_close_loader"}),
                available_capabilities=frozenset({"broker_client"}),
            ),
            "tech_pullback_cash_buffer": StrategyRuntimeAdapter(
                available_inputs=frozenset({"feature_snapshot"}),
            ),
        }

        enabled = derive_enabled_profiles_for_platform(
            catalog,
            capability_matrix=ibkr_matrix,
            runtime_adapter_loader=lambda profile: adapters[profile],
            rollout_allowlist=("tech_pullback_cash_buffer",),
        )

        self.assertEqual(enabled, frozenset({"tech_pullback_cash_buffer"}))

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
