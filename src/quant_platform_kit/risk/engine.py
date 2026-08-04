"""Unified risk engine — aggregates regime detection with plugin signals.

Consolidates logic previously scattered across:
- QuantStrategyPlugins.market_regime_control_plugin (signal aggregation)
- quant_platform_kit.strategy_lifecycle.market_regime (regime detection)
- Runtime execution policy in each platform

Usage::

    engine = build_risk_engine(regime_detector=detector, plugins=plugins)
    assessment = engine.evaluate(market_data, plugin_signals)
    action = engine.resolve(assessment, strategy_config)
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable, Mapping, Protocol

from quant_platform_kit.common.models import PortfolioSnapshot
from quant_platform_kit.risk.contracts import (
    REGIME_NORMAL,
    ROUTE_BLOCKED,
    ROUTE_NO_ACTION,
    ROUTE_RISK_OFF,
    ROUTE_RISK_REDUCED,
    ROUTE_WATCH,
    RegimeContext,
    RiskAction,
    RiskAssessment,
    RiskSignal,
    normalise_regime,
)


class RegimeDetector(Protocol):
    """Detect market regime from price/volatility data."""

    def detect(self, market_data: Mapping[str, Any]) -> RegimeContext:
        ...


class RiskPlugin(Protocol):
    """A risk plugin that produces a RiskSignal."""

    plugin_name: str
    schema_version: str

    def evaluate(self, market_data: Mapping[str, Any]) -> RiskSignal:
        ...


@dataclass
class RiskEngine:
    """Orchestrates risk evaluation across regime detection and plugins.

    Aggregates multiple signal sources into a single RiskAssessment using
    a conservative (worst-case) aggregation strategy.
    """

    regime_detector: RegimeDetector | None = None
    plugins: tuple[RiskPlugin, ...] = ()
    default_route: str = ROUTE_NO_ACTION

    def evaluate(
        self,
        market_data: Mapping[str, Any],
        *,
        plugin_signals: tuple[RiskSignal, ...] | None = None,
    ) -> RiskAssessment:
        """Evaluate risk across all configured sources.

        If *plugin_signals* is provided, they are merged with the output of
        any configured plugins. The most severe route wins.
        """
        # Detect regime
        regime_context: RegimeContext | None = None
        if self.regime_detector is not None:
            regime_context = self.regime_detector.detect(market_data)

        # Collect signals from plugins
        signals: list[RiskSignal] = []
        for plugin in self.plugins:
            try:
                signals.append(plugin.evaluate(market_data))
            except Exception:
                signals.append(
                    RiskSignal(
                        plugin="risk_engine",
                        schema_version="qpk.risk_plugin_error.v1",
                        route=ROUTE_BLOCKED,
                        confidence=1.0,
                        suggested_action="blocked",
                        reason_codes=("plugin_evaluation_error",),
                    )
                )

        # Merge external signals
        if plugin_signals:
            signals.extend(plugin_signals)

        if not signals:
            return RiskAssessment(
                as_of="",
                effective_route=self.default_route,
                effective_regime=regime_context.regime if regime_context else REGIME_NORMAL,
                confidence=1.0,
                signals=(),
                regime_context=regime_context,
            )

        # Conservative aggregation: worst-case route
        return aggregate_risk_signals(signals, regime_context=regime_context)

    def assess(
        self,
        decision: Any,
        portfolio_snapshot: Any,
        *,
        market_data: Mapping[str, Any] | None = None,
    ) -> RiskAction:
        """Assess a decision, rejecting missing or invalid account state."""
        if portfolio_snapshot is None:
            return RiskAction(
                action="reject",
                reason="missing_portfolio_snapshot",
                budget_scalar=0.0,
                leverage_scalar=0.0,
                risk_asset_scalar=0.0,
            )
        if isinstance(portfolio_snapshot, PortfolioSnapshot):
            total_equity = portfolio_snapshot.total_equity
        elif isinstance(portfolio_snapshot, Mapping):
            total_equity = portfolio_snapshot.get("total_equity")
        else:
            total_equity = None
        if (
            isinstance(total_equity, bool)
            or not isinstance(total_equity, (int, float))
            or not math.isfinite(float(total_equity))
            or float(total_equity) <= 0.0
        ):
            return RiskAction(
                action="reject",
                reason="invalid_portfolio_snapshot",
                budget_scalar=0.0,
                leverage_scalar=0.0,
                risk_asset_scalar=0.0,
            )

        md: dict[str, Any] = dict(market_data or {})
        md["portfolio_snapshot"] = portfolio_snapshot
        md["strategy_decision"] = decision

        assessment = self.evaluate(md)
        resolved = self.resolve(assessment)

        if resolved.action in {"blocked", "risk_off"}:
            return RiskAction(
                action="reject",
                reason=resolved.reason,
                budget_scalar=0.0,
                leverage_scalar=0.0,
                risk_asset_scalar=0.0,
            )
        return RiskAction(action="approve", reason="risk_engine_passed")

    def resolve(
        self,
        assessment: RiskAssessment,
        strategy_config: Mapping[str, Any] | None = None,
    ) -> RiskAction:
        """Translate a risk assessment into a concrete action."""
        cfg = dict(strategy_config or {})
        emergency = any(s.emergency for s in assessment.signals)
        route = assessment.effective_route

        if route == ROUTE_NO_ACTION:
            return RiskAction(action="no_action", reason="no_risk_detected")
        if route == ROUTE_WATCH:
            notify = cfg.get("risk_watch_notify", True)
            return RiskAction(action="watch", reason="elevated_signal", notify=notify)
        if route == ROUTE_RISK_REDUCED:
            scalar = float(cfg.get("risk_reduced_scalar", 0.50))
            return RiskAction(
                action="risk_reduced",
                reason="moderate_risk",
                budget_scalar=scalar,
                risk_asset_scalar=scalar,
            )
        if route == ROUTE_RISK_OFF:
            target = cfg.get("safe_haven") or cfg.get("cash_substitute_symbol")
            return RiskAction(
                action="risk_off",
                reason="severe_risk",
                budget_scalar=0.0,
                leverage_scalar=0.0,
                risk_asset_scalar=0.0,
                target_destination=str(target) if target else None,
            )
        if route == ROUTE_BLOCKED:
            return RiskAction(action="blocked", reason="execution_blocked", budget_scalar=0.0)

        return RiskAction(action=route, reason="unknown_route")


def aggregate_risk_signals(
    signals: tuple[RiskSignal, ...],
    *,
    regime_context: RegimeContext | None = None,
) -> RiskAssessment:
    """Aggregate multiple risk signals using conservative (worst-case) selection.

    The most severe route across all signals is selected. Confidence is the
    minimum across contributing signals.
    """
    if not signals:
        return RiskAssessment(
            as_of="",
            effective_route=ROUTE_NO_ACTION,
            effective_regime=REGIME_NORMAL,
            confidence=1.0,
            signals=(),
            regime_context=regime_context,
        )

    sorted_signals = sorted(signals, key=lambda s: s.severity, reverse=True)
    worst = sorted_signals[0]
    min_conf = min(s.confidence for s in signals)

    return RiskAssessment(
        as_of=worst.as_of,
        effective_route=worst.route,
        effective_regime=normalise_regime(regime_context.regime) if regime_context else REGIME_NORMAL,
        confidence=min_conf,
        signals=tuple(sorted_signals),
        regime_context=regime_context,
    )


def build_risk_engine(
    *,
    regime_detector: RegimeDetector | None = None,
    plugins: tuple[RiskPlugin, ...] | None = None,
) -> RiskEngine:
    """Factory for RiskEngine with sensible defaults."""
    return RiskEngine(
        regime_detector=regime_detector,
        plugins=plugins or (),
    )
