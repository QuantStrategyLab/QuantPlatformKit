"""Table-driven unit tests for B13-b T1–T3 (no I/O, no broker)."""

from __future__ import annotations

import unittest

from quant_platform_kit.execution_kernel import (
    ExecutionMode,
    LiveSubmitSnapshot,
    SubmissionCertainty,
    SubmissionRetrySnapshot,
    SubmissionUnknownSnapshot,
    deny_blind_retry_after_uncertain_transport,
    deny_live_submit_without_durable_identity,
    deny_new_cycle_when_submission_unknown,
)
from quant_platform_kit.execution_kernel.guards import (
    REASON_MISSING_DURABLE_IDENTITY,
    REASON_OK,
    REASON_RECONCILE_REQUIRED,
    REASON_SUBMISSION_UNCERTAIN,
)


class T1DurableIdentityTests(unittest.TestCase):
    def test_live_without_identity_denies(self) -> None:
        decision = deny_live_submit_without_durable_identity(
            LiveSubmitSnapshot(
                mode=ExecutionMode.LIVE,
                dry_run_bypass=False,
                identity_held=False,
            )
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, REASON_MISSING_DURABLE_IDENTITY)

    def test_live_with_identity_allows(self) -> None:
        decision = deny_live_submit_without_durable_identity(
            LiveSubmitSnapshot(
                mode=ExecutionMode.LIVE,
                dry_run_bypass=False,
                identity_held=True,
            )
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason_code, REASON_OK)

    def test_dry_run_without_identity_allows_guard(self) -> None:
        decision = deny_live_submit_without_durable_identity(
            LiveSubmitSnapshot(
                mode=ExecutionMode.DRY_RUN,
                dry_run_bypass=False,
                identity_held=False,
            )
        )
        self.assertTrue(decision.allowed)

    def test_live_bypass_without_identity_allows_guard(self) -> None:
        decision = deny_live_submit_without_durable_identity(
            LiveSubmitSnapshot(
                mode=ExecutionMode.LIVE,
                dry_run_bypass=True,
                identity_held=False,
            )
        )
        self.assertTrue(decision.allowed)

    def test_paper_without_identity_allows_guard(self) -> None:
        decision = deny_live_submit_without_durable_identity(
            LiveSubmitSnapshot(
                mode=ExecutionMode.PAPER,
                dry_run_bypass=False,
                identity_held=False,
            )
        )
        self.assertTrue(decision.allowed)


class T2SubmissionUnknownTests(unittest.TestCase):
    def test_unknown_new_cycle_denies(self) -> None:
        decision = deny_new_cycle_when_submission_unknown(
            SubmissionUnknownSnapshot(
                submission_certainty=SubmissionCertainty.UNKNOWN,
                requesting_new_cycle_submit=True,
            )
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, REASON_SUBMISSION_UNCERTAIN)
        self.assertEqual(decision.certainty, SubmissionCertainty.UNKNOWN)

    def test_unknown_without_new_cycle_allows(self) -> None:
        decision = deny_new_cycle_when_submission_unknown(
            SubmissionUnknownSnapshot(
                submission_certainty=SubmissionCertainty.UNKNOWN,
                requesting_new_cycle_submit=False,
            )
        )
        self.assertTrue(decision.allowed)

    def test_terminal_new_cycle_allows(self) -> None:
        decision = deny_new_cycle_when_submission_unknown(
            SubmissionUnknownSnapshot(
                submission_certainty=SubmissionCertainty.TERMINAL,
                requesting_new_cycle_submit=True,
            )
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.certainty, SubmissionCertainty.TERMINAL)

    def test_not_applicable_new_cycle_allows(self) -> None:
        decision = deny_new_cycle_when_submission_unknown(
            SubmissionUnknownSnapshot(
                submission_certainty=SubmissionCertainty.NOT_APPLICABLE,
                requesting_new_cycle_submit=True,
            )
        )
        self.assertTrue(decision.allowed)


class T3BlindRetryTests(unittest.TestCase):
    def test_uncertain_unreconciled_blind_retry_denies(self) -> None:
        decision = deny_blind_retry_after_uncertain_transport(
            SubmissionRetrySnapshot(
                transport_uncertain=True,
                reconciled=False,
                requesting_blind_retry=True,
            )
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, REASON_RECONCILE_REQUIRED)

    def test_uncertain_but_reconciled_allows(self) -> None:
        decision = deny_blind_retry_after_uncertain_transport(
            SubmissionRetrySnapshot(
                transport_uncertain=True,
                reconciled=True,
                requesting_blind_retry=True,
            )
        )
        self.assertTrue(decision.allowed)

    def test_uncertain_without_retry_allows(self) -> None:
        decision = deny_blind_retry_after_uncertain_transport(
            SubmissionRetrySnapshot(
                transport_uncertain=True,
                reconciled=False,
                requesting_blind_retry=False,
            )
        )
        self.assertTrue(decision.allowed)

    def test_certain_transport_blind_retry_allows_guard(self) -> None:
        decision = deny_blind_retry_after_uncertain_transport(
            SubmissionRetrySnapshot(
                transport_uncertain=False,
                reconciled=False,
                requesting_blind_retry=True,
            )
        )
        self.assertTrue(decision.allowed)


class CertaintyVocabTests(unittest.TestCase):
    def test_certainty_enum_values_stable(self) -> None:
        self.assertEqual(
            {item.value for item in SubmissionCertainty},
            {
                "known_failed",
                "unknown",
                "filled_accounting_pending",
                "terminal",
                "not_applicable",
            },
        )


if __name__ == "__main__":
    unittest.main()
