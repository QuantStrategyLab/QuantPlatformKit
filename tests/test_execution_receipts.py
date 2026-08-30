from __future__ import annotations

import copy
import unittest

from quant_platform_kit.common.execution_receipts import (
    EXECUTION_RECEIPT_SCHEMA_VERSION,
    attach_execution_receipt,
    attach_runtime_execution_receipt,
    build_execution_receipt,
    calculate_execution_receipt_sha256,
    resolve_execution_receipt_fact,
    validate_execution_receipt,
)


REVISION = "a" * 40


def _receipt(**overrides: object) -> dict[str, str]:
    values: dict[str, object] = {
        "platform": "interactive_brokers",
        "strategy_profile": "soxl_soxx_trend_income",
        "strategy_revision": REVISION,
        "execution_mode": "live",
        "outcome": "filled",
        "observed_at": "2026-08-31T00:00:00Z",
    }
    values.update(overrides)
    return build_execution_receipt(**values)


def _runtime_report() -> dict[str, object]:
    return {
        "platform": "interactive_brokers",
        "strategy_profile": "soxl_soxx_trend_income",
        "runtime_target": {"execution_mode": "live"},
        "runtime_release_receipt": {
            "attestation_state": "self_attested",
            "strategy_release": {"strategy_revision": REVISION},
        },
    }


class ExecutionReceiptTest(unittest.TestCase):
    def test_builds_a_minimal_deterministic_filled_receipt(self) -> None:
        receipt = _receipt()

        self.assertEqual(receipt, _receipt())
        self.assertEqual(receipt["schema_version"], EXECUTION_RECEIPT_SCHEMA_VERSION)
        self.assertEqual(receipt["platform"], "ibkr")
        self.assertEqual(receipt["broker_confirmation"], "filled")
        self.assertTrue(receipt["receipt_id"].startswith("execution-receipt."))
        self.assertEqual(len(calculate_execution_receipt_sha256(receipt)), 64)
        self.assertEqual(
            set(receipt),
            {
                "schema_version",
                "receipt_id",
                "platform",
                "strategy_profile",
                "strategy_revision",
                "execution_mode",
                "outcome",
                "broker_confirmation",
                "observed_at",
            },
        )

    def test_failed_outcome_requires_an_explicit_non_claiming_confirmation(self) -> None:
        with self.assertRaisesRegex(ValueError, "broker_confirmation is required"):
            _receipt(outcome="failed")

        receipt = _receipt(outcome="failed", broker_confirmation="not_observed")
        self.assertEqual(receipt["broker_confirmation"], "not_observed")

    def test_rejects_tampered_or_inconsistent_receipts(self) -> None:
        receipt = _receipt()
        tampered = copy.deepcopy(receipt)
        tampered["outcome"] = "submitted"
        with self.assertRaisesRegex(ValueError, "broker_confirmation"):
            validate_execution_receipt(tampered)

        tampered = copy.deepcopy(receipt)
        tampered["strategy_profile"] = "other_strategy"
        with self.assertRaisesRegex(ValueError, "receipt_id"):
            validate_execution_receipt(tampered)

    def test_attaches_only_to_the_matching_attested_runtime_report(self) -> None:
        report = _runtime_report()
        attached = attach_execution_receipt(report, _receipt())

        self.assertIs(attached, report)
        self.assertEqual(report["execution_receipt"]["outcome"], "filled")

        wrong_revision = _receipt(strategy_revision="b" * 40)
        with self.assertRaisesRegex(ValueError, "strategy_revision"):
            attach_execution_receipt(_runtime_report(), wrong_revision)

        duplicate = _runtime_report()
        attach_execution_receipt(duplicate, _receipt())
        with self.assertRaisesRegex(ValueError, "already has"):
            attach_execution_receipt(duplicate, _receipt(outcome="no_action"))

    def test_builds_receipt_from_attested_runtime_report(self) -> None:
        report = _runtime_report()

        attached = attach_runtime_execution_receipt(report, outcome="submitted")

        self.assertEqual(attached["execution_receipt"]["platform"], "ibkr")
        self.assertEqual(attached["execution_receipt"]["strategy_profile"], "soxl_soxx_trend_income")
        self.assertEqual(attached["execution_receipt"]["outcome"], "submitted")
        self.assertEqual(attached["execution_receipt"]["broker_confirmation"], "not_observed")

    def test_runtime_helper_requires_attested_revision(self) -> None:
        report = _runtime_report()
        report["runtime_release_receipt"] = {}

        with self.assertRaises(ValueError):
            attach_runtime_execution_receipt(report, outcome="no_action")

    def test_resolves_only_the_highest_supported_execution_fact(self) -> None:
        self.assertEqual(
            resolve_execution_receipt_fact(dry_run=False, submission_attempted=True),
            ("submitted", "not_observed"),
        )
        self.assertEqual(
            resolve_execution_receipt_fact(
                dry_run=False,
                submission_attempted=True,
                failed=True,
            ),
            ("failed", "not_observed"),
        )
        self.assertEqual(
            resolve_execution_receipt_fact(
                dry_run=False,
                submission_attempted=True,
                reconciliation_required=True,
            ),
            ("reconciliation_required", "reconciliation_required"),
        )
        self.assertEqual(
            resolve_execution_receipt_fact(
                dry_run=False,
                submission_attempted=True,
                filled=True,
            ),
            ("filled", "filled"),
        )

    def test_dry_run_never_claims_a_broker_result(self) -> None:
        self.assertEqual(
            resolve_execution_receipt_fact(
                dry_run=True,
                submission_attempted=True,
                filled=True,
            ),
            ("no_action", "not_applicable"),
        )
