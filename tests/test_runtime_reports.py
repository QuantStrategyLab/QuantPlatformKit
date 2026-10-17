from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from types import MappingProxyType
import unittest
from unittest.mock import patch

import pytest

from quant_platform_kit.common.runtime_reports import (
    RUNTIME_REPORT_SCHEMA_VERSION,
    append_runtime_report_error,
    build_runtime_report_cloud_uri,
    build_runtime_report_base,
    default_runtime_report_path,
    finalize_runtime_report,
    persist_runtime_report,
    runtime_report_relative_path,
    write_runtime_report_json,
)


class FakeObjectStore:
    def __init__(self):
        self.last_uri = None
        self.last_payload = None
        self.last_content_type = None

    def write_text(self, uri: str, data: str, content_type: str = "text/plain") -> str:
        self.last_uri = uri
        self.last_payload = data
        self.last_content_type = content_type
        return uri

    def read_text(self, uri: str) -> str:
        return self.last_payload or ""

    def read_bytes(self, uri: str) -> bytes:
        return (self.last_payload or "").encode("utf-8")

    def exists(self, uri: str) -> bool:
        return True

    def list(self, prefix: str) -> list[str]:
        return []


class RuntimeReportsTests(unittest.TestCase):
    def test_build_runtime_report_base_sets_shared_fields(self) -> None:
        report = build_runtime_report_base(
            platform="charles_schwab",
            deploy_target="cloud_run",
            service_name="schwab-runtime",
            strategy_profile="tqqq_growth_income",
            strategy_domain="us_equity",
            run_id="run-001",
            run_source="cloud_run",
            runtime_target={"platform_id": "charles_schwab", "strategy_profile": "tqqq_growth_income"},
            account_region="US",
            started_at=datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc),
            summary={"managed_symbols": ("TQQQ", "BOXX")},
        )

        self.assertEqual(report["schema_version"], RUNTIME_REPORT_SCHEMA_VERSION)
        self.assertEqual(report["platform"], "charles_schwab")
        self.assertEqual(report["runtime_target"]["platform_id"], "charles_schwab")
        self.assertEqual(report["account_scope"], "US")
        self.assertEqual(report["status"], "started")
        self.assertEqual(report["summary"]["managed_symbols"], ["TQQQ", "BOXX"])
        self.assertTrue(report["started_at"].endswith("Z"))
        self.assertEqual(
            report["runtime_release_receipt"]["attestation_state"],
            "legacy_unattested",
        )

    def test_runtime_report_self_attests_complete_strategy_release_identity(self) -> None:
        digest = "b" * 64
        report = build_runtime_report_base(
            platform="longbridge",
            deploy_target="cloud_run",
            service_name="longbridge-runtime",
            strategy_profile="soxl_soxx_trend_income",
            run_id="run-release-001",
            run_source="cloud_run",
            runtime_target={
                "strategy_release": {
                    "release_id": "soxl-p2-v3.20260824",
                    "manifest_sha256": digest,
                    "strategy_revision": "2e3bb51",
                    "config_sha256": digest,
                    "risk_policy_sha256": digest,
                    "evidence_sha256": digest,
                    "plugin_bundle_sha256": digest,
                    "effective_session": "2026-08-25",
                }
            },
            started_at="2026-08-24T01:00:00Z",
            runtime_revision="longbridge-00042-abc",
        )

        receipt = report["runtime_release_receipt"]
        self.assertEqual(receipt["attestation_state"], "self_attested")
        self.assertEqual(receipt["release_id"], "soxl-p2-v3.20260824")
        self.assertEqual(receipt["runtime_revision"], "longbridge-00042-abc")

    def test_finalize_and_write_runtime_report(self) -> None:
        report = build_runtime_report_base(
            platform="binance",
            deploy_target="vps",
            service_name="binance-runtime",
            strategy_profile="crypto_leader_rotation",
            strategy_domain="crypto",
            run_id="run-002",
            run_source="github_actions",
        )
        append_runtime_report_error(
            report,
            stage="execute_cycle",
            message="example failure",
            error_type="RuntimeError",
        )
        finalize_runtime_report(
            report,
            status="error",
            diagnostics={"degraded_mode_level": "firestore_stale"},
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = default_runtime_report_path(report, base_dir=tmp_dir)
            write_runtime_report_json(report, output_path=output_path)
            payload = output_path.read_text(encoding="utf-8")

        self.assertEqual(report["status"], "error")
        self.assertEqual(report["errors"][0]["error_type"], "RuntimeError")
        self.assertIn("degraded_mode_level", report["diagnostics"])
        self.assertIn("\"schema_version\": \"runtime_report.v1\"", payload)

    def test_runtime_report_relative_path_matches_expected_layout(self) -> None:
        report = build_runtime_report_base(
            platform="longbridge",
            deploy_target="cloud_run",
            service_name="longbridge-runtime",
            strategy_profile="soxl_soxx_trend_income",
            strategy_domain="us_equity",
            account_scope="HK",
            run_id="run-003",
            run_source="cloud_run",
            started_at="2026-04-08T00:00:00Z",
        )

        self.assertEqual(
            runtime_report_relative_path(report).as_posix(),
            "longbridge/soxl_soxx_trend_income/HK/2026-04/run-003.json",
        )

    def test_build_runtime_report_cloud_uri_uses_relative_layout(self) -> None:
        report = build_runtime_report_base(
            platform="interactive_brokers",
            deploy_target="cloud_run",
            service_name="ibkr-runtime",
            strategy_profile="global_etf_rotation",
            strategy_domain="us_equity",
            account_group="paper",
            run_id="run-004",
            run_source="cloud_run",
            started_at="2026-04-08T00:00:00Z",
        )

        uri = build_runtime_report_cloud_uri(
            report,
            cloud_prefix_uri="gs://demo-bucket/runtime-reports",
        )

        self.assertEqual(
            uri,
            "gs://demo-bucket/runtime-reports/interactive_brokers/global_etf_rotation/paper/2026-04/run-004.json",
        )

    @patch("quant_platform_kit.cloud.get_object_store")
    def test_persist_runtime_report_writes_local_and_uploads_cloud(self, mock_get_store) -> None:
        report = build_runtime_report_base(
            platform="charles_schwab",
            deploy_target="cloud_run",
            service_name="schwab-runtime",
            strategy_profile="tqqq_growth_income",
            strategy_domain="us_equity",
            run_id="run-005",
            run_source="cloud_run",
            started_at=datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc),
        )

        fake_store = FakeObjectStore()
        mock_get_store.return_value = fake_store

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = persist_runtime_report(
                report,
                base_dir=tmp_dir,
                cloud_prefix_uri="gs://demo-bucket/runtime-reports",
                project_id="demo-project",
            )
            payload = json.loads(
                default_runtime_report_path(report, base_dir=tmp_dir).read_text(encoding="utf-8")
            )

        expected_uri = "gs://demo-bucket/runtime-reports/charles_schwab/tqqq_growth_income/2026-04/run-005.json"
        self.assertEqual(result.local_path, str(default_runtime_report_path(report, base_dir=tmp_dir)))
        self.assertEqual(result.cloud_uri, expected_uri)
        self.assertEqual(payload["artifacts"]["runtime_report_cloud_uri"], result.cloud_uri)
        self.assertEqual(payload["artifacts"]["runtime_report_local_path"], result.local_path)
        self.assertEqual(fake_store.last_uri, expected_uri)
        uploaded_payload = json.loads(fake_store.last_payload)
        self.assertEqual(uploaded_payload["artifacts"]["runtime_report_cloud_uri"], result.cloud_uri)
        self.assertEqual(
            fake_store.last_content_type,
            "application/json",
        )


@pytest.mark.parametrize("cloud", [False, True], ids=["local", "fake_cloud"])
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"transactions": [], "source_complete": True}, {"transactions": [], "source_complete": True}),
        ({"transactions": [], "source_complete": False}, {"transactions": [], "source_complete": False}),
        ({"source_complete": True}, {"source_complete": True}),
        ({"transactions": None, "source_complete": True}, {"source_complete": True}),
        ({"transactions": (), "source_complete": True}, {"source_complete": True}),
        ({"transactions": {}, "source_complete": True}, {"source_complete": True}),
        ({"transactions": False, "source_complete": False}, {"transactions": False, "source_complete": False}),
        ({"transactions": 0, "source_complete": False}, {"transactions": 0, "source_complete": False}),
        (
            {"transactions": [{"amount": "12.34", "optional": None}], "source_complete": False},
            {"transactions": [{"amount": "12.34"}], "source_complete": False},
        ),
    ],
    ids=["empty_true", "empty_false", "missing", "null", "tuple", "dict", "false", "zero", "nonempty"],
)
def test_raw_external_flows_survive_repeated_persist_boundaries(tmp_path, raw, expected, cloud):
    report = build_runtime_report_base(
        platform="synthetic", deploy_target="offline", service_name="test-runtime",
        strategy_profile="test-profile", run_id="raw-roundtrip", run_source="test",
        started_at="2026-10-17T00:00:00Z",
    )
    report["account_external_flows"] = deepcopy(raw)
    original = deepcopy(report)
    fake_store = FakeObjectStore()
    writes = []

    def capture_write(value, *, output_path):
        path = write_runtime_report_json(value, output_path=output_path)
        writes.append(json.loads(path.read_text(encoding="utf-8")))
        return path

    with patch("quant_platform_kit.cloud.get_object_store", return_value=fake_store) as get_store:
        with patch("quant_platform_kit.common.runtime_reports.write_runtime_report_json", side_effect=capture_write):
            for _ in range(3):
                input_raw = deepcopy(report["account_external_flows"])
                first_write = len(writes)
                result = persist_runtime_report(
                    report, output_path=tmp_path / "report.json",
                    cloud_prefix_uri="gs://demo-bucket/reports" if cloud else None,
                )
                back = json.loads(Path(result.local_path).read_text(encoding="utf-8"))
                assert report["account_external_flows"] == input_raw
                assert len(writes) - first_write == (2 if cloud else 1)
                for written in writes[first_write:]:
                    assert written["account_external_flows"] == expected
                assert back["account_external_flows"] == expected
                assert back["account_external_flows"]["source_complete"] is raw["source_complete"]
                if cloud:
                    assert json.loads(fake_store.last_payload) == back
                    assert result.cloud_uri == fake_store.last_uri
                    assert fake_store.last_content_type == "application/json"
                else:
                    assert result.cloud_uri is None
                report = back
        assert get_store.call_count == (3 if cloud else 0)
    assert original["account_external_flows"] == raw


@pytest.mark.parametrize("schema", [None, "other.v1", RUNTIME_REPORT_SCHEMA_VERSION])
def test_empty_flow_retention_is_schema_qualified_and_root_only(tmp_path, schema):
    raw = {"transactions": [], "source_complete": False}
    nested = {"schema_version": RUNTIME_REPORT_SCHEMA_VERSION, "account_external_flows": raw}
    report = {"account_external_flows": raw, "summary": deepcopy(nested),
              "diagnostics": deepcopy(nested), "context": deepcopy(nested)}
    if schema is not None:
        report["schema_version"] = schema
    original = deepcopy(report)
    path = write_runtime_report_json(report, output_path=tmp_path / "scoped.json")
    back = json.loads(path.read_text(encoding="utf-8"))
    expected = {"source_complete": False}
    if schema == RUNTIME_REPORT_SCHEMA_VERSION:
        expected["transactions"] = []
    assert back["account_external_flows"] == expected
    for section in ("summary", "diagnostics", "context"):
        assert back[section]["account_external_flows"] == {"source_complete": False}
    assert report == original


def test_empty_flow_retention_accepts_mapping_without_mutation(tmp_path):
    raw = {"transactions": []}
    report = {"schema_version": RUNTIME_REPORT_SCHEMA_VERSION,
              "account_external_flows": MappingProxyType(raw)}
    path = write_runtime_report_json(report, output_path=tmp_path / "mapping.json")
    assert json.loads(path.read_text(encoding="utf-8"))["account_external_flows"] == raw
    assert raw == {"transactions": []}


@pytest.mark.parametrize("raw", [None, [], (), False, 0])
def test_non_mapping_flow_values_keep_default_normalization(tmp_path, raw):
    report = {"schema_version": RUNTIME_REPORT_SCHEMA_VERSION, "account_external_flows": raw}
    path = write_runtime_report_json(report, output_path=tmp_path / "non_mapping.json")
    assert json.loads(path.read_text(encoding="utf-8"))["account_external_flows"] == ([] if raw == () else raw)


def test_unrelated_cleanup_and_top_level_values_keep_default_json(tmp_path):
    report = {
        "schema_version": RUNTIME_REPORT_SCHEMA_VERSION, "runtime_target": {}, "errors": [],
        "top_null": None, "top_blank": " ", "top_tuple": (),
        "summary": {"none": None, "blank": " ", "list": [], "tuple": (), "dict": {},
                    "false": False, "zero": 0, "symbols": ("SYNTH",), "path": Path("sample"),
                    "time": datetime(2026, 10, 17, tzinfo=timezone.utc), "items": [None, "", {}, []]},
        "diagnostics": {"none": None, "empty": [], "false": False},
    }
    original = deepcopy(report)
    path = write_runtime_report_json(report, output_path=tmp_path / "defaults.json")
    expected = {
        "schema_version": RUNTIME_REPORT_SCHEMA_VERSION, "runtime_target": {}, "errors": [],
        "top_null": None, "top_blank": " ", "top_tuple": [],
        "summary": {"false": False, "zero": 0, "symbols": ["SYNTH"], "path": "sample",
                    "time": "2026-10-17T00:00:00Z", "items": [None, "", {}, []]},
        "diagnostics": {"false": False},
    }
    assert path.read_text(encoding="utf-8") == json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True)
    assert report == original
