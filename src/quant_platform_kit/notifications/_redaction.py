"""Small helpers for keeping notification errors safe to log."""

from __future__ import annotations

import re


_REDACTED = "<redacted>"
_TELEGRAM_BOT_PATH_RE = re.compile(r"(?i)(/bot)([^/\s]+)")
_SENSITIVE_QUERY_RE = re.compile(
    r"(?i)([?&](?:access[_-]?token|api[_-]?key|auth[_-]?token|key|password|secret|signature|token)=)([^&\s]+)"
)
_AUTH_HEADER_RE = re.compile(r"(?i)\b(Bearer|Basic)\s+([A-Za-z0-9._~+/=-]{8,})")
_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|auth[_-]?token|credential|password|private[_-]?key|secret|token)\s*[:=]\s*([\"']?)([^\"'\s,;]{8,})([\"']?)"
)


def redact_sensitive_text(value: object) -> str:
    """Return text suitable for logs without exposing common secret shapes."""

    text = str(value)
    text = _TELEGRAM_BOT_PATH_RE.sub(r"\1" + _REDACTED, text)
    text = _SENSITIVE_QUERY_RE.sub(r"\1" + _REDACTED, text)
    text = _AUTH_HEADER_RE.sub(r"\1 " + _REDACTED, text)
    return _ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}={_REDACTED}", text)
