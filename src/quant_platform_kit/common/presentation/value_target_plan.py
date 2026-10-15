"""Split value-target execution semantics from display/layout knobs.

``ValueTargetExecutionAnnotations`` in ``strategy_contracts`` remains the
compatibility wire aggregate (execution + display fields). New callers should
prefer:
- ``ValueTargetExecutionSemantics`` for thresholds / timing / numeric gates
- ``ValueTargetDisplayAnnotations`` for dashboard/signal copy
- ``ValueTargetPlanPresentation`` for portfolio row layout / field selection

Construct the wire aggregate with ``merge_value_target_execution_annotations``
(or pass ``semantics`` / ``display`` into
``build_value_target_execution_runtime_plan``). Mixed-field removal waits on
consumer adoption evidence (B12).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from quant_platform_kit.common.strategy_contracts import (
    StrategyContractValidationError,
    StrategyDecision,
    ValueTargetExecutionAnnotations,
    validate_strategy_decision,
)

# Source of truth for which annotation keys are presentation-owned.
VALUE_TARGET_DISPLAY_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "signal_display",
        "status_display",
        "dashboard_text",
        "separator",
        "deploy_ratio_text",
        "income_ratio_text",
        "income_locked_ratio_text",
    }
)


@dataclass(frozen=True)
class ValueTargetExecutionSemantics:
    """Execution-relevant annotation fields (no dashboard layout/copy)."""

    trade_threshold_value: float
    reserved_cash: float = 0.0
    signal_date: str | None = None
    effective_date: str | None = None
    execution_timing_contract: str | None = None
    execution_calendar_source: str | None = None
    signal_effective_after_trading_days: int | None = None
    benchmark_symbol: str | None = None
    benchmark_price: float | None = None
    long_trend_value: float | None = None
    exit_line: float | None = None
    active_risk_asset: str | None = None
    current_min_trade: float | None = None
    investable_cash: float | None = None


@dataclass(frozen=True)
class ValueTargetDisplayAnnotations:
    """Human-facing copy for notifications / dashboards."""

    signal_display: str | None = None
    status_display: str | None = None
    dashboard_text: str | None = None
    separator: str | None = None
    deploy_ratio_text: str | None = None
    income_ratio_text: str | None = None
    income_locked_ratio_text: str | None = None


@dataclass(frozen=True)
class ValueTargetPlanPresentation:
    """Legacy payload shaping (row layout + optional execution field filter)."""

    portfolio_rows_layout: tuple[str, ...] = ("risk_safe", "income")
    execution_fields: tuple[str, ...] | None = None
    execution_defaults: Mapping[str, Any] | None = None


def execution_semantics_from_annotations(
    annotations: ValueTargetExecutionAnnotations,
) -> ValueTargetExecutionSemantics:
    return ValueTargetExecutionSemantics(
        trade_threshold_value=float(annotations.trade_threshold_value),
        reserved_cash=float(annotations.reserved_cash),
        signal_date=annotations.signal_date,
        effective_date=annotations.effective_date,
        execution_timing_contract=annotations.execution_timing_contract,
        execution_calendar_source=annotations.execution_calendar_source,
        signal_effective_after_trading_days=annotations.signal_effective_after_trading_days,
        benchmark_symbol=annotations.benchmark_symbol,
        benchmark_price=annotations.benchmark_price,
        long_trend_value=annotations.long_trend_value,
        exit_line=annotations.exit_line,
        active_risk_asset=annotations.active_risk_asset,
        current_min_trade=annotations.current_min_trade,
        investable_cash=annotations.investable_cash,
    )


def display_annotations_from_execution_annotations(
    annotations: ValueTargetExecutionAnnotations,
) -> ValueTargetDisplayAnnotations:
    return ValueTargetDisplayAnnotations(
        signal_display=annotations.signal_display,
        status_display=annotations.status_display,
        dashboard_text=annotations.dashboard_text,
        separator=annotations.separator,
        deploy_ratio_text=annotations.deploy_ratio_text,
        income_ratio_text=annotations.income_ratio_text,
        income_locked_ratio_text=annotations.income_locked_ratio_text,
    )


def merge_value_target_execution_annotations(
    semantics: ValueTargetExecutionSemantics,
    display: ValueTargetDisplayAnnotations | None = None,
) -> ValueTargetExecutionAnnotations:
    """Build the compatibility wire aggregate from split types."""
    display = display or ValueTargetDisplayAnnotations()
    return ValueTargetExecutionAnnotations(
        trade_threshold_value=float(semantics.trade_threshold_value),
        reserved_cash=float(semantics.reserved_cash),
        signal_display=display.signal_display,
        status_display=display.status_display,
        dashboard_text=display.dashboard_text,
        signal_date=semantics.signal_date,
        effective_date=semantics.effective_date,
        execution_timing_contract=semantics.execution_timing_contract,
        execution_calendar_source=semantics.execution_calendar_source,
        signal_effective_after_trading_days=semantics.signal_effective_after_trading_days,
        separator=display.separator,
        benchmark_symbol=semantics.benchmark_symbol,
        benchmark_price=semantics.benchmark_price,
        long_trend_value=semantics.long_trend_value,
        exit_line=semantics.exit_line,
        deploy_ratio_text=display.deploy_ratio_text,
        income_ratio_text=display.income_ratio_text,
        income_locked_ratio_text=display.income_locked_ratio_text,
        active_risk_asset=semantics.active_risk_asset,
        current_min_trade=semantics.current_min_trade,
        investable_cash=semantics.investable_cash,
    )


def _pick_annotation_str(
    annotations: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    *keys: str,
) -> str | None:
    for key in keys:
        value = annotations.get(key, diagnostics.get(key))
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _ensure_finite_annotation_number(value: object, *, field_name: str) -> None:
    if value is None:
        return
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise StrategyContractValidationError(
            f"{field_name} must be a finite number when provided"
        )


def _pick_annotation_float(
    annotations: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    *keys: str,
    default: float | None = None,
    field_prefix: str = "execution_annotations",
) -> float | None:
    for key in keys:
        value = annotations.get(key, diagnostics.get(key))
        if value is None:
            continue
        _ensure_finite_annotation_number(value, field_name=f"{field_prefix}.{key}")
        return float(value)
    return default


def split_value_target_annotation_parts(
    decision: StrategyDecision,
) -> tuple[ValueTargetExecutionSemantics, ValueTargetDisplayAnnotations]:
    """Parse decision diagnostics into execution semantics + display copy."""
    validate_strategy_decision(decision)
    diagnostics = dict(decision.diagnostics)
    raw_annotations = diagnostics.get("execution_annotations")
    annotations = dict(raw_annotations) if isinstance(raw_annotations, Mapping) else {}

    threshold_value = _pick_annotation_float(
        annotations,
        diagnostics,
        "trade_threshold_value",
        "threshold",
        "threshold_value",
    )
    if threshold_value is None:
        raise StrategyContractValidationError(
            "ValueTargetExecutionAnnotations requires trade_threshold_value "
            "(or legacy threshold/threshold_value)"
        )

    signal_delay = _pick_annotation_float(
        annotations,
        diagnostics,
        "signal_effective_after_trading_days",
    )
    semantics = ValueTargetExecutionSemantics(
        trade_threshold_value=threshold_value,
        reserved_cash=float(
            _pick_annotation_float(
                annotations,
                diagnostics,
                "reserved_cash",
                "reserved",
                default=0.0,
            )
            or 0.0
        ),
        signal_date=_pick_annotation_str(annotations, diagnostics, "signal_date"),
        effective_date=_pick_annotation_str(annotations, diagnostics, "effective_date"),
        execution_timing_contract=_pick_annotation_str(
            annotations, diagnostics, "execution_timing_contract"
        ),
        execution_calendar_source=_pick_annotation_str(
            annotations, diagnostics, "execution_calendar_source"
        ),
        signal_effective_after_trading_days=(
            int(signal_delay) if signal_delay is not None else None
        ),
        benchmark_symbol=_pick_annotation_str(annotations, diagnostics, "benchmark_symbol"),
        benchmark_price=_pick_annotation_float(
            annotations, diagnostics, "benchmark_price", "qqq_price"
        ),
        long_trend_value=_pick_annotation_float(
            annotations, diagnostics, "long_trend_value", "ma200"
        ),
        exit_line=_pick_annotation_float(annotations, diagnostics, "exit_line"),
        active_risk_asset=_pick_annotation_str(annotations, diagnostics, "active_risk_asset"),
        current_min_trade=_pick_annotation_float(
            annotations, diagnostics, "current_min_trade"
        ),
        investable_cash=_pick_annotation_float(annotations, diagnostics, "investable_cash"),
    )
    display = ValueTargetDisplayAnnotations(
        signal_display=_pick_annotation_str(
            annotations, diagnostics, "signal_display", "signal_message"
        ),
        status_display=_pick_annotation_str(
            annotations, diagnostics, "status_display", "market_status"
        ),
        dashboard_text=_pick_annotation_str(
            annotations, diagnostics, "dashboard_text", "dashboard"
        ),
        separator=_pick_annotation_str(annotations, diagnostics, "separator"),
        deploy_ratio_text=_pick_annotation_str(
            annotations, diagnostics, "deploy_ratio_text"
        ),
        income_ratio_text=_pick_annotation_str(
            annotations, diagnostics, "income_ratio_text"
        ),
        income_locked_ratio_text=_pick_annotation_str(
            annotations, diagnostics, "income_locked_ratio_text"
        ),
    )
    return semantics, display


def resolve_value_target_execution_annotations(
    *,
    decision: StrategyDecision | None = None,
    annotations: ValueTargetExecutionAnnotations | None = None,
    semantics: ValueTargetExecutionSemantics | None = None,
    display: ValueTargetDisplayAnnotations | None = None,
) -> ValueTargetExecutionAnnotations:
    """Resolve wire annotations from preferred split types or legacy aggregate.

    Precedence:
    1. Explicit ``annotations`` (compat facade)
    2. ``semantics`` (+ optional ``display``) merged
    3. Parse ``decision`` diagnostics into split parts then merge
    """
    if annotations is not None and (semantics is not None or display is not None):
        raise StrategyContractValidationError(
            "Pass either annotations= (compat) or semantics=/display= (preferred), not both"
        )
    if annotations is not None:
        return annotations
    if semantics is not None:
        return merge_value_target_execution_annotations(semantics, display)
    if decision is None:
        raise StrategyContractValidationError(
            "resolve_value_target_execution_annotations requires annotations, "
            "semantics, or decision"
        )
    parsed_semantics, parsed_display = split_value_target_annotation_parts(decision)
    return merge_value_target_execution_annotations(parsed_semantics, parsed_display)
