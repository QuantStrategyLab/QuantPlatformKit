"""Boundary tests for shared FUSE-2 pre-trade readback contract."""

from __future__ import annotations

import unittest

from quant_platform_kit.common.broker_new_risk_gate_helpers import (
    resolve_fuse_readback_inputs,
)
from quant_platform_kit.risk.account_new_risk_gate import (
    InjectedReconciliationSnapshot,
    NewRiskDisposition,
    evaluate_new_risk_admission,
)
from quant_platform_kit.risk.fuse_readback import (
    FuseReadbackRecord,
    evaluate_fuse_readback,
)


def _valid_record(trade_date: str = "2026-11-27", **overrides) -> FuseReadbackRecord:
    payload = {
        "trade_date": trade_date,
        "session_allowed": True,
        "session_state": "regular",
        "fuse_latched": False,
        "fuse_level": "L0",
        "blocks_orders": False,
        "blocks_eligibility": False,
        "calendar_version": "test-cal-v1",
        "spec_digest": "0" * 64,
    }
    payload.update(overrides)
    return FuseReadbackRecord(**payload)


class FuseReadbackTests(unittest.TestCase):
    def test_same_day_clean_record_allows(self) -> None:
        decision = evaluate_fuse_readback(_valid_record(), current_trade_date="2026-11-27")
        self.assertFalse(decision.blocks_new_risk)
        self.assertFalse(decision.would_block)
        self.assertEqual(decision.reason_codes, ())
        self.assertEqual(decision.effective_mode, "enforce")
        self.assertFalse(decision.stale_or_invalid)
        self.assertFalse(decision.observe_window_expired)

    def test_non_same_day_record_fails_closed_even_if_healthy(self) -> None:
        for stale_date in ("2026-11-26", "2026-11-28"):
            decision = evaluate_fuse_readback(_valid_record(stale_date), current_trade_date="2026-11-27")
            self.assertTrue(decision.blocks_new_risk)
            self.assertTrue(decision.stale_or_invalid)
            self.assertIn("FUSE_READBACK_STALE_FAIL_CLOSED", decision.reason_codes)

    def test_missing_or_malformed_record_fails_closed_for_both_input_forms(self) -> None:
        missing = evaluate_fuse_readback(None, current_trade_date="2026-11-27")
        self.assertTrue(missing.blocks_new_risk)
        self.assertIn("FUSE_READBACK_MISSING_FAIL_CLOSED", missing.reason_codes)

        bad = evaluate_fuse_readback(
            {"trade_date": "2026-11-27", "fuse_latched": "yes"},
            current_trade_date="2026-11-27",
        )
        self.assertTrue(bad.blocks_new_risk)
        self.assertIn("FUSE_READBACK_INVALID_FAIL_CLOSED", bad.reason_codes)

        # Direct construction enforces the exact same type & state invariants as from_mapping.
        with self.assertRaises(ValueError):
            FuseReadbackRecord(
                trade_date="2026-11-27",
                session_allowed="false",  # type: ignore[arg-type]
                session_state="regular",
                fuse_latched=False,
                fuse_level="L0",
                blocks_orders=False,
                blocks_eligibility=False,
            )

        with self.assertRaises(ValueError):
            FuseReadbackRecord(
                trade_date="2026-11-27",
                session_allowed=True,
                session_state="closed",
                fuse_latched=False,
                fuse_level="L0",
                blocks_orders=False,
                blocks_eligibility=False,
            )

        closed_bad = evaluate_fuse_readback(
            {
                "trade_date": "2026-11-27",
                "session_allowed": True,
                "session_state": "closed",
                "fuse_latched": False,
                "fuse_level": "L0",
                "blocks_orders": False,
                "blocks_eligibility": False,
            },
            current_trade_date="2026-11-27",
        )
        self.assertTrue(closed_bad.blocks_new_risk)
        self.assertIn("FUSE_READBACK_INVALID_FAIL_CLOSED", closed_bad.reason_codes)

    def test_session_and_latch_blocks_trigger_prohibition(self) -> None:
        decision = evaluate_fuse_readback(
            _valid_record(
                session_allowed=False,
                session_state="closed",
                fuse_latched=True,
                blocks_orders=True,
                blocks_eligibility=True,
            ),
            current_trade_date="2026-11-27",
        )
        self.assertTrue(decision.blocks_new_risk)
        self.assertEqual(
            decision.reason_codes,
            (
                "FUSE_SESSION_BLOCKED",
                "FUSE_ORDERS_BLOCKED",
                "FUSE_ELIGIBILITY_BLOCKED",
                "FUSE_LATCHED_BLOCKED",
            ),
        )

    def test_legacy_switch_off_cannot_disable_fuse_and_tighter_wins(self) -> None:
        clean_fuse_legacy_off = evaluate_fuse_readback(
            _valid_record(),
            current_trade_date="2026-11-27",
            legacy_switch_enabled=False,
        )
        self.assertTrue(clean_fuse_legacy_off.blocks_new_risk)
        self.assertTrue(clean_fuse_legacy_off.legacy_tighter_block)
        self.assertIn("LEGACY_NEW_RISK_SWITCH_DISABLED", clean_fuse_legacy_off.reason_codes)

        latched_fuse_legacy_off = evaluate_fuse_readback(
            _valid_record(fuse_latched=True),
            current_trade_date="2026-11-27",
            legacy_switch_enabled=False,
        )
        self.assertTrue(latched_fuse_legacy_off.blocks_new_risk)
        self.assertIn("FUSE_LATCHED_BLOCKED", latched_fuse_legacy_off.reason_codes)
        self.assertIn("LEGACY_NEW_RISK_SWITCH_DISABLED", latched_fuse_legacy_off.reason_codes)

    def test_observe_mode_active_and_expired_healthy_vs_latched(self) -> None:
        observed = evaluate_fuse_readback(
            _valid_record(fuse_latched=True),
            current_trade_date="2026-12-01",
            mode="observe",
            observe_until="2026-12-11",
        )
        self.assertEqual(observed.effective_mode, "observe")
        self.assertTrue(observed.would_block)
        self.assertFalse(observed.blocks_new_risk)
        self.assertIn("FUSE_LATCHED_BLOCKED", observed.reason_codes)

        # Normal expiry switches to enforce: healthy same-day record ALLOWS new risk.
        expired_clean = evaluate_fuse_readback(
            _valid_record(trade_date="2026-12-12"),
            current_trade_date="2026-12-12",
            mode="observe",
            observe_until="2026-12-11",
        )
        self.assertEqual(expired_clean.effective_mode, "enforce")
        self.assertTrue(expired_clean.observe_window_expired)
        self.assertFalse(expired_clean.blocks_new_risk)
        self.assertEqual(expired_clean.reason_codes, ())

        # Normal expiry switches to enforce: latched record BLOCKS new risk.
        expired_latched = evaluate_fuse_readback(
            _valid_record(fuse_latched=True, trade_date="2026-12-12"),
            current_trade_date="2026-12-12",
            mode="observe",
            observe_until="2026-12-11",
        )
        self.assertEqual(expired_latched.effective_mode, "enforce")
        self.assertTrue(expired_latched.observe_window_expired)
        self.assertTrue(expired_latched.blocks_new_risk)
        self.assertIn("FUSE_LATCHED_BLOCKED", expired_latched.reason_codes)

    def test_account_new_risk_gate_integrates_fuse_enabled_even_when_data_missing(self) -> None:
        # Configured FUSE caller with missing readback & missing trade date still fails closed.
        missing_all = InjectedReconciliationSnapshot(
            observation_status="COMPLETE",
            reconciliation_status="VERIFIED",
            circuit_breaker_state="CLOSED",
            equity_usd=40_000.0,
            **resolve_fuse_readback_inputs({}, {}, environ={"FUSE_READBACK_MODE": "enforce"}),
        )
        res_missing = evaluate_new_risk_admission(missing_all)
        self.assertEqual(res_missing.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("FUSE_READBACK_MISSING_FAIL_CLOSED", res_missing.reason_codes)

        # Stale projection carrying its own trade_date must NOT self-validate against FUSE_TRADE_DATE.
        stale_self_dated = InjectedReconciliationSnapshot(
            observation_status="COMPLETE",
            reconciliation_status="VERIFIED",
            circuit_breaker_state="CLOSED",
            equity_usd=40_000.0,
            **resolve_fuse_readback_inputs(
                {},
                {"trade_date": "2026-11-26", "fuse_readback": _valid_record("2026-11-26")},
                environ={"FUSE_READBACK_MODE": "enforce", "FUSE_TRADE_DATE": "2026-11-27"},
            ),
        )
        res_stale = evaluate_new_risk_admission(stale_self_dated)
        self.assertEqual(res_stale.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("FUSE_READBACK_STALE_FAIL_CLOSED", res_stale.reason_codes)

    def test_explicit_null_readback_fails_closed_even_without_env(self) -> None:
        null_inputs = resolve_fuse_readback_inputs({}, {"fuse_readback": None}, environ={})
        self.assertTrue(null_inputs["fuse_enabled"])
        snap = InjectedReconciliationSnapshot(
            observation_status="COMPLETE",
            reconciliation_status="VERIFIED",
            circuit_breaker_state="CLOSED",
            equity_usd=40_000.0,
            **null_inputs,
        )
        res = evaluate_new_risk_admission(snap)
        self.assertEqual(res.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertEqual(res.reason_codes, ("FUSE_READBACK_MISSING_FAIL_CLOSED",))

    def test_projection_cannot_override_trade_date_or_downgrade_enforce(self) -> None:
        # Stale projection carrying fuse_expected_trade_date, fuse_mode='observe', and an
        # active observe window must NOT override env FUSE_TRADE_DATE / FUSE_READBACK_MODE=enforce.
        inputs = resolve_fuse_readback_inputs(
            {"fuse_expected_trade_date": "2026-11-26", "metadata": {"fuse_observe_until": "2026-12-11"}},
            {
                "fuse_readback": _valid_record("2026-11-26"),
                "fuse_expected_trade_date": "2026-11-26",
                "fuse_mode": "observe",
                "fuse_observe_until": "2026-12-11",
            },
            environ={"FUSE_READBACK_MODE": "enforce", "FUSE_TRADE_DATE": "2026-11-27"},
        )
        self.assertEqual(inputs["fuse_mode"], "enforce")
        self.assertEqual(inputs["fuse_trade_date"], "2026-11-27")
        self.assertIsNone(inputs["fuse_observe_until"])
        snap = InjectedReconciliationSnapshot(
            observation_status="COMPLETE",
            reconciliation_status="VERIFIED",
            circuit_breaker_state="CLOSED",
            equity_usd=40_000.0,
            **inputs,
        )
        res = evaluate_new_risk_admission(snap)
        self.assertEqual(res.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("FUSE_READBACK_STALE_FAIL_CLOSED", res.reason_codes)

    def test_resolve_fuse_readback_inputs_preserves_explicit_invalid_mode_and_separates_observe_reasons(self) -> None:
        inputs = resolve_fuse_readback_inputs(
            {},
            {"fuse_readback": _valid_record()},
            mode=False,
            observe_until="2026-12-11",
            environ={"FUSE_READBACK_MODE": "observe", "FUSE_TRADE_DATE": "2026-11-27"},
        )
        self.assertIs(inputs["fuse_mode"], False)
        self.assertEqual(inputs["fuse_trade_date"], "2026-11-27")
        self.assertEqual(inputs["fuse_observe_until"], "2026-12-11")
        snap = InjectedReconciliationSnapshot(
            observation_status="COMPLETE",
            reconciliation_status="VERIFIED",
            circuit_breaker_state="CLOSED",
            equity_usd=40_000.0,
            **inputs,
        )
        res = evaluate_new_risk_admission(snap)
        self.assertEqual(res.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("FUSE_READBACK_MODE_INVALID_FAIL_CLOSED", res.reason_codes)

        # In observe mode with legacy switch disabled, account-level reason_codes only carry
        # LEGACY_NEW_RISK_SWITCH_DISABLED while fuse_decision preserves FUSE observation diagnostics.
        obs_snap = InjectedReconciliationSnapshot(
            observation_status="COMPLETE",
            reconciliation_status="VERIFIED",
            circuit_breaker_state="CLOSED",
            equity_usd=40_000.0,
            legacy_new_risk_switch_enabled=False,
            **resolve_fuse_readback_inputs(
                {},
                {"fuse_readback": _valid_record("2026-11-26")},
                environ={
                    "FUSE_READBACK_MODE": "observe",
                    "FUSE_OBSERVE_UNTIL": "2026-12-11",
                    "FUSE_TRADE_DATE": "2026-11-27",
                },
            ),
        )
        obs_res = evaluate_new_risk_admission(obs_snap)
        self.assertEqual(obs_res.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertEqual(obs_res.reason_codes, ("LEGACY_NEW_RISK_SWITCH_DISABLED",))
        assert obs_res.fuse_decision is not None
        self.assertIn("FUSE_READBACK_STALE_FAIL_CLOSED", obs_res.fuse_decision.reason_codes)
