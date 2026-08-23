import unittest

from quant_platform_kit.risk import build_cross_asset_snapshot, build_risk_snapshot


def _snapshot(**overrides):
    values = {
        "account_equity": 10_000.0,
        "risk_budget": 0.01,
        "effective_exposure": 0.20,
        "max_loss_estimate": 0.01,
        "drawdown_scalar": 1.0,
        "kelly_fraction": 0.20,
        "applied_fraction": 0.10,
        "circuit_state": "ACTIVE",
        "evidence_package_id": "sha256:abc",
        "expires_at": "2026-08-24T00:00:00Z",
    }
    values.update(overrides)
    return build_risk_snapshot(values)


class CrossAssetSnapshotTests(unittest.TestCase):
    def test_ready_envelope_is_no_order_and_deterministic(self):
        result = build_cross_asset_snapshot(
            {"crypto": _snapshot(), "us_equity": _snapshot()},
            as_of="2026-08-23T00:00:00Z",
            run_mode="shadow_active",
        )
        self.assertEqual(result["status"], "READY")
        self.assertTrue(result["no_order"])
        self.assertEqual(list(result["assets"]), ["crypto", "us_equity"])
        self.assertEqual(result["effective_exposure"], 0.4)

    def test_missing_or_parked_asset_is_partial_not_zero_risk(self):
        result = build_cross_asset_snapshot(
            {"cn_equity": _snapshot(), "hk_equity": _snapshot(circuit_state="TRIPPED")},
            as_of="2026-08-23",
        )
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["parked_assets"], ["hk_equity"])
        self.assertEqual(result["ready_asset_count"], 1)

    def test_rejects_live_mode(self):
        with self.assertRaises(ValueError):
            build_cross_asset_snapshot({"us_equity": _snapshot()}, as_of="today", run_mode="live")
