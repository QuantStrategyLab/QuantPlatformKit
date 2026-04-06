from __future__ import annotations

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


class StrategyEntrypoint(Protocol):
    manifest: StrategyManifest

    def evaluate(self, ctx: StrategyContext) -> StrategyDecision: ...


@dataclass(frozen=True)
class StrategyRuntimeAdapter:
    status_icon: str = "🐤"
    required_feature_columns: frozenset[str] = frozenset()
    snapshot_date_columns: tuple[str, ...] = ("as_of", "snapshot_date")
    max_snapshot_month_lag: int = 1
    require_snapshot_manifest: bool = False
    snapshot_contract_version: str | None = None
    runtime_parameter_loader: Callable[..., Mapping[str, object]] | None = None
    managed_symbols_extractor: Callable[..., tuple[str, ...]] | None = None


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


def validate_strategy_runtime_adapter(adapter: StrategyRuntimeAdapter) -> StrategyRuntimeAdapter:
    if not isinstance(adapter, StrategyRuntimeAdapter):
        raise StrategyContractValidationError(
            f"runtime adapter must be StrategyRuntimeAdapter, got {type(adapter).__name__}"
        )

    _ensure_non_empty_string(adapter.status_icon, field_name="runtime_adapter.status_icon")
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
    return adapter
