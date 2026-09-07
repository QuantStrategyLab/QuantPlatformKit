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
from quant_platform_kit.strategy_lifecycle.production_drift_evaluator import (
    ProductionDriftThresholds,
    evaluate_production_drift_health,
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy-profile", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--as-of", required=True, help="ISO date (YYYY-MM-DD)")
    parser.add_argument("--drift-score", required=True, type=float)
    parser.add_argument("--threshold-version", default="production_drift.v1")
    parser.add_argument("--review", type=float, default=0.50)
    parser.add_argument("--critical", type=float, default=0.75)
    args = parser.parse_args(argv)

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
