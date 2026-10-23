"""Feature snapshot types, constants and normalization helpers."""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from ..strategies import normalize_profile_name


DEFAULT_SNAPSHOT_DATE_COLUMNS = ("as_of", "snapshot_date")
DEFAULT_MAX_SNAPSHOT_MONTH_LAG = 1
DEFAULT_SNAPSHOT_MANIFEST_SUFFIX = ".manifest.json"
DEFAULT_ARTIFACT_CACHE_DIR = Path(tempfile.gettempdir()) / "quant_strategy_artifacts"
DEFAULT_FEATURE_SNAPSHOT_FALLBACK_MODE = "none"
FEATURE_SNAPSHOT_FALLBACK_MODE_NONE = "none"
FEATURE_SNAPSHOT_FALLBACK_MODE_LAST_VALID = "last_valid"
DEFAULT_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS = 3
DEFAULT_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR = (
    DEFAULT_ARTIFACT_CACHE_DIR / "last_valid_feature_snapshots"
)
_CURRENT_GENERATION_SCHEMA = "current_generation.v1"
_CURRENT_GENERATION_OBJECT_NAMES = ("snapshot", "manifest", "ranking", "release_summary")
_CURRENT_GENERATION_POINTER_FILENAME = "current_generation.json"
_CURRENT_GENERATION_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
_CURRENT_GENERATION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_MANIFEST_DIAGNOSTIC_FIELDS = (
    "price_as_of",
    "universe_as_of",
    "source_input_status",
    "source_input_fallback_used",
    "source_input_fallback_reason",
    "source_input_fallback_streak",
    "source_input_manifest_path",
    "source_refresh_run_id",
    "source_refresh_generated_at",
)


def _normalize_strategy_profile_label(value: object) -> str:
    return normalize_profile_name(str(value or "").strip())


def _normalize_contract_version_label(value: object) -> str:
    label = str(value or "").strip()
    if not label:
        return ""
    prefix, marker, suffix = label.partition(".feature_snapshot.")
    if not marker:
        return label
    return f"{_normalize_strategy_profile_label(prefix)}{marker}{suffix}"


def _normalize_config_name_label(value: object) -> str:
    return _normalize_strategy_profile_label(value)


@dataclass(frozen=True)
class FeatureSnapshotGuardResult:
    frame: pd.DataFrame | None
    metadata: dict[str, object]


def _normalize_timestamp(value) -> pd.Timestamp | None:
    if value is None or value == "":
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert(None)
    else:
        ts = ts.tz_localize(None)
    return ts.normalize()


def _month_lag(snapshot_as_of: pd.Timestamp, run_as_of: pd.Timestamp) -> int:
    return (run_as_of.year - snapshot_as_of.year) * 12 + (run_as_of.month - snapshot_as_of.month)


def _build_guard_metadata(
    *,
    snapshot_path: Path,
    decision: str,
    snapshot_format: str | None = None,
    snapshot_exists: bool,
    snapshot_as_of: pd.Timestamp | None = None,
    file_timestamp: str | None = None,
    age_days: int | None = None,
    no_op_reason: str | None = None,
    fail_reason: str | None = None,
    **extra,
) -> dict[str, object]:
    payload = {
        "feature_snapshot_path": str(snapshot_path),
        "snapshot_path": str(snapshot_path),
        "snapshot_format": snapshot_format,
        "snapshot_exists": bool(snapshot_exists),
        "snapshot_as_of": snapshot_as_of,
        "snapshot_file_timestamp": file_timestamp,
        "snapshot_age_days": age_days,
        "snapshot_guard_decision": decision,
        "no_op_reason": no_op_reason,
        "fail_reason": fail_reason,
    }
    payload.update(extra)
    return payload


def normalize_feature_snapshot_fallback_mode(value: object) -> str:
    mode = str(value or DEFAULT_FEATURE_SNAPSHOT_FALLBACK_MODE).strip().lower().replace("-", "_")
    aliases = {
        "": FEATURE_SNAPSHOT_FALLBACK_MODE_NONE,
        "off": FEATURE_SNAPSHOT_FALLBACK_MODE_NONE,
        "disabled": FEATURE_SNAPSHOT_FALLBACK_MODE_NONE,
        "false": FEATURE_SNAPSHOT_FALLBACK_MODE_NONE,
        "none": FEATURE_SNAPSHOT_FALLBACK_MODE_NONE,
        "last": FEATURE_SNAPSHOT_FALLBACK_MODE_LAST_VALID,
        "last_valid": FEATURE_SNAPSHOT_FALLBACK_MODE_LAST_VALID,
        "last_valid_snapshot": FEATURE_SNAPSHOT_FALLBACK_MODE_LAST_VALID,
    }
    normalized = aliases.get(mode, mode)
    if normalized not in {
        FEATURE_SNAPSHOT_FALLBACK_MODE_NONE,
        FEATURE_SNAPSHOT_FALLBACK_MODE_LAST_VALID,
    }:
        raise ValueError(
            "unsupported feature snapshot fallback mode "
            f"{value!r}; supported: none, last_valid"
        )
    return normalized


def _path_from_metadata(value: object) -> Path | None:
    text = str(value or "").strip()
    if not text or text.startswith("gs://"):
        return None
    return Path(text)


def _json_safe_value(value: object) -> object:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
