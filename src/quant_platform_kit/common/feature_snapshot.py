"""Shared feature snapshot loading helpers."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd


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
    label = str(value or "").strip()
    if not label:
        return ""
    try:
        from us_equity_strategies.catalog import resolve_canonical_profile
    except Exception:
        return label
    try:
        return str(resolve_canonical_profile(label)).strip()
    except Exception:
        return label


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


def _load_snapshot_frame(snapshot_path: Path) -> pd.DataFrame:
    suffix = snapshot_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(snapshot_path)
    if suffix in {".json", ".jsonl"}:
        return pd.read_json(snapshot_path, orient="records", lines=suffix == ".jsonl")
    if suffix == ".parquet":
        return pd.read_parquet(snapshot_path)

    raise ValueError(
        "Unsupported feature snapshot format; expected .csv, .json, .jsonl, or .parquet"
    )


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


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _resolve_manifest_path(snapshot_path: Path, manifest_path: str | None) -> Path:
    raw_manifest = str(manifest_path or "").strip()
    if raw_manifest:
        return Path(raw_manifest)
    return Path(f"{snapshot_path}{DEFAULT_SNAPSHOT_MANIFEST_SUFFIX}")


def _is_cloud_uri(reference: str | None) -> bool:
    return str(reference or "").strip().startswith("gs://") or str(reference or "").strip().startswith("s3://")


# Backward-compatible alias
_is_gcs_uri = _is_cloud_uri


def _resolve_manifest_reference(snapshot_reference: str, manifest_path: str | None) -> str:
    raw_manifest = str(manifest_path or "").strip()
    if raw_manifest:
        return raw_manifest
    return f"{str(snapshot_reference).strip()}{DEFAULT_SNAPSHOT_MANIFEST_SUFFIX}"


def _parse_cloud_uri(uri: str) -> tuple[str, str]:
    raw_uri = str(uri or "").strip()
    if not raw_uri.startswith("gs://") and not raw_uri.startswith("s3://"):
        raise ValueError(f"Unsupported cloud storage URI: {raw_uri}")
    bucket_name, _, object_name = raw_uri[5:].partition("/")
    if not bucket_name or not object_name:
        raise ValueError(f"Invalid cloud storage URI: {raw_uri}")
    return bucket_name, object_name


def _download_remote_object(uri: str, destination: Path) -> None:
    from quant_platform_kit.cloud import get_object_store

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(get_object_store().read_bytes(uri))


# Backward-compatible aliases
_parse_gcs_uri = _parse_cloud_uri
_download_gcs_object = _download_remote_object


def _cache_path_for_remote_artifact(reference: str) -> Path:
    raw_reference = str(reference or "").strip()
    digest = hashlib.sha256(raw_reference.encode("utf-8")).hexdigest()[:16]
    leaf_name = Path(raw_reference).name or "artifact"
    return DEFAULT_ARTIFACT_CACHE_DIR / digest / leaf_name


def _materialize_artifact_path(reference: str) -> tuple[Path, dict[str, object]]:
    raw_reference = str(reference or "").strip()
    if not raw_reference:
        raise ValueError("artifact reference is required")

    if not _is_cloud_uri(raw_reference):
        return Path(raw_reference), {"source_uri": None, "local_path": raw_reference}

    local_path = _cache_path_for_remote_artifact(raw_reference)
    _download_gcs_object(raw_reference, local_path)
    return local_path, {"source_uri": raw_reference, "local_path": str(local_path)}


def _normalize_manifest_payload(payload: dict[str, object]) -> dict[str, object]:
    normalized = dict(payload)
    if "snapshot_as_of" in normalized:
        normalized["snapshot_as_of"] = _normalize_timestamp(normalized.get("snapshot_as_of"))
    return normalized


def _load_manifest_payload(manifest_path: Path) -> dict[str, object]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("snapshot manifest must be a JSON object")
    return _normalize_manifest_payload(payload)


def _manifest_diagnostic_metadata(payload: dict[str, object] | None) -> dict[str, object]:
    if not payload:
        return {}
    return {
        f"snapshot_manifest_{field}": payload.get(field)
        for field in _MANIFEST_DIAGNOSTIC_FIELDS
        if payload.get(field) not in (None, "")
    }


def _load_optional_manifest_payload(manifest_path: Path) -> dict[str, object] | None:
    if not manifest_path.exists():
        return None
    try:
        return _load_manifest_payload(manifest_path)
    except Exception:
        return None


def load_feature_snapshot(path: str) -> pd.DataFrame:
    raw_path = str(path or "").strip()
    if not raw_path:
        raise EnvironmentError("Feature snapshot path is required")
    try:
        snapshot_path, _ = _materialize_artifact_path(raw_path)
    except Exception as exc:
        raise FileNotFoundError(
            f"Feature snapshot unavailable: {raw_path} ({type(exc).__name__}: {exc})"
        ) from exc
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Feature snapshot not found: {snapshot_path}")
    return _load_snapshot_frame(snapshot_path)


def load_feature_snapshot_guarded(
    path: str,
    *,
    run_as_of,
    required_columns: Iterable[str] | None = None,
    snapshot_date_columns: Iterable[str] = DEFAULT_SNAPSHOT_DATE_COLUMNS,
    max_snapshot_month_lag: int = DEFAULT_MAX_SNAPSHOT_MONTH_LAG,
    manifest_path: str | None = None,
    require_manifest: bool = False,
    expected_strategy_profile: str | None = None,
    expected_config_name: str | None = None,
    expected_config_path: str | None = None,
    expected_contract_version: str | None = None,
    fallback_mode: str | None = DEFAULT_FEATURE_SNAPSHOT_FALLBACK_MODE,
    fallback_cache_dir: str | Path | None = None,
    fallback_max_stale_days: int | None = DEFAULT_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS,
) -> FeatureSnapshotGuardResult:
    """Load a guarded snapshot, optionally falling back to the last valid artifact."""

    fallback_context = _feature_snapshot_fallback_context(
        path=path,
        manifest_path=manifest_path,
        expected_strategy_profile=expected_strategy_profile,
        expected_config_name=expected_config_name,
        expected_contract_version=expected_contract_version,
        required_columns=required_columns,
        snapshot_date_columns=snapshot_date_columns,
        cache_dir=fallback_cache_dir,
    )
    result = _load_feature_snapshot_guarded_without_fallback(
        path,
        run_as_of=run_as_of,
        required_columns=required_columns,
        snapshot_date_columns=snapshot_date_columns,
        max_snapshot_month_lag=max_snapshot_month_lag,
        manifest_path=manifest_path,
        require_manifest=require_manifest,
        expected_strategy_profile=expected_strategy_profile,
        expected_config_name=expected_config_name,
        expected_config_path=expected_config_path,
        expected_contract_version=expected_contract_version,
    )
    normalized_fallback_mode = normalize_feature_snapshot_fallback_mode(fallback_mode)
    if result.metadata.get("snapshot_guard_decision") == "proceed":
        if normalized_fallback_mode == FEATURE_SNAPSHOT_FALLBACK_MODE_LAST_VALID:
            _write_feature_snapshot_last_valid(fallback_context, result.metadata)
        return result
    if normalized_fallback_mode != FEATURE_SNAPSHOT_FALLBACK_MODE_LAST_VALID:
        return result

    fallback_result = _load_feature_snapshot_last_valid(
        fallback_context,
        run_as_of=run_as_of,
        required_columns=required_columns,
        snapshot_date_columns=snapshot_date_columns,
        max_snapshot_month_lag=max_snapshot_month_lag,
        require_manifest=require_manifest,
        expected_strategy_profile=expected_strategy_profile,
        expected_config_name=expected_config_name,
        expected_config_path=expected_config_path,
        expected_contract_version=expected_contract_version,
        failed_metadata=result.metadata,
        max_stale_days=fallback_max_stale_days,
    )
    return fallback_result if fallback_result is not None else result


def _load_feature_snapshot_guarded_without_fallback(
    path: str,
    *,
    run_as_of,
    required_columns: Iterable[str] | None = None,
    snapshot_date_columns: Iterable[str] = DEFAULT_SNAPSHOT_DATE_COLUMNS,
    max_snapshot_month_lag: int = DEFAULT_MAX_SNAPSHOT_MONTH_LAG,
    manifest_path: str | None = None,
    require_manifest: bool = False,
    expected_strategy_profile: str | None = None,
    expected_config_name: str | None = None,
    expected_config_path: str | None = None,
    expected_contract_version: str | None = None,
) -> FeatureSnapshotGuardResult:
    raw_path = str(path or "").strip()
    if not raw_path:
        snapshot_path = Path("<missing>")
        return FeatureSnapshotGuardResult(
            frame=None,
            metadata=_build_guard_metadata(
                snapshot_path=snapshot_path,
                decision="fail_closed",
                snapshot_exists=False,
                fail_reason="feature_snapshot_path_missing",
            ),
        )

    manifest_reference = _resolve_manifest_reference(raw_path, manifest_path)
    if _is_cloud_uri(raw_path) or _is_cloud_uri(manifest_reference):
        try:
            local_snapshot_path, snapshot_artifact_metadata = _materialize_artifact_path(raw_path)
        except Exception as exc:
            return FeatureSnapshotGuardResult(
                frame=None,
                metadata=_build_guard_metadata(
                    snapshot_path=raw_path,
                    decision="fail_closed",
                    snapshot_exists=False,
                    snapshot_source_uri=raw_path if _is_cloud_uri(raw_path) else None,
                    fail_reason=f"feature_snapshot_download_failed:{type(exc).__name__}:{exc}",
                ),
            )

        local_manifest_path = None
        manifest_artifact_metadata = {
            "source_uri": manifest_reference if _is_cloud_uri(manifest_reference) else None,
            "local_path": manifest_reference,
        }
        manifest_download_error = None
        try:
            local_manifest_path, manifest_artifact_metadata = _materialize_artifact_path(
                manifest_reference
            )
        except Exception as exc:
            manifest_download_error = f"{type(exc).__name__}:{exc}"
            if require_manifest:
                return FeatureSnapshotGuardResult(
                    frame=None,
                    metadata=_build_guard_metadata(
                        snapshot_path=raw_path,
                        decision="fail_closed",
                        snapshot_exists=True,
                        snapshot_source_uri=snapshot_artifact_metadata.get("source_uri"),
                        snapshot_local_path=snapshot_artifact_metadata.get("local_path"),
                        snapshot_manifest_path=manifest_reference,
                        snapshot_manifest_exists=False,
                        snapshot_manifest_source_uri=manifest_artifact_metadata.get("source_uri"),
                        snapshot_manifest_download_error=manifest_download_error,
                        fail_reason=f"feature_snapshot_manifest_download_failed:{manifest_download_error}",
                    ),
                )

        result = _load_feature_snapshot_guarded_without_fallback(
            str(local_snapshot_path),
            run_as_of=run_as_of,
            required_columns=required_columns,
            snapshot_date_columns=snapshot_date_columns,
            max_snapshot_month_lag=max_snapshot_month_lag,
            manifest_path=str(local_manifest_path) if local_manifest_path is not None else None,
            require_manifest=require_manifest,
            expected_strategy_profile=expected_strategy_profile,
            expected_config_name=expected_config_name,
            expected_config_path=expected_config_path,
            expected_contract_version=expected_contract_version,
        )
        metadata = dict(result.metadata)
        metadata["feature_snapshot_path"] = raw_path
        metadata["snapshot_path"] = raw_path
        metadata["snapshot_source_uri"] = snapshot_artifact_metadata.get("source_uri")
        metadata["snapshot_local_path"] = snapshot_artifact_metadata.get("local_path")
        metadata["snapshot_manifest_path"] = manifest_reference
        metadata["snapshot_manifest_source_uri"] = manifest_artifact_metadata.get("source_uri")
        metadata["snapshot_manifest_local_path"] = manifest_artifact_metadata.get("local_path")
        if manifest_download_error is not None:
            metadata["snapshot_manifest_download_error"] = manifest_download_error
            metadata["snapshot_manifest_exists"] = False
        return FeatureSnapshotGuardResult(frame=result.frame, metadata=metadata)

    snapshot_path = Path(raw_path)
    manifest_file = _resolve_manifest_path(snapshot_path, manifest_path)
    manifest_exists = manifest_file.exists()
    file_timestamp = None
    if snapshot_path.exists():
        stat = snapshot_path.stat()
        file_timestamp = pd.Timestamp(stat.st_mtime, unit="s", tz=timezone.utc).isoformat()
    manifest_file_timestamp = None
    if manifest_exists:
        manifest_stat = manifest_file.stat()
        manifest_file_timestamp = pd.Timestamp(
            manifest_stat.st_mtime,
            unit="s",
            tz=timezone.utc,
        ).isoformat()

    if not snapshot_path.exists():
        return FeatureSnapshotGuardResult(
            frame=None,
            metadata=_build_guard_metadata(
                snapshot_path=snapshot_path,
                decision="fail_closed",
                snapshot_exists=False,
                snapshot_manifest_path=str(manifest_file),
                snapshot_manifest_exists=False,
                fail_reason=f"feature_snapshot_missing:{snapshot_path}",
            ),
        )

    try:
        frame = _load_snapshot_frame(snapshot_path)
    except Exception as exc:  # pragma: no cover - exercised in tests through ValueError path
        return FeatureSnapshotGuardResult(
            frame=None,
            metadata=_build_guard_metadata(
                snapshot_path=snapshot_path,
                decision="fail_closed",
                snapshot_format=snapshot_path.suffix.lower() or None,
                snapshot_exists=True,
                file_timestamp=file_timestamp,
                snapshot_manifest_path=str(manifest_file),
                snapshot_manifest_exists=manifest_file.exists(),
                snapshot_manifest_file_timestamp=manifest_file_timestamp,
                fail_reason=f"feature_snapshot_parse_failed:{type(exc).__name__}:{exc}",
            ),
        )

    if frame.empty:
        return FeatureSnapshotGuardResult(
            frame=None,
            metadata=_build_guard_metadata(
                snapshot_path=snapshot_path,
                decision="fail_closed",
                snapshot_format=snapshot_path.suffix.lower() or None,
                snapshot_exists=True,
                file_timestamp=file_timestamp,
                snapshot_manifest_path=str(manifest_file),
                snapshot_manifest_exists=manifest_file.exists(),
                snapshot_manifest_file_timestamp=manifest_file_timestamp,
                fail_reason="feature_snapshot_empty",
            ),
        )

    required = {str(column) for column in (required_columns or ()) if str(column).strip()}
    missing_columns = required - set(frame.columns)
    if missing_columns:
        missing_text = ",".join(sorted(missing_columns))
        return FeatureSnapshotGuardResult(
            frame=None,
            metadata=_build_guard_metadata(
                snapshot_path=snapshot_path,
                decision="fail_closed",
                snapshot_format=snapshot_path.suffix.lower() or None,
                snapshot_exists=True,
                file_timestamp=file_timestamp,
                snapshot_manifest_path=str(manifest_file),
                snapshot_manifest_exists=manifest_file.exists(),
                snapshot_manifest_file_timestamp=manifest_file_timestamp,
                fail_reason=f"feature_snapshot_missing_columns:{missing_text}",
            ),
        )

    date_columns = tuple(str(column) for column in snapshot_date_columns if str(column).strip())
    selected_date_column = next((column for column in date_columns if column in frame.columns), None)
    if selected_date_column is None:
        return FeatureSnapshotGuardResult(
            frame=None,
            metadata=_build_guard_metadata(
                snapshot_path=snapshot_path,
                decision="fail_closed",
                snapshot_format=snapshot_path.suffix.lower() or None,
                snapshot_exists=True,
                file_timestamp=file_timestamp,
                snapshot_manifest_path=str(manifest_file),
                snapshot_manifest_exists=manifest_file.exists(),
                snapshot_manifest_file_timestamp=manifest_file_timestamp,
                fail_reason=f"feature_snapshot_missing_date_column:candidates={','.join(date_columns)}",
            ),
        )

    snapshot_dates = pd.to_datetime(frame[selected_date_column], errors="coerce", utc=False)
    if getattr(snapshot_dates.dt, "tz", None) is not None:
        snapshot_dates = snapshot_dates.dt.tz_localize(None)
    snapshot_dates = snapshot_dates.dt.normalize()
    if snapshot_dates.notna().sum() == 0:
        return FeatureSnapshotGuardResult(
            frame=None,
            metadata=_build_guard_metadata(
                snapshot_path=snapshot_path,
                decision="fail_closed",
                snapshot_format=snapshot_path.suffix.lower() or None,
                snapshot_exists=True,
                file_timestamp=file_timestamp,
                snapshot_manifest_path=str(manifest_file),
                snapshot_manifest_exists=manifest_file.exists(),
                snapshot_manifest_file_timestamp=manifest_file_timestamp,
                fail_reason=f"feature_snapshot_invalid_date_column:{selected_date_column}",
            ),
        )

    snapshot_as_of = pd.Timestamp(snapshot_dates.max()).normalize()
    run_date = _normalize_timestamp(run_as_of)
    if run_date is None:
        raise ValueError("run_as_of is required for guarded feature snapshot loading")

    manifest_payload_for_diagnostics = _load_optional_manifest_payload(manifest_file)
    age_days = int((run_date - snapshot_as_of).days)
    if age_days < 0:
        return FeatureSnapshotGuardResult(
            frame=None,
            metadata=_build_guard_metadata(
                snapshot_path=snapshot_path,
                decision="fail_closed",
                snapshot_format=snapshot_path.suffix.lower() or None,
                snapshot_exists=True,
                snapshot_as_of=snapshot_as_of,
                file_timestamp=file_timestamp,
                age_days=age_days,
                snapshot_manifest_path=str(manifest_file),
                snapshot_manifest_exists=manifest_exists,
                snapshot_manifest_file_timestamp=manifest_file_timestamp,
                fail_reason=f"feature_snapshot_future_as_of:{snapshot_as_of.date()}",
                **_manifest_diagnostic_metadata(manifest_payload_for_diagnostics),
            ),
        )

    if _month_lag(snapshot_as_of, run_date) > int(max_snapshot_month_lag):
        return FeatureSnapshotGuardResult(
            frame=None,
            metadata=_build_guard_metadata(
                snapshot_path=snapshot_path,
                decision="fail_closed",
                snapshot_format=snapshot_path.suffix.lower() or None,
                snapshot_exists=True,
                snapshot_as_of=snapshot_as_of,
                file_timestamp=file_timestamp,
                age_days=age_days,
                snapshot_manifest_path=str(manifest_file),
                snapshot_manifest_exists=manifest_exists,
                snapshot_manifest_file_timestamp=manifest_file_timestamp,
                fail_reason=(
                    "feature_snapshot_stale:"
                    f"snapshot_as_of={snapshot_as_of.date()} run_as_of={run_date.date()} "
                    f"max_month_lag={int(max_snapshot_month_lag)}"
                ),
                **_manifest_diagnostic_metadata(manifest_payload_for_diagnostics),
            ),
        )

    actual_snapshot_sha256 = None
    actual_config_sha256 = None
    manifest_payload: dict[str, object] | None = None
    if require_manifest:
        if not manifest_exists:
            return FeatureSnapshotGuardResult(
                frame=None,
                metadata=_build_guard_metadata(
                    snapshot_path=snapshot_path,
                    decision="fail_closed",
                    snapshot_format=snapshot_path.suffix.lower() or None,
                    snapshot_exists=True,
                    snapshot_as_of=snapshot_as_of,
                    file_timestamp=file_timestamp,
                    age_days=age_days,
                    snapshot_manifest_path=str(manifest_file),
                    snapshot_manifest_exists=False,
                    snapshot_manifest_file_timestamp=manifest_file_timestamp,
                    fail_reason=f"feature_snapshot_manifest_missing:{manifest_file}",
                ),
            )
        try:
            manifest_payload = _load_manifest_payload(manifest_file)
        except Exception as exc:
            return FeatureSnapshotGuardResult(
                frame=None,
                metadata=_build_guard_metadata(
                    snapshot_path=snapshot_path,
                    decision="fail_closed",
                    snapshot_format=snapshot_path.suffix.lower() or None,
                    snapshot_exists=True,
                    snapshot_as_of=snapshot_as_of,
                    file_timestamp=file_timestamp,
                    age_days=age_days,
                    snapshot_manifest_path=str(manifest_file),
                    snapshot_manifest_exists=True,
                    snapshot_manifest_file_timestamp=manifest_file_timestamp,
                    fail_reason=f"feature_snapshot_manifest_parse_failed:{type(exc).__name__}:{exc}",
                ),
            )

        required_manifest_fields = {
            "contract_version",
            "strategy_profile",
            "config_name",
            "snapshot_as_of",
            "snapshot_sha256",
            "config_sha256",
        }
        missing_manifest_fields = sorted(
            field for field in required_manifest_fields if not str(manifest_payload.get(field) or "").strip()
        )
        if missing_manifest_fields:
            missing_text = ",".join(missing_manifest_fields)
            return FeatureSnapshotGuardResult(
                frame=None,
                metadata=_build_guard_metadata(
                    snapshot_path=snapshot_path,
                    decision="fail_closed",
                    snapshot_format=snapshot_path.suffix.lower() or None,
                    snapshot_exists=True,
                    snapshot_as_of=snapshot_as_of,
                    file_timestamp=file_timestamp,
                    age_days=age_days,
                    snapshot_manifest_path=str(manifest_file),
                    snapshot_manifest_exists=True,
                    snapshot_manifest_file_timestamp=manifest_file_timestamp,
                    fail_reason=f"feature_snapshot_manifest_missing_fields:{missing_text}",
                ),
            )

        manifest_as_of = manifest_payload.get("snapshot_as_of")
        if manifest_as_of != snapshot_as_of:
            return FeatureSnapshotGuardResult(
                frame=None,
                metadata=_build_guard_metadata(
                    snapshot_path=snapshot_path,
                    decision="fail_closed",
                    snapshot_format=snapshot_path.suffix.lower() or None,
                    snapshot_exists=True,
                    snapshot_as_of=snapshot_as_of,
                    file_timestamp=file_timestamp,
                    age_days=age_days,
                    snapshot_manifest_path=str(manifest_file),
                    snapshot_manifest_exists=True,
                    snapshot_manifest_file_timestamp=manifest_file_timestamp,
                    snapshot_manifest_contract_version=manifest_payload.get("contract_version"),
                    snapshot_manifest_strategy_profile=manifest_payload.get("strategy_profile"),
                    snapshot_manifest_config_name=manifest_payload.get("config_name"),
                    fail_reason=(
                        "feature_snapshot_manifest_as_of_mismatch:"
                        f"manifest={manifest_as_of} snapshot={snapshot_as_of.date()}"
                    ),
                ),
            )

        if expected_strategy_profile and _normalize_strategy_profile_label(manifest_payload.get("strategy_profile")) != _normalize_strategy_profile_label(expected_strategy_profile):
            return FeatureSnapshotGuardResult(
                frame=None,
                metadata=_build_guard_metadata(
                    snapshot_path=snapshot_path,
                    decision="fail_closed",
                    snapshot_format=snapshot_path.suffix.lower() or None,
                    snapshot_exists=True,
                    snapshot_as_of=snapshot_as_of,
                    file_timestamp=file_timestamp,
                    age_days=age_days,
                    snapshot_manifest_path=str(manifest_file),
                    snapshot_manifest_exists=True,
                    snapshot_manifest_file_timestamp=manifest_file_timestamp,
                    snapshot_manifest_contract_version=manifest_payload.get("contract_version"),
                    snapshot_manifest_strategy_profile=manifest_payload.get("strategy_profile"),
                    snapshot_manifest_config_name=manifest_payload.get("config_name"),
                    fail_reason=(
                        "feature_snapshot_manifest_strategy_profile_mismatch:"
                        f"expected={expected_strategy_profile} actual={manifest_payload.get('strategy_profile')}"
                    ),
                ),
            )

        if expected_config_name and _normalize_config_name_label(manifest_payload.get("config_name")) != _normalize_config_name_label(expected_config_name):
            return FeatureSnapshotGuardResult(
                frame=None,
                metadata=_build_guard_metadata(
                    snapshot_path=snapshot_path,
                    decision="fail_closed",
                    snapshot_format=snapshot_path.suffix.lower() or None,
                    snapshot_exists=True,
                    snapshot_as_of=snapshot_as_of,
                    file_timestamp=file_timestamp,
                    age_days=age_days,
                    snapshot_manifest_path=str(manifest_file),
                    snapshot_manifest_exists=True,
                    snapshot_manifest_file_timestamp=manifest_file_timestamp,
                    snapshot_manifest_contract_version=manifest_payload.get("contract_version"),
                    snapshot_manifest_strategy_profile=manifest_payload.get("strategy_profile"),
                    snapshot_manifest_config_name=manifest_payload.get("config_name"),
                    fail_reason=(
                        "feature_snapshot_manifest_config_name_mismatch:"
                        f"expected={expected_config_name} actual={manifest_payload.get('config_name')}"
                    ),
                ),
            )

        if expected_contract_version and _normalize_contract_version_label(manifest_payload.get("contract_version")) != _normalize_contract_version_label(expected_contract_version):
            return FeatureSnapshotGuardResult(
                frame=None,
                metadata=_build_guard_metadata(
                    snapshot_path=snapshot_path,
                    decision="fail_closed",
                    snapshot_format=snapshot_path.suffix.lower() or None,
                    snapshot_exists=True,
                    snapshot_as_of=snapshot_as_of,
                    file_timestamp=file_timestamp,
                    age_days=age_days,
                    snapshot_manifest_path=str(manifest_file),
                    snapshot_manifest_exists=True,
                    snapshot_manifest_file_timestamp=manifest_file_timestamp,
                    snapshot_manifest_contract_version=manifest_payload.get("contract_version"),
                    snapshot_manifest_strategy_profile=manifest_payload.get("strategy_profile"),
                    snapshot_manifest_config_name=manifest_payload.get("config_name"),
                    fail_reason=(
                        "feature_snapshot_manifest_contract_version_mismatch:"
                        f"expected={expected_contract_version} actual={manifest_payload.get('contract_version')}"
                    ),
                ),
            )

        actual_snapshot_sha256 = _sha256_file(snapshot_path)
        if str(manifest_payload.get("snapshot_sha256")).strip() != actual_snapshot_sha256:
            return FeatureSnapshotGuardResult(
                frame=None,
                metadata=_build_guard_metadata(
                    snapshot_path=snapshot_path,
                    decision="fail_closed",
                    snapshot_format=snapshot_path.suffix.lower() or None,
                    snapshot_exists=True,
                    snapshot_as_of=snapshot_as_of,
                    file_timestamp=file_timestamp,
                    age_days=age_days,
                    snapshot_manifest_path=str(manifest_file),
                    snapshot_manifest_exists=True,
                    snapshot_manifest_file_timestamp=manifest_file_timestamp,
                    snapshot_manifest_contract_version=manifest_payload.get("contract_version"),
                    snapshot_manifest_strategy_profile=manifest_payload.get("strategy_profile"),
                    snapshot_manifest_config_name=manifest_payload.get("config_name"),
                    snapshot_manifest_snapshot_sha256=manifest_payload.get("snapshot_sha256"),
                    fail_reason="feature_snapshot_manifest_snapshot_checksum_mismatch",
                ),
            )

        if expected_config_path:
            config_file = Path(str(expected_config_path))
            if not config_file.exists():
                return FeatureSnapshotGuardResult(
                    frame=None,
                    metadata=_build_guard_metadata(
                        snapshot_path=snapshot_path,
                        decision="fail_closed",
                        snapshot_format=snapshot_path.suffix.lower() or None,
                        snapshot_exists=True,
                        snapshot_as_of=snapshot_as_of,
                        file_timestamp=file_timestamp,
                        age_days=age_days,
                        snapshot_manifest_path=str(manifest_file),
                        snapshot_manifest_exists=True,
                        snapshot_manifest_file_timestamp=manifest_file_timestamp,
                        snapshot_manifest_contract_version=manifest_payload.get("contract_version"),
                        snapshot_manifest_strategy_profile=manifest_payload.get("strategy_profile"),
                        snapshot_manifest_config_name=manifest_payload.get("config_name"),
                        fail_reason=f"feature_snapshot_expected_config_missing:{config_file}",
                    ),
                )
            actual_config_sha256 = _sha256_file(config_file)
            if str(manifest_payload.get("config_sha256")).strip() != actual_config_sha256:
                return FeatureSnapshotGuardResult(
                    frame=None,
                    metadata=_build_guard_metadata(
                        snapshot_path=snapshot_path,
                        decision="fail_closed",
                        snapshot_format=snapshot_path.suffix.lower() or None,
                        snapshot_exists=True,
                        snapshot_as_of=snapshot_as_of,
                        file_timestamp=file_timestamp,
                        age_days=age_days,
                        snapshot_manifest_path=str(manifest_file),
                        snapshot_manifest_exists=True,
                        snapshot_manifest_file_timestamp=manifest_file_timestamp,
                        snapshot_manifest_contract_version=manifest_payload.get("contract_version"),
                        snapshot_manifest_strategy_profile=manifest_payload.get("strategy_profile"),
                        snapshot_manifest_config_name=manifest_payload.get("config_name"),
                        snapshot_manifest_config_sha256=manifest_payload.get("config_sha256"),
                        fail_reason="feature_snapshot_manifest_config_checksum_mismatch",
                    ),
                )

    return FeatureSnapshotGuardResult(
        frame=frame,
        metadata=_build_guard_metadata(
            snapshot_path=snapshot_path,
            decision="proceed",
            snapshot_format=snapshot_path.suffix.lower() or None,
            snapshot_exists=True,
            snapshot_as_of=snapshot_as_of,
            file_timestamp=file_timestamp,
            age_days=age_days,
            snapshot_manifest_path=str(manifest_file),
            snapshot_manifest_exists=manifest_exists,
            snapshot_manifest_file_timestamp=manifest_file_timestamp,
            snapshot_manifest_contract_version=(manifest_payload or {}).get("contract_version"),
            snapshot_manifest_strategy_profile=(manifest_payload or {}).get("strategy_profile"),
            snapshot_manifest_config_name=(manifest_payload or {}).get("config_name"),
            snapshot_manifest_config_path=(manifest_payload or {}).get("config_path"),
            snapshot_manifest_snapshot_sha256=(manifest_payload or {}).get("snapshot_sha256"),
            snapshot_manifest_config_sha256=(manifest_payload or {}).get("config_sha256"),
            **_manifest_diagnostic_metadata(manifest_payload),
            expected_strategy_profile=expected_strategy_profile,
            expected_config_name=expected_config_name,
            expected_config_path=expected_config_path,
            expected_contract_version=expected_contract_version,
            actual_snapshot_sha256=actual_snapshot_sha256,
            actual_config_sha256=actual_config_sha256,
        ),
    )


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
