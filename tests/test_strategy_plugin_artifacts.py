from pathlib import Path

import pytest

from quant_platform_kit.common.strategy_plugin_artifacts import (
    cache_path_for_remote_artifact,
    materialize_local_or_remote_artifact,
    parse_cloud_uri,
)


def test_parse_cloud_uri_requires_bucket_and_object():
    assert parse_cloud_uri("gs://bucket/path/latest_signal.json") == (
        "bucket",
        "path/latest_signal.json",
    )

    with pytest.raises(ValueError, match="Invalid cloud storage URI"):
        parse_cloud_uri("gs://bucket")

    with pytest.raises(ValueError, match="Unsupported cloud storage URI"):
        parse_cloud_uri("https://example.com/latest_signal.json")


def test_cache_path_for_remote_artifact_is_stable_under_cache_dir():
    cache_dir = Path("/tmp/cache")
    first = cache_path_for_remote_artifact(
        "gs://bucket/path/latest_signal.json",
        cache_dir=cache_dir,
    )
    second = cache_path_for_remote_artifact(
        "gs://bucket/path/latest_signal.json",
        cache_dir=cache_dir,
    )

    assert first == second
    assert first.parent.parent == cache_dir
    assert first.name == "latest_signal.json"


def test_materialize_local_artifact_does_not_download():
    local_path, metadata = materialize_local_or_remote_artifact(
        "~/signals/latest_signal.json",
        cache_dir=Path("/tmp/cache"),
        client_factory=lambda: (_ for _ in ()).throw(AssertionError("should not download")),
    )

    assert local_path == Path("~/signals/latest_signal.json").expanduser()
    assert metadata == {
        "source_uri": None,
        "local_path": "~/signals/latest_signal.json",
    }
