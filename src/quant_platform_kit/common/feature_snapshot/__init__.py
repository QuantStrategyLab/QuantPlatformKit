"""Shared feature snapshot loading helpers."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from ..strategies import normalize_profile_name

from .types import (
    DEFAULT_ARTIFACT_CACHE_DIR,
    DEFAULT_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR,
    DEFAULT_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS,
    DEFAULT_FEATURE_SNAPSHOT_FALLBACK_MODE,
    DEFAULT_MAX_SNAPSHOT_MONTH_LAG,
    DEFAULT_SNAPSHOT_DATE_COLUMNS,
    DEFAULT_SNAPSHOT_MANIFEST_SUFFIX,
    FEATURE_SNAPSHOT_FALLBACK_MODE_LAST_VALID,
    FEATURE_SNAPSHOT_FALLBACK_MODE_NONE,
    FeatureSnapshotGuardResult,
    _CURRENT_GENERATION_DIGEST_RE,
    _CURRENT_GENERATION_ID_RE,
    _CURRENT_GENERATION_OBJECT_NAMES,
    _CURRENT_GENERATION_POINTER_FILENAME,
    _CURRENT_GENERATION_SCHEMA,
    _MANIFEST_DIAGNOSTIC_FIELDS,
    _build_guard_metadata,
    _json_safe_value,
    _month_lag,
    _normalize_config_name_label,
    _normalize_contract_version_label,
    _normalize_strategy_profile_label,
    _normalize_timestamp,
    _path_from_metadata,
    normalize_feature_snapshot_fallback_mode,
)
from .io import (
    _cache_path_for_remote_artifact,
    _download_gcs_object,
    _download_remote_object,
    _is_cloud_uri,
    _is_gcs_uri,
    _load_snapshot_frame,
    _materialize_artifact_path,
    _parse_cloud_uri,
    _parse_gcs_uri,
    _resolve_manifest_path,
    _resolve_manifest_reference,
    _sha256_file,
)
from .guard import (
    _is_current_generation_pointer_reference,
    _is_safe_generation_basename,
    _load_current_generation_feature_snapshot_guarded,
    _load_feature_snapshot_guarded_without_fallback,
    _load_manifest_payload,
    _load_optional_manifest_payload,
    _manifest_diagnostic_metadata,
    _normalize_manifest_payload,
    _read_current_generation_pointer,
    _reject_duplicate_json_keys,
    _reject_nonfinite_json_constant,
    _validate_current_generation_pointer_uri,
    load_feature_snapshot,
    load_feature_snapshot_guarded,
)
from .fallback import (
    _feature_snapshot_fallback_context,
    _feature_snapshot_fallback_failure,
    _feature_snapshot_fallback_stale_reason,
    _load_feature_snapshot_last_valid,
    _write_feature_snapshot_last_valid,
)
