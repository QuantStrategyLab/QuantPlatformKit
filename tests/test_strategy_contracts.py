from __future__ import annotations

from types import ModuleType
import sys
import unittest

from quant_platform_kit.common.strategies import (
    CRYPTO_DOMAIN,
    PlatformStrategyPolicy,
    StrategyComponentDefinition,
    StrategyDefinition,
    StrategyEntrypointDefinition,
    StrategyMetadata,
    US_EQUITY_DOMAIN,
    build_strategy_manifest,
    build_strategy_catalog,
    get_enabled_profiles_for_platform,
    load_strategy_entrypoint,
    resolve_platform_strategy_definition,
)
from quant_platform_kit.strategy_contracts import (
    CallableStrategyEntrypoint,
    PositionTarget,
    StrategyContext,
    StrategyContractValidationError,
    StrategyDecision,
    StrategyManifest,
    StrategyRuntimeAdapter,
    validate_strategy_decision,
    validate_strategy_manifest,
    validate_strategy_runtime_adapter,
)


class StrategyContractMigrationTests(unittest.TestCase):
    def _install_module(self, name: str, **attrs: object) -> None:
        module = ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        sys.modules[name] = module
        self.addCleanup(sys.modules.pop, name, None)

    def test_build_strategy_manifest_uses_metadata_and_new_contract_fields(self) -> None:
        definition = StrategyDefinition(
            profile="global_etf_rotation",
            domain=US_EQUITY_DOMAIN,
            supported_platforms=frozenset({"ibkr"}),
            required_inputs=frozenset({"market_data", "portfolio"}),
            compatible_capabilities=frozenset({"rebalance_orders"}),
            default_config={"safe_haven": "BIL"},
        )
        metadata = StrategyMetadata(
            canonical_profile="global_etf_rotation",
            display_name="Global ETF Rotation Defense",
            description="legacy adapter",
            aliases=("global_macro_etf_rotation",),
        )

        manifest = build_strategy_manifest(definition, metadata=metadata)

        self.assertEqual(manifest.display_name, "Global ETF Rotation Defense")
        self.assertEqual(manifest.aliases, ("global_macro_etf_rotation",))
        self.assertEqual(manifest.required_inputs, frozenset({"market_data", "portfolio"}))
        self.assertEqual(manifest.default_config["safe_haven"], "BIL")

    def test_load_strategy_entrypoint_prefers_explicit_entrypoint_definition(self) -> None:
        module_name = "_quant_platform_kit_test_explicit_entrypoint"
        entrypoint = CallableStrategyEntrypoint(
            manifest=StrategyManifest(
                profile="global_etf_rotation",
                domain=US_EQUITY_DOMAIN,
                display_name="Global ETF Rotation Defense",
                description="explicit entrypoint",
                required_inputs=frozenset({"market_data"}),
                compatible_capabilities=frozenset({"rebalance_orders"}),
            ),
            _evaluate=lambda ctx: StrategyDecision(
                positions=(PositionTarget(symbol="SPY", target_weight=1.0),),
                diagnostics={"as_of": ctx.as_of},
            ),
        )
        self._install_module(module_name, entrypoint=entrypoint)
        definition = StrategyDefinition(
            profile="global_etf_rotation",
            domain=US_EQUITY_DOMAIN,
            supported_platforms=frozenset({"ibkr"}),
            entrypoint=StrategyEntrypointDefinition(module_path=module_name),
        )

        loaded = load_strategy_entrypoint(
            definition,
            platform_id="ibkr",
            available_inputs={"market_data"},
            available_capabilities={"rebalance_orders", "notifications"},
        )
        decision = loaded.evaluate(StrategyContext(as_of="2026-04-06"))

        self.assertEqual(loaded.manifest.profile, "global_etf_rotation")
        self.assertEqual(decision.positions[0].symbol, "SPY")
        self.assertEqual(decision.diagnostics["as_of"], "2026-04-06")

    def test_load_strategy_entrypoint_falls_back_to_legacy_component_module(self) -> None:
        module_name = "_quant_platform_kit_test_legacy_component"
        manifest = StrategyManifest(
            profile="tech_pullback_cash_buffer",
            domain=US_EQUITY_DOMAIN,
            display_name="Tech Pullback Cash Buffer",
            description="legacy component with manifest/evaluate",
            required_inputs=frozenset({"market_data"}),
        )

        def evaluate(ctx: StrategyContext) -> StrategyDecision:
            self.assertEqual(ctx.as_of, "2026-04-06")
            return StrategyDecision(
                positions=(PositionTarget(symbol="BOXX", target_weight=0.25),),
                risk_flags=("cash_buffer",),
            )

        self._install_module(module_name, manifest=manifest, evaluate=evaluate)
        definition = StrategyDefinition(
            profile="tech_pullback_cash_buffer",
            domain=US_EQUITY_DOMAIN,
            supported_platforms=frozenset({"ibkr"}),
            components=(
                StrategyComponentDefinition(
                    name="signal_logic",
                    module_path=module_name,
                ),
            ),
        )

        loaded = load_strategy_entrypoint(
            definition,
            platform_id="ibkr",
            available_inputs={"market_data"},
        )
        decision = loaded.evaluate(StrategyContext(as_of="2026-04-06"))

        self.assertEqual(decision.risk_flags, ("cash_buffer",))
        self.assertEqual(loaded.manifest.display_name, "Tech Pullback Cash Buffer")

    def test_load_strategy_entrypoint_rejects_missing_inputs_and_legacy_platform_fallback(self) -> None:
        module_name = "_quant_platform_kit_test_requirements"

        def evaluate(_ctx: StrategyContext) -> StrategyDecision:
            return StrategyDecision(
                positions=(PositionTarget(symbol="BTCUSDT", target_weight=1.0),),
            )

        self._install_module(module_name, evaluate=evaluate)
        definition = StrategyDefinition(
            profile="crypto_leader_rotation",
            domain=CRYPTO_DOMAIN,
            supported_platforms=frozenset({"binance"}),
            components=(
                StrategyComponentDefinition(name="core", module_path=module_name),
            ),
            required_inputs=frozenset({"artifacts"}),
        )
        metadata = StrategyMetadata(
            canonical_profile="crypto_leader_rotation",
            display_name="Crypto Leader Rotation",
            description="legacy fallback manifest",
        )

        with self.assertRaisesRegex(StrategyContractValidationError, "missing inputs"):
            load_strategy_entrypoint(
                definition,
                metadata=metadata,
                platform_id="binance",
                available_inputs={"market_data"},
            )

        with self.assertRaisesRegex(StrategyContractValidationError, "not compatible with platform"):
            load_strategy_entrypoint(
                definition,
                metadata=metadata,
                platform_id="ibkr",
                available_inputs={"artifacts"},
            )

    def test_validators_reject_invalid_manifest_and_decision_shapes(self) -> None:
        with self.assertRaisesRegex(StrategyContractValidationError, "manifest.display_name"):
            validate_strategy_manifest(
                StrategyManifest(
                    profile="global_etf_rotation",
                    domain=US_EQUITY_DOMAIN,
                    display_name="",
                    description="bad",
                )
            )

        with self.assertRaisesRegex(StrategyContractValidationError, "must set target_weight or target_value"):
            validate_strategy_decision(
                StrategyDecision(
                    positions=(PositionTarget(symbol="SPY"),),
                )
            )

        with self.assertRaisesRegex(
            StrategyContractValidationError,
            "runtime_adapter.max_snapshot_month_lag",
        ):
            validate_strategy_runtime_adapter(
                StrategyRuntimeAdapter(max_snapshot_month_lag=-1)
            )

        adapter = validate_strategy_runtime_adapter(
            StrategyRuntimeAdapter(
                status_icon="🧲",
                required_feature_columns=frozenset({"symbol", "close"}),
                snapshot_contract_version="contract.v1",
                runtime_parameter_loader=lambda **_kwargs: {"safe_haven": "BOXX"},
                managed_symbols_extractor=lambda *_args, **_kwargs: ("AAPL", "BOXX"),
            )
        )
        self.assertEqual(adapter.status_icon, "🧲")

    def test_platform_policy_helpers_replace_legacy_global_helpers(self) -> None:
        strategy_definitions = {
            "global_etf_rotation": StrategyDefinition(
                profile="global_etf_rotation",
                domain=US_EQUITY_DOMAIN,
                supported_platforms=frozenset({"ibkr"}),
            )
        }
        catalog = build_strategy_catalog(strategy_definitions=strategy_definitions)
        policy = PlatformStrategyPolicy(
            platform_id="ibkr",
            supported_domains=frozenset({US_EQUITY_DOMAIN}),
            enabled_profiles=frozenset({"global_etf_rotation"}),
            default_profile="global_etf_rotation",
            rollback_profile="global_etf_rotation",
        )
        supported = get_enabled_profiles_for_platform("ibkr", policy=policy)
        definition = resolve_platform_strategy_definition(
            "global_etf_rotation",
            platform_id="ibkr",
            strategy_catalog=catalog,
            policy=policy,
        )
        self.assertEqual(supported, frozenset({"global_etf_rotation"}))
        self.assertEqual(definition.profile, "global_etf_rotation")
