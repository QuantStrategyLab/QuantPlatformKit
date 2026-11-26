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
        "calendar_version": "csa22-v3",
        "spec_digest": "416f8eff74a1962b4432e90f10f50da043e7e54a18ce30c3d79f26a5ea268654",
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

    def test_non_same_day_record_fails_closed_even_if_healthy(self) -> None:
        for stale_date in ("2026-11-26", "2026-11-28"):
            decision = evaluate_fuse_readback(_valid_record(stale_date), current_trade_date="2026-11-27")
            self.assertTrue(decision.blocks_new_risk)
            self.assertTrue(decision.stale_or_invalid)
            self.assertIn("FUSE_READBACK_STALE_FAIL_CLOSED", decision.reason_codes)

    def test_missing_or_malformed_record_fails_closed(self) -> None:
        missing = evaluate_fuse_readback(None, current_trade_date="2026-11-27")
        self.assertTrue(missing.blocks_new_risk)
        self.assertIn("FUSE_READBACK_MISSING_FAIL_CLOSED", missing.reason_codes)

        bad = evaluate_fuse_readback({"trade_date": "2026-11-27", "fuse_latched": "yes"}, current_trade_date="2026-11-27")
        self.assertTrue(bad.blocks_new_risk)
        self.assertIn("FUSE_READBACK_INVALID_FAIL_CLOSED", bad.reason_codes)

    def test_session_and_latch_blocks_trigger_prohibition(self) -> None:
        decision = evaluate_fuse_readback(
            _valid_record(session_allowed=False, session_state="closed", fuse_latched=True, blocks_orders=True),
            current_trade_date="2026-11-27",
        )
        self.assertTrue(decision.blocks_new_risk)
        self.assertEqual(
            decision.reason_codes,
            ("FUSE_SESSION_BLOCKED", "FUSE_ORDERS_BLOCKED", "FUSE_LATCHED_BLOCKED"),
        )

    def test_legacy_switch_off_cannot_disable_fuse_and_tighter_wins(self) -> None:
        # Legacy switch False + clean FUSE -> legacy tighter block still prohibits.
        clean_fuse_legacy_off = evaluate_fuse_readback(
            _valid_record(),
            current_trade_date="2026-11-27",
            legacy_switch_enabled=False,
        )
        self.assertTrue(clean_fuse_legacy_off.blocks_new_risk)
        self.assertTrue(clean_fuse_legacy_off.legacy_tighter_block)
        self.assertIn("LEGACY_NEW_RISK_SWITCH_DISABLED", clean_fuse_legacy_off.reason_codes)

        # Legacy switch False + latched FUSE -> FUSE reasons are still preserved & enforced.
        latched_fuse_legacy_off = evaluate_fuse_readback(
            _valid_record(fuse_latched=True),
            current_trade_date="2026-11-27",
            legacy_switch_enabled=False,
        )
        self.assertTrue(latched_fuse_legacy_off.blocks_new_risk)
        self.assertIn("FUSE_LATCHED_BLOCKED", latched_fuse_legacy_off.reason_codes)
        self.assertIn("LEGACY_NEW_RISK_SWITCH_DISABLED", latched_fuse_legacy_off.reason_codes)

    def test_observe_mode_active_logs_would_block_without_fuse_enforcement_and_expires_to_enforce(self) -> None:
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

        # After 2-week observe window expires -> automatically enforces fail-closed.
        expired = evaluate_fuse_readback(
            _valid_record(fuse_latched=True, trade_date="2026-12-12"),
            current_trade_date="2026-12-12",
            mode="observe",
            observe_until="2026-12-11",
        )
        self.assertEqual(expired.effective_mode, "enforce")
        self.assertTrue(expired.blocks_new_risk)
        self.assertIn("FUSE_OBSERVE_WINDOW_EXPIRED_ENFORCED", expired.reason_codes)
        self.assertIn("FUSE_LATCHED_BLOCKED", expired.reason_codes)

    def test_account_new_risk_gate_integrates_fuse_readback(self) -> None:
        snap_blocked = InjectedReconciliationSnapshot(
            observation_status="COMPLETE",
            reconciliation_status="VERIFIED",
            circuit_breaker_state="CLOSED",
            equity_usd=40_000.0,
            fuse_readback=_valid_record(fuse_latched=True),
            fuse_trade_date="2026-11-27",
            fuse_mode="enforce",
        )
        res = evaluate_new_risk_admission(snap_blocked)
        self.assertEqual(res.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("FUSE_LATCHED_BLOCKED", res.reason_codes)
        self.assertIsNotNone(res.fuse_decision)
        self.assertTrue(res.fuse_decision.would_block)

        snap_observe = InjectedReconciliationSnapshot(
            observation_status="COMPLETE",
            reconciliation_status="VERIFIED",
            circuit_breaker_state="CLOSED",
            equity_usd=40_000.0,
            fuse_readback=_valid_record(fuse_latched=True),
            fuse_trade_date="2026-11-27",
            fuse_mode="observe",
            fuse_observe_until="2026-12-11",
        )
        obs_res = evaluate_new_risk_admission(snap_observe)
        self.assertEqual(obs_res.disposition, NewRiskDisposition.ALLOW_NEW_RISK)
        self.assertIsNotNone(obs_res.fuse_decision)
        self.assertTrue(obs_res.fuse_decision.would_block)
        self.assertEqual(obs_res.fuse_decision.reason_codes, ("FUSE_LATCHED_BLOCKED",))

        legacy_off_only = InjectedReconciliationSnapshot(
            observation_status="COMPLETE",
            reconciliation_status="VERIFIED",
            circuit_breaker_state="CLOSED",
            equity_usd=40_000.0,
            legacy_new_risk_switch_enabled=False,
        )
        legacy_off_res = evaluate_new_risk_admission(legacy_off_only)
        self.assertEqual(legacy_off_res.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("LEGACY_NEW_RISK_SWITCH_DISABLED", legacy_off_res.reason_codes)

    def test_resolve_fuse_readback_inputs_precedence(self) -> None:
        inputs = resolve_fuse_readback_inputs(
            {"metadata": {"fuse_mode": "observe", "fuse_observe_until": "2026-12-11"}},
            {"fuse_readback": _valid_record(), "trade_date": "2026-11-27"},
            environ={"FUSE_READBACK_MODE": "enforce", "FUSE_TRADE_DATE": "2026-11-26"},
        )
        self.assertEqual(inputs["fuse_trade_date"], "2026-11-27")
        self.assertEqual(inputs["fuse_mode"], "observe")
        self.assertEqual(inputs["fuse_observe_until"], "2026-12-11")
        self.assertIsNotNone(inputs["fuse_readback"])

