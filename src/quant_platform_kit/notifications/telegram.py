"""Telegram Bot API notification helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from collections.abc import Sequence
from typing import Any, TypedDict

from ._redaction import redact_exception, redact_sensitive_text
from .intent import NotificationIntent


DEFAULT_TELEGRAM_BOT_API_BASE_URL = "https://api.telegram.org"
_TELEGRAM_MARKET_SYMBOL_LINK_RE = re.compile(r"(?<![A-Za-z0-9_])([A-Z0-9]{1,12})\.([A-Z]{2,4})(?![A-Za-z0-9_])")
_TELEGRAM_MARKET_SYMBOL_LINK_JOINER = "\u2060"


class NotificationReceipt(TypedDict):
    status: str
    http_status: int | None
    sha256: str
    length: int
    run_id: str
    ok: bool


def send_notification_intent(
    intent: NotificationIntent,
    *,
    bot_token_env: str = "TELEGRAM_TOKEN",
    secret_name: str | None = None,
    project_id: str | None = None,
    api_base_url: str | None = None,
    parse_mode: str | None = None,
    disable_web_page_preview: bool = True,
    timeout: float = 10.0,
    opener: Any = None,
) -> NotificationReceipt:
    """Resolve credentials only during delivery and return report-safe evidence.

    An explicit secret name uses the existing cloud SecretStore; otherwise read
    the named environment variable. Dry runs read neither source. No provider
    payload, recipient, message text or exception is retained in the receipt.
    """
    receipt: NotificationReceipt = {
        "status": "failed", "http_status": None,
        "sha256": hashlib.sha256(intent.text.encode("utf-8")).hexdigest(),
        "length": len(intent.text), "run_id": intent.run_id, "ok": False,
    }
    if intent.channel != "telegram":
        return receipt
    if intent.dry_run:
        receipt.update(status="dry_run", ok=True)
        return receipt
    try:
        if secret_name is not None:
            from quant_platform_kit.cloud import get_secret_store
            token = get_secret_store().get_secret(secret_name, project_id=project_id)
        else:
            token = os.environ.get(bot_token_env)
        ok, status = _send_telegram_message(
            bot_token=token, chat_ids=intent.chat_ids, text=intent.text,
            api_base_url=api_base_url, parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview, timeout=timeout,
            opener=opener, printer=lambda *_args, **_kwargs: None,
        )
    except Exception:
        # Provider exceptions may contain arbitrary credential material. The new
        # boundary returns only a failed receipt, without retaining the exception.
        return receipt
    receipt.update(status="sent" if ok else "failed", http_status=status, ok=ok)
    return receipt


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
    sent, _status = _send_telegram_message(
        bot_token=bot_token, chat_ids=chat_ids, text=text, api_base_url=api_base_url,
        parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview,
        timeout=timeout, opener=opener, printer=printer,
    )
    return sent


def _send_telegram_message(
    *,
    bot_token: str | None,
    chat_ids: str | Sequence[str] | None,
    text: str | None,
    api_base_url: str | None,
    parse_mode: str | None,
    disable_web_page_preview: bool,
    timeout: float,
    opener: Any,
    printer,
) -> tuple[bool, int | None]:
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
    statuses: list[int | None] = []
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
        sent, status = _request_succeeded(request_opener, request, timeout, printer, chat_id)
        statuses.append(status)
        if not sent:
            all_sent = False
    # A single HTTP status is meaningful only when every recipient agrees.
    return all_sent, statuses[0] if len(set(statuses)) == 1 else None


def _request_succeeded(
    request_opener: Any,
    request: urllib.request.Request,
    timeout: float,
    printer,
    chat_id: str,
) -> tuple[bool, int | None]:
    raw_response = b""
    safe_chat_id = redact_sensitive_text(chat_id)
    try:
        with request_opener(request, timeout=timeout) as response:
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            status = int(status)
            read_response = getattr(response, "read", None)
            if callable(read_response):
                raw_response = read_response()
    except Exception as exc:
        printer(f"Telegram send failed for {safe_chat_id}: {redact_exception(exc)}", flush=True)
        code = getattr(exc, "code", None)
        return False, code if isinstance(code, int) else None
    if status < 200 or status >= 300:
        printer(f"Telegram send failed for {safe_chat_id}: HTTP {status}", flush=True)
        return False, status
    try:
        response_payload = json.loads(raw_response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        response_payload = None
    if isinstance(response_payload, dict) and response_payload.get("ok") is True:
        return True, status
    description = (
        response_payload.get("description")
        if isinstance(response_payload, dict)
        else None
    )
    printer(
        "Telegram send failed for "
        f"{safe_chat_id}: {redact_sensitive_text(description or 'missing affirmative API acknowledgement')}",
        flush=True,
    )
    return False, status


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
