"""Split value-target execution semantics from display/layout knobs.

``ValueTargetExecutionAnnotations`` in ``strategy_contracts`` remains the
compatibility wire type (all fields). New callers should prefer:
- ``ValueTargetExecutionSemantics`` for thresholds / timing / numeric gates
- ``ValueTargetDisplayAnnotations`` for dashboard/signal copy
- ``ValueTargetPlanPresentation`` for portfolio row layout / field selection
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from quant_platform_kit.common.strategy_contracts import ValueTargetExecutionAnnotations


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
