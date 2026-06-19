from __future__ import annotations

import json
from pathlib import Path

import pytest

from quant_platform_kit.common.market_signal_artifacts import (
    cache_root_for_market_signal_artifact_tree,
    local_path_for_gcs_object,
    materialize_market_signal_artifact_tree,
    resolve_gcs_artifact_reference,
)


class _FakeBlob:
    def __init__(self, payloads: dict[str, str], key: str) -> None:
        self._payloads = payloads
        self._key = key

    def download_to_filename(self, destination: str) -> None:
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        Path(destination).write_text(self._payloads[self._key], encoding="utf-8")


class _FakeBucket:
    def __init__(self, payloads: dict[str, str], bucket_name: str) -> None:
        self._payloads = payloads
        self._bucket_name = bucket_name

    def blob(self, object_name: str) -> _FakeBlob:
        return _FakeBlob(self._payloads, f"gs://{self._bucket_name}/{object_name}")


class _FakeClient:
    def __init__(self, payloads: dict[str, str]) -> None:
        self._payloads = payloads

    def bucket(self, bucket_name: str) -> _FakeBucket:
        return _FakeBucket(self._payloads, bucket_name)


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


def test_materialize_gcs_market_signal_artifact_tree_downloads_linked_artifacts(tmp_path):
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

    local_path, metadata = materialize_market_signal_artifact_tree(
        "gs://signals/live/platform_handoffs/index.json",
        cache_dir=tmp_path,
        client_factory=lambda: _FakeClient(payloads),
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
