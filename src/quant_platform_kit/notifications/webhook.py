"""Webhook notification helpers for Chinese chat platforms.

Supported providers:
  - wecom      — 企业微信机器人 (WeCom Bot)
  - dingtalk   — 钉钉机器人 (DingTalk Bot)
  - feishu     — 飞书机器人 (Feishu Bot)
  - serverchan — Server酱 (ServerChan)

Usage::

    from quant_platform_kit.notifications.webhook import send_strategy_plugin_webhook

    send_strategy_plugin_webhook(
        provider="wecom",
        title="Alert Title",
        body="Alert body text.",
        webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
    )
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Sequence
from typing import Any


# ──────────────────────────────────────────────────────────────────────
#  Provider constants
# ──────────────────────────────────────────────────────────────────────

WEBHOOK_PROVIDER_WECOM = "wecom"
WEBHOOK_PROVIDER_DINGTALK = "dingtalk"
WEBHOOK_PROVIDER_FEISHU = "feishu"
WEBHOOK_PROVIDER_SERVERCHAN = "serverchan"

_SUPPORTED_WEBHOOK_PROVIDERS = frozenset({
    WEBHOOK_PROVIDER_WECOM,
    WEBHOOK_PROVIDER_DINGTALK,
    WEBHOOK_PROVIDER_FEISHU,
    WEBHOOK_PROVIDER_SERVERCHAN,
})


# ──────────────────────────────────────────────────────────────────────
#  Parser
# ──────────────────────────────────────────────────────────────────────

def parse_webhook_providers(raw_value: str | Sequence[str] | None) -> tuple[str, ...]:
    """Parse comma/semicolon/newline-separated provider names into a deduplicated tuple.

    Unknown provider names are silently skipped.
    """
    if raw_value is None:
        return ()
    if isinstance(raw_value, str):
        values = raw_value.replace(";", ",").replace("\n", ",").split(",")
    else:
        values = raw_value
    providers: list[str] = []
    seen: set[str] = set()
    for value in values:
        provider = str(value or "").strip().lower()
        if not provider or provider in seen:
            continue
        if provider not in _SUPPORTED_WEBHOOK_PROVIDERS:
            continue
        providers.append(provider)
        seen.add(provider)
    return tuple(providers)


# ──────────────────────────────────────────────────────────────────────
#  Dispatch function
# ──────────────────────────────────────────────────────────────────────

def send_strategy_plugin_webhook(
    *,
    provider: str,
    title: str,
    body: str,
    webhook_url: str,
    timeout: float = 10.0,
    opener: Any = None,
    printer=print,
) -> bool:
    """Send a strategy plugin alert via the specified webhook provider.

    Returns True if the message was sent successfully, False otherwise.
    """
    normalized = str(provider or "").strip().lower()
    if normalized == WEBHOOK_PROVIDER_WECOM:
        return send_wecom_webhook(
            webhook_url,
            _build_markdown_body(title, body),
            timeout=timeout,
            opener=opener,
            printer=printer,
        )
    if normalized == WEBHOOK_PROVIDER_DINGTALK:
        return send_dingtalk_webhook(
            webhook_url,
            _build_markdown_body(title, body),
            title=title,
            timeout=timeout,
            opener=opener,
            printer=printer,
        )
    if normalized == WEBHOOK_PROVIDER_FEISHU:
        return send_feishu_webhook(
            webhook_url,
            _build_plain_body(title, body),
            timeout=timeout,
            opener=opener,
            printer=printer,
        )
    if normalized == WEBHOOK_PROVIDER_SERVERCHAN:
        return send_serverchan_webhook(
            webhook_url,
            title=title,
            body=body,
            timeout=timeout,
            opener=opener,
            printer=printer,
        )
    printer(f"Webhook send failed: unsupported provider {provider!r}", flush=True)
    return False


# ──────────────────────────────────────────────────────────────────────
#  Per-provider send functions
# ──────────────────────────────────────────────────────────────────────

def send_wecom_webhook(
    webhook_url: str,
    text: str,
    *,
    timeout: float = 10.0,
    opener: Any = None,
    printer=print,
) -> bool:
    """Send a markdown message to a WeCom (企业微信) bot webhook.

    Webhook URL format: ``https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=KEY``
    """
    url = str(webhook_url or "").strip()
    message = str(text or "").strip()
    if not url or not message:
        return False
    request_opener = opener or urllib.request.urlopen
    payload = {"msgtype": "markdown", "markdown": {"content": message}}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    return _json_webhook_request_succeeded(
        request_opener, request, timeout, printer,
        provider="WeCom", errcode_key="errcode", errmsg_key="errmsg",
    )


def send_dingtalk_webhook(
    webhook_url: str,
    text: str,
    *,
    title: str = "",
    timeout: float = 10.0,
    opener: Any = None,
    printer=print,
) -> bool:
    """Send a markdown message to a DingTalk (钉钉) bot webhook.

    Webhook URL format: ``https://oapi.dingtalk.com/robot/send?access_token=TOKEN``
    """
    url = str(webhook_url or "").strip()
    message = str(text or "").strip()
    if not url or not message:
        return False
    request_opener = opener or urllib.request.urlopen
    msg_title = str(title or "").strip() or "Notification"
    payload = {"msgtype": "markdown", "markdown": {"title": msg_title, "text": message}}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    return _json_webhook_request_succeeded(
        request_opener, request, timeout, printer,
        provider="DingTalk", errcode_key="errcode", errmsg_key="errmsg",
    )


def send_feishu_webhook(
    webhook_url: str,
    text: str,
    *,
    timeout: float = 10.0,
    opener: Any = None,
    printer=print,
) -> bool:
    """Send a text message to a Feishu (飞书) bot webhook.

    Webhook URL format: ``https://open.feishu.cn/open-apis/bot/v2/hook/KEY``
    """
    url = str(webhook_url or "").strip()
    message = str(text or "").strip()
    if not url or not message:
        return False
    request_opener = opener or urllib.request.urlopen
    payload = {"msg_type": "text", "content": {"text": message}}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    return _json_webhook_request_succeeded(
        request_opener, request, timeout, printer,
        provider="Feishu", errcode_key="code", errmsg_key="msg",
    )


def send_serverchan_webhook(
    webhook_url: str,
    *,
    title: str = "",
    body: str = "",
    timeout: float = 10.0,
    opener: Any = None,
    printer=print,
) -> bool:
    """Send a message via Server酱 (ServerChan).

    URL format: ``https://sctapi.ftqq.com/SENDKEY.send``
    """
    url = str(webhook_url or "").strip()
    text_title = str(title or "").strip()
    text_body = str(body or "").strip()
    if not url or not (text_title or text_body):
        return False
    request_opener = opener or urllib.request.urlopen
    payload = {"title": text_title, "desp": text_body}
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
        method="POST",
    )
    return _json_webhook_request_succeeded(
        request_opener, request, timeout, printer,
        provider="ServerChan", errcode_key="code", errmsg_key="message",
    )


# ──────────────────────────────────────────────────────────────────────
#  Internal helpers
# ──────────────────────────────────────────────────────────────────────

def _build_markdown_body(title: str, body: str) -> str:
    """Build a markdown body by joining title and body.

    Title is rendered as bold text (``**title**``).
    """
    text_title = str(title or "").strip()
    text_body = str(body or "").strip()
    if text_title and text_body:
        return f"**{text_title}**\n\n{text_body}"
    return text_body or text_title


def _build_plain_body(title: str, body: str) -> str:
    """Build a plain-text body by joining title and body with double newlines."""
    text_title = str(title or "").strip()
    text_body = str(body or "").strip()
    if text_title and text_body:
        return f"{text_title}\n\n{text_body}"
    return text_body or text_title


def _json_webhook_request_succeeded(
    request_opener: Any,
    request: urllib.request.Request,
    timeout: float,
    printer,
    provider: str,
    errcode_key: str,
    errmsg_key: str,
) -> bool:
    """Validate HTTP status and JSON response code for a webhook request.

    Returns True only when HTTP status is 2xx AND the JSON response
    indicates success (errcode/code == 0). If the response body cannot
    be parsed as JSON, HTTP 2xx alone is treated as success.
    """
    try:
        with request_opener(request, timeout=timeout) as response:
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            status = int(status)
            raw = response.read()
    except Exception as exc:
        printer(f"{provider} webhook send failed: {exc}", flush=True)
        return False
    if status < 200 or status >= 300:
        printer(f"{provider} webhook send failed: HTTP {status}", flush=True)
        return False
    try:
        body = json.loads(raw.decode("utf-8"))
        if body.get(errcode_key, -1) != 0:
            printer(
                f"{provider} webhook send failed: {body.get(errmsg_key, 'unknown error')}",
                flush=True,
            )
            return False
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass  # unparseable body on HTTP 2xx → treat as success
    return True


# ──────────────────────────────────────────────────────────────────────
#  Channel auto-detection
# ──────────────────────────────────────────────────────────────────────

# Domain patterns for each supported webhook platform
_CHANNEL_DOMAIN_PATTERNS: dict[str, str] = {
    "qyapi.weixin.qq.com": WEBHOOK_PROVIDER_WECOM,
    "oapi.dingtalk.com": WEBHOOK_PROVIDER_DINGTALK,
    "open.feishu.cn": WEBHOOK_PROVIDER_FEISHU,
    "sctapi.ftqq.com": WEBHOOK_PROVIDER_SERVERCHAN,
}


def detect_channel_from_url(url: str) -> str | None:
    """Detect the webhook channel type from a webhook URL's hostname.

    Returns one of ``"wecom"``, ``"dingtalk"``, ``"feishu"``, ``"serverchan"``,
    or ``None`` if the URL doesn't match any known platform.

    >>> detect_channel_from_url("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx")
    'wecom'
    >>> detect_channel_from_url("https://oapi.dingtalk.com/robot/send?access_token=xxx")
    'dingtalk'
    """
    host = urllib.parse.urlparse(str(url or "")).hostname or ""
    for domain, channel in _CHANNEL_DOMAIN_PATTERNS.items():
        if domain in host:
            return channel
    return None
