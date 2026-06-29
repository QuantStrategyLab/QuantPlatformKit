"""Backtest scheduler — centralizes optimization scheduling decisions.

Answers two questions:
  1. When should a strategy be optimized? (cadence-based + event-driven)
  2. What triggered this optimization run? (audit trail)
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ScheduleCadence(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ON_DEMAND = "on_demand"


class TriggerReason(str, enum.Enum):
    SCHEDULED = "scheduled"        # regular cron
    DRIFT_ESCALATED = "drift"     # drift reached REVIEW/CRITICAL
    MANUAL = "manual"             # human triggered
    POST_DEPLOY = "post_deploy"   # after deployment monitoring


# High-cadence strategies (daily rebalance) → optimize monthly
HIGH_CADENCE_PROFILES = frozenset({
    "crypto_live_pool_rotation",
    "cn_industry_etf_rotation",
    "cn_stock_momentum_rotation",
})


def resolve_cadence(
    strategy_profile: str,
    *,
    drift_active: bool = False,
) -> ScheduleCadence:
    """Determine the optimization cadence for a strategy.

    Args:
        strategy_profile: Canonical strategy profile name.
        drift_active: Whether drift has been detected for this strategy.

    Returns:
        Appropriate cadence for optimization.
    """
    if drift_active:
        return ScheduleCadence.ON_DEMAND

    if strategy_profile in HIGH_CADENCE_PROFILES:
        return ScheduleCadence.MONTHLY

    return ScheduleCadence.QUARTERLY


def should_optimize(
    strategy_profile: str,
    *,
    last_optimized_at: str | None = None,
    drift_active: bool = False,
    force: bool = False,
) -> tuple[bool, TriggerReason]:
    """Decide whether a strategy should be optimized now.

    Args:
        strategy_profile: Strategy to check.
        last_optimized_at: ISO-8601 timestamp of last optimization.
        drift_active: Whether drift has been detected.
        force: Bypass schedule checks.

    Returns:
        (should_optimize, reason)
    """
    if force:
        return True, TriggerReason.MANUAL

    if drift_active:
        return True, TriggerReason.DRIFT_ESCALATED

    cadence = resolve_cadence(strategy_profile)

    if cadence == ScheduleCadence.ON_DEMAND:
        return drift_active, TriggerReason.SCHEDULED

    if last_optimized_at is None:
        return True, TriggerReason.SCHEDULED

    # Check if enough time has passed
    try:
        last = datetime.fromisoformat(last_optimized_at.replace("Z", "+00:00"))
        days_since = (datetime.now(timezone.utc) - last).days
    except Exception:
        return True, TriggerReason.SCHEDULED

    min_days = {
        ScheduleCadence.MONTHLY: 25,
        ScheduleCadence.QUARTERLY: 80,
        ScheduleCadence.WEEKLY: 6,
        ScheduleCadence.DAILY: 1,
    }

    threshold = min_days.get(cadence, 80)
    if days_since >= threshold:
        return True, TriggerReason.SCHEDULED

    return False, TriggerReason.SCHEDULED
