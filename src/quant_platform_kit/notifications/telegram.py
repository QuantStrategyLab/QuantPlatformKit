"""Telegram Bot API notification helpers."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from collections.abc import Sequence
from typing import Any

from ._redaction import redact_sensitive_text


DEFAULT_TELEGRAM_BOT_API_BASE_URL = "https://api.telegram.org"
_TELEGRAM_MARKET_SYMBOL_LINK_RE = re.compile(r"(?<![A-Za-z0-9_])([A-Z0-9]{1,12})\.([A-Z]{2,4})(?![A-Za-z0-9_])")
_TELEGRAM_MARKET_SYMBOL_LINK_JOINER = "\u2060"


def _break_telegram_market_symbol_auto_links(value: object) -> str:
    text = str(value or "")
    return _TELEGRAM_MARKET_SYMBOL_LINK_RE.sub(
        lambda match: f"{match.group(1)}.{_TELEGRAM_MARKET_SYMBOL_LINK_JOINER}{match.group(2)}",
        text,
    )


def parse_telegram_chat_ids(raw_value: str | Sequence[str] | None) -> tuple[str, ...]:
    if raw_value is None:
        return ()
    if isinstance(raw_value, str):
        values = raw_value.replace(";", ",").replace("\n", ",").split(",")
    else:
        values = raw_value
    chat_ids = []
    seen = set()
    for value in values:
        chat_id = str(value or "").strip()
        if not chat_id or chat_id in seen:
            continue
        chat_ids.append(chat_id)
        seen.add(chat_id)
    return tuple(chat_ids)


def send_strategy_plugin_telegram(
    *,
    title: str,
    body: str,
    chat_ids: Sequence[str],
    bot_token: str | None,
    api_base_url: str | None = None,
    parse_mode: str | None = None,
    disable_web_page_preview: bool = True,
    timeout: float = 10.0,
    opener: Any = None,
    printer=print,
) -> bool:
    message = _build_message_text(title=title, body=body)
    return send_telegram_message(
        text=message,
        chat_ids=chat_ids,
        bot_token=bot_token,
        api_base_url=api_base_url,
        parse_mode=parse_mode,
        disable_web_page_preview=disable_web_page_preview,
        timeout=timeout,
        opener=opener,
        printer=printer,
    )


def send_telegram_message(
    bot_token: str | None = None,
    chat_ids: str | Sequence[str] | None = None,
    text: str | None = None,
    *,
    api_base_url: str | None = None,
    parse_mode: str | None = None,
    disable_web_page_preview: bool = True,
    timeout: float = 10.0,
    opener: Any = None,
    printer=print,
) -> bool:
    resolved_chat_ids = parse_telegram_chat_ids(chat_ids)
    token = str(bot_token or "").strip()
    message = str(text or "").strip()
    if not token:
        raise ValueError("token must not be empty.")
    if not resolved_chat_ids:
        raise ValueError("chat_id must not be empty.")
    if not message:
        raise ValueError("message must not be empty.")

    request_opener = opener or urllib.request.urlopen
    endpoint = _telegram_send_message_endpoint(api_base_url, token)
    all_sent = True
    for chat_id in resolved_chat_ids:
        payload: dict[str, object] = {
            "chat_id": chat_id,
            "text": _break_telegram_market_symbol_auto_links(message),
            "disable_web_page_preview": bool(disable_web_page_preview),
        }
        text_parse_mode = str(parse_mode or "").strip()
        if text_parse_mode:
            payload["parse_mode"] = text_parse_mode
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if not _request_succeeded(request_opener, request, timeout, printer, chat_id):
            all_sent = False
    return all_sent


def _request_succeeded(
    request_opener: Any,
    request: urllib.request.Request,
    timeout: float,
    printer,
    chat_id: str,
) -> bool:
    try:
        with request_opener(request, timeout=timeout) as response:
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            status = int(status)
    except Exception as exc:
        printer(f"Telegram send failed for {chat_id}: {redact_sensitive_text(exc)}", flush=True)
        return False
    if status < 200 or status >= 300:
        printer(f"Telegram send failed for {chat_id}: HTTP {status}", flush=True)
        return False
    return True


def _telegram_send_message_endpoint(api_base_url: str | None, bot_token: str) -> str:
    base_url = str(api_base_url or DEFAULT_TELEGRAM_BOT_API_BASE_URL).rstrip("/")
    encoded_token = urllib.parse.quote(str(bot_token), safe=":")
    return f"{base_url}/bot{encoded_token}/sendMessage"


def _build_message_text(*, title: str, body: str) -> str:
    text_title = str(title or "").strip()
    text_body = str(body or "").strip()
    if text_title and text_body:
        return f"{text_title}\n\n{text_body}"
    return text_body or text_title
