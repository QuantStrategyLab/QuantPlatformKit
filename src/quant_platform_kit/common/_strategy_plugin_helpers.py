"""Internal shared helpers for strategy plugin loading, consumption, and alerts."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Callable, Sequence

from quant_platform_kit.common.strategy_plugin_artifacts import (
    cache_path_for_remote_artifact,
    download_remote_object,
    materialize_local_or_remote_artifact,
    parse_cloud_uri,
)

DEFAULT_PLUGIN_ARTIFACT_CACHE_DIR = Path(tempfile.gettempdir()) / "quant_strategy_plugin_artifacts"

def _compact_strategy_plugin_error(error: object, *, max_chars: int = 240) -> str:
    text = " ".join(str(error or "").split())
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _translator_uses_zh(translator: Callable[..., str] | None) -> bool:
    if translator is None:
        return False
    for key in ("strategy_plugin_alert_locale", "no_trades"):
        try:
            sample = str(translator(key))
        except Exception:
            continue
        if sample.strip().lower().startswith("zh"):
            return True
        if any("\u4e00" <= char <= "\u9fff" for char in sample):
            return True
    return False


def _optional_key_part(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sanitize_key_part(value: Any) -> str:
    text = str(value or "").strip().lower()
    chars: list[str] = []
    previous_dash = False
    for char in text:
        if char.isalnum() or char in {"_", "."}:
            chars.append(char)
            previous_dash = False
        elif not previous_dash:
            chars.append("-")
            previous_dash = True
    sanitized = "".join(chars).strip("-._")
    return sanitized[:80] or "unknown"


def _materialize_artifact_path(reference: str, *, client_factory: Any = None) -> tuple[Path, dict[str, str | None]]:
    return materialize_local_or_remote_artifact(
        reference,
        cache_dir=DEFAULT_PLUGIN_ARTIFACT_CACHE_DIR,
        client_factory=client_factory,
    )


def _download_remote_object(uri: str, destination: Path, *, client_factory: Any = None) -> None:
    download_remote_object(uri, destination, client_factory=client_factory)


def _parse_cloud_uri(uri: str) -> tuple[str, str]:
    return parse_cloud_uri(uri)


def _cache_path_for_remote_artifact(reference: str) -> Path:
    return cache_path_for_remote_artifact(reference, cache_dir=DEFAULT_PLUGIN_ARTIFACT_CACHE_DIR)


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_strategy_plugin_field(value: str | None) -> str:
    return str(value or "").strip().lower() or "unknown"


def _translate(
    translator: Callable[..., str] | None,
    key: str,
    *,
    fallback: str,
    **kwargs: Any,
) -> str:
    if translator is None:
        return fallback.format(**kwargs)
    try:
        translated = translator(key, **kwargs)
    except TypeError:
        translated = translator(key)
    return translated if translated != key else fallback.format(**kwargs)


def _translate_first(
    translator: Callable[..., str] | None,
    keys: Sequence[str],
) -> str | None:
    if translator is None:
        return None
    for key in keys:
        translated = translator(key)
        if translated != key:
            text = str(translated).strip()
            if text:
                return text
    return None


def _required_string(value: Any, *, field_name: str) -> str:
    text = _optional_string(value)
    if text is None:
        raise ValueError(f"{field_name} is required")
    return text
