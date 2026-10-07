"""Deterministic policy for strategy optimization watch triggers."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

SEVERITY_NONE = "none"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"

DEFAULT_METRIC_RULES: dict[str, dict[str, Any]] = {
    "sharpe": {"higher_better": True, "relative_drop": 0.05},
    "cagr": {"higher_better": True, "relative_drop": 0.05},
    "calmar": {"higher_better": True, "relative_drop": 0.05},
    "win_rate": {"higher_better": True, "relative_drop": 0.03},
    "max_dd": {"higher_better": False, "absolute_worsening": 0.02},
}
HIGH_SEVERITY_SIGNAL_COUNT = 2
HIGH_SEVERITY_MAX_DD_WORSENING = 0.05


@dataclass(frozen=True)
class StrategyOptimizationPolicy:
    """Thresholds used by the watcher; deterministic and service-owned."""

    metric_rules: dict[str, dict[str, Any]] = field(default_factory=lambda: deepcopy(DEFAULT_METRIC_RULES))
    high_severity_signal_count: int = HIGH_SEVERITY_SIGNAL_COUNT
    high_severity_max_dd_worsening: float = HIGH_SEVERITY_MAX_DD_WORSENING


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def metric_degradation_signals(
    current_metrics: dict[str, Any],
    baseline_metrics: dict[str, Any],
    *,
    policy: StrategyOptimizationPolicy | None = None,
) -> list[dict[str, Any]]:
    """Return deterministic degradation signals beyond configured thresholds."""
    active_policy = policy or StrategyOptimizationPolicy()
    signals: list[dict[str, Any]] = []
    for metric, rule in active_policy.metric_rules.items():
        current = _safe_float(current_metrics.get(metric))
        baseline = _safe_float(baseline_metrics.get(metric))
        if current is None or baseline is None:
            continue
        delta = current - baseline
        signal: dict[str, Any] | None = None
        if rule.get("higher_better") is False:
            threshold = float(rule.get("absolute_worsening", 0.0))
            if delta > threshold:
                signal = {
                    "metric": metric,
                    "baseline": baseline,
                    "current": current,
                    "delta": delta,
                    "threshold": threshold,
                    "reason": f"{metric} worsened by {delta:.4g} > {threshold:.4g}",
                }
        else:
            threshold = float(rule.get("relative_drop", 0.0))
            absolute_threshold = float(rule.get("absolute_drop_when_zero", threshold))
            if baseline == 0:
                relative_delta = None
                degraded = current < -absolute_threshold
            else:
                relative_delta = delta / abs(baseline)
                degraded = relative_delta < -threshold
            if degraded:
                reason = (
                    f"{metric} dropped below zero by {abs(current):.4g} > {absolute_threshold:.4g}"
                    if relative_delta is None
                    else f"{metric} dropped {relative_delta:.1%} beyond {threshold:.1%}"
                )
                signal = {
                    "metric": metric,
                    "baseline": baseline,
                    "current": current,
                    "delta": delta,
                    "relative_delta": relative_delta,
                    "threshold": threshold,
                    "reason": reason,
                }
        if signal is not None:
            signals.append(signal)
    return signals


def classify_strategy_degradation(
    signals: list[dict[str, Any]],
    *,
    policy: StrategyOptimizationPolicy | None = None,
) -> str:
    """Classify watcher severity without involving an LLM."""
    if not signals:
        return SEVERITY_NONE
    active_policy = policy or StrategyOptimizationPolicy()
    if len(signals) >= active_policy.high_severity_signal_count:
        return SEVERITY_HIGH
    for signal in signals:
        if signal.get("metric") == "max_dd" and float(signal.get("delta") or 0.0) >= active_policy.high_severity_max_dd_worsening:
            return SEVERITY_HIGH
    return SEVERITY_MEDIUM


def evaluate_strategy_metrics(
    current_metrics: dict[str, Any],
    baseline_metrics: dict[str, Any],
    *,
    policy: StrategyOptimizationPolicy | None = None,
) -> dict[str, Any]:
    """Evaluate whether a strategy profile should open an optimization issue."""
    active_policy = policy or StrategyOptimizationPolicy()
    signals = metric_degradation_signals(current_metrics, baseline_metrics, policy=active_policy)
    severity = classify_strategy_degradation(signals, policy=active_policy)
    return {
        "should_open_issue": bool(signals),
        "severity": severity,
        "signals": signals,
        "signal_count": len(signals),
    }
