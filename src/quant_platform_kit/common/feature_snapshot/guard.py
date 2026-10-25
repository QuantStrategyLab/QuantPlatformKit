"""Feature snapshot guard state machine and current-generation pointer validation."""

from __future__ import annotations

import json
import tempfile
from datetime import timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .io import (
    _is_cloud_uri,
    _load_snapshot_frame,
    _materialize_artifact_path,
    _parse_cloud_uri,
    _resolve_manifest_path,
    _resolve_manifest_reference,
    _sha256_file,
)
from .types import (
    DEFAULT_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS,
    DEFAULT_FEATURE_SNAPSHOT_FALLBACK_MODE,
    DEFAULT_MAX_SNAPSHOT_MONTH_LAG,
    DEFAULT_SNAPSHOT_DATE_COLUMNS,
    FEATURE_SNAPSHOT_FALLBACK_MODE_LAST_VALID,
    _CURRENT_GENERATION_DIGEST_RE,
    _CURRENT_GENERATION_ID_RE,
    _CURRENT_GENERATION_OBJECT_NAMES,
    _CURRENT_GENERATION_POINTER_FILENAME,
    _CURRENT_GENERATION_SCHEMA,
    _MANIFEST_DIAGNOSTIC_FIELDS,
    FeatureSnapshotGuardResult,
    _build_guard_metadata,
    _month_lag,
    _normalize_config_name_label,
    _normalize_contract_version_label,
    _normalize_strategy_profile_label,
    _normalize_timestamp,
    normalize_feature_snapshot_fallback_mode,
)


def _is_current_generation_pointer_reference(reference: str) -> bool:
    raw_reference = str(reference or "").strip()
    return _is_cloud_uri(raw_reference) and raw_reference.endswith(
        f"/{_CURRENT_GENERATION_POINTER_FILENAME}"
    )


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate pointer field")
        result[key] = value
    return result


def _reject_nonfinite_json_constant(value: str) -> None:
    raise ValueError(f"invalid pointer JSON constant: {value}")


def _is_safe_generation_basename(value: object) -> bool:
    if not isinstance(value, str) or not value or "\x00" in value:
        return False
    return (
        "/" not in value
        and "\\" not in value
        and value not in {".", ".."}
        and Path(value).name == value
    )


def _validate_current_generation_pointer_uri(pointer_uri: str) -> str:
    bucket, object_name = _parse_cloud_uri(pointer_uri)
    if (
        object_name.split("/")[-1] != _CURRENT_GENERATION_POINTER_FILENAME
        or any(segment in {"", ".", ".."} for segment in object_name.split("/"))
        or any(character.isspace() or character == "\\" for character in object_name)
    ):
        raise ValueError("unsafe current generation pointer URI")
    parent = object_name.rsplit("/", 1)[0] if "/" in object_name else ""
    return f"{pointer_uri[:5]}{bucket}/{parent}" if parent else f"{pointer_uri[:5]}{bucket}"


def _read_current_generation_pointer(pointer_bytes: bytes) -> dict[str, object]:
    try:
        text = pointer_bytes.decode("utf-8")
        payload = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_nonfinite_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
        raise ValueError("invalid current generation pointer") from None

    if not isinstance(payload, dict):
        raise ValueError("invalid current generation pointer")
    if set(payload) != {
        "schema",
        "profile",
        "generation_id",
        "immutable_prefix",
        "snapshot_as_of",
        "objects",
    }:
        raise ValueError("invalid current generation pointer fields")

    try:
        canonical_bytes = json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8") + b"\n"
    except (TypeError, ValueError):
        raise ValueError("invalid current generation pointer") from None
    if pointer_bytes != canonical_bytes:
        raise ValueError("non-canonical current generation pointer")

    if payload["schema"] != _CURRENT_GENERATION_SCHEMA:
        raise ValueError("unsupported current generation pointer schema")
    if (
        not isinstance(payload["profile"], str)
        or not payload["profile"]
        or payload["profile"] != payload["profile"].strip()
    ):
        raise ValueError("invalid current generation pointer profile")
    generation_id = payload["generation_id"]
    if not isinstance(generation_id, str) or _CURRENT_GENERATION_ID_RE.fullmatch(generation_id) is None:
        raise ValueError("invalid current generation pointer generation_id")
    snapshot_as_of = payload["snapshot_as_of"]
    if (
        not isinstance(snapshot_as_of, str)
        or pd.Timestamp(snapshot_as_of).strftime("%Y-%m-%d") != snapshot_as_of
    ):
        raise ValueError("invalid current generation pointer snapshot_as_of")

    objects = payload["objects"]
    if not isinstance(objects, dict) or set(objects) != set(_CURRENT_GENERATION_OBJECT_NAMES):
        raise ValueError("invalid current generation pointer objects")
    basenames: set[str] = set()
    for name in _CURRENT_GENERATION_OBJECT_NAMES:
        item = objects[name]
        if not isinstance(item, dict) or set(item) != {"basename", "sha256"}:
            raise ValueError("invalid current generation pointer object fields")
        basename = item["basename"]
        digest = item["sha256"]
        if not _is_safe_generation_basename(basename) or basename in basenames:
            raise ValueError("invalid current generation pointer basename")
        if not isinstance(digest, str) or _CURRENT_GENERATION_DIGEST_RE.fullmatch(digest) is None:
            raise ValueError("invalid current generation pointer sha256")
        basenames.add(basename)

    return payload


def _load_current_generation_feature_snapshot_guarded(
    pointer_uri: str,
    *,
    run_as_of,
    required_columns: Iterable[str] | None,
    snapshot_date_columns: Iterable[str],
    max_snapshot_month_lag: int,
    expected_strategy_profile: str | None,
    expected_config_name: str | None,
    expected_config_path: str | None,
    expected_contract_version: str | None,
) -> FeatureSnapshotGuardResult:
    pointer_metadata = {
        "feature_snapshot_pointer_uri": pointer_uri,
        "feature_snapshot_generation_id": None,
        "feature_snapshot_immutable_prefix": None,
        "feature_snapshot_object_digests": None,
    }
    try:
        prefix_root = _validate_current_generation_pointer_uri(pointer_uri)
        with tempfile.TemporaryDirectory(prefix="feature-snapshot-generation-") as temporary_dir:
            pointer_path = Path(temporary_dir) / _CURRENT_GENERATION_POINTER_FILENAME
            from . import _download_gcs_object as download

            download(pointer_uri, pointer_path)
            payload = _read_current_generation_pointer(pointer_path.read_bytes())
            pointer_profile = str(payload["profile"])
            if expected_strategy_profile and _normalize_strategy_profile_label(
                pointer_profile
            ) != _normalize_strategy_profile_label(expected_strategy_profile):
                raise ValueError("current generation pointer profile mismatch")
            generation_id = payload["generation_id"]
            immutable_prefix = payload["immutable_prefix"]
            expected_prefix = f"{prefix_root}/generations/{generation_id}"
            if immutable_prefix != expected_prefix:
                raise ValueError("current generation pointer prefix mismatch")

            objects = payload["objects"]
            object_digests = {
                name: objects[name]["sha256"] for name in _CURRENT_GENERATION_OBJECT_NAMES
            }
            pointer_metadata.update(
                {
                    "feature_snapshot_generation_id": generation_id,
                    "feature_snapshot_immutable_prefix": immutable_prefix,
                    "feature_snapshot_object_digests": dict(object_digests),
                }
            )
            local_paths: dict[str, Path] = {}
            for name in _CURRENT_GENERATION_OBJECT_NAMES:
                basename = objects[name]["basename"]
                object_uri = f"{immutable_prefix}/{basename}"
                local_path = Path(temporary_dir) / f"{name}-{basename}"
                download(object_uri, local_path)
                if _sha256_file(local_path) != object_digests[name]:
                    return FeatureSnapshotGuardResult(
                        frame=None,
                        metadata=_build_guard_metadata(
                            snapshot_path=pointer_uri,
                            decision="fail_closed",
                            snapshot_exists=False,
                            **pointer_metadata,
                            fail_reason="feature_snapshot_pointer_object_digest_mismatch",
                        ),
                    )
                local_paths[name] = local_path

            result = _load_feature_snapshot_guarded_without_fallback(
                str(local_paths["snapshot"]),
                run_as_of=run_as_of,
                required_columns=required_columns,
                snapshot_date_columns=snapshot_date_columns,
                max_snapshot_month_lag=max_snapshot_month_lag,
                manifest_path=str(local_paths["manifest"]),
                require_manifest=True,
                expected_strategy_profile=expected_strategy_profile or pointer_profile,
                expected_config_name=expected_config_name,
                expected_config_path=expected_config_path,
                expected_contract_version=expected_contract_version,
            )
            metadata = dict(result.metadata)
            metadata.update(pointer_metadata)
            metadata.update(
                {
                    "feature_snapshot_path": pointer_uri,
                    "snapshot_path": pointer_uri,
                    "snapshot_source_uri": f"{immutable_prefix}/{objects['snapshot']['basename']}",
                    "snapshot_manifest_path": f"{immutable_prefix}/{objects['manifest']['basename']}",
                    "snapshot_manifest_source_uri": f"{immutable_prefix}/{objects['manifest']['basename']}",
                    "snapshot_local_path": None,
                    "snapshot_manifest_local_path": None,
                }
            )
            if result.metadata.get("snapshot_guard_decision") != "proceed":
                metadata = _build_guard_metadata(
                    snapshot_path=pointer_uri,
                    decision="fail_closed",
                    snapshot_exists=False,
                    **pointer_metadata,
                    fail_reason="feature_snapshot_pointer_guard_failed",
                )
                return FeatureSnapshotGuardResult(frame=None, metadata=metadata)
            if result.metadata.get("snapshot_guard_decision") == "proceed" and str(
                result.metadata.get("snapshot_as_of")
            )[:10] != payload["snapshot_as_of"]:
                return FeatureSnapshotGuardResult(
                    frame=None,
                    metadata={
                        **metadata,
                        "snapshot_guard_decision": "fail_closed",
                        "fail_reason": "feature_snapshot_pointer_snapshot_as_of_mismatch",
                    },
                )
            return FeatureSnapshotGuardResult(frame=result.frame, metadata=metadata)
    except Exception:
        return FeatureSnapshotGuardResult(
            frame=None,
            metadata=_build_guard_metadata(
                snapshot_path=pointer_uri,
                decision="fail_closed",
                snapshot_exists=False,
                **pointer_metadata,
                fail_reason="feature_snapshot_pointer_read_failed",
            ),
        )


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

    from . import (
        _feature_snapshot_fallback_context,
        _load_feature_snapshot_last_valid,
        _write_feature_snapshot_last_valid,
    )

    raw_path = str(path or "").strip()
    if _is_current_generation_pointer_reference(raw_path):
        if str(manifest_path or "").strip() not in {"", raw_path}:
            return FeatureSnapshotGuardResult(
                frame=None,
                metadata=_build_guard_metadata(
                    snapshot_path=raw_path,
                    decision="fail_closed",
                    snapshot_exists=False,
                    feature_snapshot_pointer_uri=raw_path,
                    feature_snapshot_generation_id=None,
                    feature_snapshot_immutable_prefix=None,
                    feature_snapshot_object_digests=None,
                    fail_reason="feature_snapshot_pointer_manifest_mismatch",
                ),
            )
        return _load_current_generation_feature_snapshot_guarded(
            raw_path,
            run_as_of=run_as_of,
            required_columns=required_columns,
            snapshot_date_columns=snapshot_date_columns,
            max_snapshot_month_lag=max_snapshot_month_lag,
            expected_strategy_profile=expected_strategy_profile,
            expected_config_name=expected_config_name,
            expected_config_path=expected_config_path,
            expected_contract_version=expected_contract_version,
        )

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

    if _is_current_generation_pointer_reference(raw_path):
        if str(manifest_path or "").strip() not in {"", raw_path}:
            return FeatureSnapshotGuardResult(
                frame=None,
                metadata=_build_guard_metadata(
                    snapshot_path=raw_path,
                    decision="fail_closed",
                    snapshot_exists=False,
                    feature_snapshot_pointer_uri=raw_path,
                    feature_snapshot_generation_id=None,
                    feature_snapshot_immutable_prefix=None,
                    feature_snapshot_object_digests=None,
                    fail_reason="feature_snapshot_pointer_manifest_mismatch",
                ),
            )
        return _load_current_generation_feature_snapshot_guarded(
            raw_path,
            run_as_of=run_as_of,
            required_columns=required_columns,
            snapshot_date_columns=snapshot_date_columns,
            max_snapshot_month_lag=max_snapshot_month_lag,
            expected_strategy_profile=expected_strategy_profile,
            expected_config_name=expected_config_name,
            expected_config_path=expected_config_path,
            expected_contract_version=expected_contract_version,
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
