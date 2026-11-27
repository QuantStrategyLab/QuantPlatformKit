"""Shared FUSE-3 external state-store readback contract and pure port (fail-closed)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Any

from quant_platform_kit.risk.fuse_readback import FuseReadbackRecord

DEFAULT_MAX_FUSE_STATE_BYTES = 262_144

_GCS_BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")

FuseReadbackGcsReader = Callable[[str, str], bytes]
_REGISTERED_GCS_READER: FuseReadbackGcsReader | None = None


def register_fuse_readback_gcs_reader(reader: FuseReadbackGcsReader | None) -> None:
    """Register or clear the process-level edge adapter used for ``gs://`` URIs."""
    global _REGISTERED_GCS_READER
    if reader is not None and not callable(reader):
        raise TypeError("gcs_reader must be callable or None")
    _REGISTERED_GCS_READER = reader


def get_fuse_readback_gcs_reader() -> FuseReadbackGcsReader | None:
    """Return the currently registered edge adapter for ``gs://`` URIs, if any."""
    return _REGISTERED_GCS_READER


@dataclass(frozen=True)
class FuseReadbackStoreResult:
    """Result of loading FUSE readback state from configured runtime environment."""

    configured: bool
    record: FuseReadbackRecord | None
    source_kind: str | None = None
    error_code: str | None = None


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("FUSE_STATE_DUPLICATE_JSON_KEY")
        out[key] = value
    return out


def _clean_optional_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def parse_fuse_readback_json(
    raw: bytes | str,
    *,
    max_bytes: int = DEFAULT_MAX_FUSE_STATE_BYTES,
    expected_spec_digest: str | None = None,
    expected_calendar_version: str | None = None,
) -> FuseReadbackRecord:
    """Parse and validate FUSE readback JSON payload with strict bounds (fail-closed)."""
    if max_bytes <= 0:
        raise ValueError("FUSE_STATE_INVALID_MAX_BYTES")
    if isinstance(raw, bytes):
        if len(raw) > max_bytes:
            raise ValueError("FUSE_STATE_TOO_LARGE")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("FUSE_STATE_INVALID_UTF8") from exc
    elif isinstance(raw, str):
        encoded = raw.encode("utf-8")
        if len(encoded) > max_bytes:
            raise ValueError("FUSE_STATE_TOO_LARGE")
        text = raw
    else:
        raise ValueError("FUSE_STATE_INVALID_PAYLOAD_TYPE")

    try:
        parsed = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except ValueError as exc:
        if str(exc) == "FUSE_STATE_DUPLICATE_JSON_KEY":
            raise
        raise ValueError("FUSE_STATE_INVALID_JSON") from exc

    if not isinstance(parsed, dict):
        raise ValueError("FUSE_STATE_JSON_NOT_OBJECT")

    record = FuseReadbackRecord.from_mapping(parsed)

    exp_cal = _clean_optional_str(expected_calendar_version)
    if exp_cal is not None and record.calendar_version != exp_cal:
        raise ValueError("FUSE_STATE_CALENDAR_VERSION_MISMATCH")

    exp_digest = _clean_optional_str(expected_spec_digest)
    if exp_digest is not None and record.spec_digest != exp_digest:
        raise ValueError("FUSE_STATE_SPEC_DIGEST_MISMATCH")

    return record


def _parse_gcs_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError("FUSE_STATE_URI_INVALID_SCHEME")
    remainder = uri[5:]
    if "?" in remainder or "#" in remainder:
        raise ValueError("FUSE_STATE_URI_INVALID")
    bucket, sep, obj = remainder.partition("/")
    if not sep or not _GCS_BUCKET_RE.fullmatch(bucket) or not obj:
        raise ValueError("FUSE_STATE_URI_INVALID")
    segments = obj.split("/")
    if any(seg in ("", ".", "..") for seg in segments):
        raise ValueError("FUSE_STATE_URI_INVALID_PATH")
    return bucket, obj


def _read_local_file_bounded(path_str: str, max_bytes: int) -> bytes:
    path = Path(path_str)
    if not path.is_file():
        raise ValueError("FUSE_STATE_FILE_MISSING")
    try:
        with path.open("rb") as handle:
            raw = handle.read(max_bytes + 1)
    except OSError as exc:
        raise ValueError("FUSE_STATE_FILE_UNREADABLE") from exc
    if len(raw) > max_bytes:
        raise ValueError("FUSE_STATE_TOO_LARGE")
    return raw


def load_fuse_readback_from_env(
    *,
    environ: Mapping[str, str] | None = None,
    gcs_reader: FuseReadbackGcsReader | None = None,
    max_bytes: int = DEFAULT_MAX_FUSE_STATE_BYTES,
) -> FuseReadbackStoreResult:
    """Load and validate external FUSE state snapshot configured in ``environ``.

    Configuration keys:
    - ``FUSE_READBACK_STATE_PATH``: bounded local JSON file path
    - ``FUSE_READBACK_STATE_URI``: ``gs://<bucket>/<object>`` JSON object URI
    - ``FUSE_READBACK_EXPECTED_SPEC_DIGEST``: optional pinned ``spec_digest``
    - ``FUSE_READBACK_EXPECTED_CALENDAR_VERSION``: optional pinned ``calendar_version``

    Cloud ``gs://`` reads delegate strictly to the injected ``gcs_reader`` or
    the process-registered edge adapter port (never importing cloud SDKs here).
    Setting both path and URI, omitting a GCS port for ``gs://``, or any
    unreadable/malformed/oversized/mismatched payload returns
    ``configured=True, record=None`` with a fixed ``error_code`` (fail closed).
    """
    env = os.environ if environ is None else environ
    state_path = _clean_optional_str(env.get("FUSE_READBACK_STATE_PATH"))
    state_uri = _clean_optional_str(env.get("FUSE_READBACK_STATE_URI"))
    expected_spec_digest = _clean_optional_str(env.get("FUSE_READBACK_EXPECTED_SPEC_DIGEST"))
    expected_calendar_version = _clean_optional_str(env.get("FUSE_READBACK_EXPECTED_CALENDAR_VERSION"))

    if state_path is None and state_uri is None:
        return FuseReadbackStoreResult(configured=False, record=None)

    if state_path is not None and state_uri is not None:
        return FuseReadbackStoreResult(
            configured=True,
            record=None,
            error_code="FUSE_STATE_SOURCE_AMBIGUOUS",
        )

    source_kind = "file" if state_path is not None else "gcs"
    try:
        if state_path is not None:
            raw = _read_local_file_bounded(state_path, max_bytes)
        else:
            assert state_uri is not None
            bucket, obj = _parse_gcs_uri(state_uri)
            active_reader = _REGISTERED_GCS_READER if gcs_reader is None else gcs_reader
            if active_reader is None:
                raise ValueError("FUSE_STATE_GCS_READER_UNCONFIGURED")
            raw = active_reader(bucket, obj)
            if not isinstance(raw, (bytes, bytearray)):
                raise ValueError("FUSE_STATE_INVALID_PAYLOAD_TYPE")
            raw = bytes(raw)

        record = parse_fuse_readback_json(
            raw,
            max_bytes=max_bytes,
            expected_spec_digest=expected_spec_digest,
            expected_calendar_version=expected_calendar_version,
        )
        return FuseReadbackStoreResult(
            configured=True,
            record=record,
            source_kind=source_kind,
            error_code=None,
        )
    except ValueError as exc:
        code = str(exc) if str(exc).startswith("FUSE_") else "FUSE_STATE_INVALID"
        return FuseReadbackStoreResult(
            configured=True,
            record=None,
            source_kind=source_kind,
            error_code=code,
        )
    except Exception:
        return FuseReadbackStoreResult(
            configured=True,
            record=None,
            source_kind=source_kind,
            error_code="FUSE_STATE_READ_FAILED",
        )


__all__ = [
    "DEFAULT_MAX_FUSE_STATE_BYTES",
    "FuseReadbackGcsReader",
    "FuseReadbackStoreResult",
    "get_fuse_readback_gcs_reader",
    "load_fuse_readback_from_env",
    "parse_fuse_readback_json",
    "register_fuse_readback_gcs_reader",
]
