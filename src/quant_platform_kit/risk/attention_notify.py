"""Publish AttentionLevel ACTION/HALT transitions to Telegram (operator page).

Does not grant live, raise RRL, or auto-resume. Marker recording only after send.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from quant_platform_kit.risk.attention import (
    AttentionDecision,
    AttentionLevel,
    attention_transition_key,
    render_attention_compact,
    should_notify_attention_transition,
)


def publish_attention_telegram_transition(
    *,
    decision: AttentionDecision,
    platform: str,
    account_alias: str,
    strategy_profile: str,
    locale: object | None = None,
    previous_level: AttentionLevel | str | None = None,
    previous_reason_codes: Sequence[str] | None = None,
    already_sent_keys: Sequence[str] | None = None,
    record_sent_key: Callable[[str], Any] | None = None,
    telegram_sender: Callable[..., bool] | None = None,
    log_message: Callable[..., Any] = print,
) -> dict[str, int]:
    """Send one compact Telegram page on ACTION/HALT transition.

    Returns counts ``sent`` / ``skipped`` / ``failed`` (sum-friendly for CLI).
    """

    counts = {"sent": 0, "skipped": 0, "failed": 0}
    if not should_notify_attention_transition(
        previous_level=previous_level,
        new_level=decision.level,
        previous_reason_codes=previous_reason_codes,
        new_reason_codes=decision.reason_codes,
    ):
        counts["skipped"] += 1
        return counts

    primary = decision.reason_codes[0] if decision.reason_codes else decision.level.value
    alert_key = attention_transition_key(
        platform=platform,
        account_alias=account_alias,
        strategy_profile=strategy_profile,
        level=decision.level,
        primary_reason=primary,
    )
    seen = {str(key) for key in (already_sent_keys or ())}
    if alert_key in seen:
        counts["skipped"] += 1
        return counts

    text = render_attention_compact(
        locale=locale or os.environ.get("QSL_NOTIFY_LANG") or os.environ.get("NOTIFY_LANG"),
        platform=platform,
        account_alias=account_alias,
        strategy_profile=strategy_profile,
        decision=decision,
    )
    sender = telegram_sender or _default_telegram_sender
    try:
        ok = bool(sender(text=text, alert_key=alert_key))
    except Exception as exc:  # noqa: BLE001
        log_message(f"attention_telegram_failed key={alert_key} error={type(exc).__name__}")
        counts["failed"] += 1
        return counts
    if not ok:
        log_message(f"attention_telegram_skipped key={alert_key} reason=telegram_not_configured_or_false")
        counts["skipped"] += 1
        return counts
    counts["sent"] += 1
    if record_sent_key is not None:
        record_sent_key(alert_key)
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
        return False
    return bool(
        send_telegram_message(
            bot_token=token,
            chat_ids=chats,
            text=text,
            parse_mode=None,
        )
    )


__all__ = ["publish_attention_telegram_transition"]
