"""Credential-free notification data for reports and deferred delivery."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from ._redaction import _is_sensitive_key, redact_sensitive_text


def _freeze(value: Any) -> Any:
    if isinstance(value, str):
        if redact_sensitive_text(value) != value:
            raise ValueError("NotificationIntent must contain only non-credential data.")
        return value
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str) or _is_sensitive_key(key):
                raise ValueError("NotificationIntent metadata contains a credential-like key.")
            result[_freeze(key)] = _freeze(item)
        return MappingProxyType(result)
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise TypeError("NotificationIntent metadata must contain JSON-compatible data.")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class NotificationIntent:
    """Immutable non-credential data; use ``to_dict()`` for JSON serialization.

    Credential-like keys or text are rejected without echoing their contents.
    Metadata is copied and recursively frozen, preventing later secret insertion.
    """

    text: str
    run_id: str
    chat_ids: tuple[str, ...] = ()
    channel: str = "telegram"
    dry_run: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("text", "run_id", "channel"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise TypeError("NotificationIntent text, run_id and channel must be strings.")
            _freeze(value)
        if isinstance(self.chat_ids, str):
            raise TypeError("NotificationIntent chat_ids must be a sequence of strings.")
        chats = tuple(self.chat_ids)
        if any(not isinstance(chat, str) for chat in chats):
            raise TypeError("NotificationIntent chat_ids must contain strings.")
        object.__setattr__(self, "chat_ids", _freeze(chats))
        if not isinstance(self.dry_run, bool):
            raise TypeError("NotificationIntent dry_run must be a bool.")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("NotificationIntent metadata must be a mapping.")
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text, "run_id": self.run_id, "chat_ids": list(self.chat_ids),
            "channel": self.channel, "dry_run": self.dry_run, "metadata": _thaw(self.metadata),
        }
