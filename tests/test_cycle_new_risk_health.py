import unittest

from quant_platform_kit.risk.cycle_new_risk_health import (
    CycleNewRiskHealthEvidence,
    apply_cycle_new_risk_health_axes,
    project_cycle_new_risk_health_axes,
)


class CycleNewRiskHealthTests(unittest.TestCase):
    def test_healthy_cycle_without_digests_allows_axes(self) -> None:
        axes = project_cycle_new_risk_health_axes(
            CycleNewRiskHealthEvidence(observation_ok=True)
        )
        self.assertEqual(axes["observation_status"], "COMPLETE")
        self.assertEqual(axes["reconciliation_status"], "VERIFIED")
        self.assertEqual(axes["circuit_breaker_state"], "CLOSED")

    def test_missing_observation_stays_fail_closed(self) -> None:
        axes = project_cycle_new_risk_health_axes(
            CycleNewRiskHealthEvidence(observation_ok=False)
        )
        self.assertEqual(axes["observation_status"], "UNAVAILABLE")
        self.assertEqual(axes["reconciliation_status"], "UNVERIFIED")
        self.assertEqual(axes["circuit_breaker_state"], "CLOSED")

    def test_unknown_pending_unverifies_and_opens_breaker(self) -> None:
        axes = project_cycle_new_risk_health_axes(
            CycleNewRiskHealthEvidence(observation_ok=True, unknown_pending=True)
        )
        self.assertEqual(axes["reconciliation_status"], "UNVERIFIED")
        self.assertEqual(axes["circuit_breaker_state"], "OPEN")

    def test_digests_configured_require_match_for_verified(self) -> None:
        bad = project_cycle_new_risk_health_axes(
            CycleNewRiskHealthEvidence(
                observation_ok=True,
                digests_configured=True,
                digests_verified=False,
            )
        )
        self.assertEqual(bad["reconciliation_status"], "UNVERIFIED")
        good = project_cycle_new_risk_health_axes(
            CycleNewRiskHealthEvidence(
                observation_ok=True,
                digests_configured=True,
                digests_verified=True,
            )
        )
        self.assertEqual(good["reconciliation_status"], "VERIFIED")
        self.assertEqual(good["circuit_breaker_state"], "CLOSED")

    def test_durable_open_never_auto_clears(self) -> None:
        axes = project_cycle_new_risk_health_axes(
            CycleNewRiskHealthEvidence(
                observation_ok=True,
                durable_breaker_open=True,
            )
        )
        self.assertEqual(axes["circuit_breaker_state"], "OPEN")

    def test_explicit_projection_keys_win_over_cycle_axes(self) -> None:
        merged = apply_cycle_new_risk_health_axes(
            {
                "observation_status": "STALE",
                "equity_usd": 12_345.0,
            },
            CycleNewRiskHealthEvidence(observation_ok=True),
        )
        self.assertEqual(merged["observation_status"], "STALE")
        self.assertEqual(merged["reconciliation_status"], "VERIFIED")
        self.assertEqual(merged["circuit_breaker_state"], "CLOSED")
        self.assertEqual(merged["equity_usd"], 12_345.0)


if __name__ == "__main__":
    unittest.main()
