"""Artifact path helpers for strategy plugin signal files."""

from __future__ import annotations

import hashlib
import warnings
from pathlib import Path
from typing import Any


# ──────────────────────────────────────────────────────────────────────
#  Primary (cloud-neutral) API — use these in new code
# ──────────────────────────────────────────────────────────────────────


def materialize_local_or_remote_artifact(
    reference: str,
    *,
    cache_dir: Path,
    client_factory: Any = None,
) -> tuple[Path, dict[str, str | None]]:
    """Resolve a local path or download a remote (gs:// / s3://) artifact.

    Returns (local_path, metadata_dict).
    """
    raw_reference = _required_string(reference, field_name="reference")
    if not raw_reference.startswith("gs://"):
        return Path(raw_reference).expanduser(), {"source_uri": None, "local_path": raw_reference}

    local_path = cache_path_for_remote_artifact(raw_reference, cache_dir=cache_dir)
    download_remote_object(raw_reference, local_path, client_factory=client_factory)
    return local_path, {"source_uri": raw_reference, "local_path": str(local_path)}


def download_remote_object(uri: str, destination: Path, *, client_factory: Any = None) -> None:
    """Download a remote object (gs:// or s3://) to a local path via the cloud abstraction."""
    try:
        from quant_platform_kit.cloud import get_object_store
    except ImportError as exc:
        raise RuntimeError("quant_platform_kit.cloud is required for remote strategy plugin artifacts") from exc
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(get_object_store().read_bytes(uri))


def parse_cloud_uri(uri: str) -> tuple[str, str]:
    """Parse a cloud storage URI (gs:// or s3://) into (bucket, object_name)."""
    raw_uri = str(uri or "").strip()
    if not raw_uri.startswith("gs://") and not raw_uri.startswith("s3://"):
        raise ValueError(f"Unsupported cloud storage URI: {raw_uri}. Expected gs:// or s3:// prefix.")
    bucket_name, _, object_name = raw_uri[5:].partition("/")
    if not bucket_name or not object_name:
        raise ValueError(f"Invalid cloud storage URI: {raw_uri}")
    return bucket_name, object_name


# ──────────────────────────────────────────────────────────────────────
#  Deprecated aliases — kept for backward compatibility
# ──────────────────────────────────────────────────────────────────────


def materialize_local_or_gcs_artifact(
    reference: str,
    *,
    cache_dir: Path,
    client_factory: Any = None,
) -> tuple[Path, dict[str, str | None]]:
    warnings.warn(
        "materialize_local_or_gcs_artifact is deprecated, use materialize_local_or_remote_artifact",
        DeprecationWarning,
        stacklevel=2,
    )
    return materialize_local_or_remote_artifact(reference, cache_dir=cache_dir, client_factory=client_factory)


def download_gcs_object(uri: str, destination: Path, *, client_factory: Any = None) -> None:
    warnings.warn(
        "download_gcs_object is deprecated, use download_remote_object",
        DeprecationWarning,
        stacklevel=2,
    )
    return download_remote_object(uri, destination, client_factory=client_factory)


def parse_gcs_uri(uri: str) -> tuple[str, str]:
    warnings.warn(
        "parse_gcs_uri is deprecated, use parse_cloud_uri",
        DeprecationWarning,
        stacklevel=2,
    )
    return parse_cloud_uri(uri)


def cache_path_for_remote_artifact(reference: str, *, cache_dir: Path) -> Path:
    digest = hashlib.sha256(reference.encode("utf-8")).hexdigest()[:16]
    leaf_name = Path(reference).name or "latest_signal.json"
    return cache_dir / digest / leaf_name


def _required_string(value: Any, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text
