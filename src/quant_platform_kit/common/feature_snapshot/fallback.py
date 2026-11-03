"""Last-valid feature snapshot persistence and fallback loading."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from .guard import _load_feature_snapshot_guarded_without_fallback
from .io import _resolve_manifest_reference, _sha256_file
from .types import (
    DEFAULT_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR,
    DEFAULT_MAX_SNAPSHOT_MONTH_LAG,
    DEFAULT_SNAPSHOT_DATE_COLUMNS,
    FEATURE_SNAPSHOT_FALLBACK_MODE_LAST_VALID,
    FeatureSnapshotGuardResult,
    _json_safe_value,
    _path_from_metadata,
)


def _feature_snapshot_fallback_context(
    *,
    path: str,
    manifest_path: str | None,
    expected_strategy_profile: str | None,
    expected_config_name: str | None,
    expected_contract_version: str | None,
    required_columns: Iterable[str] | None,
    snapshot_date_columns: Iterable[str],
    cache_dir: str | Path | None,
) -> dict[str, Any]:
    raw_path = str(path or "").strip()
    raw_manifest = str(manifest_path or "").strip()
    payload = {
        "path": raw_path,
        "manifest_path": raw_manifest,
        "expected_strategy_profile": str(expected_strategy_profile or "").strip(),
        "expected_config_name": str(expected_config_name or "").strip(),
        "expected_contract_version": str(expected_contract_version or "").strip(),
        "required_columns": tuple(str(column) for column in (required_columns or ())),
        "snapshot_date_columns": tuple(str(column) for column in snapshot_date_columns),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()[:24]
    cache_root = Path(cache_dir or DEFAULT_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR) / digest
    snapshot_suffix = Path(raw_path).suffix or ".snapshot"
    return {
        "cache_root": cache_root,
        "record_path": cache_root / "record.json",
        "snapshot_path": cache_root / f"snapshot{snapshot_suffix}",
        "manifest_path": cache_root / "snapshot.manifest.json",
        "source_path": raw_path,
        "source_manifest_path": raw_manifest or _resolve_manifest_reference(raw_path, manifest_path),
        "cache_key_payload": payload,
    }


def _write_feature_snapshot_last_valid(
    fallback_context: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> None:
    source_snapshot = _path_from_metadata(
        metadata.get("snapshot_local_path") or metadata.get("snapshot_path")
    )
    if source_snapshot is None or not source_snapshot.exists():
        return

    cache_root = Path(fallback_context["cache_root"])
    snapshot_path = Path(fallback_context["snapshot_path"])
    manifest_path = Path(fallback_context["manifest_path"])
    record_path = Path(fallback_context["record_path"])
    cache_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_snapshot, snapshot_path)

    source_manifest = _path_from_metadata(
        metadata.get("snapshot_manifest_local_path") or metadata.get("snapshot_manifest_path")
    )
    manifest_copied = False
    if source_manifest is not None and source_manifest.exists():
        shutil.copy2(source_manifest, manifest_path)
        manifest_copied = True

    record = {
        "schema_version": "feature_snapshot_last_valid.v1",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "source_path": fallback_context["source_path"],
        "source_manifest_path": fallback_context["source_manifest_path"],
        "snapshot_path": str(snapshot_path),
        "manifest_path": str(manifest_path) if manifest_copied else None,
        "snapshot_as_of": _json_safe_value(metadata.get("snapshot_as_of")),
        "snapshot_sha256": _sha256_file(snapshot_path),
        "manifest_sha256": _sha256_file(manifest_path) if manifest_copied else None,
        "cache_key_payload": fallback_context["cache_key_payload"],
    }
    record_path.write_text(json.dumps(record, sort_keys=True, indent=2), encoding="utf-8")


def _load_feature_snapshot_last_valid(
    fallback_context: Mapping[str, Any],
    *,
    run_as_of,
    required_columns: Iterable[str] | None,
    snapshot_date_columns: Iterable[str],
    max_snapshot_month_lag: int,
    require_manifest: bool,
    expected_strategy_profile: str | None,
    expected_config_name: str | None,
    expected_config_path: str | None,
    expected_contract_version: str | None,
    failed_metadata: Mapping[str, Any],
    max_stale_days: int | None,
) -> FeatureSnapshotGuardResult | None:
    record_path = Path(fallback_context["record_path"])
    snapshot_path = Path(fallback_context["snapshot_path"])
    manifest_path = Path(fallback_context["manifest_path"])
    if not record_path.exists() or not snapshot_path.exists():
        return _feature_snapshot_fallback_failure(
            failed_metadata,
            reason="last_valid_missing",
            fallback_context=fallback_context,
        )
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _feature_snapshot_fallback_failure(
            failed_metadata,
            reason=f"last_valid_record_invalid:{type(exc).__name__}:{exc}",
            fallback_context=fallback_context,
        )
    if not isinstance(record, Mapping):
        return _feature_snapshot_fallback_failure(
            failed_metadata,
            reason="last_valid_record_invalid:not_mapping",
            fallback_context=fallback_context,
        )
    stale_reason = _feature_snapshot_fallback_stale_reason(record, max_stale_days=max_stale_days)
    if stale_reason:
        return _feature_snapshot_fallback_failure(
            failed_metadata,
            reason=stale_reason,
            fallback_context=fallback_context,
            record=record,
        )
    if require_manifest and not manifest_path.exists():
        return _feature_snapshot_fallback_failure(
            failed_metadata,
            reason="last_valid_manifest_missing",
            fallback_context=fallback_context,
            record=record,
        )

    fallback_result = _load_feature_snapshot_guarded_without_fallback(
        str(snapshot_path),
        run_as_of=run_as_of,
        required_columns=required_columns,
        snapshot_date_columns=snapshot_date_columns,
        max_snapshot_month_lag=max_snapshot_month_lag,
        manifest_path=str(manifest_path) if manifest_path.exists() else None,
        require_manifest=require_manifest,
        expected_strategy_profile=expected_strategy_profile,
        expected_config_name=expected_config_name,
        expected_config_path=expected_config_path,
        expected_contract_version=expected_contract_version,
    )
    metadata = dict(fallback_result.metadata)
    if metadata.get("snapshot_guard_decision") != "proceed":
        return _feature_snapshot_fallback_failure(
            failed_metadata,
            reason=str(metadata.get("fail_reason") or metadata.get("no_op_reason") or "last_valid_guard_failed"),
            fallback_context=fallback_context,
            record=record,
        )

    metadata.update(
        {
            "feature_snapshot_path": fallback_context["source_path"],
            "snapshot_path": fallback_context["source_path"],
            "snapshot_manifest_path": fallback_context["source_manifest_path"],
            "snapshot_local_path": str(snapshot_path),
            "snapshot_manifest_local_path": str(manifest_path) if manifest_path.exists() else None,
            "artifact_fallback_used": True,
            "artifact_fallback_mode": FEATURE_SNAPSHOT_FALLBACK_MODE_LAST_VALID,
            "artifact_fallback_reason": failed_metadata.get("fail_reason")
            or failed_metadata.get("no_op_reason"),
            "artifact_fallback_saved_at": record.get("saved_at"),
            "artifact_fallback_cache_dir": str(fallback_context["cache_root"]),
            "artifact_fallback_snapshot_path": str(snapshot_path),
            "artifact_fallback_manifest_path": str(manifest_path) if manifest_path.exists() else None,
        }
    )
    return FeatureSnapshotGuardResult(frame=fallback_result.frame, metadata=metadata)


def _feature_snapshot_fallback_failure(
    failed_metadata: Mapping[str, Any],
    *,
    reason: str,
    fallback_context: Mapping[str, Any],
    record: Mapping[str, Any] | None = None,
) -> FeatureSnapshotGuardResult:
    metadata = dict(failed_metadata)
    metadata.update(
        {
            "artifact_fallback_used": False,
            "artifact_fallback_mode": FEATURE_SNAPSHOT_FALLBACK_MODE_LAST_VALID,
            "artifact_fallback_fail_reason": reason,
            "artifact_fallback_cache_dir": str(fallback_context["cache_root"]),
        }
    )
    if record is not None:
        metadata["artifact_fallback_saved_at"] = record.get("saved_at")
    return FeatureSnapshotGuardResult(frame=None, metadata=metadata)


def _feature_snapshot_fallback_stale_reason(
    record: Mapping[str, Any],
    *,
    max_stale_days: int | None,
) -> str | None:
    if max_stale_days is None:
        return None
    if int(max_stale_days) < 0:
        return "last_valid_max_stale_days_negative"
    saved_at = record.get("saved_at")
    try:
        saved_ts = pd.Timestamp(saved_at)
    except Exception:
        return "last_valid_saved_at_invalid"
    if pd.isna(saved_ts):
        return "last_valid_saved_at_invalid"
    if saved_ts.tzinfo is None:
        saved_ts = saved_ts.tz_localize(timezone.utc)
    now_ts = pd.Timestamp(datetime.now(timezone.utc))
    if saved_ts < now_ts - pd.Timedelta(days=int(max_stale_days)):
        return "last_valid_stale:saved_at=" + str(saved_at)
    return None
