from __future__ import annotations

from types import ModuleType
import sys
import unittest

from quant_platform_kit.common.models import PortfolioSnapshot, Position
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
    AllocationIntent,
    CallableStrategyEntrypoint,
    PositionTarget,
    StrategyArtifactContract,
    StrategyContext,
    StrategyContractValidationError,
    StrategyDecision,
    StrategyManifest,
    StrategyRuntimeAdapter,
    StrategyRuntimePolicy,
    ValueTargetExecutionAnnotations,
    ValueTargetExecutionPlan,
    build_allocation_intent,
    build_allocation_payload,
    build_account_state_from_portfolio_snapshot,
    build_portfolio_snapshot_from_account_state,
    build_strategy_evaluation_inputs,
    build_value_target_allocation_intent,
    build_value_target_execution_annotations,
    build_value_target_execution_plan,
    build_value_target_plan_payload,
    build_value_target_portfolio_inputs_from_account_state,
    build_value_target_portfolio_inputs_from_snapshot,
    build_value_target_portfolio_plan,
    build_value_target_runtime_plan,
    build_strategy_context_from_available_inputs,
    resolve_strategy_artifact_contract,
    resolve_decision_target_mode,
    translate_decision_to_target_mode,
    translate_value_decision_to_weight_targets,
    translate_weight_decision_to_value_targets,
    validate_strategy_artifact_contract,
    validate_strategy_decision,
    validate_strategy_manifest,
    validate_strategy_runtime_adapter,
    validate_strategy_runtime_policy,
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
            profile="tech_communication_pullback_enhancement",
            domain=US_EQUITY_DOMAIN,
            display_name="Tech Communication Pullback Enhancement",
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
            profile="tech_communication_pullback_enhancement",
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
        self.assertEqual(loaded.manifest.display_name, "Tech Communication Pullback Enhancement")

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
                available_inputs=frozenset({"feature_snapshot"}),
                available_capabilities=frozenset({"broker_client"}),
                required_feature_columns=frozenset({"symbol", "close"}),
                snapshot_contract_version="contract.v1",
                runtime_parameter_loader=lambda **_kwargs: {"safe_haven": "BOXX"},
                managed_symbols_extractor=lambda *_args, **_kwargs: ("AAPL", "BOXX"),
            )
        )
        self.assertEqual(adapter.status_icon, "🧲")
        self.assertEqual(adapter.available_inputs, frozenset({"feature_snapshot"}))
        self.assertEqual(adapter.available_capabilities, frozenset({"broker_client"}))

    def test_runtime_adapter_supports_explicit_artifact_contract_and_policy(self) -> None:
        contract = validate_strategy_artifact_contract(
            StrategyArtifactContract(
                requires_snapshot_artifacts=True,
                requires_snapshot_manifest_path=True,
                requires_strategy_config_path=True,
                snapshot_contract_version="tech.feature_snapshot.v1",
                config_source_policy="bundled_or_env",
            )
        )
        policy = validate_strategy_runtime_policy(
            StrategyRuntimePolicy(
                reconciliation_output_policy="optional",
                runtime_execution_window_trading_days=1,
            )
        )
        adapter = validate_strategy_runtime_adapter(
            StrategyRuntimeAdapter(
                available_inputs=frozenset({"feature_snapshot"}),
                artifact_contract=contract,
                runtime_policy=policy,
            )
        )

        resolved_contract = resolve_strategy_artifact_contract(
            adapter,
            required_inputs=frozenset({"feature_snapshot"}),
        )

        self.assertIs(resolved_contract, contract)
        self.assertTrue(resolved_contract.requires_snapshot_manifest_path)
        self.assertTrue(resolved_contract.requires_strategy_config_path)
        self.assertEqual(resolved_contract.config_source_policy, "bundled_or_env")
        self.assertEqual(adapter.runtime_policy.reconciliation_output_policy, "optional")
        self.assertEqual(adapter.runtime_policy.runtime_execution_window_trading_days, 1)

    def test_artifact_contract_resolver_preserves_legacy_adapter_inference(self) -> None:
        adapter = StrategyRuntimeAdapter(
            require_snapshot_manifest=True,
            snapshot_contract_version="legacy.feature_snapshot.v1",
            runtime_parameter_loader=lambda **_kwargs: {"name": "legacy"},
        )

        contract = resolve_strategy_artifact_contract(
            adapter,
            required_inputs=frozenset({"feature_snapshot"}),
        )

        self.assertTrue(contract.requires_snapshot_artifacts)
        self.assertTrue(contract.requires_snapshot_manifest_path)
        self.assertTrue(contract.requires_strategy_config_path)
        self.assertEqual(contract.snapshot_contract_version, "legacy.feature_snapshot.v1")
        self.assertEqual(contract.config_source_policy, "runtime_parameter_loader")

    def test_build_account_state_from_portfolio_snapshot_filters_strategy_symbols(self) -> None:
        snapshot = PortfolioSnapshot(
            as_of="2026-04-09",
            total_equity=50000.0,
            buying_power=12000.0,
            positions=(
                Position(symbol="TQQQ", quantity=5, market_value=1000.0),
                Position(symbol="BOXX", quantity=10, market_value=5000.0),
                Position(symbol="QQQ", quantity=99, market_value=9999.0),
            ),
            metadata={"cash_available_for_trading": 8000.0},
        )

        account_state = build_account_state_from_portfolio_snapshot(
            snapshot,
            strategy_symbols=("TQQQ", "BOXX", "QQQI"),
        )

        self.assertEqual(account_state["available_cash"], 8000.0)
        self.assertEqual(
            account_state["market_values"],
            {"TQQQ": 1000.0, "BOXX": 5000.0, "QQQI": 0.0},
        )
        self.assertEqual(
            account_state["quantities"],
            {"TQQQ": 5, "BOXX": 10, "QQQI": 0},
        )
        self.assertEqual(
            account_state["sellable_quantities"],
            {"TQQQ": 5, "BOXX": 10, "QQQI": 0},
        )
        self.assertEqual(account_state["total_strategy_equity"], 50000.0)

    def test_build_portfolio_snapshot_from_account_state_keeps_strategy_symbol_order(self) -> None:
        snapshot = build_portfolio_snapshot_from_account_state(
            {
                "available_cash": 1500.0,
                "cash_by_currency": {"usd": 1500.0, "sgd": 350.0},
                "market_values": {"QQQI": 300.0, "TQQQ": 1200.0, "QQQ": 8000.0},
                "quantities": {"QQQI": 10, "TQQQ": 3, "QQQ": 99},
                "total_strategy_equity": 3000.0,
            },
            strategy_symbols=("TQQQ", "QQQI", "BOXX"),
            metadata={"account_hash": "acct-001"},
        )

        self.assertEqual(snapshot.total_equity, 3000.0)
        self.assertEqual(snapshot.buying_power, 1500.0)
        self.assertEqual(snapshot.cash_balance, 1500.0)
        self.assertEqual([position.symbol for position in snapshot.positions], ["TQQQ", "QQQI"])
        self.assertEqual(snapshot.metadata["account_hash"], "acct-001")
        self.assertEqual(snapshot.metadata["strategy_symbols"], ("TQQQ", "QQQI", "BOXX"))
        self.assertEqual(snapshot.metadata["cash_by_currency"], {"USD": 1500.0, "SGD": 350.0})

    def test_build_strategy_evaluation_inputs_only_keeps_available_inputs(self) -> None:
        snapshot = object()
        evaluation_inputs = build_strategy_evaluation_inputs(
            available_inputs=frozenset({"benchmark_history", "portfolio_snapshot"}),
            market_inputs={
                "benchmark_history": [1, 2, 3],
                "derived_indicators": {"soxl": {"price": 1.0}},
            },
            portfolio_snapshot=snapshot,
            account_state={"available_cash": 0.0},
            translator=lambda key: key,
            signal_text_fn=lambda key: key,
        )

        self.assertEqual(evaluation_inputs["benchmark_history"], [1, 2, 3])
        self.assertIs(evaluation_inputs["portfolio_snapshot"], snapshot)
        self.assertIn("translator", evaluation_inputs)
        self.assertIn("signal_text_fn", evaluation_inputs)
        self.assertNotIn("derived_indicators", evaluation_inputs)
        self.assertNotIn("account_state", evaluation_inputs)

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

    def test_build_value_target_execution_plan_groups_symbols_by_role(self) -> None:
        decision = StrategyDecision(
            positions=(
                PositionTarget(symbol="TQQQ", target_value=30000.0),
                PositionTarget(symbol="BOXX", target_value=35000.0, role="safe_haven"),
                PositionTarget(symbol="SPYI", target_value=12000.0, role="income"),
                PositionTarget(symbol="QQQI", target_value=18000.0, role="income"),
            )
        )

        plan = build_value_target_execution_plan(
            decision,
            strategy_profile="tqqq_growth_income",
        )

        self.assertEqual(plan.strategy_profile, "tqqq_growth_income")
        self.assertEqual(plan.target_values["BOXX"], 35000.0)
        self.assertEqual(plan.risk_symbols, ("TQQQ",))
        self.assertEqual(plan.income_symbols, ("QQQI", "SPYI"))
        self.assertEqual(plan.safe_haven_symbols, ("BOXX",))
        self.assertEqual(
            plan.strategy_symbols_risk_safe_income,
            ("TQQQ", "BOXX", "QQQI", "SPYI"),
        )

    def test_translate_value_decision_to_weight_targets(self) -> None:
        decision = StrategyDecision(
            positions=(
                PositionTarget(symbol="SOXL", target_value=30000.0),
                PositionTarget(symbol="BOXX", target_value=20000.0, role="safe_haven"),
            ),
            diagnostics={"signal_description": "risk on"},
        )

        translated = translate_value_decision_to_weight_targets(decision, total_equity=50000.0)

        self.assertEqual(translated.positions[0].target_weight, 0.6)
        self.assertEqual(translated.positions[1].target_weight, 0.4)
        self.assertEqual(translated.positions[1].role, "safe_haven")
        self.assertEqual(translated.diagnostics["signal_description"], "risk on")

    def test_translate_weight_decision_to_value_targets(self) -> None:
        decision = StrategyDecision(
            positions=(
                PositionTarget(symbol="AAPL", target_weight=0.35),
                PositionTarget(symbol="MSFT", target_weight=0.35),
                PositionTarget(symbol="BOXX", target_weight=0.30, role="safe_haven"),
            ),
            diagnostics={"benchmark_symbol": "QQQ"},
        )

        translated = translate_weight_decision_to_value_targets(decision, total_equity=20000.0)

        self.assertEqual(translated.positions[0].target_value, 7000.0)
        self.assertEqual(translated.positions[1].target_value, 7000.0)
        self.assertEqual(translated.positions[2].target_value, 6000.0)
        self.assertEqual(translated.positions[2].role, "safe_haven")
        self.assertEqual(translated.diagnostics["benchmark_symbol"], "QQQ")

    def test_resolve_decision_target_mode(self) -> None:
        self.assertEqual(
            resolve_decision_target_mode(
                StrategyDecision(
                    positions=(PositionTarget(symbol="SOXL", target_value=30000.0),)
                )
            ),
            "value",
        )
        self.assertEqual(
            resolve_decision_target_mode(
                StrategyDecision(
                    positions=(PositionTarget(symbol="SOXL", target_weight=0.6),)
                )
            ),
            "weight",
        )
        self.assertIsNone(resolve_decision_target_mode(StrategyDecision()))

    def test_translate_decision_to_target_mode(self) -> None:
        weight_decision = StrategyDecision(
            positions=(
                PositionTarget(symbol="AAPL", target_weight=0.35),
                PositionTarget(symbol="BOXX", target_weight=0.65, role="safe_haven"),
            )
        )
        value_decision = StrategyDecision(
            positions=(
                PositionTarget(symbol="SOXL", target_value=30000.0),
                PositionTarget(symbol="BOXX", target_value=20000.0, role="safe_haven"),
            )
        )

        translated_to_value = translate_decision_to_target_mode(
            weight_decision,
            target_mode="value",
            total_equity=20000.0,
        )
        translated_to_weight = translate_decision_to_target_mode(
            value_decision,
            target_mode="weight",
            total_equity=50000.0,
        )

        self.assertEqual(translated_to_value.positions[0].target_value, 7000.0)
        self.assertEqual(translated_to_value.positions[1].target_value, 13000.0)
        self.assertEqual(translated_to_weight.positions[0].target_weight, 0.6)
        self.assertEqual(translated_to_weight.positions[1].target_weight, 0.4)

    def test_build_value_target_execution_plan_rejects_weight_only_positions(self) -> None:
        decision = StrategyDecision(
            positions=(PositionTarget(symbol="TQQQ", target_weight=1.0),)
        )

        with self.assertRaisesRegex(
            StrategyContractValidationError,
            "requires target_value positions",
        ):
            build_value_target_execution_plan(
                decision,
                strategy_profile="tqqq_growth_income",
            )

    def test_build_allocation_intent_for_weight_targets(self) -> None:
        decision = StrategyDecision(
            positions=(
                PositionTarget(symbol="AAA", target_weight=0.6),
                PositionTarget(symbol="BOXX", target_weight=0.4, role="safe_haven"),
            )
        )

        intent = build_allocation_intent(
            decision,
            strategy_profile="tech_communication_pullback_enhancement",
            strategy_symbols_order="risk_safe_income",
        )

        self.assertIsInstance(intent, AllocationIntent)
        self.assertEqual(intent.target_mode, "weight")
        self.assertEqual(intent.strategy_symbols, ("AAA", "BOXX"))
        self.assertEqual(intent.safe_haven_symbols, ("BOXX",))
        payload = build_allocation_payload(intent)
        self.assertEqual(payload["target_mode"], "weight")
        self.assertEqual(payload["targets"]["AAA"], 0.6)
        self.assertEqual(payload["positions"][1]["role"], "safe_haven")

    def test_build_allocation_intent_rejects_mixed_target_modes(self) -> None:
        decision = StrategyDecision(
            positions=(
                PositionTarget(symbol="AAA", target_weight=0.6),
                PositionTarget(symbol="BOXX", target_value=400.0, role="safe_haven"),
            )
        )

        with self.assertRaisesRegex(StrategyContractValidationError, "single target mode"):
            build_allocation_intent(
                decision,
                strategy_profile="tech_communication_pullback_enhancement",
            )

    def test_build_strategy_context_from_available_inputs_uses_required_inputs_and_portfolio_mapping(self) -> None:
        entrypoint = CallableStrategyEntrypoint(
            manifest=StrategyManifest(
                profile="tqqq_growth_income",
                domain=US_EQUITY_DOMAIN,
                display_name="Hybrid Growth Income",
                description="test",
                required_inputs=frozenset({"qqq_history"}),
            ),
            _evaluate=lambda ctx: StrategyDecision(diagnostics={"ok": True}),
        )
        adapter = StrategyRuntimeAdapter(portfolio_input_name="snapshot")

        ctx = build_strategy_context_from_available_inputs(
            entrypoint=entrypoint,
            runtime_adapter=adapter,
            as_of="2026-04-08",
            available_inputs={"qqq_history": [1, 2, 3], "snapshot": {"positions": []}},
            runtime_config={"translator": "stub"},
        )

        self.assertEqual(ctx.as_of, "2026-04-08")
        self.assertEqual(ctx.market_data, {"qqq_history": [1, 2, 3]})
        self.assertEqual(ctx.portfolio, {"positions": []})
        self.assertEqual(ctx.runtime_config["translator"], "stub")

    def test_build_strategy_context_from_available_inputs_rejects_missing_required_input(self) -> None:
        entrypoint = CallableStrategyEntrypoint(
            manifest=StrategyManifest(
                profile="tqqq_growth_income",
                domain=US_EQUITY_DOMAIN,
                display_name="Hybrid Growth Income",
                description="test",
                required_inputs=frozenset({"qqq_history"}),
            ),
            _evaluate=lambda ctx: StrategyDecision(),
        )

        with self.assertRaisesRegex(StrategyContractValidationError, "missing required inputs"):
            build_strategy_context_from_available_inputs(
                entrypoint=entrypoint,
                runtime_adapter=StrategyRuntimeAdapter(),
                as_of="2026-04-08",
                available_inputs={},
            )

    def test_build_value_target_portfolio_plan_normalizes_state_and_layout(self) -> None:
        decision = StrategyDecision(
            positions=(
                PositionTarget(symbol="TQQQ", target_value=30000.0),
                PositionTarget(symbol="BOXX", target_value=35000.0, role="safe_haven"),
                PositionTarget(symbol="SPYI", target_value=12000.0, role="income"),
                PositionTarget(symbol="QQQI", target_value=18000.0, role="income"),
            )
        )
        execution_plan = build_value_target_execution_plan(
            decision,
            strategy_profile="tqqq_growth_income",
        )

        portfolio_plan = build_value_target_portfolio_plan(
            execution_plan,
            market_values={"TQQQ": 1000.0, "SPYI": 200.0},
            quantities={"TQQQ": 3, "SPYI": 4},
            total_equity=120000.0,
            liquid_cash=20000.0,
            strategy_symbols_order="risk_safe_income",
            portfolio_rows_layout=("risk_safe", "income"),
        )

        self.assertEqual(portfolio_plan.strategy_symbols, ("TQQQ", "BOXX", "QQQI", "SPYI"))
        self.assertEqual(portfolio_plan.portfolio_rows, (("TQQQ", "BOXX"), ("QQQI", "SPYI")))
        self.assertEqual(portfolio_plan.market_values["BOXX"], 0.0)
        self.assertEqual(portfolio_plan.quantities["QQQI"], 0)
        self.assertEqual(portfolio_plan.cash_sweep_symbol, "BOXX")

    def test_build_value_target_portfolio_plan_rejects_unknown_layout(self) -> None:
        execution_plan = ValueTargetExecutionPlan(
            strategy_profile="tqqq_growth_income",
            target_values={"TQQQ": 1.0},
            risk_symbols=("TQQQ",),
            income_symbols=(),
            safe_haven_symbols=(),
        )

        with self.assertRaisesRegex(StrategyContractValidationError, "Unsupported portfolio row layout"):
            build_value_target_portfolio_plan(
                execution_plan,
                market_values={},
                quantities={},
                total_equity=100.0,
                liquid_cash=10.0,
                portfolio_rows_layout=("unknown",),
            )

    def test_build_value_target_plan_payload_supports_field_selection_and_defaults(self) -> None:
        decision = StrategyDecision(
            positions=(
                PositionTarget(symbol="SOXL", target_value=30000.0),
                PositionTarget(symbol="BOXX", target_value=15000.0, role="safe_haven"),
            ),
            diagnostics={
                "execution_annotations": {
                    "trade_threshold_value": 250.0,
                    "signal_display": "risk-on",
                }
            },
        )
        execution_plan = build_value_target_execution_plan(
            decision,
            strategy_profile="soxl_soxx_trend_income",
        )
        portfolio_plan = build_value_target_portfolio_plan(
            execution_plan,
            market_values={"SOXL": 5000.0, "BOXX": 1000.0},
            quantities={"SOXL": 10, "BOXX": 5},
            sellable_quantities={"SOXL": 10, "BOXX": 5},
            total_equity=50000.0,
            liquid_cash=12000.0,
            portfolio_rows_layout=("risk", "safe"),
        )
        annotations = build_value_target_execution_annotations(decision)

        payload = build_value_target_plan_payload(
            strategy_profile="soxl_soxx_trend_income",
            portfolio_plan=portfolio_plan,
            annotations=annotations,
            include_sellable_quantities=True,
            execution_fields=(
                "trade_threshold_value",
                "signal_display",
                "status_display",
                "investable_cash",
            ),
            execution_defaults={
                "status_display": "",
                "investable_cash": portfolio_plan.liquid_cash,
            },
        )

        self.assertEqual(payload["strategy_profile"], "soxl_soxx_trend_income")
        self.assertEqual(payload["allocation"]["target_mode"], "value")
        self.assertEqual(payload["allocation"]["targets"]["SOXL"], 30000.0)
        self.assertEqual(payload["allocation"]["positions"][1]["role"], "safe_haven")
        self.assertEqual(payload["portfolio"]["strategy_symbols"], ("SOXL", "BOXX"))
        self.assertEqual(payload["portfolio"]["sellable_quantities"]["SOXL"], 10)
        self.assertEqual(payload["execution"]["trade_threshold_value"], 250.0)
        self.assertEqual(payload["execution"]["signal_display"], "risk-on")
        self.assertEqual(payload["execution"]["status_display"], "")
        self.assertEqual(payload["execution"]["investable_cash"], 12000.0)

    def test_build_value_target_allocation_intent_reuses_portfolio_symbol_order(self) -> None:
        portfolio_plan = build_value_target_portfolio_plan(
            ValueTargetExecutionPlan(
                strategy_profile="tqqq_growth_income",
                target_values={"TQQQ": 30000.0, "BOXX": 35000.0, "QQQI": 18000.0},
                risk_symbols=("TQQQ",),
                income_symbols=("QQQI",),
                safe_haven_symbols=("BOXX",),
            ),
            market_values={"TQQQ": 1000.0},
            quantities={"TQQQ": 1},
            total_equity=120000.0,
            liquid_cash=20000.0,
            strategy_symbols_order="risk_safe_income",
            portfolio_rows_layout=("risk_safe", "income"),
        )

        intent = build_value_target_allocation_intent(portfolio_plan)

        self.assertEqual(intent.target_mode, "value")
        self.assertEqual(intent.strategy_symbols, ("TQQQ", "BOXX", "QQQI"))
        self.assertEqual(intent.positions[1].symbol, "BOXX")
        self.assertEqual(intent.positions[1].target_value, 35000.0)

    def test_build_value_target_execution_annotations_prefers_normalized_mapping(self) -> None:
        decision = StrategyDecision(
            positions=(PositionTarget(symbol="TQQQ", target_value=1.0),),
            diagnostics={
                "execution_annotations": {
                    "trade_threshold_value": 250.0,
                    "reserved_cash": 500.0,
                    "signal_display": "hold",
                    "status_display": "risk-on",
                    "benchmark_symbol": "QQQ",
                    "benchmark_price": 400.0,
                    "long_trend_value": 380.0,
                    "exit_line": 360.0,
                }
            },
        )

        annotations = build_value_target_execution_annotations(decision)

        self.assertIsInstance(annotations, ValueTargetExecutionAnnotations)
        self.assertEqual(annotations.trade_threshold_value, 250.0)
        self.assertEqual(annotations.reserved_cash, 500.0)
        self.assertEqual(annotations.signal_display, "hold")
        self.assertEqual(annotations.status_display, "risk-on")
        self.assertEqual(annotations.benchmark_symbol, "QQQ")

    def test_build_value_target_execution_annotations_falls_back_to_legacy_keys(self) -> None:
        decision = StrategyDecision(
            positions=(PositionTarget(symbol="SOXL", target_value=1.0),),
            diagnostics={
                "threshold_value": 300.0,
                "signal_message": "signal",
                "market_status": "status",
                "deploy_ratio_text": "60%",
            },
        )

        annotations = build_value_target_execution_annotations(decision)

        self.assertEqual(annotations.trade_threshold_value, 300.0)
        self.assertEqual(annotations.signal_display, "signal")
        self.assertEqual(annotations.status_display, "status")
        self.assertEqual(annotations.deploy_ratio_text, "60%")

    def test_build_value_target_portfolio_inputs_from_snapshot_supports_sellable_quantities(self) -> None:
        snapshot = type(
            "Snapshot",
            (),
            {
                "total_equity": 25000.0,
                "buying_power": 6000.0,
                "positions": (
                    type("Pos", (), {"symbol": "TQQQ", "quantity": 10, "market_value": 5000.0})(),
                    type("Pos", (), {"symbol": "BOXX", "quantity": 20, "market_value": 2000.0})(),
                ),
            },
        )()

        inputs = build_value_target_portfolio_inputs_from_snapshot(
            snapshot,
            include_sellable_quantities=True,
        )

        self.assertEqual(inputs.market_values["TQQQ"], 5000.0)
        self.assertEqual(inputs.quantities["BOXX"], 20)
        self.assertEqual(inputs.sellable_quantities, {"TQQQ": 10, "BOXX": 20})
        self.assertEqual(inputs.total_equity, 25000.0)
        self.assertEqual(inputs.liquid_cash, 6000.0)

    def test_build_value_target_portfolio_inputs_from_account_state_normalizes_payload(self) -> None:
        inputs = build_value_target_portfolio_inputs_from_account_state(
            {
                "market_values": {"SOXL": 30000, "BOXX": 15000},
                "quantities": {"SOXL": 100, "BOXX": 50},
                "sellable_quantities": {"SOXL": 100, "BOXX": 50},
                "total_strategy_equity": 50000,
                "available_cash": 10000,
            }
        )

        self.assertEqual(inputs.market_values, {"SOXL": 30000.0, "BOXX": 15000.0})
        self.assertEqual(inputs.quantities, {"SOXL": 100, "BOXX": 50})
        self.assertEqual(inputs.sellable_quantities, {"SOXL": 100, "BOXX": 50})
        self.assertEqual(inputs.total_equity, 50000.0)
        self.assertEqual(inputs.liquid_cash, 10000.0)

    def test_build_value_target_runtime_plan_translates_decision_with_shared_helper(self) -> None:
        decision = StrategyDecision(
            positions=(
                PositionTarget(symbol="SOXL", target_value=30000.0),
                PositionTarget(symbol="BOXX", target_value=15000.0, role="safe_haven"),
            ),
            diagnostics={
                "execution_annotations": {
                    "trade_threshold_value": 250.0,
                    "signal_display": "risk-on",
                }
            },
        )
        inputs = build_value_target_portfolio_inputs_from_account_state(
            {
                "market_values": {"SOXL": 5000.0, "BOXX": 1000.0},
                "quantities": {"SOXL": 10, "BOXX": 5},
                "sellable_quantities": {"SOXL": 10, "BOXX": 5},
                "total_strategy_equity": 50000.0,
                "available_cash": 12000.0,
            }
        )

        payload = build_value_target_runtime_plan(
            decision,
            strategy_profile="soxl_soxx_trend_income",
            portfolio_inputs=inputs,
            portfolio_rows_layout=("risk", "safe"),
            execution_fields=(
                "trade_threshold_value",
                "signal_display",
                "investable_cash",
            ),
            execution_defaults={"investable_cash": 12000.0},
        )

        self.assertEqual(payload["allocation"]["target_mode"], "value")
        self.assertEqual(payload["allocation"]["targets"]["SOXL"], 30000.0)
        self.assertEqual(payload["portfolio"]["sellable_quantities"]["BOXX"], 5)
        self.assertEqual(payload["execution"]["trade_threshold_value"], 250.0)
        self.assertEqual(payload["execution"]["signal_display"], "risk-on")
        self.assertEqual(payload["execution"]["investable_cash"], 12000.0)
