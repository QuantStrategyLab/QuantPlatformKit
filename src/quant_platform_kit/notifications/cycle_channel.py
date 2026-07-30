"""Cycle notification sender factory.

Provides a single entry point for building channel-agnostic notification
senders.  Each sender is a ``Callable[[str], bool]`` that accepts a fully
rendered message string and returns whether the transport acknowledged it.

Supported channels:
  - telegram   — Telegram Bot API (default)
  - wecom      — 企业微信机器人 (WeCom Bot)
  - dingtalk   — 钉钉机器人 (DingTalk Bot)
  - feishu     — 飞书机器人 (Feishu Bot)
  - serverchan — Server酱 (ServerChan)

Usage::

    from quant_platform_kit.notifications.cycle_channel import build_cycle_sender

    send = build_cycle_sender(
        channel="wecom",
        webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
    )
    send("🔔 【调仓指令】\\n\\n...")
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


# ──────────────────────────────────────────────────────────────────────
#  Channel constants
# ──────────────────────────────────────────────────────────────────────

CYCLE_CHANNEL_TELEGRAM = "telegram"
CYCLE_CHANNEL_WECOM = "wecom"
CYCLE_CHANNEL_DINGTALK = "dingtalk"
CYCLE_CHANNEL_FEISHU = "feishu"
CYCLE_CHANNEL_SERVERCHAN = "serverchan"

_SUPPORTED_CYCLE_CHANNELS = frozenset({
    CYCLE_CHANNEL_TELEGRAM,
    CYCLE_CHANNEL_WECOM,
    CYCLE_CHANNEL_DINGTALK,
    CYCLE_CHANNEL_FEISHU,
    CYCLE_CHANNEL_SERVERCHAN,
})


# ──────────────────────────────────────────────────────────────────────
#  Factory
# ──────────────────────────────────────────────────────────────────────

def build_cycle_sender(
    *,
    channel: str = CYCLE_CHANNEL_TELEGRAM,
    telegram_token: str | None = None,
    telegram_chat_id: str | None = None,
    webhook_url: str | None = None,
    printer: Any = print,
) -> Callable[[str], bool]:
    """Build a ``send_message(message: str) -> bool`` callback for *channel*.

    Args:
        channel: One of ``"telegram"``, ``"wecom"``, ``"dingtalk"``,
            ``"feishu"``, ``"serverchan"``.  Defaults to ``"telegram"``.
        telegram_token: Bot token (required when channel is ``"telegram"``).
        telegram_chat_id: Target chat ID (required when channel is ``"telegram"``).
        webhook_url: Full webhook URL (required for non-telegram channels).
        printer: Error logger (defaults to ``print``).
    """
    normalized = str(channel or "").strip().lower() or CYCLE_CHANNEL_TELEGRAM
    if normalized not in _SUPPORTED_CYCLE_CHANNELS:
        printer(
            f"Cycle sender: unsupported channel {channel!r}, falling back to telegram",
            flush=True,
        )
        normalized = CYCLE_CHANNEL_TELEGRAM

    if normalized == CYCLE_CHANNEL_TELEGRAM:
        return _build_telegram_sender(
            token=telegram_token,
            chat_id=telegram_chat_id,
            printer=printer,
        )
    return _build_webhook_sender(
        channel=normalized,
        webhook_url=webhook_url,
        printer=printer,
    )


# ──────────────────────────────────────────────────────────────────────
#  Smart channel resolution
# ──────────────────────────────────────────────────────────────────────

def resolve_cycle_channel_and_url(
    *,
    explicit_channel: str = CYCLE_CHANNEL_TELEGRAM,
    telegram_token: str | None = None,
    telegram_chat_id: str | None = None,
    wecom_url: str | None = None,
    dingtalk_url: str | None = None,
    feishu_url: str | None = None,
    serverchan_url: str | None = None,
) -> tuple[str, str | None]:
    """Resolve the notification channel and optional webhook URL.

    Resolution order:
    1. If *explicit_channel* is not ``"telegram"``, use it with the
       matching webhook URL.
    2. If *telegram_token* and *telegram_chat_id* are both set, use Telegram.
    3. Otherwise, scan the webhook URLs and auto-detect the first configured
       channel.
    4. Fall back to ``"telegram"`` with no URL (sender will log a warning).

    Returns:
        A ``(channel, webhook_url)`` tuple.  *webhook_url* is ``None``
        when the channel is ``"telegram"``.
    """
    normalized = str(explicit_channel or "").strip().lower() or CYCLE_CHANNEL_TELEGRAM

    # Explicit non-telegram channel → use it with matching URL
    if normalized != CYCLE_CHANNEL_TELEGRAM:
        url_map = {
            CYCLE_CHANNEL_WECOM: wecom_url,
            CYCLE_CHANNEL_DINGTALK: dingtalk_url,
            CYCLE_CHANNEL_FEISHU: feishu_url,
            CYCLE_CHANNEL_SERVERCHAN: serverchan_url,
        }
        return normalized, _first_set(url_map.get(normalized))

    # Telegram explicitly configured → use it
    if telegram_token and telegram_chat_id:
        return CYCLE_CHANNEL_TELEGRAM, None

    # Auto-detect from webhook URLs
    for channel, url in [
        (CYCLE_CHANNEL_WECOM, wecom_url),
        (CYCLE_CHANNEL_DINGTALK, dingtalk_url),
        (CYCLE_CHANNEL_FEISHU, feishu_url),
        (CYCLE_CHANNEL_SERVERCHAN, serverchan_url),
    ]:
        if url:
            return channel, url

    # Nothing configured → keep telegram (sender will print warnings)
    return CYCLE_CHANNEL_TELEGRAM, None


def _first_set(value: str | None) -> str | None:
    """Return *value* if it is a non-empty string, otherwise None."""
    text = str(value or "").strip()
    return text if text else None


# ──────────────────────────────────────────────────────────────────────
#  Telegram sender
# ──────────────────────────────────────────────────────────────────────

def _build_telegram_sender(
    *,
    token: str | None,
    chat_id: str | None,
    printer: Any = print,
) -> Callable[[str], bool]:
    from .telegram import send_telegram_message

    resolved_token = str(token or "").strip()
    resolved_chat_id = str(chat_id or "").strip()

    def send_message(message: str) -> bool:
        if not resolved_token:
            printer("Cycle sender: telegram token not configured", flush=True)
            return False
        if not resolved_chat_id:
            printer("Cycle sender: telegram chat_id not configured", flush=True)
            return False
        text = str(message or "").strip()
        if not text:
            return False
        return send_telegram_message(
            bot_token=resolved_token,
            chat_ids=resolved_chat_id,
            text=text,
            parse_mode="",  # plain text — no HTML/Markdown parsing
            printer=printer,
        )

    return send_message


# ──────────────────────────────────────────────────────────────────────
#  Webhook senders
# ──────────────────────────────────────────────────────────────────────

def _build_webhook_sender(
    *,
    channel: str,
    webhook_url: str | None,
    printer: Any = print,
) -> Callable[[str], bool]:
    from .webhook import (
        WEBHOOK_PROVIDER_DINGTALK,
        WEBHOOK_PROVIDER_FEISHU,
        WEBHOOK_PROVIDER_SERVERCHAN,
        WEBHOOK_PROVIDER_WECOM,
        send_dingtalk_webhook,
        send_feishu_webhook,
        send_serverchan_webhook,
        send_wecom_webhook,
    )

    resolved_url = str(webhook_url or "").strip()

    def send_message(message: str) -> bool:
        nonlocal resolved_url
        if not resolved_url:
            printer(f"Cycle sender: webhook URL not configured for {channel}", flush=True)
            return False
        text = str(message or "").strip()
        if not text:
            return False
        if channel == WEBHOOK_PROVIDER_WECOM:
            return send_wecom_webhook(resolved_url, text, printer=printer)
        elif channel == WEBHOOK_PROVIDER_DINGTALK:
            return send_dingtalk_webhook(resolved_url, text, printer=printer)
        elif channel == WEBHOOK_PROVIDER_FEISHU:
            return send_feishu_webhook(resolved_url, text, printer=printer)
        elif channel == WEBHOOK_PROVIDER_SERVERCHAN:
            # ServerChan: first line → title, remainder → body
            lines = text.split("\n", 1)
            title = lines[0]
            body = lines[1] if len(lines) > 1 else ""
            return send_serverchan_webhook(
                resolved_url,
                title=title,
                body=body,
                printer=printer,
            )
        return False

    return send_message
