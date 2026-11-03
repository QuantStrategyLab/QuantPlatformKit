"""Small helpers for keeping notification errors safe to log."""

from __future__ import annotations

import json
import re
import traceback
from collections.abc import Mapping


_REDACTED = "<redacted>"
_TELEGRAM_TOKEN_RE = re.compile(r"\b\d{6,12}:A[A-Za-z0-9_-]{34}(?![A-Za-z0-9_-])")
_TELEGRAM_BOT_PATH_RE = re.compile(r"(?i)(/bot)([^/\s]+)")
_SENSITIVE_QUERY_RE = re.compile(
    r"(?i)([?&](?:access[_-]?token|api[_-]?key|auth[_-]?token|key|password|secret|signature|token)=)([^&\s]+)"
)
_AUTH_HEADER_RE = re.compile(r"(?i)\b(Bearer|Basic)\s+([A-Za-z0-9._~+/=-]{8,})")
_ASSIGNMENT_RE = re.compile(
    r"(?i)(\b[A-Za-z0-9_-]{0,64}(?:api[_-]?key|auth[_-]?token|authorization|credential|"
    r"password|passwd|private[_-]?key|secret|token)[A-Za-z0-9_-]{0,64}[\"']?\s*[:=]\s*)"
    r"(?:([\"'])(.*?)\2|([^\s,;}\]]+))"
)


def redact_sensitive_text(value: object) -> str:
    """Return text suitable for logs without exposing common secret shapes."""

    text = str(value)
    # JSON field names can be quoted, and their values need not look like tokens.
    try:
        data = json.loads(text) if text.lstrip().startswith(("{", "[")) else None
    except (ValueError, RecursionError):
        data = None
    if isinstance(data, (dict, list)):
        redacted = redact_sensitive_data(data)
        return json.dumps(redacted, ensure_ascii=False) if redacted != data else text
    text = _TELEGRAM_TOKEN_RE.sub(_REDACTED, text)
    text = _TELEGRAM_BOT_PATH_RE.sub(r"\1" + _REDACTED, text)
    text = _SENSITIVE_QUERY_RE.sub(r"\1" + _REDACTED, text)
    text = _AUTH_HEADER_RE.sub(r"\1 " + _REDACTED, text)
    return _ASSIGNMENT_RE.sub(
        lambda match: f"{match.group(1)}{match.group(2) or ''}{_REDACTED}{match.group(2) or ''}",
        text,
    )


def _is_sensitive_key(key: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
    return normalized in {"key", "auth"} or any(
        part in normalized for part in (
            "token", "secret", "password", "passwd", "apikey", "authorization",
            "privatekey", "credential", "accesskey", "signingkey",
        )
    )


def redact_sensitive_data(obj: object) -> object:
    """Copy JSON-like data, redacting credential fields and secret-shaped text."""
    if isinstance(obj, Mapping):
        return {
            redact_sensitive_text(key) if isinstance(key, str) else key:
            _REDACTED if _is_sensitive_key(key) else redact_sensitive_data(value)
            for key, value in obj.items()
        }
    if isinstance(obj, list):
        return [redact_sensitive_data(value) for value in obj]
    if isinstance(obj, tuple):
        return tuple(redact_sensitive_data(value) for value in obj)
    if isinstance(obj, BaseException):
        return redact_exception(obj)
    if isinstance(obj, str):
        return redact_sensitive_text(obj)
    return obj


def redact_exception(exc: BaseException) -> str:
    """Render a traceback and its chained causes without credential-shaped text."""
    return redact_sensitive_text("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


def mask_identifier(value: object) -> str:
    """Fully mask a known identifier, including aliases and short numeric IDs."""
    return _REDACTED
