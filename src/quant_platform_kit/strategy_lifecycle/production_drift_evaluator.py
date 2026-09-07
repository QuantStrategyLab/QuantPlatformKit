"""Pure, read-only evaluation of production drift health metrics."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from numbers import Real
from typing import Any

from quant_platform_kit.strategy_lifecycle.contracts import (
    DriftResult,
    DriftStatus,
    StrategyPerformanceSnapshot,
)


@dataclass(frozen=True)
class ProductionDriftThresholds:
    """Versioned thresholds for production drift escalation."""

    threshold_version: str = "production_drift.v1"
    review_score: float = 0.50
    critical_score: float = 0.75

    def __post_init__(self) -> None:
        if not isinstance(self.threshold_version, str) or not self.threshold_version.strip():
            raise ValueError("threshold_version must be non-empty")
        if not _is_unit_score(self.review_score):
            raise ValueError("review_score must be finite and between 0 and 1")
        if not _is_unit_score(self.critical_score):
            raise ValueError("critical_score must be finite and between 0 and 1")
        if self.review_score >= self.critical_score:
            raise ValueError("review_score must be lower than critical_score")


def sanitize_unit_drift_score(value: object) -> float:
    """Fail-closed cast of a unit-interval drift score."""

    if not _is_unit_score(value):
        raise ValueError("drift_score must be finite and between 0 and 1")
    return float(value)


def resolve_injected_drift_score(
    *,
    drift: DriftResult | None = None,
    snapshot: StrategyPerformanceSnapshot | None = None,
) -> float | None:
    """Prefer latest DriftResult score, else snapshot.drift_score; never invent 0.0.

    DriftResult with ``baseline_available=False`` is treated as unavailable even
    when ``drift_score`` is 0.0 (no-baseline detect_drift must not look healthy).
    """

    if drift is not None:
        if getattr(drift, "baseline_available", True) is False:
            return None
        try:
            return sanitize_unit_drift_score(drift.drift_score)
        except ValueError:
            return None
    if snapshot is not None and snapshot.drift_score is not None:
        try:
            return sanitize_unit_drift_score(snapshot.drift_score)
        except ValueError:
            return None
    return None


def evaluate_production_drift_health(
    *,
    strategy_profile: str,
    domain: str,
    as_of: date,
    metrics: Mapping[str, Any],
    thresholds: ProductionDriftThresholds | None = None,
) -> DriftResult:
    """Map read-only health metrics to a drift status without side effects."""

    if not isinstance(strategy_profile, str) or not strategy_profile.strip():
        raise ValueError("strategy_profile must be non-empty")
    if not isinstance(domain, str) or not domain.strip():
        raise ValueError("domain must be non-empty")
    if not isinstance(as_of, date):
        raise ValueError("as_of must be a date")
    if not isinstance(metrics, Mapping):
        raise ValueError("metrics must be a mapping")

    score = sanitize_unit_drift_score(metrics.get("drift_score"))

    policy = thresholds or ProductionDriftThresholds()
    status = (
        DriftStatus.CRITICAL
        if score >= policy.critical_score
        else DriftStatus.REVIEW
        if score >= policy.review_score
        else DriftStatus.HEALTHY
    )
    return DriftResult(
        strategy_profile=strategy_profile,
        domain=domain,
        as_of=as_of,
        drift_score=score,
        status=status,
    )


def _is_unit_score(value: object) -> bool:
    return (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0.0 <= value <= 1.0
    )
