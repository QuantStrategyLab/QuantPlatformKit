"""Artifact path helpers for strategy plugin signal files."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def materialize_local_or_gcs_artifact(
    reference: str,
    *,
    cache_dir: Path,
    client_factory: Any = None,
) -> tuple[Path, dict[str, str | None]]:
    raw_reference = _required_string(reference, field_name="reference")
    if not raw_reference.startswith("gs://"):
        return Path(raw_reference).expanduser(), {"source_uri": None, "local_path": raw_reference}

    local_path = cache_path_for_remote_artifact(raw_reference, cache_dir=cache_dir)
    download_gcs_object(raw_reference, local_path, client_factory=client_factory)
    return local_path, {"source_uri": raw_reference, "local_path": str(local_path)}


def download_gcs_object(uri: str, destination: Path, *, client_factory: Any = None) -> None:
    if client_factory is None:
        try:
            from google.cloud import storage  # type: ignore
        except ImportError as exc:
            raise RuntimeError("google-cloud-storage is required for GCS strategy plugin artifacts") from exc
        client_factory = storage.Client
    bucket_name, object_name = parse_gcs_uri(uri)
    destination.parent.mkdir(parents=True, exist_ok=True)
    client = client_factory()
    client.bucket(bucket_name).blob(object_name).download_to_filename(str(destination))


def parse_gcs_uri(uri: str) -> tuple[str, str]:
    raw_uri = str(uri or "").strip()
    if not raw_uri.startswith("gs://"):
        raise ValueError(f"Unsupported GCS URI: {raw_uri}")
    bucket_name, _, object_name = raw_uri[5:].partition("/")
    if not bucket_name or not object_name:
        raise ValueError(f"Invalid GCS URI: {raw_uri}")
    return bucket_name, object_name


def cache_path_for_remote_artifact(reference: str, *, cache_dir: Path) -> Path:
    digest = hashlib.sha256(reference.encode("utf-8")).hexdigest()[:16]
    leaf_name = Path(reference).name or "latest_signal.json"
    return cache_dir / digest / leaf_name


def _required_string(value: Any, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text
