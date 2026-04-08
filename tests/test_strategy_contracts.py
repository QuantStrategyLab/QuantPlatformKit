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
    ValueTargetExecutionAnnotations,
    ValueTargetExecutionPlan,
    build_value_target_execution_annotations,
    build_value_target_execution_plan,
    build_value_target_plan_payload,
    build_value_target_portfolio_plan,
    build_strategy_context_from_available_inputs,
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
            strategy_profile="hybrid_growth_income",
        )

        self.assertEqual(plan.strategy_profile, "hybrid_growth_income")
        self.assertEqual(plan.target_values["BOXX"], 35000.0)
        self.assertEqual(plan.risk_symbols, ("TQQQ",))
        self.assertEqual(plan.income_symbols, ("QQQI", "SPYI"))
        self.assertEqual(plan.safe_haven_symbols, ("BOXX",))
        self.assertEqual(
            plan.strategy_symbols_risk_safe_income,
            ("TQQQ", "BOXX", "QQQI", "SPYI"),
        )

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
                strategy_profile="hybrid_growth_income",
            )

    def test_build_strategy_context_from_available_inputs_uses_required_inputs_and_portfolio_mapping(self) -> None:
        entrypoint = CallableStrategyEntrypoint(
            manifest=StrategyManifest(
                profile="hybrid_growth_income",
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
                profile="hybrid_growth_income",
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
            strategy_profile="hybrid_growth_income",
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
            strategy_profile="hybrid_growth_income",
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
            strategy_profile="semiconductor_rotation_income",
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
            strategy_profile="semiconductor_rotation_income",
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

        self.assertEqual(payload["strategy_profile"], "semiconductor_rotation_income")
        self.assertEqual(payload["portfolio"]["strategy_symbols"], ("SOXL", "BOXX"))
        self.assertEqual(payload["portfolio"]["sellable_quantities"]["SOXL"], 10)
        self.assertEqual(payload["execution"]["trade_threshold_value"], 250.0)
        self.assertEqual(payload["execution"]["signal_display"], "risk-on")
        self.assertEqual(payload["execution"]["status_display"], "")
        self.assertEqual(payload["execution"]["investable_cash"], 12000.0)

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
