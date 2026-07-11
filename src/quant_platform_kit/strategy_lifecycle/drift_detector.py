"""Drift detector — compares live performance against backtest expectations."""

from __future__ import annotations


from dataclasses import replace

import numpy as np

from quant_platform_kit.strategy_lifecycle.contracts import (
    BacktestResult,
    DriftDimension,
    DriftResult,
    DriftStatus,
    StrategyPerformanceSnapshot,
)
from quant_platform_kit.strategy_lifecycle.drift_policy import DriftPolicy
from quant_platform_kit.strategy_lifecycle.market_regime import (
    DynamicDriftThresholds,
    MarketRegime,
    MarketRegimeResult,
)
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore


# ── Dimension registry ──────────────────────────────────────────────
# Each dimension: (key, metric_name, get_actual, get_expected, get_threshold, breach_fn)
_DIMENSION_SPECS = [
    ("cagr_drift", "cagr", "cagr", "cagr", "cagr_deviation_pct"),
    ("sharpe_drift", "sharpe_ratio", "sharpe_ratio", "sharpe_ratio", "sharpe_deviation"),
    ("max_drawdown_breach", "max_drawdown", "max_drawdown", "max_drawdown", "max_drawdown_multiplier"),
    ("volatility_drift", "volatility", "volatility", "volatility", "volatility_deviation_pct"),
    ("win_rate_drift", "win_rate", "win_rate", "win_rate", "win_rate_deviation_pct"),
]


def _compute_dimension(
    key: str, metric: str,
    actual_val: float, expected_val: float, threshold: float,
) -> DriftDimension:
    """Compute a single drift dimension. Handles the special drawdown logic."""
    if key == "max_drawdown_breach":
        actual = abs(actual_val)
        expected = abs(expected_val)
        dev = actual
        dev_pct = actual / max(expected, 0.001)
        breached = dev_pct > threshold
    else:
        dev = abs(actual_val - expected_val)
        denom = max(abs(expected_val), 0.001 if metric == "sharpe_ratio" else 0.01)
        dev_pct = dev / denom
        breached = dev > threshold if metric == "sharpe_ratio" else dev_pct > threshold

    return DriftDimension(
        metric_name=metric, actual=actual_val, expected=expected_val,
        deviation=dev, deviation_pct=dev_pct, threshold=threshold,
        breached=breached,
    )


def _compute_drift_score(dimensions: dict[str, DriftDimension]) -> float:
    """Composite drift score from breached count + deviation magnitude."""
    breached = [d for d in dimensions.values() if d.breached]
    if not breached:
        return 0.0

    # Score from breached count (1→0.30, 2→0.55, 3→0.75, 4+→0.90)
    count_scores = {1: 0.30, 2: 0.55, 3: 0.75}
    breach_score = count_scores.get(len(breached), 0.90)

    # Score from deviation magnitude (0→0, ~1→0.5, 2+→1.0)
    avg = float(np.mean([d.deviation_pct for d in dimensions.values()]))
    dev_score = min(avg / 2.0, 1.0)

    # Take the higher of the two — a single severe breach should not be buried
    return max(breach_score, dev_score)


# ── Public API ───────────────────────────────────────────────────────


def detect_drift(
    snapshot: StrategyPerformanceSnapshot,
    *,
    backtest: BacktestResult | None = None,
    policy: DriftPolicy | None = None,
    previous_status: DriftStatus | None = None,
    regime: MarketRegimeResult | None = None,
) -> DriftResult:
    """Analyze a performance snapshot for drift against backtest expectations.

    Thresholds are dynamically relaxed during ELEVATED/STRESS regimes.
    """
    policy = policy or DriftPolicy.load_default()

    # Resolve thresholds with regime adjustment
    r = regime.regime if (regime and regime.regime != MarketRegime.UNKNOWN) else MarketRegime.NORMAL
    thresholds = DynamicDriftThresholds.from_baseline(policy.thresholds.to_dict(), regime=r)

    ref_window = snapshot.windows.get(126) or snapshot.windows.get(252)
    if ref_window is None:
        return DriftResult(strategy_profile=snapshot.strategy_profile,
                           domain=snapshot.domain, as_of=snapshot.as_of,
                           drift_score=0.0, status=DriftStatus.HEALTHY)

    # Compute each dimension via registry
    dimensions: dict[str, DriftDimension] = {}
    for key, metric, actual_attr, expected_attr, threshold_attr in _DIMENSION_SPECS:
        if backtest is None:
            continue
        actual = getattr(ref_window, actual_attr, None)
        expected = getattr(backtest, expected_attr, None)
        if actual is None or expected is None:
            continue
        if np.isnan(actual) or np.isnan(expected):
            continue
        dimensions[key] = _compute_dimension(key, metric, float(actual), float(expected),
                                              getattr(thresholds, threshold_attr))

    drift_score = _compute_drift_score(dimensions)
    status = _status_from_score(drift_score, policy.escalation)
    escalated = previous_status is not None and status.severity_order > previous_status.severity_order

    return DriftResult(
        strategy_profile=snapshot.strategy_profile, domain=snapshot.domain,
        as_of=snapshot.as_of, drift_score=round(drift_score, 4),
        status=status, dimensions=dimensions,
        previous_status=previous_status,
        baseline_param_set_id=backtest.param_set_id if backtest else None,
        escalated=escalated,
    )


def run_drift_detection(
    domain: str,
    *,
    strategy_profile: str | None = None,
    policy: DriftPolicy | None = None,
    fail_on_empty: bool = True,
    store: PerformanceStore | None = None,
    baseline_store: PerformanceStore | None = None,
    previous_drift_store: PerformanceStore | None = None,
    baseline_lineage_policy: str = "auto",
) -> list[DriftResult]:
    """Run drift detection with explicit baseline and transition-state stores.

    External baselines are strict by default. ``migration`` is an explicit,
    one-run compatibility mode for legacy drift history without a lineage ID;
    it writes the accepted baseline ID into the next result.
    """
    store = store or PerformanceStore.from_env()
    explicit_baseline_store = baseline_store is not None
    if baseline_lineage_policy not in {"auto", "compatible", "migration", "strict"}:
        raise ValueError("baseline_lineage_policy must be auto, compatible, migration, or strict")
    if explicit_baseline_store and baseline_lineage_policy == "compatible":
        raise ValueError("compatible baseline lineage is not allowed with an external baseline store")
    if baseline_lineage_policy == "migration" and not explicit_baseline_store:
        raise ValueError("migration baseline lineage requires an external baseline store")
    if baseline_lineage_policy == "auto":
        baseline_lineage_policy = "strict" if explicit_baseline_store else "compatible"
    baseline_store = baseline_store or store
    read_previous = previous_drift_store or store
    policy = policy or DriftPolicy.load_default()

    from quant_platform_kit.strategy_lifecycle.return_collector import ReturnCollector
    collector = ReturnCollector(store=store)
    discovered = collector.collect(domain)
    profiles = [strategy_profile] if strategy_profile else sorted(discovered)
    if not profiles:
        if fail_on_empty:
            raise RuntimeError(
                f"No strategy return series found for domain={domain!r}; "
                "set QUANT_PROJECTS_ROOT or persist lifecycle performance artifacts before drift detection."
            )
        return []

    results: list[DriftResult] = []
    missing_snapshots = 0
    for profile in profiles:
        snapshot = store.load_latest_snapshot(domain, profile)
        if snapshot is None:
            missing_snapshots += 1
            continue
        backtest = baseline_store.load_latest_backtest(domain, profile)
        previous = read_previous.load_latest_drift(domain, profile)
        previous_before_lineage_check = previous
        current_baseline_id = backtest.param_set_id if backtest else None
        if previous:
            previous_baseline_id = previous.baseline_param_set_id
            if baseline_lineage_policy == "strict":
                if not (previous_baseline_id and current_baseline_id and previous_baseline_id == current_baseline_id):
                    previous = None
            elif baseline_lineage_policy == "migration":
                if current_baseline_id is None or (
                    previous_baseline_id is not None and previous_baseline_id != current_baseline_id
                ):
                    previous = None
        if backtest is None:
            continuity_result = (
                previous_before_lineage_check
                if baseline_lineage_policy != "migration"
                and previous_before_lineage_check is not None
                and previous_before_lineage_check.baseline_param_set_id
                else None
            )
            if continuity_result is not None:
                result = DriftResult(
                    strategy_profile=snapshot.strategy_profile,
                    domain=snapshot.domain,
                    as_of=snapshot.as_of,
                    drift_score=0.0,
                    status=continuity_result.status,
                    previous_status=continuity_result.status,
                    alert_suppressed=True,
                    baseline_param_set_id=continuity_result.baseline_param_set_id,
                    baseline_available=False,
                )
            else:
                result = replace(
                    detect_drift(snapshot, backtest=None, policy=policy),
                    alert_suppressed=True,
                    baseline_available=False,
                )
        else:
            result = detect_drift(snapshot, backtest=backtest, policy=policy,
                                  previous_status=previous.status if previous else None)
        if backtest is not None or not (
            previous_before_lineage_check is not None
            and previous_before_lineage_check.as_of == snapshot.as_of
        ):
            store.save_drift_result(result)
        results.append(result)
    if not results and fail_on_empty:
        raise RuntimeError(
            f"No drift checks completed for domain={domain!r}; "
            f"profiles={len(profiles)}, missing_snapshots={missing_snapshots}."
        )
    return results


def _status_from_score(score: float, escalation: object) -> DriftStatus:
    if hasattr(escalation, "critical") and score >= escalation.critical:
        return DriftStatus.CRITICAL
    if hasattr(escalation, "review") and score >= escalation.review:
        return DriftStatus.REVIEW
    if hasattr(escalation, "watch") and score >= escalation.watch:
        return DriftStatus.WATCH
    return DriftStatus.HEALTHY
