from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quant_platform_kit.common.feature_snapshot import (
    load_feature_snapshot_guarded,
)


POINTER_URI = "gs://bucket/feature/current_generation.json"


def _current_generation_fixture() -> tuple[dict[str, bytes], bytes]:
    snapshot = b"as_of,symbol,close\n2026-04-01,QQQ,500\n"
    manifest = json.dumps(
        {
            "snapshot_as_of": "2026-04-01",
            "strategy_profile": "feature_snapshot_strategy",
            "config_name": "feature_snapshot_strategy",
            "contract_version": "feature_snapshot_strategy.feature_snapshot.v1",
            "snapshot_sha256": hashlib.sha256(snapshot).hexdigest(),
            "config_sha256": "a" * 64,
        }
    ).encode("utf-8")
    objects = {
        "snapshot": snapshot,
        "manifest": manifest,
        "ranking": b"rank,symbol\n1,QQQ\n",
        "release_summary": b'{"release_status":"ready"}\n',
    }
    immutable_prefix = "gs://bucket/feature/generations/g-1"
    payload = {
        "schema": "current_generation.v1",
        "profile": "feature_snapshot_strategy",
        "generation_id": "g-1",
        "immutable_prefix": immutable_prefix,
        "snapshot_as_of": "2026-04-01",
        "objects": {
            name: {
                "basename": f"{name}.json",
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            for name, data in objects.items()
        },
    }
    payload["objects"]["snapshot"]["basename"] = "feature.csv"
    payload["objects"]["manifest"]["basename"] = "feature.manifest.json"
    payload["objects"]["ranking"]["basename"] = "ranking.csv"
    payload["objects"]["release_summary"]["basename"] = "release_status_summary.json"
    pointer = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    remote_objects = {
        POINTER_URI: pointer,
        **{
            f"{immutable_prefix}/{item['basename']}": objects[name]
            for name, item in payload["objects"].items()
        },
    }
    return remote_objects, pointer


class FeatureSnapshotCurrentGenerationReaderTests(unittest.TestCase):
    def test_reader_dereferences_and_verifies_all_objects_before_guarded_load(self) -> None:
        remote_objects, _ = _current_generation_fixture()
        downloads: list[str] = []

        def download(uri: str, destination: Path) -> None:
            downloads.append(uri)
            destination.write_bytes(remote_objects[uri])

        with patch(
            "quant_platform_kit.common.feature_snapshot._download_remote_object",
            side_effect=download,
        ), patch(
            "quant_platform_kit.common.feature_snapshot._download_gcs_object",
            side_effect=download,
        ):
            result = load_feature_snapshot_guarded(
                POINTER_URI,
                run_as_of="2026-04-02",
                required_columns=("as_of", "symbol", "close"),
                manifest_path=POINTER_URI,
                require_manifest=True,
                expected_strategy_profile="feature_snapshot_strategy",
                expected_config_name="feature_snapshot_strategy",
            )

        self.assertIsNotNone(result.frame)
        self.assertEqual(
            downloads,
            [
                POINTER_URI,
                "gs://bucket/feature/generations/g-1/feature.csv",
                "gs://bucket/feature/generations/g-1/feature.manifest.json",
                "gs://bucket/feature/generations/g-1/ranking.csv",
                "gs://bucket/feature/generations/g-1/release_status_summary.json",
            ],
        )
        self.assertEqual(result.metadata["feature_snapshot_pointer_uri"], POINTER_URI)
        self.assertEqual(result.metadata["feature_snapshot_generation_id"], "g-1")
        self.assertEqual(
            result.metadata["feature_snapshot_immutable_prefix"],
            "gs://bucket/feature/generations/g-1",
        )
        self.assertEqual(
            result.metadata["feature_snapshot_object_digests"],
            {
                name: hashlib.sha256(data).hexdigest()
                for name, data in {
                    "snapshot": remote_objects[
                        "gs://bucket/feature/generations/g-1/feature.csv"
                    ],
                    "manifest": remote_objects[
                        "gs://bucket/feature/generations/g-1/feature.manifest.json"
                    ],
                    "ranking": remote_objects[
                        "gs://bucket/feature/generations/g-1/ranking.csv"
                    ],
                    "release_summary": remote_objects[
                        "gs://bucket/feature/generations/g-1/release_status_summary.json"
                    ],
                }.items()
            },
        )

    def test_reader_rejects_non_pointer_manifest_path_without_download(self) -> None:
        remote_objects, _ = _current_generation_fixture()
        downloads: list[str] = []

        def download(uri: str, destination: Path) -> None:
            downloads.append(uri)
            destination.write_bytes(remote_objects[uri])

        with patch(
            "quant_platform_kit.common.feature_snapshot._download_remote_object",
            side_effect=download,
        ), patch(
            "quant_platform_kit.common.feature_snapshot._download_gcs_object",
            side_effect=download,
        ):
            result = load_feature_snapshot_guarded(
                POINTER_URI,
                run_as_of="2026-04-02",
                manifest_path="gs://bucket/feature/other.manifest.json",
            )

        self.assertIsNone(result.frame)
        self.assertEqual(result.metadata["snapshot_guard_decision"], "fail_closed")
        self.assertEqual(result.metadata["fail_reason"], "feature_snapshot_pointer_manifest_mismatch")
        self.assertEqual(downloads, [])

    def test_reader_rejects_noncanonical_pointer_and_bad_contract_without_object_download(self) -> None:
        remote_objects, canonical = _current_generation_fixture()
        payload = json.loads(canonical)
        bad_digest_payload = json.loads(canonical)
        bad_digest_payload["objects"]["snapshot"]["sha256"] = "0" * 64
        cases = {
            "noncanonical": json.dumps(payload).encode(),
            "unknown_field": canonical.replace(b'"schema"', b'"extra":1,"schema"'),
            "path_traversal": canonical.replace(b'feature.csv', b'../feature.csv'),
            "absolute_path": canonical.replace(b'feature.csv', b'/tmp/feature.csv'),
            "wrong_prefix": canonical.replace(
                b"gs://bucket/feature/generations/g-1",
                b"gs://bucket/other/generations/g-1",
            ),
            "wrong_digest": json.dumps(
                bad_digest_payload, sort_keys=True, separators=(",", ":")
            ).encode()
            + b"\n",
        }
        for name, pointer in cases.items():
            with self.subTest(name=name):
                downloads: list[str] = []
                remote_objects[POINTER_URI] = pointer

                def download(uri: str, destination: Path) -> None:
                    downloads.append(uri)
                    destination.write_bytes(remote_objects[uri])

                with patch(
                    "quant_platform_kit.common.feature_snapshot._download_remote_object",
                    side_effect=download,
                ), patch(
                    "quant_platform_kit.common.feature_snapshot._download_gcs_object",
                    side_effect=download,
                ):
                    result = load_feature_snapshot_guarded(
                        POINTER_URI,
                        run_as_of="2026-04-02",
                        manifest_path=POINTER_URI,
                        require_manifest=True,
                    )

                self.assertIsNone(result.frame)
                self.assertEqual(result.metadata["snapshot_guard_decision"], "fail_closed")
                expected_downloads = [POINTER_URI]
                if name == "wrong_digest":
                    expected_downloads.append(
                        "gs://bucket/feature/generations/g-1/feature.csv"
                    )
                self.assertEqual(downloads, expected_downloads)
                remote_objects[POINTER_URI] = canonical

    def test_reader_rejects_downloaded_object_digest_mismatch_without_guarded_load(self) -> None:
        remote_objects, _ = _current_generation_fixture()
        remote_objects["gs://bucket/feature/generations/g-1/feature.csv"] = b"tampered"
        downloads: list[str] = []

        def download(uri: str, destination: Path) -> None:
            downloads.append(uri)
            destination.write_bytes(remote_objects[uri])

        with patch(
            "quant_platform_kit.common.feature_snapshot._download_remote_object",
            side_effect=download,
        ):
            result = load_feature_snapshot_guarded(
                POINTER_URI,
                run_as_of="2026-04-02",
                manifest_path=POINTER_URI,
                require_manifest=True,
            )

        self.assertIsNone(result.frame)
        self.assertEqual(result.metadata["snapshot_guard_decision"], "fail_closed")
        self.assertEqual(
            result.metadata["fail_reason"],
            "feature_snapshot_pointer_object_digest_mismatch",
        )
        self.assertEqual(
            downloads,
            [
                POINTER_URI,
                "gs://bucket/feature/generations/g-1/feature.csv",
            ],
        )

    def test_reader_binds_pointer_profile_to_expected_profile(self) -> None:
        remote_objects, canonical = _current_generation_fixture()
        payload = json.loads(canonical)
        payload["profile"] = "other_profile"
        remote_objects[POINTER_URI] = (
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        )
        downloads: list[str] = []

        def download(uri: str, destination: Path) -> None:
            downloads.append(uri)
            destination.write_bytes(remote_objects[uri])

        with patch(
            "quant_platform_kit.common.feature_snapshot._download_remote_object",
            side_effect=download,
        ):
            result = load_feature_snapshot_guarded(
                POINTER_URI,
                run_as_of="2026-04-02",
                manifest_path=POINTER_URI,
                expected_strategy_profile="feature_snapshot_strategy",
            )

        self.assertIsNone(result.frame)
        self.assertEqual(result.metadata["snapshot_guard_decision"], "fail_closed")
        self.assertEqual(result.metadata["fail_reason"], "feature_snapshot_pointer_read_failed")
        self.assertEqual(downloads, [POINTER_URI])

    def test_reader_binds_pointer_profile_to_manifest_without_caller_expectation(self) -> None:
        remote_objects, canonical = _current_generation_fixture()
        payload = json.loads(canonical)
        payload["profile"] = "other_profile"
        remote_objects[POINTER_URI] = (
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        )

        def download(uri: str, destination: Path) -> None:
            destination.write_bytes(remote_objects[uri])

        with patch(
            "quant_platform_kit.common.feature_snapshot._download_gcs_object",
            side_effect=download,
        ):
            result = load_feature_snapshot_guarded(
                POINTER_URI,
                run_as_of="2026-04-02",
                manifest_path=POINTER_URI,
                require_manifest=True,
            )

        self.assertIsNone(result.frame)
        self.assertEqual(result.metadata["snapshot_guard_decision"], "fail_closed")
        self.assertEqual(result.metadata["fail_reason"], "feature_snapshot_pointer_guard_failed")

    def test_pointer_failure_bypasses_last_valid_fallback(self) -> None:
        remote_objects, _ = _current_generation_fixture()
        remote_objects[POINTER_URI] = b"{}\n"

        def download(uri: str, destination: Path) -> None:
            destination.write_bytes(remote_objects[uri])

        with patch(
            "quant_platform_kit.common.feature_snapshot._download_remote_object",
            side_effect=download,
        ), patch(
            "quant_platform_kit.common.feature_snapshot._feature_snapshot_fallback_context",
            side_effect=AssertionError("pointer must bypass fallback context"),
        ), patch(
            "quant_platform_kit.common.feature_snapshot._load_feature_snapshot_last_valid",
            side_effect=AssertionError("pointer must bypass fallback read"),
        ):
            result = load_feature_snapshot_guarded(
                POINTER_URI,
                run_as_of="2026-04-02",
                manifest_path=POINTER_URI,
                fallback_mode="last_valid",
            )

        self.assertIsNone(result.frame)
        self.assertEqual(result.metadata["snapshot_guard_decision"], "fail_closed")

    def test_pointer_success_does_not_write_last_valid_fallback(self) -> None:
        remote_objects, _ = _current_generation_fixture()

        def download(uri: str, destination: Path) -> None:
            destination.write_bytes(remote_objects[uri])

        with patch(
            "quant_platform_kit.common.feature_snapshot._download_remote_object",
            side_effect=download,
        ), patch(
            "quant_platform_kit.common.feature_snapshot._feature_snapshot_fallback_context",
            side_effect=AssertionError("pointer must bypass fallback context"),
        ), patch(
            "quant_platform_kit.common.feature_snapshot._write_feature_snapshot_last_valid",
            side_effect=AssertionError("pointer must not write fallback"),
        ), patch(
            "quant_platform_kit.common.feature_snapshot._load_feature_snapshot_last_valid",
            side_effect=AssertionError("pointer must not read fallback"),
        ):
            result = load_feature_snapshot_guarded(
                POINTER_URI,
                run_as_of="2026-04-02",
                manifest_path=POINTER_URI,
                require_manifest=True,
                fallback_mode="last_valid",
            )

        self.assertIsNotNone(result.frame)


class FeatureSnapshotGuardAliasTests(unittest.TestCase):
    def test_guard_rejects_retired_strategy_profile_alias_in_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            snapshot_path = tmp_path / "snapshot.csv"
            manifest_path = tmp_path / "snapshot.csv.manifest.json"
            snapshot_path.write_text(
                "as_of,symbol,close\n2026-04-01,QQQ,500\n",
                encoding="utf-8",
            )
            snapshot_sha256 = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
            manifest_path.write_text(
                json.dumps(
                    {
                        "snapshot_as_of": "2026-04-01",
                        "strategy_profile": "tech_pullback_cash_buffer",
                        "config_name": "tech_pullback_cash_buffer",
                        "contract_version": "tech_pullback_cash_buffer.feature_snapshot.v1",
                        "snapshot_sha256": snapshot_sha256,
                        "config_sha256": "abc",
                        "price_as_of": "2026-04-01",
                        "universe_as_of": "2026-03-31",
                        "source_input_status": "fresh",
                        "source_input_fallback_used": False,
                        "source_refresh_run_id": "12345",
                    }
                ),
                encoding="utf-8",
            )

            result = load_feature_snapshot_guarded(
                str(snapshot_path),
                run_as_of="2026-04-02",
                required_columns=("as_of", "symbol", "close"),
                manifest_path=str(manifest_path),
                require_manifest=True,
                expected_strategy_profile="qqq_tech_enhancement",
                expected_config_name="qqq_tech_enhancement",
            )

            self.assertIsNone(result.frame)
            self.assertEqual(result.metadata["snapshot_guard_decision"], "fail_closed")
            self.assertEqual(result.metadata["snapshot_manifest_strategy_profile"], "tech_pullback_cash_buffer")
            self.assertIn(
                "feature_snapshot_manifest_strategy_profile_mismatch",
                str(result.metadata["fail_reason"]),
            )

    def test_guard_includes_manifest_diagnostics_when_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            snapshot_path = tmp_path / "snapshot.csv"
            manifest_path = tmp_path / "snapshot.csv.manifest.json"
            snapshot_path.write_text(
                "as_of,symbol,close\n2026-04-01,QQQ,500\n",
                encoding="utf-8",
            )
            snapshot_sha256 = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
            manifest_path.write_text(
                json.dumps(
                    {
                        "snapshot_as_of": "2026-04-01",
                        "strategy_profile": "feature_snapshot_strategy",
                        "config_name": "feature_snapshot_strategy",
                        "contract_version": "feature_snapshot_strategy.feature_snapshot.v1",
                        "snapshot_sha256": snapshot_sha256,
                        "config_sha256": "abc",
                        "price_as_of": "2026-04-01",
                        "universe_as_of": "2026-03-31",
                        "source_input_status": "universe_fallback",
                        "source_input_fallback_used": True,
                        "source_input_fallback_reason": "RuntimeError: upstream returned HTML",
                        "source_input_fallback_streak": 1,
                    }
                ),
                encoding="utf-8",
            )

            result = load_feature_snapshot_guarded(
                str(snapshot_path),
                run_as_of="2026-06-01",
                required_columns=("as_of", "symbol", "close"),
                manifest_path=str(manifest_path),
                require_manifest=True,
                expected_strategy_profile="feature_snapshot_strategy",
                expected_config_name="feature_snapshot_strategy",
            )

            self.assertIsNone(result.frame)
            self.assertEqual(result.metadata["snapshot_guard_decision"], "fail_closed")
            self.assertEqual(result.metadata["snapshot_manifest_source_input_status"], "universe_fallback")
            self.assertIs(result.metadata["snapshot_manifest_source_input_fallback_used"], True)
            self.assertEqual(result.metadata["snapshot_manifest_source_input_fallback_streak"], 1)

    def test_guard_uses_last_valid_snapshot_when_current_source_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            cache_dir = tmp_path / "fallback-cache"
            snapshot_path = tmp_path / "snapshot.csv"
            manifest_path = tmp_path / "snapshot.csv.manifest.json"
            config_path = tmp_path / "config.json"
            snapshot_path.write_text(
                "as_of,symbol,close\n2026-04-01,QQQ,500\n",
                encoding="utf-8",
            )
            config_path.write_text('{"name": "feature_snapshot_strategy"}', encoding="utf-8")
            snapshot_sha256 = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
            config_sha256 = hashlib.sha256(config_path.read_bytes()).hexdigest()
            manifest_path.write_text(
                json.dumps(
                    {
                        "snapshot_as_of": "2026-04-01",
                        "strategy_profile": "feature_snapshot_strategy",
                        "config_name": "feature_snapshot_strategy",
                        "contract_version": "feature_snapshot_strategy.feature_snapshot.v1",
                        "snapshot_sha256": snapshot_sha256,
                        "config_sha256": config_sha256,
                    }
                ),
                encoding="utf-8",
            )

            first_result = load_feature_snapshot_guarded(
                str(snapshot_path),
                run_as_of="2026-04-02",
                required_columns=("as_of", "symbol", "close"),
                manifest_path=str(manifest_path),
                require_manifest=True,
                expected_strategy_profile="feature_snapshot_strategy",
                expected_config_name="feature_snapshot_strategy",
                expected_config_path=str(config_path),
                expected_contract_version="feature_snapshot_strategy.feature_snapshot.v1",
                fallback_mode="last_valid",
                fallback_cache_dir=cache_dir,
            )
            snapshot_path.unlink()
            manifest_path.unlink()

            fallback_result = load_feature_snapshot_guarded(
                str(snapshot_path),
                run_as_of="2026-04-02",
                required_columns=("as_of", "symbol", "close"),
                manifest_path=str(manifest_path),
                require_manifest=True,
                expected_strategy_profile="feature_snapshot_strategy",
                expected_config_name="feature_snapshot_strategy",
                expected_config_path=str(config_path),
                expected_contract_version="feature_snapshot_strategy.feature_snapshot.v1",
                fallback_mode="last_valid",
                fallback_cache_dir=cache_dir,
            )

            self.assertIsNotNone(first_result.frame)
            self.assertIsNotNone(fallback_result.frame)
            self.assertEqual(fallback_result.metadata["snapshot_guard_decision"], "proceed")
            self.assertIs(fallback_result.metadata["artifact_fallback_used"], True)
            self.assertEqual(fallback_result.metadata["artifact_fallback_mode"], "last_valid")
            self.assertIn("feature_snapshot_missing", fallback_result.metadata["artifact_fallback_reason"])


if __name__ == "__main__":
    unittest.main()
