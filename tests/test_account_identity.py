from __future__ import annotations

import unittest

from quant_platform_kit.common.account_identity import (
    AccountIdentityBlockedError,
    AccountIdentityEnforcement,
    AccountIdentityEvidenceSource,
    AccountIdentityField,
    AccountIdentityGuardedExecutionPort,
    AccountIdentityPolicy,
    BrokerAccountIdentity,
    evaluate_account_identity,
)
from quant_platform_kit.common.models import ExecutionReport, OrderIntent
from quant_platform_kit.common.port_adapters import CallableExecutionPort


_FINGERPRINT = "sha256:" + "a" * 64


class AccountIdentityTests(unittest.TestCase):
    def test_observe_mode_records_missing_broker_evidence_without_stopping_orders(self) -> None:
        decision = evaluate_account_identity(
            expected_platform_id="longbridge",
            policy=AccountIdentityPolicy(
                enforcement="observe",
                required_fields={AccountIdentityField.ACCOUNT_MODE},
                expected_account_modes=("paper",),
            ),
            observation=BrokerAccountIdentity(
                platform_id="longbridge",
                evidence_source=AccountIdentityEvidenceSource.BROKER_API_PARTIAL,
                account_types=("cash",),
            ),
        )

        self.assertTrue(decision.would_block)
        self.assertTrue(decision.broker_write_allowed)
        self.assertIn("account_identity_evidence_unavailable", decision.findings)
        receipt = decision.to_receipt()
        self.assertNotIn("sha256:", str(receipt))
        self.assertFalse(receipt["observation"]["account_id_fingerprint_observed"])

    def test_enforce_mode_rejects_type_and_platform_mismatch_before_delegate(self) -> None:
        decision = evaluate_account_identity(
            expected_platform_id="longbridge",
            policy=AccountIdentityPolicy(
                enforcement=AccountIdentityEnforcement.ENFORCE,
                expected_account_types=("cash",),
            ),
            observation=BrokerAccountIdentity(
                platform_id="unexpected_broker",
                account_types=("margin",),
            ),
        )
        called = []
        port = AccountIdentityGuardedExecutionPort(
            delegate=CallableExecutionPort(
                lambda _order: called.append(True)
                or ExecutionReport(symbol="SOXL", side="buy", quantity=1, status="submitted")
            ),
            decision=decision,
        )

        with self.assertRaises(AccountIdentityBlockedError):
            port.submit_order(OrderIntent(symbol="SOXL", side="buy", quantity=1))
        self.assertEqual(called, [])
        self.assertIn("account_identity_platform_mismatch", decision.findings)
        self.assertIn("account_identity_type_mismatch", decision.findings)

    def test_strict_identifier_comparison_accepts_only_redacted_fingerprint(self) -> None:
        policy = AccountIdentityPolicy(
            enforcement="enforce",
            expected_account_id_fingerprint=_FINGERPRINT,
        )
        decision = evaluate_account_identity(
            expected_platform_id="schwab",
            policy=policy,
            observation=BrokerAccountIdentity(
                platform_id="schwab",
                account_id_fingerprint=_FINGERPRINT,
            ),
        )

        self.assertTrue(decision.policy_allows)
        self.assertTrue(decision.broker_write_allowed)
        self.assertNotIn(_FINGERPRINT, str(decision.to_receipt()))

    def test_required_field_without_reviewed_expectation_is_configuration_error(self) -> None:
        decision = evaluate_account_identity(
            expected_platform_id="alpaca",
            policy={"enforcement": "enforce", "required_fields": ["account_id"]},
            observation=BrokerAccountIdentity(platform_id="alpaca"),
        )

        self.assertFalse(decision.broker_write_allowed)
        self.assertEqual(
            decision.findings,
            ("account_identity_configuration_invalid",),
        )

    def test_policy_rejects_unknown_fields_and_empty_enforcement(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported account identity policy fields"):
            AccountIdentityPolicy.from_mapping({"expected_account_type": "cash"})
        with self.assertRaisesRegex(ValueError, "must require at least one field"):
            AccountIdentityPolicy.from_mapping({"enforcement": "enforce"})

    def test_runtime_target_account_identity_must_be_mapping(self) -> None:
        from quant_platform_kit.common.runtime_target import resolve_runtime_target_from_env

        with self.assertRaisesRegex(ValueError, "account_identity must be an object"):
            resolve_runtime_target_from_env(
                env={
                    "RUNTIME_TARGET_JSON": (
                        '{"platform_id":"longbridge","strategy_profile":"soxl_soxx_trend_income",'
                        '"dry_run_only":true,"account_identity":"paper"}'
                    )
                }
            )


if __name__ == "__main__":
    unittest.main()
