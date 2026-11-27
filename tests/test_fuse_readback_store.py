"""Unit tests for shared FUSE-3 external state-store readback loader."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from quant_platform_kit.common.broker_new_risk_gate_helpers import resolve_fuse_readback_inputs
from quant_platform_kit.risk.account_new_risk_gate import (
    InjectedReconciliationSnapshot,
    NewRiskDisposition,
    evaluate_new_risk_admission,
)
from quant_platform_kit.risk.fuse_readback import FuseReadbackRecord
from quant_platform_kit.risk.fuse_readback_store import (
    DEFAULT_MAX_FUSE_STATE_BYTES,
    get_fuse_readback_gcs_reader,
    load_fuse_readback_from_env,
    parse_fuse_readback_json,
    register_fuse_readback_gcs_reader,
)


def _valid_payload(trade_date: str = "2026-11-27", **overrides) -> dict:
    payload = {
        "trade_date": trade_date,
        "session_allowed": True,
        "session_state": "regular",
        "fuse_latched": False,
        "fuse_level": "L0",
        "blocks_orders": False,
        "blocks_eligibility": False,
        "calendar_version": "csa22-v2",
        "spec_digest": "a" * 64,
    }
    payload.update(overrides)
    return payload


class FuseReadbackStoreTests(unittest.TestCase):
    def test_unconfigured_env_returns_unconfigured_and_keeps_fuse_disabled(self) -> None:
        res = load_fuse_readback_from_env(environ={})
        self.assertFalse(res.configured)
        self.assertIsNone(res.record)
        self.assertIsNone(res.source_kind)
        self.assertIsNone(res.error_code)

        inputs = resolve_fuse_readback_inputs({}, {}, environ={"   ": "ignored"})
        self.assertFalse(inputs["fuse_enabled"])
        self.assertIsNone(inputs["fuse_readback"])

    def test_valid_local_file_loads_and_wires_through_resolve_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "fuse_state.json"
            state_file.write_text(json.dumps(_valid_payload()), encoding="utf-8")

            env = {
                "FUSE_READBACK_STATE_PATH": str(state_file),
                "FUSE_READBACK_EXPECTED_CALENDAR_VERSION": "csa22-v2",
                "FUSE_READBACK_EXPECTED_SPEC_DIGEST": "a" * 64,
                "FUSE_TRADE_DATE": "2026-11-27",
                "FUSE_READBACK_MODE": "enforce",
            }
            res = load_fuse_readback_from_env(environ=env)
            self.assertTrue(res.configured)
            self.assertEqual(res.source_kind, "file")
            self.assertIsNone(res.error_code)
            self.assertIsInstance(res.record, FuseReadbackRecord)

            inputs = resolve_fuse_readback_inputs({}, {}, environ=env)
            self.assertTrue(inputs["fuse_enabled"])
            self.assertEqual(inputs["fuse_readback"], res.record)

            gate = evaluate_new_risk_admission(
                InjectedReconciliationSnapshot(
                    observation_status="COMPLETE",
                    reconciliation_status="VERIFIED",
                    circuit_breaker_state="CLOSED",
                    equity_usd=50_000.0,
                    **inputs,
                ),
            )
            self.assertEqual(gate.disposition, NewRiskDisposition.ALLOW_NEW_RISK)

    def test_valid_gcs_uri_loads_via_injected_reader(self) -> None:
        seen_calls: list[tuple[str, str]] = []

        def fake_gcs_reader(bucket: str, obj: str) -> bytes:
            seen_calls.append((bucket, obj))
            return json.dumps(_valid_payload(fuse_latched=True, fuse_level="L2")).encode("utf-8")

        res = load_fuse_readback_from_env(
            environ={"FUSE_READBACK_STATE_URI": "gs://example-fuse-state/prod/latest.json"},
            gcs_reader=fake_gcs_reader,
        )
        self.assertEqual(seen_calls, [("example-fuse-state", "prod/latest.json")])
        self.assertTrue(res.configured)
        self.assertEqual(res.source_kind, "gcs")
        self.assertIsNone(res.error_code)
        assert res.record is not None
        self.assertTrue(res.record.fuse_latched)
        self.assertEqual(res.record.fuse_level, "L2")

    def test_ambiguous_path_and_uri_fails_closed(self) -> None:
        res = load_fuse_readback_from_env(
            environ={
                "FUSE_READBACK_STATE_PATH": "/tmp/does-not-matter.json",
                "FUSE_READBACK_STATE_URI": "gs://example-fuse-state/latest.json",
            }
        )
        self.assertTrue(res.configured)
        self.assertIsNone(res.record)
        self.assertEqual(res.error_code, "FUSE_STATE_SOURCE_AMBIGUOUS")

        inputs = resolve_fuse_readback_inputs(
            {},
            {},
            environ={
                "FUSE_READBACK_STATE_PATH": "/tmp/a.json",
                "FUSE_READBACK_STATE_URI": "gs://example-fuse-state/latest.json",
                "FUSE_TRADE_DATE": "2026-11-27",
            },
        )
        self.assertTrue(inputs["fuse_enabled"])
        self.assertIsNone(inputs["fuse_readback"])
        gate = evaluate_new_risk_admission(
            InjectedReconciliationSnapshot(
                observation_status="COMPLETE",
                reconciliation_status="VERIFIED",
                circuit_breaker_state="CLOSED",
                equity_usd=50_000.0,
                **inputs,
            ),
        )
        self.assertEqual(gate.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("FUSE_READBACK_MISSING_FAIL_CLOSED", gate.reason_codes)

    def test_file_errors_fail_closed(self) -> None:
        missing = load_fuse_readback_from_env(
            environ={"FUSE_READBACK_STATE_PATH": "/nonexistent/path/fuse_state.json"}
        )
        self.assertTrue(missing.configured)
        self.assertIsNone(missing.record)
        self.assertEqual(missing.error_code, "FUSE_STATE_FILE_MISSING")

        with tempfile.TemporaryDirectory() as tmpdir:
            oversized = Path(tmpdir) / "big.json"
            oversized.write_bytes(b"{" + b" " * (DEFAULT_MAX_FUSE_STATE_BYTES + 10) + b"}")
            res_big = load_fuse_readback_from_env(environ={"FUSE_READBACK_STATE_PATH": str(oversized)})
            self.assertTrue(res_big.configured)
            self.assertIsNone(res_big.record)
            self.assertEqual(res_big.error_code, "FUSE_STATE_TOO_LARGE")

            dup_json = Path(tmpdir) / "dup.json"
            dup_json.write_text('{"trade_date": "2026-11-27", "trade_date": "2026-11-27"}', encoding="utf-8")
            res_dup = load_fuse_readback_from_env(environ={"FUSE_READBACK_STATE_PATH": str(dup_json)})
            self.assertTrue(res_dup.configured)
            self.assertIsNone(res_dup.record)
            self.assertEqual(res_dup.error_code, "FUSE_STATE_DUPLICATE_JSON_KEY")

            bad_schema = Path(tmpdir) / "bad_schema.json"
            bad_schema.write_text(
                json.dumps(_valid_payload(session_allowed=True, session_state="closed")),
                encoding="utf-8",
            )
            res_schema = load_fuse_readback_from_env(environ={"FUSE_READBACK_STATE_PATH": str(bad_schema)})
            self.assertTrue(res_schema.configured)
            self.assertIsNone(res_schema.record)
            self.assertEqual(res_schema.error_code, "FUSE_READBACK_INVALID")

    def test_gcs_errors_and_invalid_uris_fail_closed(self) -> None:
        for bad_uri in (
            "https://example.com/fuse.json",
            "gs://bad_bucket/fuse.json",
            "gs://example-fuse-state/../secret.json",
            "gs://example-fuse-state/latest.json?alt=media",
            "gs://example-fuse-state/",
        ):
            res = load_fuse_readback_from_env(
                environ={"FUSE_READBACK_STATE_URI": bad_uri},
                gcs_reader=lambda b, o: json.dumps(_valid_payload()).encode("utf-8"),
            )
            self.assertTrue(res.configured)
            self.assertIsNone(res.record)
            self.assertTrue((res.error_code or "").startswith("FUSE_STATE_URI_INVALID"))

        def exploding_reader(bucket: str, obj: str) -> bytes:
            raise RuntimeError("network_down")

        res_err = load_fuse_readback_from_env(
            environ={"FUSE_READBACK_STATE_URI": "gs://example-fuse-state/latest.json"},
            gcs_reader=exploding_reader,
        )
        self.assertTrue(res_err.configured)
        self.assertIsNone(res_err.record)
        self.assertEqual(res_err.error_code, "FUSE_STATE_READ_FAILED")

    def test_unregistered_and_registered_gcs_port_behavior(self) -> None:
        previous = get_fuse_readback_gcs_reader()
        self.addCleanup(lambda: register_fuse_readback_gcs_reader(previous))

        register_fuse_readback_gcs_reader(None)
        unconfigured = load_fuse_readback_from_env(
            environ={"FUSE_READBACK_STATE_URI": "gs://example-fuse-state/latest.json"}
        )
        self.assertTrue(unconfigured.configured)
        self.assertIsNone(unconfigured.record)
        self.assertEqual(unconfigured.error_code, "FUSE_STATE_GCS_READER_UNCONFIGURED")

        register_fuse_readback_gcs_reader(
            lambda b, o: json.dumps(_valid_payload(fuse_latched=True, fuse_level="L2")).encode("utf-8")
        )
        inputs = resolve_fuse_readback_inputs(
            {},
            {},
            environ={
                "FUSE_READBACK_STATE_URI": "gs://example-fuse-state/latest.json",
                "FUSE_TRADE_DATE": "2026-11-27",
                "FUSE_READBACK_MODE": "enforce",
            },
        )
        self.assertTrue(inputs["fuse_enabled"])
        self.assertIsInstance(inputs["fuse_readback"], FuseReadbackRecord)

    def test_expected_spec_digest_and_calendar_version_mismatch_fail_closed(self) -> None:
        raw = json.dumps(_valid_payload()).encode("utf-8")
        with self.assertRaisesRegex(ValueError, "FUSE_STATE_CALENDAR_VERSION_MISMATCH"):
            parse_fuse_readback_json(raw, expected_calendar_version="csa22-v3")
        with self.assertRaisesRegex(ValueError, "FUSE_STATE_SPEC_DIGEST_MISMATCH"):
            parse_fuse_readback_json(raw, expected_spec_digest="b" * 64)

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "fuse.json"
            state_file.write_bytes(raw)
            res = load_fuse_readback_from_env(
                environ={
                    "FUSE_READBACK_STATE_PATH": str(state_file),
                    "FUSE_READBACK_EXPECTED_SPEC_DIGEST": "b" * 64,
                }
            )
            self.assertTrue(res.configured)
            self.assertIsNone(res.record)
            self.assertEqual(res.error_code, "FUSE_STATE_SPEC_DIGEST_MISMATCH")

    def test_explicit_snapshot_readback_takes_precedence_over_env_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "fuse.json"
            state_file.write_text(json.dumps(_valid_payload()), encoding="utf-8")

            env = {
                "FUSE_READBACK_STATE_PATH": str(state_file),
                "FUSE_TRADE_DATE": "2026-11-27",
            }
            explicit_none = resolve_fuse_readback_inputs({}, {"fuse_readback": None}, environ=env)
            self.assertTrue(explicit_none["fuse_enabled"])
            self.assertIsNone(explicit_none["fuse_readback"])

            override_payload = _valid_payload(fuse_latched=True, fuse_level="L3")
            explicit_override = resolve_fuse_readback_inputs(
                {}, {"fuse_readback": override_payload}, environ=env
            )
            self.assertEqual(explicit_override["fuse_readback"], override_payload)


if __name__ == "__main__":
    unittest.main()
