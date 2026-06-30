from __future__ import annotations

from datetime import date, datetime, timedelta
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol
import math


class StrategyContractValidationError(ValueError):
    """Raised when a strategy manifest or decision violates the shared contract."""


@dataclass(frozen=True)
class StrategyManifest:
    profile: str
    domain: str
    display_name: str
    description: str
    aliases: tuple[str, ...] = ()
    required_inputs: frozenset[str] = frozenset()
    compatible_capabilities: frozenset[str] = frozenset()
    default_config: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PositionTarget:
    symbol: str
    target_weight: float | None = None
    target_value: float | None = None
    role: str | None = None
    order_preference: str | None = None


@dataclass(frozen=True)
class BudgetIntent:
    name: str
    symbol: str | None = None
    amount: float | None = None
    unit: str = "quote_ccy"
    purpose: str | None = None


@dataclass(frozen=True)
class StrategyContext:
    as_of: Any
    market_data: Mapping[str, Any] = field(default_factory=dict)
    portfolio: Any | None = None
    state: Mapping[str, Any] = field(default_factory=dict)
    runtime_config: Mapping[str, Any] = field(default_factory=dict)
    capabilities: Mapping[str, Any] = field(default_factory=dict)
    artifacts: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyDecision:
    positions: tuple[PositionTarget, ...] = ()
    budgets: tuple[BudgetIntent, ...] = ()
    risk_flags: tuple[str, ...] = ()
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AllocationIntent:
    strategy_profile: str
    target_mode: str
    strategy_symbols: tuple[str, ...]
    risk_symbols: tuple[str, ...]
    income_symbols: tuple[str, ...]
    safe_haven_symbols: tuple[str, ...]
    positions: tuple[PositionTarget, ...]


@dataclass(frozen=True)
class ValueTargetExecutionPlan:
    strategy_profile: str
    target_values: Mapping[str, float]
    risk_symbols: tuple[str, ...]
    income_symbols: tuple[str, ...]
    safe_haven_symbols: tuple[str, ...]

    @property
    def strategy_symbols_risk_safe_income(self) -> tuple[str, ...]:
        return tuple(self.risk_symbols + self.safe_haven_symbols + self.income_symbols)

    @property
    def strategy_symbols_risk_income_safe(self) -> tuple[str, ...]:
        return tuple(self.risk_symbols + self.income_symbols + self.safe_haven_symbols)


@dataclass(frozen=True)
class ValueTargetPortfolioPlan:
    strategy_profile: str
    target_values: Mapping[str, float]
    risk_symbols: tuple[str, ...]
    income_symbols: tuple[str, ...]
    safe_haven_symbols: tuple[str, ...]
    strategy_symbols: tuple[str, ...]
    portfolio_rows: tuple[tuple[str, ...], ...]
    market_values: Mapping[str, float]
    quantities: Mapping[str, float]
    sellable_quantities: Mapping[str, float] | None
    total_equity: float
    liquid_cash: float
    cash_sweep_symbol: str | None = None


@dataclass(frozen=True)
class ValueTargetExecutionAnnotations:
    trade_threshold_value: float
    reserved_cash: float = 0.0
    signal_display: str | None = None
    status_display: str | None = None
    dashboard_text: str | None = None
    signal_date: str | None = None
    effective_date: str | None = None
    execution_timing_contract: str | None = None
    execution_calendar_source: str | None = None
    signal_effective_after_trading_days: int | None = None
    separator: str | None = None
    benchmark_symbol: str | None = None
    benchmark_price: float | None = None
    long_trend_value: float | None = None
    exit_line: float | None = None
    deploy_ratio_text: str | None = None
    income_ratio_text: str | None = None
    income_locked_ratio_text: str | None = None
    active_risk_asset: str | None = None
    current_min_trade: float | None = None
    investable_cash: float | None = None


class StrategyEntrypoint(Protocol):
    manifest: StrategyManifest

    def evaluate(self, ctx: StrategyContext) -> StrategyDecision: ...


@dataclass(frozen=True)
class StrategyArtifactContract:
    requires_snapshot_artifacts: bool = False
    requires_snapshot_manifest_path: bool = False
    requires_strategy_config_path: bool = False
    snapshot_contract_version: str | None = None
    config_source_policy: str = "none"


@dataclass(frozen=True)
class StrategyRuntimePolicy:
    reconciliation_output_policy: str = "none"
    runtime_execution_window_trading_days: int | None = None
    signal_effective_after_trading_days: int | None = None


@dataclass(frozen=True)
class StrategyRuntimeAdapter:
    status_icon: str = "🐤"
    available_inputs: frozenset[str] = frozenset()
    available_capabilities: frozenset[str] = frozenset()
    required_feature_columns: frozenset[str] = frozenset()
    snapshot_date_columns: tuple[str, ...] = ("as_of", "snapshot_date")
    max_snapshot_month_lag: int = 1
    require_snapshot_manifest: bool = False
    snapshot_contract_version: str | None = None
    runtime_parameter_loader: Callable[..., Mapping[str, object]] | None = None
    managed_symbols_extractor: Callable[..., tuple[str, ...]] | None = None
    portfolio_input_name: str | None = None
    artifact_contract: StrategyArtifactContract | None = None
    runtime_policy: StrategyRuntimePolicy = field(default_factory=StrategyRuntimePolicy)


@dataclass(frozen=True)
class CallableStrategyEntrypoint:
    manifest: StrategyManifest
    _evaluate: Callable[[StrategyContext], StrategyDecision]

    def evaluate(self, ctx: StrategyContext) -> StrategyDecision:
        decision = self._evaluate(ctx)
        return validate_strategy_decision(decision)


def _ensure_non_empty_string(value: str, *, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise StrategyContractValidationError(f"{field_name} must be a non-empty string")


def _ensure_string_set(values: frozenset[str] | tuple[str, ...], *, field_name: str) -> None:
    for value in values:
        _ensure_non_empty_string(value, field_name=field_name)


def _ensure_finite_number(value: float | None, *, field_name: str) -> None:
    if value is None:
        return
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise StrategyContractValidationError(f"{field_name} must be a finite number when provided")


def _ensure_bool(value: bool, *, field_name: str) -> None:
    if not isinstance(value, bool):
        raise StrategyContractValidationError(f"{field_name} must be a bool")


def _ensure_allowed_string(
    value: str,
    *,
    field_name: str,
    allowed_values: frozenset[str],
) -> None:
    _ensure_non_empty_string(value, field_name=field_name)
    if value not in allowed_values:
        allowed = ", ".join(sorted(allowed_values))
        raise StrategyContractValidationError(f"{field_name} must be one of: {allowed}")


_CONFIG_SOURCE_POLICIES = frozenset(
    {
        "none",
        "bundled_or_env",
        "env_only",
        "artifact_manifest",
        "runtime_parameter_loader",
    }
)
_RECONCILIATION_OUTPUT_POLICIES = frozenset({"none", "optional", "required"})


def _normalize_as_of_date(as_of: Any) -> date:
    if isinstance(as_of, datetime):
        return as_of.date()
    if isinstance(as_of, date):
        return as_of
    to_pydatetime = getattr(as_of, "to_pydatetime", None)
    if callable(to_pydatetime):
        candidate = to_pydatetime()
        if isinstance(candidate, datetime):
            return candidate.date()
        if isinstance(candidate, date):
            return candidate
    if isinstance(as_of, str):
        try:
            return datetime.fromisoformat(as_of).date()
        except ValueError:
            return date.fromisoformat(as_of)
    return datetime.fromisoformat(str(as_of)).date()


def _next_trading_days(
    start_date: date,
    *,
    count: int,
) -> tuple[tuple[date, ...], str]:
    normalized_start = _normalize_as_of_date(start_date)
    days: list[date] = []
    current = normalized_start
    while len(days) < max(1, count):
        current += timedelta(days=1)
        if current.weekday() < 5:
            days.append(current)
    return tuple(days[:count]), "business_day_fallback"


def build_execution_timing_metadata(
    *,
    signal_date: Any,
    signal_effective_after_trading_days: int | None = None,
) -> dict[str, Any]:
    resolved_signal_date = _normalize_as_of_date(signal_date)
    metadata: dict[str, Any] = {
        "signal_date": resolved_signal_date.isoformat(),
    }
    if signal_effective_after_trading_days is None:
        return metadata

    delay = int(signal_effective_after_trading_days)
    metadata["signal_effective_after_trading_days"] = delay
    if delay == 0:
        metadata["effective_date"] = resolved_signal_date.isoformat()
        metadata["execution_timing_contract"] = "same_trading_day"
        metadata["execution_calendar_source"] = "signal_date"
        return metadata

    trading_days, calendar_source = _next_trading_days(
        resolved_signal_date,
        count=delay,
    )
    effective_date = trading_days[-1] if trading_days else resolved_signal_date
    metadata["effective_date"] = effective_date.isoformat()
    metadata["execution_timing_contract"] = (
        "next_trading_day" if delay == 1 else f"next_{delay}_trading_days"
    )
    metadata["execution_calendar_source"] = calendar_source
    return metadata


def apply_runtime_policy_to_runtime_config(
    runtime_config: dict[str, Any],
    runtime_adapter: StrategyRuntimeAdapter,
) -> None:
    trading_days = runtime_adapter.runtime_policy.runtime_execution_window_trading_days
    if trading_days is not None:
        runtime_config.setdefault("runtime_execution_window_trading_days", trading_days)
    signal_delay = runtime_adapter.runtime_policy.signal_effective_after_trading_days
    if signal_delay is not None:
        runtime_config.setdefault("signal_effective_after_trading_days", signal_delay)


def validate_strategy_manifest(manifest: StrategyManifest) -> StrategyManifest:
    if not isinstance(manifest, StrategyManifest):
        raise StrategyContractValidationError(
            f"manifest must be StrategyManifest, got {type(manifest).__name__}"
        )

    _ensure_non_empty_string(manifest.profile, field_name="manifest.profile")
    _ensure_non_empty_string(manifest.domain, field_name="manifest.domain")
    _ensure_non_empty_string(manifest.display_name, field_name="manifest.display_name")
    _ensure_non_empty_string(manifest.description, field_name="manifest.description")
    _ensure_string_set(manifest.aliases, field_name="manifest.aliases[]")
    _ensure_string_set(manifest.required_inputs, field_name="manifest.required_inputs[]")
    _ensure_string_set(
        manifest.compatible_capabilities,
        field_name="manifest.compatible_capabilities[]",
    )
    if not isinstance(manifest.default_config, Mapping):
        raise StrategyContractValidationError("manifest.default_config must be a mapping")
    return manifest


def validate_strategy_decision(decision: StrategyDecision) -> StrategyDecision:
    if not isinstance(decision, StrategyDecision):
        raise StrategyContractValidationError(
            f"decision must be StrategyDecision, got {type(decision).__name__}"
        )

    if not isinstance(decision.diagnostics, Mapping):
        raise StrategyContractValidationError("decision.diagnostics must be a mapping")

    for position in decision.positions:
        if not isinstance(position, PositionTarget):
            raise StrategyContractValidationError(
                f"decision.positions entries must be PositionTarget, got {type(position).__name__}"
            )
        _ensure_non_empty_string(position.symbol, field_name="position.symbol")
        if position.target_weight is None and position.target_value is None:
            raise StrategyContractValidationError(
                f"position {position.symbol!r} must set target_weight or target_value"
            )
        _ensure_finite_number(position.target_weight, field_name="position.target_weight")
        _ensure_finite_number(position.target_value, field_name="position.target_value")

    for budget in decision.budgets:
        if not isinstance(budget, BudgetIntent):
            raise StrategyContractValidationError(
                f"decision.budgets entries must be BudgetIntent, got {type(budget).__name__}"
            )
        _ensure_non_empty_string(budget.name, field_name="budget.name")
        if budget.symbol is not None:
            _ensure_non_empty_string(budget.symbol, field_name="budget.symbol")
        _ensure_non_empty_string(budget.unit, field_name="budget.unit")
        _ensure_finite_number(budget.amount, field_name="budget.amount")

    for risk_flag in decision.risk_flags:
        _ensure_non_empty_string(risk_flag, field_name="decision.risk_flags[]")

    return decision


def validate_strategy_artifact_contract(
    contract: StrategyArtifactContract,
) -> StrategyArtifactContract:
    if not isinstance(contract, StrategyArtifactContract):
        raise StrategyContractValidationError(
            f"artifact contract must be StrategyArtifactContract, got {type(contract).__name__}"
        )

    _ensure_bool(
        contract.requires_snapshot_artifacts,
        field_name="artifact_contract.requires_snapshot_artifacts",
    )
    _ensure_bool(
        contract.requires_snapshot_manifest_path,
        field_name="artifact_contract.requires_snapshot_manifest_path",
    )
    _ensure_bool(
        contract.requires_strategy_config_path,
        field_name="artifact_contract.requires_strategy_config_path",
    )
    if contract.requires_snapshot_manifest_path and not contract.requires_snapshot_artifacts:
        raise StrategyContractValidationError(
            "artifact_contract.requires_snapshot_manifest_path requires snapshot artifacts"
        )
    if contract.requires_strategy_config_path and contract.config_source_policy == "none":
        raise StrategyContractValidationError(
            "artifact_contract.config_source_policy must describe required strategy config"
        )
    if contract.snapshot_contract_version is not None:
        _ensure_non_empty_string(
            contract.snapshot_contract_version,
            field_name="artifact_contract.snapshot_contract_version",
        )
    _ensure_allowed_string(
        contract.config_source_policy,
        field_name="artifact_contract.config_source_policy",
        allowed_values=_CONFIG_SOURCE_POLICIES,
    )
    return contract


def validate_strategy_runtime_policy(policy: StrategyRuntimePolicy) -> StrategyRuntimePolicy:
    if not isinstance(policy, StrategyRuntimePolicy):
        raise StrategyContractValidationError(
            f"runtime policy must be StrategyRuntimePolicy, got {type(policy).__name__}"
        )

    _ensure_allowed_string(
        policy.reconciliation_output_policy,
        field_name="runtime_policy.reconciliation_output_policy",
        allowed_values=_RECONCILIATION_OUTPUT_POLICIES,
    )
    if policy.runtime_execution_window_trading_days is not None:
        if (
            not isinstance(policy.runtime_execution_window_trading_days, int)
            or policy.runtime_execution_window_trading_days <= 0
        ):
            raise StrategyContractValidationError(
                "runtime_policy.runtime_execution_window_trading_days must be a positive integer"
            )
    if policy.signal_effective_after_trading_days is not None:
        if (
            not isinstance(policy.signal_effective_after_trading_days, int)
            or policy.signal_effective_after_trading_days < 0
        ):
            raise StrategyContractValidationError(
                "runtime_policy.signal_effective_after_trading_days must be a non-negative integer"
            )
    return policy


def validate_strategy_runtime_adapter(adapter: StrategyRuntimeAdapter) -> StrategyRuntimeAdapter:
    if not isinstance(adapter, StrategyRuntimeAdapter):
        raise StrategyContractValidationError(
            f"runtime adapter must be StrategyRuntimeAdapter, got {type(adapter).__name__}"
        )

    _ensure_non_empty_string(adapter.status_icon, field_name="runtime_adapter.status_icon")
    _ensure_string_set(
        adapter.available_inputs,
        field_name="runtime_adapter.available_inputs[]",
    )
    _ensure_string_set(
        adapter.available_capabilities,
        field_name="runtime_adapter.available_capabilities[]",
    )
    _ensure_string_set(
        adapter.required_feature_columns,
        field_name="runtime_adapter.required_feature_columns[]",
    )
    _ensure_string_set(
        adapter.snapshot_date_columns,
        field_name="runtime_adapter.snapshot_date_columns[]",
    )
    if not isinstance(adapter.max_snapshot_month_lag, int) or adapter.max_snapshot_month_lag < 0:
        raise StrategyContractValidationError(
            "runtime_adapter.max_snapshot_month_lag must be a non-negative integer"
        )
    if adapter.snapshot_contract_version is not None:
        _ensure_non_empty_string(
            adapter.snapshot_contract_version,
            field_name="runtime_adapter.snapshot_contract_version",
        )
    if adapter.runtime_parameter_loader is not None and not callable(adapter.runtime_parameter_loader):
        raise StrategyContractValidationError(
            "runtime_adapter.runtime_parameter_loader must be callable when provided"
        )
    if adapter.managed_symbols_extractor is not None and not callable(adapter.managed_symbols_extractor):
        raise StrategyContractValidationError(
            "runtime_adapter.managed_symbols_extractor must be callable when provided"
        )
    if adapter.portfolio_input_name is not None:
        _ensure_non_empty_string(
            adapter.portfolio_input_name,
            field_name="runtime_adapter.portfolio_input_name",
        )
    if adapter.artifact_contract is not None:
        validate_strategy_artifact_contract(adapter.artifact_contract)
    validate_strategy_runtime_policy(adapter.runtime_policy)
    return adapter


def resolve_strategy_artifact_contract(
    adapter: StrategyRuntimeAdapter,
    *,
    required_inputs: frozenset[str] | set[str] | tuple[str, ...] = frozenset(),
) -> StrategyArtifactContract:
    validate_strategy_runtime_adapter(adapter)
    if adapter.artifact_contract is not None:
        return adapter.artifact_contract

    normalized_required_inputs = frozenset(str(value).strip() for value in required_inputs)
    requires_snapshot_artifacts = "feature_snapshot" in normalized_required_inputs
    requires_strategy_config_path = bool(
        requires_snapshot_artifacts and callable(adapter.runtime_parameter_loader)
    )
    config_source_policy = "runtime_parameter_loader" if requires_strategy_config_path else "none"
    return validate_strategy_artifact_contract(
        StrategyArtifactContract(
            requires_snapshot_artifacts=requires_snapshot_artifacts,
            requires_snapshot_manifest_path=bool(
                requires_snapshot_artifacts and adapter.require_snapshot_manifest
            ),
            requires_strategy_config_path=requires_strategy_config_path,
            snapshot_contract_version=adapter.snapshot_contract_version,
            config_source_policy=config_source_policy,
        )
    )


def build_value_target_execution_plan(
    decision: StrategyDecision,
    *,
    strategy_profile: str,
) -> ValueTargetExecutionPlan:
    validate_strategy_decision(decision)

    target_values: dict[str, float] = {}
    for position in decision.positions:
        if position.target_value is None:
            raise StrategyContractValidationError(
                "ValueTargetExecutionPlan requires target_value positions; "
                f"position {position.symbol!r} is missing target_value"
            )
        target_values[position.symbol] = float(position.target_value)

    risk_symbols: list[str] = []
    income_symbols: list[str] = []
    safe_haven_symbols: list[str] = []
    for position in decision.positions:
        if position.role == "safe_haven":
            safe_haven_symbols.append(position.symbol)
        elif position.role == "income":
            income_symbols.append(position.symbol)
        else:
            risk_symbols.append(position.symbol)

    ordered_income = tuple(
        sorted(
            dict.fromkeys(income_symbols),
            key=lambda symbol: (-target_values.get(symbol, 0.0), symbol),
        )
    )
    return ValueTargetExecutionPlan(
        strategy_profile=str(strategy_profile),
        target_values=target_values,
        risk_symbols=tuple(sorted(dict.fromkeys(risk_symbols))),
        income_symbols=ordered_income,
        safe_haven_symbols=tuple(sorted(dict.fromkeys(safe_haven_symbols))),
    )


def _role_for_symbol(
    symbol: str,
    *,
    risk_symbols: tuple[str, ...],
    income_symbols: tuple[str, ...],
    safe_haven_symbols: tuple[str, ...],
) -> str:
    if symbol in safe_haven_symbols:
        return "safe_haven"
    if symbol in income_symbols:
        return "income"
    if symbol in risk_symbols:
        return "risk"
    return "risk"


def build_allocation_intent(
    decision: StrategyDecision,
    *,
    strategy_profile: str,
    strategy_symbols_order: str = "decision",
) -> AllocationIntent:
    validate_strategy_decision(decision)
    if not decision.positions:
        raise StrategyContractValidationError(
            "AllocationIntent requires at least one position target"
        )

    weight_symbols: list[str] = []
    value_symbols: list[str] = []
    risk_symbols: list[str] = []
    income_symbols: list[str] = []
    safe_haven_symbols: list[str] = []
    for position in decision.positions:
        has_weight = position.target_weight is not None
        has_value = position.target_value is not None
        if has_weight and has_value:
            raise StrategyContractValidationError(
                "AllocationIntent positions must not set both target_weight and target_value; "
                f"position {position.symbol!r} is ambiguous"
            )
        if has_weight:
            weight_symbols.append(position.symbol)
        elif has_value:
            value_symbols.append(position.symbol)
        else:
            raise StrategyContractValidationError(
                f"position {position.symbol!r} must set target_weight or target_value"
            )

        if position.role == "safe_haven":
            safe_haven_symbols.append(position.symbol)
        elif position.role == "income":
            income_symbols.append(position.symbol)
        else:
            risk_symbols.append(position.symbol)

    target_mode: str
    if weight_symbols and value_symbols:
        raise StrategyContractValidationError(
            "AllocationIntent requires a single target mode across all positions"
        )
    if weight_symbols:
        target_mode = "weight"
    elif value_symbols:
        target_mode = "value"
    else:
        raise StrategyContractValidationError(
            "AllocationIntent requires at least one target_weight or target_value"
        )

    decision_order_symbols = tuple(dict.fromkeys(position.symbol for position in decision.positions))
    risk_symbols_unique = tuple(sorted(dict.fromkeys(risk_symbols)))
    safe_haven_symbols_unique = tuple(sorted(dict.fromkeys(safe_haven_symbols)))
    income_symbols_unique = tuple(sorted(dict.fromkeys(income_symbols)))
    if strategy_symbols_order == "decision":
        strategy_symbols = decision_order_symbols
    elif strategy_symbols_order == "risk_safe_income":
        strategy_symbols = tuple(
            risk_symbols_unique + safe_haven_symbols_unique + income_symbols_unique
        )
    elif strategy_symbols_order == "risk_income_safe":
        strategy_symbols = tuple(
            risk_symbols_unique + income_symbols_unique + safe_haven_symbols_unique
        )
    else:
        raise StrategyContractValidationError(
            "allocation_intent.strategy_symbols_order must be one of: "
            "decision, risk_safe_income, risk_income_safe"
        )

    positions_by_symbol = {position.symbol: position for position in decision.positions}
    ordered_positions = tuple(positions_by_symbol[symbol] for symbol in strategy_symbols)
    return AllocationIntent(
        strategy_profile=str(strategy_profile),
        target_mode=target_mode,
        strategy_symbols=strategy_symbols,
        risk_symbols=risk_symbols_unique,
        income_symbols=income_symbols_unique,
        safe_haven_symbols=safe_haven_symbols_unique,
        positions=ordered_positions,
    )


def build_allocation_payload(intent: AllocationIntent) -> dict[str, Any]:
    if not isinstance(intent, AllocationIntent):
        raise StrategyContractValidationError("intent must be AllocationIntent")
    if intent.target_mode not in {"weight", "value"}:
        raise StrategyContractValidationError(
            "allocation intent target_mode must be weight or value"
        )

    target_key = "target_weight" if intent.target_mode == "weight" else "target_value"
    targets: dict[str, float] = {}
    positions_payload: list[dict[str, Any]] = []
    for position in intent.positions:
        target_value = (
            float(position.target_weight)
            if intent.target_mode == "weight"
            else float(position.target_value)
        )
        targets[position.symbol] = target_value
        payload = {
            "symbol": position.symbol,
            target_key: target_value,
            "role": _role_for_symbol(
                position.symbol,
                risk_symbols=intent.risk_symbols,
                income_symbols=intent.income_symbols,
                safe_haven_symbols=intent.safe_haven_symbols,
            ),
        }
        if position.order_preference:
            payload["order_preference"] = str(position.order_preference)
        positions_payload.append(payload)

    return {
        "strategy_profile": intent.strategy_profile,
        "target_mode": intent.target_mode,
        "strategy_symbols": intent.strategy_symbols,
        "risk_symbols": intent.risk_symbols,
        "income_symbols": intent.income_symbols,
        "safe_haven_symbols": intent.safe_haven_symbols,
        "targets": targets,
        "positions": positions_payload,
    }


def build_value_target_allocation_intent(
    portfolio_plan: ValueTargetPortfolioPlan,
) -> AllocationIntent:
    if not isinstance(portfolio_plan, ValueTargetPortfolioPlan):
        raise StrategyContractValidationError(
            "portfolio_plan must be ValueTargetPortfolioPlan"
        )
    positions = []
    for symbol in portfolio_plan.strategy_symbols:
        role = _role_for_symbol(
            symbol,
            risk_symbols=portfolio_plan.risk_symbols,
            income_symbols=portfolio_plan.income_symbols,
            safe_haven_symbols=portfolio_plan.safe_haven_symbols,
        )
        positions.append(
            PositionTarget(
                symbol=symbol,
                target_value=float(portfolio_plan.target_values.get(symbol, 0.0)),
                role=role,
            )
        )
    return AllocationIntent(
        strategy_profile=portfolio_plan.strategy_profile,
        target_mode="value",
        strategy_symbols=portfolio_plan.strategy_symbols,
        risk_symbols=portfolio_plan.risk_symbols,
        income_symbols=portfolio_plan.income_symbols,
        safe_haven_symbols=portfolio_plan.safe_haven_symbols,
        positions=tuple(positions),
    )


def build_strategy_context_from_available_inputs(
    *,
    entrypoint: StrategyEntrypoint,
    runtime_adapter: StrategyRuntimeAdapter | None,
    as_of: Any,
    available_inputs: Mapping[str, Any],
    runtime_config: Mapping[str, Any] | None = None,
    state: Mapping[str, Any] | None = None,
    capabilities: Mapping[str, Any] | None = None,
) -> StrategyContext:
    manifest = validate_strategy_manifest(entrypoint.manifest)
    required_inputs = frozenset(manifest.required_inputs)
    provided = dict(available_inputs or {})
    missing_inputs = sorted(required_inputs - frozenset(provided))
    if missing_inputs:
        raise StrategyContractValidationError(
            "Strategy runtime is missing required inputs: "
            + ", ".join(missing_inputs)
        )

    portfolio = None
    if runtime_adapter is not None and runtime_adapter.portfolio_input_name is not None:
        portfolio_input_name = runtime_adapter.portfolio_input_name
        if portfolio_input_name not in provided:
            raise StrategyContractValidationError(
                f"Strategy runtime is missing portfolio input: {portfolio_input_name}"
            )
        portfolio = provided[portfolio_input_name]

    market_data = {name: provided[name] for name in required_inputs}
    return StrategyContext(
        as_of=as_of,
        market_data=market_data,
        portfolio=portfolio,
        state=dict(state or {}),
        runtime_config=dict(runtime_config or {}),
        capabilities=dict(capabilities or {}),
    )


def build_value_target_portfolio_plan(
    execution_plan: ValueTargetExecutionPlan,
    *,
    market_values: Mapping[str, float],
    quantities: Mapping[str, float],
    total_equity: float,
    liquid_cash: float,
    sellable_quantities: Mapping[str, float] | None = None,
    strategy_symbols_order: str = "risk_safe_income",
    portfolio_rows_layout: tuple[str, ...] = ("risk_safe", "income"),
) -> ValueTargetPortfolioPlan:
    if not isinstance(execution_plan, ValueTargetExecutionPlan):
        raise StrategyContractValidationError(
            "execution_plan must be ValueTargetExecutionPlan"
        )
    _ensure_finite_number(total_equity, field_name="portfolio_plan.total_equity")
    _ensure_finite_number(liquid_cash, field_name="portfolio_plan.liquid_cash")

    if strategy_symbols_order == "risk_safe_income":
        strategy_symbols = execution_plan.strategy_symbols_risk_safe_income
    elif strategy_symbols_order == "risk_income_safe":
        strategy_symbols = execution_plan.strategy_symbols_risk_income_safe
    else:
        raise StrategyContractValidationError(
            "portfolio_plan.strategy_symbols_order must be one of: "
            "risk_safe_income, risk_income_safe"
        )

    row_segments = {
        "risk": execution_plan.risk_symbols,
        "income": execution_plan.income_symbols,
        "safe": execution_plan.safe_haven_symbols,
        "risk_safe": execution_plan.risk_symbols + execution_plan.safe_haven_symbols,
        "risk_income": execution_plan.risk_symbols + execution_plan.income_symbols,
    }
    portfolio_rows: list[tuple[str, ...]] = []
    for row_name in portfolio_rows_layout:
        row_key = str(row_name).strip().lower()
        row_symbols = row_segments.get(row_key)
        if row_symbols is None:
            raise StrategyContractValidationError(
                f"Unsupported portfolio row layout segment: {row_name!r}"
            )
        if row_symbols:
            portfolio_rows.append(tuple(row_symbols))

    normalized_market_values = {
        symbol: float(market_values.get(symbol, 0.0))
        for symbol in strategy_symbols
    }
    normalized_quantities = {
        symbol: float(quantities.get(symbol, 0.0))
        for symbol in strategy_symbols
    }
    normalized_sellable_quantities = (
        None
        if sellable_quantities is None
        else {
            symbol: float(sellable_quantities.get(symbol, 0.0))
            for symbol in strategy_symbols
        }
    )
    cash_sweep_symbol = (
        execution_plan.safe_haven_symbols[0]
        if execution_plan.safe_haven_symbols
        else None
    )
    return ValueTargetPortfolioPlan(
        strategy_profile=execution_plan.strategy_profile,
        target_values=dict(execution_plan.target_values),
        risk_symbols=execution_plan.risk_symbols,
        income_symbols=execution_plan.income_symbols,
        safe_haven_symbols=execution_plan.safe_haven_symbols,
        strategy_symbols=strategy_symbols,
        portfolio_rows=tuple(portfolio_rows),
        market_values=normalized_market_values,
        quantities=normalized_quantities,
        sellable_quantities=normalized_sellable_quantities,
        total_equity=float(total_equity),
        liquid_cash=float(liquid_cash),
        cash_sweep_symbol=cash_sweep_symbol,
    )


def build_value_target_plan_payload(
    *,
    strategy_profile: str,
    portfolio_plan: ValueTargetPortfolioPlan,
    annotations: ValueTargetExecutionAnnotations,
    include_sellable_quantities: bool = False,
    execution_fields: tuple[str, ...] | None = None,
    execution_defaults: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(portfolio_plan, ValueTargetPortfolioPlan):
        raise StrategyContractValidationError(
            "portfolio_plan must be ValueTargetPortfolioPlan"
        )
    if not isinstance(annotations, ValueTargetExecutionAnnotations):
        raise StrategyContractValidationError(
            "annotations must be ValueTargetExecutionAnnotations"
        )

    portfolio_payload: dict[str, Any] = {
        "strategy_symbols": portfolio_plan.strategy_symbols,
        "portfolio_rows": portfolio_plan.portfolio_rows,
        "market_values": dict(portfolio_plan.market_values),
        "quantities": dict(portfolio_plan.quantities),
        "target_values": dict(portfolio_plan.target_values),
        "total_equity": portfolio_plan.total_equity,
        "liquid_cash": portfolio_plan.liquid_cash,
        "cash_sweep_symbol": portfolio_plan.cash_sweep_symbol,
        "risk_symbols": portfolio_plan.risk_symbols,
        "income_symbols": portfolio_plan.income_symbols,
        "safe_haven_symbols": portfolio_plan.safe_haven_symbols,
    }
    if include_sellable_quantities:
        portfolio_payload["sellable_quantities"] = dict(
            portfolio_plan.sellable_quantities or {}
        )

    defaults = dict(execution_defaults or {})
    candidate_values: dict[str, Any] = {
        "trade_threshold_value": float(annotations.trade_threshold_value),
        "reserved_cash": float(annotations.reserved_cash),
        "signal_display": annotations.signal_display,
        "status_display": annotations.status_display,
        "dashboard_text": annotations.dashboard_text,
        "signal_date": annotations.signal_date,
        "effective_date": annotations.effective_date,
        "execution_timing_contract": annotations.execution_timing_contract,
        "execution_calendar_source": annotations.execution_calendar_source,
        "signal_effective_after_trading_days": annotations.signal_effective_after_trading_days,
        "separator": annotations.separator,
        "benchmark_symbol": annotations.benchmark_symbol,
        "benchmark_price": annotations.benchmark_price,
        "long_trend_value": annotations.long_trend_value,
        "exit_line": annotations.exit_line,
        "deploy_ratio_text": annotations.deploy_ratio_text,
        "income_ratio_text": annotations.income_ratio_text,
        "income_locked_ratio_text": annotations.income_locked_ratio_text,
        "active_risk_asset": annotations.active_risk_asset,
        "current_min_trade": annotations.current_min_trade,
        "investable_cash": annotations.investable_cash,
    }
    selected_fields = tuple(execution_fields or candidate_values.keys())
    execution_payload: dict[str, Any] = {}
    for field_name in selected_fields:
        candidate = candidate_values.get(field_name)
        if candidate is None:
            candidate = defaults.get(field_name)
        if candidate is None:
            continue
        if field_name in {
            "trade_threshold_value",
            "reserved_cash",
            "benchmark_price",
            "long_trend_value",
            "exit_line",
            "current_min_trade",
            "investable_cash",
        }:
            _ensure_finite_number(candidate, field_name=f"execution_payload.{field_name}")
            execution_payload[field_name] = float(candidate)
            continue
        text = str(candidate).strip()
        if not text and field_name not in defaults:
            continue
        execution_payload[field_name] = text

    return {
        "strategy_profile": str(strategy_profile),
        "allocation": build_allocation_payload(
            build_value_target_allocation_intent(portfolio_plan)
        ),
        "portfolio": portfolio_payload,
        "execution": execution_payload,
    }


def build_value_target_execution_annotations(
    decision: StrategyDecision,
) -> ValueTargetExecutionAnnotations:
    validate_strategy_decision(decision)
    diagnostics = dict(decision.diagnostics)
    raw_annotations = diagnostics.get("execution_annotations")
    annotations = dict(raw_annotations) if isinstance(raw_annotations, Mapping) else {}

    def _pick_str(*keys: str) -> str | None:
        for key in keys:
            value = annotations.get(key, diagnostics.get(key))
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    def _pick_float(*keys: str, default: float | None = None) -> float | None:
        for key in keys:
            value = annotations.get(key, diagnostics.get(key))
            if value is None:
                continue
            _ensure_finite_number(value, field_name=f"execution_annotations.{key}")
            return float(value)
        return default

    threshold_value = _pick_float("trade_threshold_value", "threshold", "threshold_value")
    if threshold_value is None:
        raise StrategyContractValidationError(
            "ValueTargetExecutionAnnotations requires trade_threshold_value "
            "(or legacy threshold/threshold_value)"
        )

    return ValueTargetExecutionAnnotations(
        trade_threshold_value=threshold_value,
        reserved_cash=float(_pick_float("reserved_cash", "reserved", default=0.0) or 0.0),
        signal_display=_pick_str("signal_display", "signal_message"),
        status_display=_pick_str("status_display", "market_status"),
        dashboard_text=_pick_str("dashboard_text", "dashboard"),
        signal_date=_pick_str("signal_date"),
        effective_date=_pick_str("effective_date"),
        execution_timing_contract=_pick_str("execution_timing_contract"),
        execution_calendar_source=_pick_str("execution_calendar_source"),
        signal_effective_after_trading_days=(
            int(signal_delay)
            if (signal_delay := _pick_float("signal_effective_after_trading_days")) is not None
            else None
        ),
        separator=_pick_str("separator"),
        benchmark_symbol=_pick_str("benchmark_symbol"),
        benchmark_price=_pick_float("benchmark_price", "qqq_price"),
        long_trend_value=_pick_float("long_trend_value", "ma200"),
        exit_line=_pick_float("exit_line"),
        deploy_ratio_text=_pick_str("deploy_ratio_text"),
        income_ratio_text=_pick_str("income_ratio_text"),
        income_locked_ratio_text=_pick_str("income_locked_ratio_text"),
        active_risk_asset=_pick_str("active_risk_asset"),
        current_min_trade=_pick_float("current_min_trade"),
        investable_cash=_pick_float("investable_cash"),
    )


# Note: load_strategy_entrypoint is in common/strategies.py (v0.9.0+).
# Import from quant_platform_kit.common.strategies, not strategy_contracts.
# Use from quant_platform_kit.common.strategies import load_strategy_entrypoint.
