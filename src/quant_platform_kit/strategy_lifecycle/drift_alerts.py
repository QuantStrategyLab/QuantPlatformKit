"""Drift alert signal builder — Telegram via real send path + attention keys."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from quant_platform_kit.risk.attention import (
    AttentionAxes,
    AttentionDecision,
    AttentionLevel,
    attention_level_from_drift_status,
    attention_transition_key,
    evaluate_attention,
    render_attention_compact,
)
from quant_platform_kit.strategy_lifecycle.contracts import DriftResult, DriftStatus
from quant_platform_kit.strategy_lifecycle.drift_policy import DriftPolicy

_PAGEABLE = frozenset({DriftStatus.REVIEW, DriftStatus.CRITICAL})


@dataclass(frozen=True)
class DriftAlertEvent:
    strategy_profile: str
    domain: str
    as_of: date
    drift_score: float
    status: DriftStatus
    escalated: bool
    subject: str
    body: str
    alert_key: str
    channels: tuple[str, ...]
    severity: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


def build_drift_alert(
    drift: DriftResult,
    *,
    policy: DriftPolicy | None = None,
    previous_alerts_sent: int = 0,
    locale: object | None = None,
    platform: str | None = None,
    account_alias: str | None = None,
) -> DriftAlertEvent | None:
    """Build a pageable drift alert. WATCH/HEALTHY return None (no Telegram page)."""

    policy = policy or DriftPolicy.load_default()
    if drift.as_of is None or drift.status == DriftStatus.HEALTHY:
        return None
    if drift.status not in _PAGEABLE:
        return None
    if drift.alert_suppressed:
        return None
    if previous_alerts_sent >= policy.max_alerts_per_strategy_per_week:
        return None

    attention = evaluate_attention(
        AttentionAxes(drift_status=drift.status.value)
    )
    platform_id = str(platform or drift.domain or "platform").strip() or "platform"
    account = str(account_alias or "-").strip() or "-"
    primary_reason = attention.reason_codes[0] if attention.reason_codes else f"drift_{drift.status.value}"
    alert_key = attention_transition_key(
        platform=platform_id,
        account_alias=account,
        strategy_profile=drift.strategy_profile,
        level=attention.level,
        primary_reason=primary_reason,
    )

    severity = "critical" if drift.status == DriftStatus.CRITICAL else "warning"
    label = "🚨 CRITICAL" if drift.status == DriftStatus.CRITICAL else "🔴 REVIEW"
    escalated_tag = " [ESCALATED]" if drift.escalated else ""
    subject = (
        f"[{drift.domain}] {label}{escalated_tag}: "
        f"{drift.strategy_profile} — drift={drift.drift_score:.2f}"
    )
    body = render_attention_compact(
        locale=locale,
        platform=platform_id,
        account_alias=account,
        strategy_profile=drift.strategy_profile,
        decision=attention,
    )

    return DriftAlertEvent(
        strategy_profile=drift.strategy_profile,
        domain=drift.domain,
        as_of=drift.as_of,
        drift_score=drift.drift_score,
        status=drift.status,
        escalated=drift.escalated,
        subject=subject,
        body=body,
        alert_key=alert_key,
        channels=policy.notification_channels,
        severity=severity,
        metadata={
            "alert_type": "drift",
            "attention_level": attention.level.value,
            "reason_codes": list(attention.reason_codes),
            "drift_score": drift.drift_score,
        },
    )


def publish_drift_alerts(
    events: Sequence[DriftAlertEvent],
    *,
    dry_run: bool = False,
    telegram_sender: Callable[..., bool] | None = None,
    already_sent_keys: Sequence[str] | None = None,
    record_sent_key: Callable[[str], Any] | None = None,
    log_message: Callable[..., Any] = print,
) -> dict[str, int]:
    """Publish pageable drift alerts. Returns counts: sent/skipped/failed.

    Compatible with lifecycle CLI ``sum(counts.values())``.
    """

    counts = {"sent": 0, "skipped": 0, "failed": 0}
    seen = {str(key) for key in (already_sent_keys or ())}

    for event in events:
        if "telegram" not in event.channels:
            _log(log_message, f"drift_alert_skipped_no_telegram_channel key={event.alert_key}")
            counts["skipped"] += 1
            continue
        if event.alert_key in seen:
            counts["skipped"] += 1
            continue
        if dry_run:
            _log(log_message, f"drift_alert_dry_run key={event.alert_key}")
            counts["sent"] += 1
            seen.add(event.alert_key)
            if record_sent_key is not None:
                record_sent_key(event.alert_key)
            continue

        sender = telegram_sender or _default_telegram_sender
        try:
            ok = bool(
                sender(
                    subject=event.subject,
                    body=event.body,
                    text=f"{event.subject}\n\n{event.body}",
                    alert_key=event.alert_key,
                )
            )
        except Exception as exc:  # noqa: BLE001
            _log(
                log_message,
                f"drift_alert_send_failed key={event.alert_key} error={type(exc).__name__}",
            )
            counts["failed"] += 1
            continue
        if not ok:
            _log(log_message, f"telegram_not_configured_or_send_false key={event.alert_key}")
            # Missing config is skipped (observable), hard false from sender after config is failed.
            # Default sender returns False only when unconfigured → skipped.
            if telegram_sender is None:
                counts["skipped"] += 1
                _log(log_message, f"telegram_not_configured key={event.alert_key}")
            else:
                counts["failed"] += 1
            continue
        counts["sent"] += 1
        seen.add(event.alert_key)
        if record_sent_key is not None:
            record_sent_key(event.alert_key)
    return counts


def _default_telegram_sender(**kwargs: Any) -> bool:
    from quant_platform_kit.notifications.telegram import send_telegram_message

    token = str(
        os.environ.get("STRATEGY_PLUGIN_ALERT_TELEGRAM_BOT_TOKEN")
        or os.environ.get("TELEGRAM_TOKEN")
        or ""
    ).strip()
    chats = (
        os.environ.get("QSL_GLOBAL_TELEGRAM_CHAT_ID")
        or os.environ.get("STRATEGY_PLUGIN_ALERT_TELEGRAM_CHAT_IDS")
        or os.environ.get("GLOBAL_TELEGRAM_CHAT_ID")
        or ""
    )
    if not token or not str(chats).strip():
        return False
    text = str(kwargs.get("text") or "").strip()
    if not text:
        subject = str(kwargs.get("subject") or "").strip()
        body = str(kwargs.get("body") or "").strip()
        text = f"{subject}\n\n{body}".strip()
    if not text:
        return False
    return bool(
        send_telegram_message(
            bot_token=token,
            chat_ids=chats,
            text=text,
            parse_mode=None,
        )
    )


def _log(log_message: Callable[..., Any], line: str) -> None:
    try:
        log_message(line)
    except TypeError:
        log_message(line, flush=True)
