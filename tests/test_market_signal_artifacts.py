from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from quant_platform_kit.common.market_signal_artifacts import (
    cache_root_for_market_signal_artifact_tree,
    local_path_for_gcs_object,
    materialize_market_signal_artifact_tree,
    resolve_gcs_artifact_reference,
)


class _FakeObjectStore:
    """Mocks ObjectStore for GCS materialization tests."""

    def __init__(self, payloads: dict[str, str]) -> None:
        self._payloads = payloads

    def read_text(self, uri: str) -> str:
        if uri not in self._payloads:
            raise FileNotFoundError(f"Object not found: {uri}")
        return self._payloads[uri]

    def read_bytes(self, uri: str) -> bytes:
        return self.read_text(uri).encode("utf-8")

    def write_text(self, uri: str, data: str, content_type: str = "text/plain") -> str:
        self._payloads[uri] = data
        return uri

    def write_bytes(self, uri: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        return self.write_text(uri, data.decode("utf-8"), content_type)

    def exists(self, uri: str) -> bool:
        return uri in self._payloads

    def list(self, prefix: str) -> list[str]:
        return [k for k in self._payloads if k.startswith(prefix)]


def _json(payload: object) -> str:
    return json.dumps(payload)


def test_materialize_local_market_signal_artifact_tree_does_not_download():
    local_path, metadata = materialize_market_signal_artifact_tree(
        "~/signals/platform_handoff_index.json",
        cache_dir=Path("/tmp/cache"),
        client_factory=lambda: (_ for _ in ()).throw(AssertionError("should not download")),
    )

    assert local_path == Path("~/signals/platform_handoff_index.json").expanduser()
    assert metadata == {
        "source_uri": None,
        "local_path": "~/signals/platform_handoff_index.json",
        "cache_dir": None,
        "materialized_count": 0,
        "materialized_paths": (),
    }


@patch("quant_platform_kit.cloud.get_object_store")
def test_materialize_gcs_market_signal_artifact_tree_downloads_linked_artifacts(mock_get_store, tmp_path):
    payloads = {
        "gs://signals/live/platform_handoffs/index.json": _json(
            {
                "handoffs": [
                    {
                        "handoff_manifest_path": "2026-06-19/platform_handoff.json",
                    }
                ],
            }
        ),
        "gs://signals/live/platform_handoffs/2026-06-19/platform_handoff.json": _json(
            {
                "signal_bundle_manifest_path": "../bundles/manifest.json",
                "source_family_catalog_manifest_path": "../catalog/source.manifest.json",
                "consumer_contract_registry_manifest_path": "../contracts/registry.manifest.json",
            }
        ),
        "gs://signals/live/platform_handoffs/bundles/manifest.json": _json(
            {
                "bundle_path": "signal_bundle.json",
                "quality_report_path": "quality_report.json",
            }
        ),
        "gs://signals/live/platform_handoffs/bundles/signal_bundle.json": _json(
            {"schema_version": "test.signal_bundle.v1"}
        ),
        "gs://signals/live/platform_handoffs/bundles/quality_report.json": _json(
            {"schema_version": "test.quality_report.v1"}
        ),
        "gs://signals/live/platform_handoffs/catalog/source.manifest.json": _json(
            {"catalog_path": "signal_source_families.json"}
        ),
        "gs://signals/live/platform_handoffs/catalog/signal_source_families.json": _json(
            {"schema_version": "test.source_catalog.v1"}
        ),
        "gs://signals/live/platform_handoffs/contracts/registry.manifest.json": _json(
            {"registry_path": "market_signal_consumers.json"}
        ),
        "gs://signals/live/platform_handoffs/contracts/market_signal_consumers.json": _json(
            {"schema_version": "test.consumer_registry.v1"}
        ),
    }

    mock_get_store.return_value = _FakeObjectStore(payloads)

    local_path, metadata = materialize_market_signal_artifact_tree(
        "gs://signals/live/platform_handoffs/index.json",
        cache_dir=tmp_path,
    )

    cache_root = cache_root_for_market_signal_artifact_tree(
        "gs://signals/live/platform_handoffs/index.json",
        cache_dir=tmp_path,
    )
    assert local_path == cache_root / "live" / "platform_handoffs" / "index.json"
    assert metadata["source_uri"] == "gs://signals/live/platform_handoffs/index.json"
    assert metadata["local_path"] == str(local_path)
    assert metadata["cache_dir"] == str(cache_root)
    assert metadata["materialized_count"] == len(payloads)
    assert set(metadata["materialized_paths"]) == {
        str(local_path_for_gcs_object(cache_root, uri.removeprefix("gs://signals/")))
        for uri in payloads
    }

    for uri in payloads:
        object_name = uri.removeprefix("gs://signals/")
        assert local_path_for_gcs_object(cache_root, object_name).exists()


def test_resolve_gcs_artifact_reference_rejects_non_portable_paths():
    assert (
        resolve_gcs_artifact_reference(
            "gs://bucket/root/platform_handoffs/index.json",
            "2026-06-19/platform_handoff.json",
        )
        == "gs://bucket/root/platform_handoffs/2026-06-19/platform_handoff.json"
    )
    assert (
        resolve_gcs_artifact_reference(
            "gs://bucket/root/platform_handoffs/2026-06-19/platform_handoff.json",
            "../bundles/manifest.json",
        )
        == "gs://bucket/root/platform_handoffs/bundles/manifest.json"
    )

    with pytest.raises(ValueError, match="relative linked paths"):
        resolve_gcs_artifact_reference(
            "gs://bucket/root/platform_handoffs/index.json",
            "/tmp/signal_bundle_manifest.json",
        )

    with pytest.raises(ValueError, match="escapes the bucket root"):
        resolve_gcs_artifact_reference(
            "gs://bucket/root/platform_handoffs/index.json",
            "../../../signal_bundle_manifest.json",
        )
