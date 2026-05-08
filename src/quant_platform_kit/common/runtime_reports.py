from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .runtime_target import RuntimeTarget

RUNTIME_REPORT_SCHEMA_VERSION = "runtime_report.v1"


@dataclass(frozen=True)
class RuntimeReportPersistResult:
    local_path: str | None = None
    gcs_uri: str | None = None


def build_runtime_report_base(
    *,
    platform: str,
    deploy_target: str,
    service_name: str,
    strategy_profile: str,
    run_id: str,
    run_source: str,
    runtime_target: RuntimeTarget | Mapping[str, Any] | None = None,
    strategy_domain: str | None = None,
    account_scope: str | None = None,
    account_group: str | None = None,
    account_region: str | None = None,
    project_id: str | None = None,
    instance_name: str | None = None,
    extra_context_fields: Mapping[str, Any] | None = None,
    dry_run: bool = False,
    status: str = "started",
    started_at: datetime | str | None = None,
    finished_at: datetime | str | None = None,
    summary: Mapping[str, Any] | None = None,
    diagnostics: Mapping[str, Any] | None = None,
    artifacts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": RUNTIME_REPORT_SCHEMA_VERSION,
        "platform": str(platform),
        "deploy_target": str(deploy_target),
        "service_name": str(service_name),
        "strategy_profile": str(strategy_profile),
        "runtime_target": _normalize_runtime_target(runtime_target),
        "strategy_domain": _optional_string(strategy_domain),
        "account_scope": _resolve_account_scope(
            account_scope=account_scope,
            account_group=account_group,
            account_region=account_region,
        ),
        "account_group": _optional_string(account_group),
        "account_region": _optional_string(account_region),
        "project_id": _optional_string(project_id),
        "instance_name": _optional_string(instance_name),
        "run_id": str(run_id),
        "run_source": str(run_source),
        "status": str(status),
        "dry_run": bool(dry_run),
        "started_at": _normalize_datetime(started_at),
        "finished_at": _normalize_datetime(finished_at),
        **_normalize_mapping(extra_context_fields),
        "summary": _normalize_mapping(summary),
        "diagnostics": _normalize_mapping(diagnostics),
        "artifacts": _normalize_mapping(artifacts),
        "errors": [],
    }


def finalize_runtime_report(
    report: dict[str, Any],
    *,
    status: str,
    finished_at: datetime | str | None = None,
    summary: Mapping[str, Any] | None = None,
    diagnostics: Mapping[str, Any] | None = None,
    artifacts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    report["status"] = str(status)
    report["finished_at"] = _normalize_datetime(finished_at or datetime.now(timezone.utc))
    _merge_section(report, "summary", summary)
    _merge_section(report, "diagnostics", diagnostics)
    _merge_section(report, "artifacts", artifacts)
    return report


def append_runtime_report_error(
    report: dict[str, Any],
    *,
    stage: str,
    message: str,
    **fields: Any,
) -> dict[str, Any]:
    entry = {
        "stage": str(stage),
        "message": str(message),
        **_normalize_mapping(fields),
    }
    cleaned = _drop_empty(entry)
    report.setdefault("errors", []).append(cleaned)
    return cleaned


def default_runtime_report_path(
    report: Mapping[str, Any],
    *,
    base_dir: str | Path | None = None,
) -> Path:
    root = Path(base_dir).expanduser() if base_dir else Path(tempfile.gettempdir()) / "quant_runtime_reports"
    return root / runtime_report_relative_path(report)


def runtime_report_relative_path(report: Mapping[str, Any]) -> Path:
    started_at = _coerce_datetime(report.get("started_at"))
    month_segment = started_at.strftime("%Y-%m") if started_at is not None else "unknown-month"
    segments = [
        _sanitize_path_segment(report.get("platform")) or "unknown-platform",
        _sanitize_path_segment(report.get("strategy_profile")) or "unknown-profile",
    ]
    account_scope = _sanitize_path_segment(report.get("account_scope"))
    if account_scope:
        segments.append(account_scope)
    run_id = _sanitize_path_segment(report.get("run_id")) or "run"
    return Path(*segments, month_segment, f"{run_id}.json")


def write_runtime_report_json(
    report: Mapping[str, Any],
    *,
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _normalize_mapping(report)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def build_runtime_report_gcs_uri(
    report: Mapping[str, Any],
    *,
    gcs_prefix_uri: str,
) -> str:
    bucket_name, prefix = _parse_gcs_uri(gcs_prefix_uri)
    object_name = runtime_report_relative_path(report).as_posix()
    if prefix:
        object_name = f"{prefix.rstrip('/')}/{object_name}"
    return f"gs://{bucket_name}/{object_name}"


def upload_runtime_report_to_gcs(
    report: Mapping[str, Any],
    *,
    gcs_uri: str,
    gcp_project_id: str | None = None,
    client_factory: Any = None,
) -> str:
    bucket_name, object_name = _parse_gcs_uri(gcs_uri)
    if not object_name:
        raise ValueError(f"gcs_uri must include an object path, got: {gcs_uri!r}")
    if client_factory is None:
        try:
            from google.cloud import storage  # type: ignore
        except ImportError as exc:
            raise RuntimeError("google-cloud-storage is required for GCS runtime report upload") from exc
        client_factory = storage.Client
    client = client_factory(project=gcp_project_id) if gcp_project_id is not None else client_factory()
    blob = client.bucket(bucket_name).blob(object_name)
    payload = json.dumps(_normalize_mapping(report), ensure_ascii=False, indent=2, sort_keys=True)
    blob.upload_from_string(payload, content_type="application/json")
    return f"gs://{bucket_name}/{object_name}"


def persist_runtime_report(
    report: dict[str, Any],
    *,
    base_dir: str | Path | None = None,
    output_path: str | Path | None = None,
    gcs_prefix_uri: str | None = None,
    gcp_project_id: str | None = None,
    client_factory: Any = None,
) -> RuntimeReportPersistResult:
    local_path = Path(output_path).expanduser() if output_path else default_runtime_report_path(report, base_dir=base_dir)
    gcs_uri = build_runtime_report_gcs_uri(report, gcs_prefix_uri=gcs_prefix_uri) if _optional_string(gcs_prefix_uri) else None
    _merge_section(
        report,
        "artifacts",
        {
            "runtime_report_local_path": str(local_path),
        },
    )
    write_runtime_report_json(report, output_path=local_path)
    if gcs_uri is not None:
        upload_report = _normalize_mapping(report)
        _merge_section(
            upload_report,
            "artifacts",
            {
                "runtime_report_gcs_uri": gcs_uri,
            },
        )
        gcs_uri = upload_runtime_report_to_gcs(
            upload_report,
            gcs_uri=gcs_uri,
            gcp_project_id=gcp_project_id,
            client_factory=client_factory,
        )
        _merge_section(
            report,
            "artifacts",
            {
                "runtime_report_gcs_uri": gcs_uri,
            },
        )
        write_runtime_report_json(report, output_path=local_path)
    return RuntimeReportPersistResult(local_path=str(local_path), gcs_uri=gcs_uri)


def _merge_section(report: dict[str, Any], key: str, payload: Mapping[str, Any] | None) -> None:
    if not payload:
        return
    current = dict(report.get(key) or {})
    current.update(_normalize_mapping(payload))
    report[key] = current


def _resolve_account_scope(
    *,
    account_scope: str | None,
    account_group: str | None,
    account_region: str | None,
) -> str | None:
    for value in (account_scope, account_group, account_region):
        normalized = _optional_string(value)
        if normalized is not None:
            return normalized
    return None


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_datetime(value: datetime | str | None) -> str | None:
    coerced = _coerce_datetime(value)
    if coerced is None:
        return _optional_string(value)
    return coerced.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_datetime(value: datetime | str | None) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    text = _optional_string(value)
    if text is None:
        return None
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
        return datetime.fromisoformat(text).astimezone(timezone.utc)
    except ValueError:
        return None


def _normalize_mapping(mapping: Mapping[str, Any] | None) -> dict[str, Any]:
    if not mapping:
        return {}
    return {str(key): _normalize_value(value) for key, value in mapping.items()}


def _normalize_runtime_target(value: RuntimeTarget | Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, RuntimeTarget):
        return _normalize_mapping(value.to_dict())
    return _normalize_mapping(value)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return _drop_empty({str(key): _normalize_value(item) for key, item in value.items()})
    if isinstance(value, tuple):
        return [_normalize_value(item) for item in value]
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    return value


def _drop_empty(payload: Mapping[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, tuple, dict)) and len(value) == 0:
            continue
        cleaned[str(key)] = value
    return cleaned


def _sanitize_path_segment(value: Any) -> str | None:
    text = _optional_string(value)
    if text is None:
        return None
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in text)
    return safe or None


def _parse_gcs_uri(value: str) -> tuple[str, str]:
    text = _optional_string(value)
    if text is None or not text.startswith("gs://"):
        raise ValueError(f"Expected gs://bucket[/prefix] URI, got: {value!r}")
    remainder = text[5:]
    bucket_name, _, object_name = remainder.partition("/")
    bucket = _optional_string(bucket_name)
    if bucket is None:
        raise ValueError(f"GCS bucket name is missing in URI: {value!r}")
    return bucket, object_name.strip("/")
