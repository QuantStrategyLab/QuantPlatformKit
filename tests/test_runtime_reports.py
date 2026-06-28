from __future__ import annotations

from datetime import datetime, timezone
import json
import tempfile
import unittest
from unittest.mock import patch

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
