"""Shared cloud/local alert marker store — eliminates duplicate code across email/sms/push/telegram channels."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quant_platform_kit.cloud import get_object_store


def _clean_relative_key(key: str) -> str:
    """Sanitize a string for use as a filesystem/object path segment."""
    parts = []
    for raw_part in str(key or "").replace("\\", "/").split("/"):
        cleaned = "".join(
            char if char.isalnum() or char in {"-", "_", "."} else "-"
            for char in raw_part.strip()
        ).strip("-._")
        if cleaned:
            parts.append(cleaned[:100])
    return "/".join(parts) or "unknown"


def _parse_cloud_uri(uri: str) -> tuple[str, str]:
    """Parse a cloud storage URI (gs://, s3://, or az://) into (bucket, prefix)."""
    raw_uri = str(uri or "").strip()
    if not raw_uri.startswith("gs://") and not raw_uri.startswith("s3://") and not raw_uri.startswith("az://"):
        raise ValueError(f"Cloud URI must start with gs://, s3://, or az://, got: {uri!r}")
    remainder = raw_uri[5:]
    bucket_name, _, object_prefix = remainder.partition("/")
    if not bucket_name:
        raise ValueError(f"Cloud URI must include a bucket name, got: {uri!r}")
    return bucket_name, object_prefix.strip("/")


@dataclass(frozen=True)
class CloudAlertMarkerStore:
    """Shared marker store for strategy plugin alerts.

    Persists alert markers to either cloud ObjectStore or local filesystem.
    Used as base for channel-specific stores (email, sms, push, telegram).

    Usage::

        store = CloudAlertMarkerStore(
            namespace="strategy_plugin_telegram_alerts",
            schema_version="strategy_plugin_telegram_alert_marker.v1",
            cloud_prefix_uri="gs://bucket/alerts",
            project_id="my-project",
        )
        if not store.has_alert("some-key"):
            store.record_alert("some-key")
    """

    namespace: str = "strategy_plugin_alerts"
    schema_version: str = "strategy_plugin_alert_marker.v1"
    local_dir: str | Path | None = None
    cloud_prefix_uri: str | None = None
    project_id: str | None = None
    client_factory: Any = None

    def _object_store(self):
        return get_object_store(project_id=self.project_id)

    def has_alert(self, alert_key: str) -> bool:
        if self.cloud_prefix_uri and self._object_store().exists(
            self._cloud_uri(alert_key)
        ):
            return True
        if self.local_dir and self._local_path(alert_key).exists():
            return True
        return False

    def record_alert(
        self,
        alert_key: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        payload = {
            "schema_version": self.schema_version,
            "alert_key": str(alert_key),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "metadata": dict(metadata or {}),
        }
        encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        if self.cloud_prefix_uri:
            self._object_store().write_text(
                self._cloud_uri(alert_key),
                encoded,
                content_type="application/json",
            )
            return
        if self.local_dir:
            path = self._local_path(alert_key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(encoded, encoding="utf-8")

    def _local_path(self, alert_key: str) -> Path:
        root = Path(self.local_dir or tempfile.gettempdir()).expanduser()
        return root / self.namespace / f"{_clean_relative_key(alert_key)}.json"

    def _cloud_uri(self, alert_key: str) -> str:
        bucket_name, prefix = _parse_cloud_uri(str(self.cloud_prefix_uri or ""))
        object_name = "/".join(
            part.strip("/")
            for part in (prefix, self.namespace, f"{_clean_relative_key(alert_key)}.json")
            if part and part.strip("/")
        )
        scheme = str(self.cloud_prefix_uri or "").split("://")[0] if "://" in str(self.cloud_prefix_uri or "") else "gs"
        return f"{scheme}://{bucket_name}/{object_name}"
