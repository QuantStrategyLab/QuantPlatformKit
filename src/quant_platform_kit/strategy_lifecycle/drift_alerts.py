"""Drift alert signal builder — integrates with existing notification channels."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Sequence

from quant_platform_kit.strategy_lifecycle.contracts import DriftResult, DriftStatus
from quant_platform_kit.strategy_lifecycle.drift_policy import DriftPolicy


@dataclass(frozen=True)
class DriftAlertEvent:
    """A drift alert ready for dispatch through notification channels."""

    strategy_profile: str
    domain: str
    as_of: date
    drift_score: float
    status: DriftStatus
    escalated: bool

    # Alert content
    subject: str
    body: str

    # Metadata for dedup and routing
    alert_key: str
    channels: tuple[str, ...]
    severity: str  # info, warning, critical

    metadata: Mapping[str, Any] = field(default_factory=dict)


def build_drift_alert(
    drift: DriftResult,
    *,
    policy: DriftPolicy | None = None,
    previous_alerts_sent: int = 0,
) -> DriftAlertEvent | None:
    """Build a drift alert event from a DriftResult.

    Returns None if the drift status is HEALTHY or if the alert should be suppressed
    (e.g., cooldown active, weekly limit reached).

    Args:
        drift: The drift analysis result.
        policy: Drift policy for cooldown/limit checks.
        previous_alerts_sent: Count of alerts already sent for this strategy this week.

    Returns:
        DriftAlertEvent if an alert should be sent, None otherwise.
    """
    policy = policy or DriftPolicy.load_default()

    if drift.status == DriftStatus.HEALTHY:
        return None

    if drift.alert_suppressed:
        return None

    if previous_alerts_sent >= policy.max_alerts_per_strategy_per_week:
        return None

    # Determine severity
    severity_map = {
        DriftStatus.WATCH: "info",
        DriftStatus.REVIEW: "warning",
        DriftStatus.CRITICAL: "critical",
    }
    severity = severity_map.get(drift.status, "info")

    # Build subject
    status_labels = {
        DriftStatus.WATCH: "⚠️ WATCH",
        DriftStatus.REVIEW: "🔴 REVIEW",
        DriftStatus.CRITICAL: "🚨 CRITICAL",
    }
    label = status_labels.get(drift.status, "UNKNOWN")
    escalated_tag = " [ESCALATED]" if drift.escalated else ""
    subject = f"[{drift.domain}] {label}{escalated_tag}: {drift.strategy_profile} — drift={drift.drift_score:.2f}"

    # Build body
    lines = [
        f"Strategy Lifecycle Drift Alert",
        f"",
        f"Strategy: {drift.strategy_profile}",
        f"Domain: {drift.domain}",
        f"As-of: {drift.as_of}",
        f"Drift Score: {drift.drift_score:.3f}",
        f"Status: {drift.status.value.upper()}",
        f"Escalated: {'Yes' if drift.escalated else 'No'}",
        f"",
        f"Breached Dimensions:",
    ]

    breached = drift.breached_dimensions
    if breached:
        for dim in breached:
            lines.append(
                f"  - {dim.metric_name}: actual={dim.actual:.4f}, "
                f"expected={dim.expected:.4f}, "
                f"deviation={dim.deviation_pct:.1%} (threshold: {dim.threshold:.1%})"
            )
    else:
        lines.append("  (no individual dimensions breached — composite score triggered)")

    lines.extend(
        [
            "",
            "Action required:",
            _action_for_status(drift.status),
        ]
    )

    # Build dedup key
    alert_key = f"drift/{drift.domain}/{drift.strategy_profile}/{drift.as_of.isoformat()}/{drift.status.value}"

    return DriftAlertEvent(
        strategy_profile=drift.strategy_profile,
        domain=drift.domain,
        as_of=drift.as_of,
        drift_score=drift.drift_score,
        status=drift.status,
        escalated=drift.escalated,
        subject=subject,
        body="\n".join(lines),
        alert_key=alert_key,
        channels=policy.notification_channels,
        severity=severity,
        metadata={
            "alert_type": "drift",
            "drift_score": drift.drift_score,
            "breached_count": len(breached),
            "dimensions": {k: v.to_dict() for k, v in drift.dimensions.items()},
        },
    )


def publish_drift_alerts(
    events: Sequence[DriftAlertEvent],
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Publish drift alerts through configured notification channels.

    Integrates with QuantPlatformKit notification system (telegram, email, etc.).

    Args:
        events: Alert events to publish.
        dry_run: If True, log but don't actually send.

    Returns:
        Dict of channel → count of alerts published.
    """
    counts: dict[str, int] = {}

    for event in events:
        for channel in event.channels:
            try:
                if not dry_run:
                    _dispatch_to_channel(event, channel)
                counts[channel] = counts.get(channel, 0) + 1
            except Exception:
                # Don't let one failed channel block others
                pass

    return counts


def _dispatch_to_channel(event: DriftAlertEvent, channel: str) -> None:
    """Dispatch a single alert event to a specific notification channel.

    Tries to use QuantPlatformKit notification adapters; falls back to printing.
    """
    # Try importing and using the platform notification system
    try:
        if channel == "telegram":
            from quant_platform_kit.notifications.strategy_plugin_telegram import (
                send_strategy_plugin_telegram_alert,
            )
            send_strategy_plugin_telegram_alert(
                subject=event.subject,
                body=event.body,
                alert_key=event.alert_key,
            )
        elif channel == "email":
            from quant_platform_kit.notifications.strategy_plugin_email import (
                send_strategy_plugin_email_alert,
            )
            send_strategy_plugin_email_alert(
                subject=event.subject,
                body=event.body,
                alert_key=event.alert_key,
            )
        elif channel == "push":
            from quant_platform_kit.notifications.strategy_plugin_push import (
                send_strategy_plugin_push_alert,
            )
            send_strategy_plugin_push_alert(
                subject=event.subject,
                body=event.body,
                alert_key=event.alert_key,
            )
        elif channel == "webhook":
            from quant_platform_kit.notifications.strategy_plugin_webhook import (
                send_strategy_plugin_webhook_alert,
            )
            send_strategy_plugin_webhook_alert(
                subject=event.subject,
                body=event.body,
                alert_key=event.alert_key,
            )
        else:
            # Fallback: just print
            print(f"[drift_alert][{channel}] {event.subject}")
    except ImportError:
        print(f"[drift_alert][{channel}] {event.subject}")


def _action_for_status(status: DriftStatus) -> str:
    if status == DriftStatus.CRITICAL:
        return (
            "CRITICAL: Review immediately. Consider pausing new risk additions, "
            "reducing position size, or switching to defensive allocation. "
            "The strategy may need parameter re-optimization or retirement review."
        )
    if status == DriftStatus.REVIEW:
        return (
            "REVIEW: Schedule a manual review within the next 1-2 trading days. "
            "Compare live performance against backtest on multiple dimensions. "
            "Consider triggering a parameter re-optimization run."
        )
    return (
        "WATCH: Monitor for further deterioration. No immediate action required, "
        "but track the trend over the next week. If drift persists or worsens, "
        "escalate to REVIEW."
    )
