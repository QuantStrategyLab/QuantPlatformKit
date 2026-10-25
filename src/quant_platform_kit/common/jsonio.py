"""Deterministic and strict JSON helpers shared across QuantStrategyLab packages.

These helpers centralize the canonical-serialization and strict-parsing
conventions that were previously copied into individual modules:

* canonical bytes: UTF-8, sorted keys, compact separators, no NaN/Infinity;
* strict parsing: duplicate object keys and non-finite constants are rejected;
* atomic writes: a temporary file in the destination directory, fsync, then
  ``os.replace`` so readers never observe a partially written document.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def canonical_json_bytes(payload: Any) -> bytes:
    """Serialize *payload* to deterministic UTF-8 JSON bytes."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_non_finite_constant(value: str) -> Any:
    raise ValueError(f"non-finite JSON constant: {value}")


def strict_json_loads(text: str) -> Any:
    """Parse *text*, rejecting duplicate object keys and NaN/Infinity values."""
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_non_finite_constant,
    )


def load_strict_json(path: str | Path) -> Any:
    """Read a UTF-8 JSON document from *path* using :func:`strict_json_loads`."""
    return strict_json_loads(Path(path).read_text(encoding="utf-8"))


def atomic_write_json(
    path: str | Path,
    payload: Any,
    *,
    indent: int | None = None,
    sort_keys: bool = True,
) -> Path:
    """Atomically write *payload* as UTF-8 JSON to *path*.

    Parent directories are created as needed.  The document is written to a
    temporary file in the same directory, fsynced, and moved into place with
    ``os.replace`` so the destination is either the previous complete document
    or the new one.
    """
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        payload,
        ensure_ascii=False,
        indent=indent,
        sort_keys=sort_keys,
        allow_nan=False,
    )
    descriptor, temporary_name = tempfile.mkstemp(
        dir=resolved.parent,
        prefix=f".{resolved.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, resolved)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return resolved


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with offset."""
    return datetime.now(timezone.utc).isoformat()


def sha256_hex(data: bytes) -> str:
    """Return the lowercase hexadecimal SHA-256 digest of *data*."""
    return hashlib.sha256(data).hexdigest()
