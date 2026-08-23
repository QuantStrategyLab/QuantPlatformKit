from __future__ import annotations

from datetime import datetime, timezone
import unittest

from quant_platform_kit.risk import RiskSnapshot, build_risk_snapshot


def _valid(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "account_equity": 10_000.0,
        "risk_budget": 0.01,
        "effective_exposure": 0.45,
        "max_loss_estimate": 0.008,
        "drawdown_scalar": 1.0,
        "kelly_fraction": 0.20,
        "applied_fraction": 0.10,
        "circuit_state": "ACTIVE",
        "evidence_package_id": "sha256:abc",
        "expires_at": "2026-08-24T00:00:00Z",
    }
    values.update(overrides)
    return values


class RiskSnapshotTests(unittest.TestCase):
    def test_valid_snapshot_is_immutable_and_serializable(self) -> None:
        snapshot = build_risk_snapshot(
            _valid(),
            now=datetime(2026, 8, 23, tzinfo=timezone.utc),
        )
        self.assertIsInstance(snapshot, RiskSnapshot)
        self.assertTrue(snapshot.is_usable)
        self.assertEqual(snapshot.to_dict()["evidence_package_id"], "sha256:abc")
        with self.assertRaises(AttributeError):
            snapshot.risk_budget = 0.5  # type: ignore[misc]

    def test_missing_provenance_fails_closed(self) -> None:
        snapshot = build_risk_snapshot(
            _valid(evidence_package_id=""),
            now=datetime(2026, 8, 23, tzinfo=timezone.utc),
        )
        self.assertEqual(snapshot.status, "PARKED")
        self.assertEqual(snapshot.risk_budget, 0.0)
        self.assertEqual(snapshot.reason_codes, ("missing_evidence_package_id",))

    def test_invalid_or_tripped_circuit_cannot_be_used(self) -> None:
        now = datetime(2026, 8, 23, tzinfo=timezone.utc)
        invalid = build_risk_snapshot(_valid(applied_fraction=0.3), now=now)
        self.assertEqual(invalid.status, "PARKED")
        tripped = build_risk_snapshot(_valid(circuit_state="TRIPPED"), now=now)
        self.assertEqual(tripped.status, "PARKED")
        self.assertEqual(tripped.reason_codes, ("circuit_tripped",))

    def test_invalid_or_expired_expiry_fails_closed(self) -> None:
        now = datetime(2026, 8, 23, tzinfo=timezone.utc)
        invalid = build_risk_snapshot(_valid(expires_at="2026-08-24"), now=now)
        self.assertEqual(invalid.status, "PARKED")
        self.assertEqual(invalid.reason_codes, ("invalid_expiry",))

        expired = build_risk_snapshot(
            _valid(expires_at="2026-08-23T00:00:00Z"),
            now=now,
        )
        self.assertEqual(expired.status, "PARKED")
        self.assertEqual(expired.risk_budget, 0.0)
        self.assertEqual(expired.reason_codes, ("expired_evidence",))

    def test_offset_expiry_is_compared_in_utc(self) -> None:
        snapshot = build_risk_snapshot(
            _valid(expires_at="2026-08-23T09:00:01+08:00"),
            now=datetime(2026, 8, 23, 1, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(snapshot.status, "READY")
