"""Feature snapshot cloud URI handling and artifact materialization."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from .types import DEFAULT_ARTIFACT_CACHE_DIR, DEFAULT_SNAPSHOT_MANIFEST_SUFFIX


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


def _download_gcs_object(uri: str, destination: Path) -> None:
    from . import _download_remote_object as remote_download

    remote_download(uri, destination)


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
    from . import _download_gcs_object as download

    download(raw_reference, local_path)
    return local_path, {"source_uri": raw_reference, "local_path": str(local_path)}
