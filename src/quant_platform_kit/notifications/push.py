"""Mobile push notification helpers."""

from __future__ import annotations

import urllib.parse
import urllib.request
from collections.abc import Sequence
from email.header import Header
from typing import Any

from ._redaction import redact_sensitive_text


PUSH_PROVIDER_NTFY = "ntfy"
PUSH_PROVIDER_PUSHOVER = "pushover"
DEFAULT_NTFY_API_BASE_URL = "https://ntfy.sh"
DEFAULT_PUSHOVER_API_BASE_URL = "https://api.pushover.net"


def parse_push_recipients(raw_value: str | Sequence[str] | None) -> tuple[str, ...]:
    if raw_value is None:
        return ()
    if isinstance(raw_value, str):
        values = raw_value.replace(";", ",").replace("\n", ",").split(",")
    else:
        values = raw_value
    recipients = []
    seen = set()
    for value in values:
        recipient = str(value or "").strip()
        if not recipient or recipient in seen:
            continue
        recipients.append(recipient)
        seen.add(recipient)
    return tuple(recipients)


def send_strategy_plugin_push(
    *,
    provider: str,
    title: str,
    body: str,
    recipients: Sequence[str],
    app_token: str | None = None,
    access_token: str | None = None,
    api_base_url: str | None = None,
    device: str | None = None,
    priority: str | int | None = None,
    tags: str | None = None,
    timeout: float = 10.0,
    opener: Any = None,
    printer=print,
) -> bool:
    normalized_provider = str(provider or "").strip().lower()
    if normalized_provider == PUSH_PROVIDER_PUSHOVER:
        return send_pushover_push(
            title=title,
            body=body,
            recipients=recipients,
            app_token=app_token,
            api_base_url=api_base_url or DEFAULT_PUSHOVER_API_BASE_URL,
            device=device,
            priority=priority,
            timeout=timeout,
            opener=opener,
            printer=printer,
        )
    if normalized_provider == PUSH_PROVIDER_NTFY:
        return send_ntfy_push(
            title=title,
            body=body,
            recipients=recipients,
            access_token=access_token,
            api_base_url=api_base_url or DEFAULT_NTFY_API_BASE_URL,
            priority=priority,
            tags=tags,
            timeout=timeout,
            opener=opener,
            printer=printer,
        )
    printer(f"Push send failed: unsupported provider {provider!r}", flush=True)
    return False


def send_pushover_push(
    *,
    title: str,
    body: str,
    recipients: Sequence[str],
    app_token: str | None,
    api_base_url: str = DEFAULT_PUSHOVER_API_BASE_URL,
    device: str | None = None,
    priority: str | int | None = None,
    timeout: float = 10.0,
    opener: Any = None,
    printer=print,
) -> bool:
    resolved_recipients = parse_push_recipients(recipients)
    token = str(app_token or "").strip()
    message = str(body or "").strip()
    if not resolved_recipients or not token or not message:
        return False

    request_opener = opener or urllib.request.urlopen
    endpoint = _pushover_messages_endpoint(api_base_url)
    all_sent = True
    for recipient in resolved_recipients:
        payload = {
            "token": token,
            "user": recipient,
            "message": message,
        }
        text_title = str(title or "").strip()
        if text_title:
            payload["title"] = text_title
        text_device = str(device or "").strip()
        if text_device:
            payload["device"] = text_device
        text_priority = str(priority or "").strip()
        if text_priority:
            payload["priority"] = text_priority
        data = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        if not _request_succeeded(request_opener, request, timeout, printer, recipient):
            all_sent = False
    return all_sent


def send_ntfy_push(
    *,
    title: str,
    body: str,
    recipients: Sequence[str],
    access_token: str | None = None,
    api_base_url: str = DEFAULT_NTFY_API_BASE_URL,
    priority: str | int | None = None,
    tags: str | None = None,
    timeout: float = 10.0,
    opener: Any = None,
    printer=print,
) -> bool:
    resolved_recipients = parse_push_recipients(recipients)
    message = str(body or "").strip()
    if not resolved_recipients or not message:
        return False

    request_opener = opener or urllib.request.urlopen
    token = str(access_token or "").strip()
    all_sent = True
    for recipient in resolved_recipients:
        headers = {
            "Content-Type": "text/plain; charset=utf-8",
        }
        text_title = str(title or "").strip()
        if text_title:
            headers["Title"] = _encode_http_header(text_title)
        text_priority = str(priority or "").strip()
        if text_priority:
            headers["Priority"] = text_priority
        text_tags = str(tags or "").strip()
        if text_tags:
            headers["Tags"] = _encode_http_header(text_tags)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            _ntfy_topic_endpoint(api_base_url, recipient),
            data=message.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        if not _request_succeeded(request_opener, request, timeout, printer, recipient):
            all_sent = False
    return all_sent


def _request_succeeded(
    request_opener: Any,
    request: urllib.request.Request,
    timeout: float,
    printer,
    recipient: str,
) -> bool:
    try:
        with request_opener(request, timeout=timeout) as response:
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            status = int(status)
    except Exception as exc:
        printer(f"Push send failed for {recipient}: {redact_sensitive_text(exc)}", flush=True)
        return False
    if status < 200 or status >= 300:
        printer(f"Push send failed for {recipient}: HTTP {status}", flush=True)
        return False
    return True


def _pushover_messages_endpoint(api_base_url: str) -> str:
    base_url = str(api_base_url or DEFAULT_PUSHOVER_API_BASE_URL).rstrip("/")
    if base_url.endswith("/1/messages.json"):
        return base_url
    return f"{base_url}/1/messages.json"


def _ntfy_topic_endpoint(api_base_url: str, recipient: str) -> str:
    target = str(recipient or "").strip()
    if target.startswith(("https://", "http://")):
        return target
    base_url = str(api_base_url or DEFAULT_NTFY_API_BASE_URL).rstrip("/")
    path = "/".join(
        urllib.parse.quote(part.strip(), safe="")
        for part in target.strip("/").split("/")
        if part.strip()
    )
    return f"{base_url}/{path}"


def _encode_http_header(value: str) -> str:
    text = str(value or "")
    try:
        text.encode("latin-1")
    except UnicodeEncodeError:
        return Header(text, "utf-8").encode()
    return text
