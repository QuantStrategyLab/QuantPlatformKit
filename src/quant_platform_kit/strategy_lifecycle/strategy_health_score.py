"""Composite health scoring for strategies (0-100 scale)."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from quant_platform_kit.strategy_lifecycle.contracts import (
    DriftResult,
    DriftStatus,
    StrategyHealthScore,
    StrategyPerformanceSnapshot,
)


# Weights for composite scoring
DEFAULT_WEIGHTS: Mapping[str, float] = {
    "performance": 0.35,
    "risk": 0.25,
    "decay": 0.20,
    "stability": 0.10,
    "operational": 0.10,
}

# Status thresholds
DEFAULT_THRESHOLDS: Mapping[str, float] = {
    "healthy": 70.0,
    "watch": 50.0,
    "review": 30.0,
    # below 30 → critical
}


def compute_health_score(
    snapshot: StrategyPerformanceSnapshot,
    *,
    drift: DriftResult | None = None,
    weights: Mapping[str, float] | None = None,
    thresholds: Mapping[str, float] | None = None,
) -> StrategyHealthScore:
    """Compute a composite health score for a strategy.

    Args:
        snapshot: Latest performance snapshot.
        drift: Optional drift analysis result.
        weights: Sub-score weights (must sum to ~1.0).
        thresholds: Status thresholds.

    Returns:
        StrategyHealthScore with breakdown.
    """
    weights = weights or DEFAULT_WEIGHTS
    thresholds = thresholds or DEFAULT_THRESHOLDS

    ref = snapshot.windows.get(126) or snapshot.windows.get(252)

    # ── Performance score (35%) ──────────────────────────────────
    perf = _score_performance(ref)

    # ── Risk score (25%) ────────────────────────────────────────
    risk = _score_risk(ref)

    # ── Decay score (20%) ───────────────────────────────────────
    decay = _score_decay(snapshot)

    # ── Stability score (10%) ───────────────────────────────────
    stability = _score_stability(snapshot, drift)

    # ── Operational score (10%) ─────────────────────────────────
    operational = _score_operational(snapshot, drift)

    overall = (
        weights["performance"] * perf
        + weights["risk"] * risk
        + weights["decay"] * decay
        + weights["stability"] * stability
        + weights["operational"] * operational
    )

    status = _status_from_score(overall, thresholds)

    return StrategyHealthScore(
        strategy_profile=snapshot.strategy_profile,
        domain=snapshot.domain,
        as_of=snapshot.as_of,
        overall_score=round(min(max(overall, 0), 100), 1),
        performance_score=round(perf, 1),
        risk_score=round(risk, 1),
        decay_score=round(decay, 1),
        stability_score=round(stability, 1),
        operational_score=round(operational, 1),
        status=status,
    )


def _score_performance(ref: object | None) -> float:
    """Score 0-100 based on Sharpe and excess CAGR."""
    if ref is None:
        return 50.0
    sharpe = getattr(ref, "sharpe_ratio", None) or 0.0
    excess = getattr(ref, "excess_cagr", None) or 0.0
    if np.isnan(sharpe):
        return 50.0
    # Sharpe mapping: 0→30, 1→60, 2→90, 3+→100
    sharpe_score = min(max(sharpe * 30 + 30, 0), 100)
    # Excess CAGR mapping: -0.1→20, 0→50, 0.1→80, 0.2+→100
    excess_score = min(max(50 + excess * 250, 0), 100) if not np.isnan(excess) else 50
    return sharpe_score * 0.7 + excess_score * 0.3


def _score_risk(ref: object | None) -> float:
    """Score 0-100 based on max drawdown (lower is better)."""
    if ref is None:
        return 50.0
    dd = getattr(ref, "max_drawdown", None) or 0.0
    if np.isnan(dd):
        return 50.0
    # DD mapping: -0.05→90, -0.10→75, -0.20→50, -0.40→20, -0.50→10
    return min(max(100 + dd * 200, 0), 100)


def _score_decay(snapshot: StrategyPerformanceSnapshot) -> float:
    """Score 0-100 based on performance trend (shorter windows vs longer)."""
    w63 = snapshot.windows.get(63)
    w252 = snapshot.windows.get(252)
    if w63 is None or w252 is None:
        return 50.0
    s63 = getattr(w63, "sharpe_ratio", None)
    s252 = getattr(w252, "sharpe_ratio", None)
    if s63 is None or s252 is None or np.isnan(s63) or np.isnan(s252):
        return 50.0
    # Recent better than long-term → higher score
    ratio = s63 / max(s252, 0.01)
    return min(max(50 + (ratio - 1) * 50, 0), 100)


def _score_stability(snapshot: StrategyPerformanceSnapshot, drift: DriftResult | None) -> float:
    """Score 0-100 based on win rate consistency and drift status."""
    ref = snapshot.windows.get(126) or snapshot.windows.get(252)
    if ref is None:
        return 50.0
    wr = getattr(ref, "win_rate", None) or 0.0
    wr_score = min(max(wr * 100, 0), 100)
    if drift and drift.status.severity_order >= DriftStatus.REVIEW.severity_order:
        wr_score *= 0.7
    return wr_score


def _score_operational(snapshot: StrategyPerformanceSnapshot, drift: DriftResult | None) -> float:
    """Score 0-100 based on data freshness and alert frequency."""
    freshness = snapshot.data_freshness_days
    fresh_score = max(100 - freshness * 20, 0) if freshness > 0 else 100
    alert_penalty = 0
    if drift and drift.status.severity_order >= DriftStatus.CRITICAL.severity_order:
        alert_penalty = 20
    elif drift and drift.status.severity_order >= DriftStatus.REVIEW.severity_order:
        alert_penalty = 10
    return max(fresh_score - alert_penalty, 0)


def _status_from_score(score: float, thresholds: Mapping[str, float]) -> str:
    if score >= thresholds.get("healthy", 70):
        return "healthy"
    if score >= thresholds.get("watch", 50):
        return "watch"
    if score >= thresholds.get("review", 30):
        return "review"
    return "critical"
