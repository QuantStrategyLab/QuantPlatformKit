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
from datetime import date, datetime, timedelta, timezone
from typing import Any

from quant_platform_kit.strategy_lifecycle.contracts import DriftStatus
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore
from quant_platform_kit.strategy_lifecycle.production_drift_evaluator import (
    ProductionDriftThresholds,
    evaluate_production_drift_health,
    resolve_injected_drift_score,
)


DEFAULT_MAX_AGE_DAYS = 7  # Calendar days, matching the monitor's 168h artifact budget.


def _date(value: date | str) -> date:
    if isinstance(value, str):
        return date.fromisoformat(value)
    if type(value) is not date:
        raise ValueError("observation/evaluation date must be an ISO date")
    return value


def _unavailable(summary: dict[str, Any], reason: str) -> dict[str, Any]:
    # Research freshness cannot clear an existing REVIEW/CRITICAL risk ban.
    # Healthy/unknown values never become a risk exemption through this field.
    summary["risk_status"] = (
        summary["status"] if summary["status"] in {"review", "critical"}
        else summary.get("risk_status")
    )
    summary.update(status="unavailable", actionable=False, reason=reason)
    return summary


def probe_production_drift_health(
    *,
    strategy_profile: str,
    domain: str,
    as_of: date | str,
    drift_score: float,
    threshold_version: str = "production_drift.v1",
    review_threshold: float = 0.50,
    critical_threshold: float = 0.75,
    evaluation_date: date | str | None = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> dict[str, Any]:
    """Evaluate explicit injected metrics; preserve their date and research TTL.

    ``evaluation_date`` is the only replay clock. ``as_of`` is always the source
    observation date. The default validity window uses calendar, not trading, days.
    """
    if type(max_age_days) is not int or max_age_days < 0:
        raise ValueError("max_age_days must be a nonnegative integer")
    observed = _date(as_of)
    evaluated = _date(evaluation_date) if evaluation_date is not None else datetime.now(timezone.utc).date()

    policy = ProductionDriftThresholds(
        threshold_version=threshold_version,
        review_score=review_threshold,
        critical_score=critical_threshold,
    )
    result = evaluate_production_drift_health(
        strategy_profile=strategy_profile,
        domain=domain,
        as_of=observed,
        metrics={"drift_score": drift_score},
        thresholds=policy,
    )
    summary = {
        "strategy_profile": strategy_profile,
        "domain": domain,
        "as_of": observed.isoformat(),
        "evaluated_as_of": evaluated.isoformat(),
        "valid_until": None,
        "max_age_days": max_age_days,
        "input_source": "caller_injected",
        "status": result.status.value,
        "score": result.drift_score,
        "threshold_version": policy.threshold_version,
        "actionable": result.status in {DriftStatus.REVIEW, DriftStatus.CRITICAL},
    }
    age = (evaluated - observed).days
    if age < 0:
        return _unavailable(summary, "observation_in_future")
    try:
        summary["valid_until"] = (observed + timedelta(days=max_age_days)).isoformat()
    except OverflowError:
        return _unavailable(summary, "observation_validity_unavailable")
    if age > max_age_days:
        return _unavailable(summary, "observation_stale")
    return summary


def probe_production_drift_health_from_store(
    *,
    strategy_profile: str,
    domain: str,
    as_of: date | str | None = None,
    store: PerformanceStore | None = None,
    threshold_version: str = "production_drift.v1",
    review_threshold: float = 0.50,
    critical_threshold: float = 0.75,
    evaluation_date: date | str | None = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> dict[str, Any]:
    """Load drift with its matching observation source; never relabel its date.

    ``as_of`` optionally checks the expected observation date. Replays must pass
    ``evaluation_date`` explicitly. A baseline artifact identifies the comparison
    baseline; only a matching snapshot supplies the observation source revision.
    """
    if type(max_age_days) is not int or max_age_days < 0:
        raise ValueError("max_age_days must be a nonnegative integer")
    evaluated = _date(evaluation_date) if evaluation_date is not None else datetime.now(timezone.utc).date()

    policy = ProductionDriftThresholds(
        threshold_version=threshold_version,
        review_score=review_threshold,
        critical_score=critical_threshold,
    )
    active_store = store if store is not None else PerformanceStore.from_env()
    drift = active_store.load_latest_drift(domain, strategy_profile)
    snapshot = active_store.load_latest_snapshot(domain, strategy_profile)
    record = drift if drift is not None else snapshot
    metadata = {
        "strategy_profile": strategy_profile,
        "domain": domain,
        "as_of": record.as_of.isoformat() if record is not None and record.as_of is not None else None,
        "evaluated_as_of": evaluated.isoformat(),
        "max_age_days": max_age_days,
        "input_source": "drift_result" if drift is not None else "performance_snapshot" if snapshot is not None else "missing",
        "source_revision": None,
        "baseline_artifact_id": getattr(drift, "baseline_artifact_id", None),
        "baseline_param_set_id": getattr(drift, "baseline_param_set_id", None),
        "baseline_param_version": getattr(drift, "baseline_param_version", None),
    }
    if record is not None and (record.strategy_profile != strategy_profile or record.domain != domain):
        return {**metadata, "status": "unavailable", "score": None,
                "threshold_version": policy.threshold_version, "actionable": False,
                "risk_status": None, "reason": "observation_identity_mismatch"}
    score = resolve_injected_drift_score(drift=drift, snapshot=snapshot)
    if score is None:
        return {
            **metadata,
            "status": "parked",
            "score": None,
            "threshold_version": policy.threshold_version,
            "actionable": False,
            "reason": "drift_score_unavailable",
        }

    if record.as_of is None:
        # Classify only the sanitized score to retain prior restrictive risk;
        # this is not a new observation or research evaluation date.
        retained = "critical" if score >= critical_threshold else "review" if score >= review_threshold else None
        return {**metadata, "status": "unavailable", "score": score,
                "threshold_version": policy.threshold_version, "actionable": False,
                "valid_until": None, "risk_status": retained,
                "reason": "observation_time_unavailable"}
    summary = probe_production_drift_health(
        strategy_profile=strategy_profile,
        domain=domain,
        as_of=record.as_of,
        drift_score=score,
        threshold_version=threshold_version,
        review_threshold=review_threshold,
        critical_threshold=critical_threshold,
        evaluation_date=evaluated,
        max_age_days=max_age_days,
    )
    summary.update(metadata)
    source_matches = (
        snapshot is not None and snapshot.as_of == record.as_of
        and snapshot.strategy_profile == strategy_profile and snapshot.domain == domain
    )
    revision = snapshot.source_revision if source_matches else None
    if isinstance(revision, str) and revision.strip():
        summary["source_revision"] = revision
    if not summary.get("reason"):
        if as_of is not None and _date(as_of) != record.as_of:
            return _unavailable(summary, "observation_date_mismatch")
        if (drift is not None and drift.source_revision
                and drift.source_revision != summary["source_revision"]):
            return _unavailable(summary, "observation_source_mismatch")
        if summary["source_revision"] is None:
            return _unavailable(summary, "observation_source_unavailable")
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
    parser.add_argument("--evaluation-date", default="", help="Explicit replay clock; defaults to current UTC date")
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS)
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
            evaluation_date=args.evaluation_date or None,
            max_age_days=args.max_age_days,
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
            evaluation_date=args.evaluation_date or None,
            max_age_days=args.max_age_days,
        )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
