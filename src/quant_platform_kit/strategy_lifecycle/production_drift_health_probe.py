"""Read-only production drift health probe for cron and health checks.

The probe evaluates caller-injected metrics and emits a sanitized summary only.
It never runs optimization, promotion, broker, or live-order code.
Only REVIEW and CRITICAL results are actionable.
Promotion remains a separate, explicitly invoked human/runner workflow.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import date
from typing import Any

from quant_platform_kit.strategy_lifecycle.contracts import DriftStatus
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore
from quant_platform_kit.strategy_lifecycle.production_drift_evaluator import (
    ProductionDriftThresholds,
    evaluate_production_drift_health,
    resolve_injected_drift_score,
)


def probe_production_drift_health(
    *,
    strategy_profile: str,
    domain: str,
    as_of: date | str,
    drift_score: float,
    threshold_version: str = "production_drift.v1",
    review_threshold: float = 0.50,
    critical_threshold: float = 0.75,
) -> dict[str, Any]:
    """Evaluate injected drift metrics without side effects."""

    policy = ProductionDriftThresholds(
        threshold_version=threshold_version,
        review_score=review_threshold,
        critical_score=critical_threshold,
    )
    result = evaluate_production_drift_health(
        strategy_profile=strategy_profile,
        domain=domain,
        as_of=date.fromisoformat(as_of) if isinstance(as_of, str) else as_of,
        metrics={"drift_score": drift_score},
        thresholds=policy,
    )
    return {
        "status": result.status.value,
        "score": result.drift_score,
        "threshold_version": policy.threshold_version,
        "actionable": result.status in {DriftStatus.REVIEW, DriftStatus.CRITICAL},
    }


def probe_production_drift_health_from_store(
    *,
    strategy_profile: str,
    domain: str,
    as_of: date | str | None = None,
    store: PerformanceStore | None = None,
    threshold_version: str = "production_drift.v1",
    review_threshold: float = 0.50,
    critical_threshold: float = 0.75,
) -> dict[str, Any]:
    """Load sanitized drift_score from PerformanceStore; PARK when unavailable."""

    policy = ProductionDriftThresholds(
        threshold_version=threshold_version,
        review_score=review_threshold,
        critical_score=critical_threshold,
    )
    active_store = store if store is not None else PerformanceStore.from_env()
    drift = active_store.load_latest_drift(domain, strategy_profile)
    snapshot = active_store.load_latest_snapshot(domain, strategy_profile)
    score = resolve_injected_drift_score(drift=drift, snapshot=snapshot)
    if score is None:
        return {
            "status": "parked",
            "score": None,
            "threshold_version": policy.threshold_version,
            "actionable": False,
            "reason": "drift_score_unavailable",
        }

    resolved_as_of: date
    if as_of is not None:
        resolved_as_of = date.fromisoformat(as_of) if isinstance(as_of, str) else as_of
    elif drift is not None:
        resolved_as_of = drift.as_of
    elif snapshot is not None:
        resolved_as_of = snapshot.as_of
    else:
        resolved_as_of = date.today()

    summary = probe_production_drift_health(
        strategy_profile=strategy_profile,
        domain=domain,
        as_of=resolved_as_of,
        drift_score=score,
        threshold_version=threshold_version,
        review_threshold=review_threshold,
        critical_threshold=critical_threshold,
    )
    summary["reason"] = "store_injected"
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy-profile", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--as-of", default="", help="ISO date (YYYY-MM-DD); optional with --from-store")
    parser.add_argument("--drift-score", type=float, default=None)
    parser.add_argument(
        "--from-store",
        action="store_true",
        help="Resolve drift_score from PerformanceStore (LIFECYCLE_* env)",
    )
    parser.add_argument("--threshold-version", default="production_drift.v1")
    parser.add_argument("--review", type=float, default=0.50)
    parser.add_argument("--critical", type=float, default=0.75)
    args = parser.parse_args(argv)

    if args.from_store:
        if args.drift_score is not None:
            raise SystemExit("use either --drift-score or --from-store, not both")
        summary = probe_production_drift_health_from_store(
            strategy_profile=args.strategy_profile,
            domain=args.domain,
            as_of=args.as_of or None,
            threshold_version=args.threshold_version,
            review_threshold=args.review,
            critical_threshold=args.critical,
        )
    else:
        if args.drift_score is None:
            raise SystemExit("--drift-score is required unless --from-store is set")
        if not args.as_of:
            raise SystemExit("--as-of is required unless --from-store is set")
        summary = probe_production_drift_health(
            strategy_profile=args.strategy_profile,
            domain=args.domain,
            as_of=args.as_of,
            drift_score=args.drift_score,
            threshold_version=args.threshold_version,
            review_threshold=args.review,
            critical_threshold=args.critical,
        )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
