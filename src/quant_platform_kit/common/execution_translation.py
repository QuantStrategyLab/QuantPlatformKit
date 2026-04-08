from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .strategy_contracts import (
    PositionTarget,
    StrategyContractValidationError,
    StrategyDecision,
    ValueTargetExecutionAnnotations,
    build_value_target_execution_annotations,
    build_value_target_execution_plan,
    build_value_target_plan_payload,
    build_value_target_portfolio_plan,
    validate_strategy_decision,
)


@dataclass(frozen=True)
class ValueTargetPortfolioInputs:
    market_values: Mapping[str, float]
    quantities: Mapping[str, int]
    total_equity: float
    liquid_cash: float
    sellable_quantities: Mapping[str, int] | None = None


def build_value_target_portfolio_inputs_from_snapshot(
    snapshot: Any,
    *,
    include_sellable_quantities: bool = False,
    liquid_cash: float | None = None,
) -> ValueTargetPortfolioInputs:
    market_values: dict[str, float] = {}
    quantities: dict[str, int] = {}
    sellable_quantities: dict[str, int] | None = (
        {} if include_sellable_quantities else None
    )
    for position in getattr(snapshot, "positions", ()) or ():
        symbol = str(position.symbol)
        quantity = int(position.quantity)
        market_values[symbol] = float(position.market_value)
        quantities[symbol] = quantity
        if sellable_quantities is not None:
            sellable_quantities[symbol] = quantity

    resolved_liquid_cash = liquid_cash
    if resolved_liquid_cash is None:
        resolved_liquid_cash = getattr(snapshot, "buying_power", None)
    if resolved_liquid_cash is None:
        resolved_liquid_cash = getattr(snapshot, "cash_balance", None)
    if resolved_liquid_cash is None:
        resolved_liquid_cash = 0.0

    return ValueTargetPortfolioInputs(
        market_values=market_values,
        quantities=quantities,
        total_equity=float(snapshot.total_equity),
        liquid_cash=float(resolved_liquid_cash),
        sellable_quantities=sellable_quantities,
    )


def build_value_target_portfolio_inputs_from_account_state(
    account_state: Mapping[str, Any],
) -> ValueTargetPortfolioInputs:
    raw_sellable_quantities = account_state.get("sellable_quantities")
    sellable_quantities = None
    if isinstance(raw_sellable_quantities, Mapping):
        sellable_quantities = {
            str(symbol): int(quantity)
            for symbol, quantity in raw_sellable_quantities.items()
        }

    return ValueTargetPortfolioInputs(
        market_values={
            str(symbol): float(value)
            for symbol, value in dict(account_state["market_values"]).items()
        },
        quantities={
            str(symbol): int(quantity)
            for symbol, quantity in dict(account_state["quantities"]).items()
        },
        total_equity=float(account_state["total_strategy_equity"]),
        liquid_cash=float(account_state["available_cash"]),
        sellable_quantities=sellable_quantities,
    )


def _require_positive_total_equity(*, total_equity: float) -> float:
    resolved = float(total_equity)
    if resolved <= 0.0:
        raise StrategyContractValidationError(
            "execution translation requires positive total_equity"
        )
    return resolved


def resolve_decision_target_mode(decision: StrategyDecision) -> str | None:
    validate_strategy_decision(decision)
    has_weight_targets = any(
        position.target_weight is not None for position in decision.positions
    )
    has_value_targets = any(
        position.target_value is not None for position in decision.positions
    )
    if has_weight_targets and has_value_targets:
        raise StrategyContractValidationError(
            "execution translation requires a single target mode across all positions"
        )
    if has_weight_targets:
        return "weight"
    if has_value_targets:
        return "value"
    return None


def translate_value_decision_to_weight_targets(
    decision: StrategyDecision,
    *,
    total_equity: float,
) -> StrategyDecision:
    validate_strategy_decision(decision)
    resolved_total_equity = _require_positive_total_equity(total_equity=total_equity)

    translated_positions: list[PositionTarget] = []
    for position in decision.positions:
        if position.target_value is None:
            raise StrategyContractValidationError(
                "value-to-weight translation requires target_value positions; "
                f"position {position.symbol!r} is missing target_value"
            )
        translated_positions.append(
            PositionTarget(
                symbol=position.symbol,
                target_weight=float(position.target_value) / resolved_total_equity,
                role=position.role,
                order_preference=position.order_preference,
            )
        )

    return StrategyDecision(
        positions=tuple(translated_positions),
        budgets=decision.budgets,
        risk_flags=decision.risk_flags,
        diagnostics=dict(decision.diagnostics),
    )


def translate_weight_decision_to_value_targets(
    decision: StrategyDecision,
    *,
    total_equity: float,
) -> StrategyDecision:
    validate_strategy_decision(decision)
    resolved_total_equity = _require_positive_total_equity(total_equity=total_equity)

    translated_positions: list[PositionTarget] = []
    for position in decision.positions:
        if position.target_weight is None:
            raise StrategyContractValidationError(
                "weight-to-value translation requires target_weight positions; "
                f"position {position.symbol!r} is missing target_weight"
            )
        translated_positions.append(
            PositionTarget(
                symbol=position.symbol,
                target_value=float(position.target_weight) * resolved_total_equity,
                role=position.role,
                order_preference=position.order_preference,
            )
        )

    return StrategyDecision(
        positions=tuple(translated_positions),
        budgets=decision.budgets,
        risk_flags=decision.risk_flags,
        diagnostics=dict(decision.diagnostics),
    )


def translate_decision_to_target_mode(
    decision: StrategyDecision,
    *,
    target_mode: str,
    total_equity: float | None = None,
) -> StrategyDecision:
    resolved_target_mode = str(target_mode).strip().lower()
    if resolved_target_mode not in {"weight", "value"}:
        raise StrategyContractValidationError(
            "execution translation target_mode must be 'weight' or 'value'"
        )

    current_target_mode = resolve_decision_target_mode(decision)
    if current_target_mode is None or current_target_mode == resolved_target_mode:
        return decision

    if total_equity is None:
        raise StrategyContractValidationError(
            "execution translation requires total_equity when converting target mode"
        )

    if resolved_target_mode == "weight":
        return translate_value_decision_to_weight_targets(
            decision,
            total_equity=float(total_equity),
        )
    return translate_weight_decision_to_value_targets(
        decision,
        total_equity=float(total_equity),
    )


def build_value_target_runtime_plan(
    decision: StrategyDecision,
    *,
    strategy_profile: str,
    portfolio_inputs: ValueTargetPortfolioInputs,
    strategy_symbols_order: str = "risk_safe_income",
    portfolio_rows_layout: tuple[str, ...] = ("risk_safe", "income"),
    execution_fields: tuple[str, ...] | None = None,
    execution_defaults: Mapping[str, Any] | None = None,
    annotations: ValueTargetExecutionAnnotations | None = None,
    include_sellable_quantities: bool | None = None,
) -> dict[str, Any]:
    execution_plan = build_value_target_execution_plan(
        decision,
        strategy_profile=strategy_profile,
    )
    resolved_annotations = annotations or build_value_target_execution_annotations(decision)
    portfolio_plan = build_value_target_portfolio_plan(
        execution_plan,
        market_values=portfolio_inputs.market_values,
        quantities=portfolio_inputs.quantities,
        sellable_quantities=portfolio_inputs.sellable_quantities,
        total_equity=float(portfolio_inputs.total_equity),
        liquid_cash=float(portfolio_inputs.liquid_cash),
        strategy_symbols_order=strategy_symbols_order,
        portfolio_rows_layout=portfolio_rows_layout,
    )
    return build_value_target_plan_payload(
        strategy_profile=strategy_profile,
        portfolio_plan=portfolio_plan,
        annotations=resolved_annotations,
        include_sellable_quantities=(
            portfolio_inputs.sellable_quantities is not None
            if include_sellable_quantities is None
            else bool(include_sellable_quantities)
        ),
        execution_fields=execution_fields,
        execution_defaults=execution_defaults,
    )
