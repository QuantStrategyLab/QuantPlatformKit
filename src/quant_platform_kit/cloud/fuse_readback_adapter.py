"""Edge adapter for reading FUSE-3 external state snapshots from Google Cloud Storage."""

from __future__ import annotations

from collections.abc import Mapping

from quant_platform_kit.risk.fuse_readback_store import (
    DEFAULT_MAX_FUSE_STATE_BYTES,
    FuseReadbackStoreResult,
    load_fuse_readback_from_env,
    register_fuse_readback_gcs_reader,
)

DEFAULT_GCS_TIMEOUT_SECONDS = 10.0


def gcs_fuse_readback_reader(
    bucket_name: str,
    object_name: str,
    *,
    max_bytes: int = DEFAULT_MAX_FUSE_STATE_BYTES,
    timeout_seconds: float = DEFAULT_GCS_TIMEOUT_SECONDS,
) -> bytes:
    """Download bounded FUSE state bytes from GCS (fail closed via ValueError codes)."""
    try:
        from google.cloud import storage  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ValueError("FUSE_STATE_GCS_CLIENT_MISSING") from exc
    try:
        client = storage.Client()
        blob = client.bucket(bucket_name).blob(object_name)
        blob.reload(timeout=timeout_seconds)
        if blob.size is not None and int(blob.size) > max_bytes:
            raise ValueError("FUSE_STATE_TOO_LARGE")
        return bytes(blob.download_as_bytes(timeout=timeout_seconds))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("FUSE_STATE_GCS_READ_FAILED") from exc


def register_default_fuse_readback_gcs_reader() -> None:
    """Bind the default GCS FUSE state reader into the pure risk port."""
    register_fuse_readback_gcs_reader(gcs_fuse_readback_reader)


def load_cloud_fuse_readback_from_env(
    *,
    environ: Mapping[str, str] | None = None,
    max_bytes: int = DEFAULT_MAX_FUSE_STATE_BYTES,
) -> FuseReadbackStoreResult:
    """Load external FUSE state using the GCS edge reader for ``gs://`` URIs."""
    return load_fuse_readback_from_env(
        environ=environ,
        gcs_reader=lambda bucket, obj: gcs_fuse_readback_reader(
            bucket, obj, max_bytes=max_bytes
        ),
        max_bytes=max_bytes,
    )


__all__ = [
    "DEFAULT_GCS_TIMEOUT_SECONDS",
    "gcs_fuse_readback_reader",
    "load_cloud_fuse_readback_from_env",
    "register_default_fuse_readback_gcs_reader",
]
