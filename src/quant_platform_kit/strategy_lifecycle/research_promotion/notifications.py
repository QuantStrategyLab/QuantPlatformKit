"""Operator-facing research promotion notifications."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .models import ResearchPromotionTicket


def build_human_promotion_notification(
    ticket: ResearchPromotionTicket,
) -> tuple[str, str]:
    """Build operator-facing subject/body. Never claims live authority."""
    subject = (
        f"[AWAITING_HUMAN] {ticket.strategy_profile}/{ticket.domain} "
        f"ticket={ticket.ticket_id}"
    )
    body = "\n".join(
        [
            "Research promotion candidate is ready for human decision.",
            f"ticket_id: {ticket.ticket_id}",
            f"strategy_profile: {ticket.strategy_profile}",
            f"domain: {ticket.domain}",
            f"drift_status: {ticket.drift_status}",
            f"drift_score: {ticket.drift_score}",
            f"search_iterations: {ticket.search_iterations}",
            f"shadow_evidence_kind: {ticket.shadow_evidence_kind or 'none'}",
            f"shadow_passed: {ticket.shadow_passed}",
            f"proposed_params: {json.dumps(dict(ticket.proposed_params), sort_keys=True)}",
            "live_authority_granted: false",
            f"suggested_risk_profile: {ticket.suggested_risk_profile}",
            "On accept choose: target_platform + execution_mode(live|paper) + risk_profile.",
            "paper only if the broker provides a real paper/sim account; no synthetic matching.",
            "Action required: accept or reject this ticket.",
            "Accept records operator intent only; it does not enable live trading.",
        ]
    )
    return subject, body


def make_telegram_research_promotion_notifier(
    *,
    bot_token: str | None = None,
    chat_ids: str | list[str] | None = None,
    printer: Any = print,
) -> Callable[[str, str], bool]:
    """Build notify(subject, body) using Telegram; soft-skip if unconfigured."""
    import os

    from quant_platform_kit.notifications.telegram import send_telegram_message

    token = str(
        bot_token
        or os.environ.get("TELEGRAM_TOKEN")
        or os.environ.get("STRATEGY_PLUGIN_ALERT_TELEGRAM_BOT_TOKEN")
        or ""
    ).strip()
    chats: str | list[str] | None = chat_ids
    if chats is None:
        chats = (
            os.environ.get("GLOBAL_TELEGRAM_CHAT_ID")
            or os.environ.get("STRATEGY_PLUGIN_ALERT_TELEGRAM_CHAT_IDS")
            or ""
        )

    def notify(subject: str, body: str) -> bool:
        if not token or not str(chats or "").strip():
            printer(
                "research promotion telegram notify skipped: token/chat not configured",
                flush=True,
            )
            return False
        message = subject + "\n\n" + body
        return bool(
            send_telegram_message(
                bot_token=token,
                chat_ids=chats,
                text=message,
                parse_mode=None,
                printer=printer,
            )
        )

    return notify
