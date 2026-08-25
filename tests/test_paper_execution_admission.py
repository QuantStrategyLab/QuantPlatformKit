from __future__ import annotations

import copy
import unittest

from quant_platform_kit.common.execution_commands import ExecutionCommand
from quant_platform_kit.common.paper_execution_admission import (
    PAPER_RISK_ADMISSION_RECEIPT_INTENT_FIELD,
    PAPER_RISK_ADMISSION_RECEIPT_SCHEMA_VERSION,
    PaperExecutionAdmissionFinding,
    PaperRiskAdmissionDisposition,
    PaperRiskAdmissionReceipt,
    build_paper_risk_admission_receipt,
    calculate_paper_risk_admission_receipt_sha256,
    canonical_paper_risk_admission_receipt_json,
    evaluate_paper_execution_admission,
)
from quant_platform_kit.common.runtime_command_gate import (
    RuntimeCommandAction,
    RuntimeCommandExposureEffect,
    RuntimeCommandGateEnforcement,
    RuntimeCommandGateMode,
    RuntimeCommandGatePolicy,
    evaluate_runtime_command_gate,
)
from quant_platform_kit.common.strategy_release import build_runtime_loaded_receipt


def _release_identity() -> dict[str, str]:
    return {
        "release_id": "soxl-p2-v3.20260824",
        "manifest_sha256": "a" * 64,
        "strategy_revision": "soxl-p2-v3",
        "config_sha256": "b" * 64,
        "risk_policy_sha256": "c" * 64,
        "evidence_sha256": "d" * 64,
        "plugin_bundle_sha256": "e" * 64,
        "effective_session": "2026-08-25",
    }


def _receipt(
    *,
    disposition: PaperRiskAdmissionDisposition = PaperRiskAdmissionDisposition.ALLOW_NEW_RISK,
    reason_codes: tuple[str, ...] = (),
) -> PaperRiskAdmissionReceipt:
    release = _release_identity()
    return build_paper_risk_admission_receipt(
        strategy_profile="soxl_soxx_trend_income",
        release_id=release["release_id"],
        risk_policy_sha256=release["risk_policy_sha256"],
        decision_digest="d" * 64,
        effective_session="2026-08-25",
        disposition=disposition,
        reason_codes=reason_codes,
    )


def _command(
    *,
    receipt: PaperRiskAdmissionReceipt | None = None,
    include_receipt: bool = True,
    execution_mode: str = "paper",
    decision_digest: str = "sha256:decision-v1",
    strategy_profile: str = "soxl_soxx_trend_income",
    effective_date: str = "2026-08-25",
) -> ExecutionCommand:
    intent: dict[str, object] = {
        "targets": {"SOXL": 0.0, "SOXX": 0.70},
        "strategy_release": _release_identity(),
    }
    if include_receipt:
        intent[PAPER_RISK_ADMISSION_RECEIPT_INTENT_FIELD] = (receipt or _receipt()).to_dict()
    return ExecutionCommand.from_decision(
        platform="longbridge",
        account_scope="sg",
        strategy_profile=strategy_profile,
        execution_mode=execution_mode,
        signal_date="2026-08-24",
        effective_date=effective_date,
        execution_timing_contract="next_trading_day",
        decision_digest=decision_digest,
        intent=intent,
        created_at="2026-08-24T20:00:00+00:00",
    )


class PaperRiskAdmissionReceiptTests(unittest.TestCase):
    def test_receipt_is_canonical_content_addressed_and_round_trips(self) -> None:
        receipt = _receipt()
        serialized = receipt.to_dict()

        self.assertEqual(serialized["schema_version"], PAPER_RISK_ADMISSION_RECEIPT_SCHEMA_VERSION)
        self.assertEqual(
            serialized["receipt_sha256"],
            calculate_paper_risk_admission_receipt_sha256(serialized),
        )
        self.assertEqual(
            canonical_paper_risk_admission_receipt_json(serialized),
            canonical_paper_risk_admission_receipt_json(dict(reversed(serialized.items()))),
        )
        self.assertEqual(PaperRiskAdmissionReceipt.from_dict(serialized), receipt)

    def test_exact_fields_and_digest_are_required(self) -> None:
        valid = _receipt().to_dict()
        cases = []
        missing = dict(valid)
        missing.pop("decision_digest")
        cases.append(missing)
        unexpected = dict(valid)
        unexpected["operator_note"] = "must not be silently accepted"
        cases.append(unexpected)
        tampered = dict(valid)
        tampered["effective_session"] = "2026-08-26"
        cases.append(tampered)

        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    PaperRiskAdmissionReceipt.from_dict(payload)

    def test_disposition_semantics_and_stable_reason_codes_are_strict(self) -> None:
        valid = _receipt().to_dict()
        allow_with_reason = copy.deepcopy(valid)
        allow_with_reason["reason_codes"] = ["RISK_LIMIT_EXCEEDED"]
        reducing_without_reason = copy.deepcopy(valid)
        reducing_without_reason["disposition"] = "reducing_only"
        raw_reason = copy.deepcopy(valid)
        raw_reason["disposition"] = "halted"
        raw_reason["reason_codes"] = ["secret=must_not_escape"]

        for payload in (allow_with_reason, reducing_without_reason, raw_reason):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    PaperRiskAdmissionReceipt.from_dict(payload)


class PaperExecutionAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.release = _release_identity()
        self.command = _command()

    def test_allow_new_risk_requires_all_immutable_bindings(self) -> None:
        decision = evaluate_paper_execution_admission(
            command=self.command,
            expected_strategy_release=self.release,
        )

        self.assertTrue(decision.allows_new_risk)
        self.assertFalse(decision.requires_exposure_reduction)
        self.assertEqual(decision.integrity_findings, ())
        self.assertEqual(decision.receipt_sha256, _receipt().receipt_sha256)

    def test_missing_or_tampered_receipt_halts_without_leaking_raw_data(self) -> None:
        missing = evaluate_paper_execution_admission(
            command=_command(include_receipt=False),
            expected_strategy_release=self.release,
        )
        self.assertEqual(missing.disposition, PaperRiskAdmissionDisposition.HALTED)
        self.assertEqual(
            missing.integrity_findings,
            (PaperExecutionAdmissionFinding.RECEIPT_MISSING.value,),
        )

        tampered_intent = self.command.intent
        tampered_receipt = dict(tampered_intent[PAPER_RISK_ADMISSION_RECEIPT_INTENT_FIELD])
        tampered_receipt["strategy_profile"] = "unapproved_profile"
        tampered_intent[PAPER_RISK_ADMISSION_RECEIPT_INTENT_FIELD] = tampered_receipt
        tampered = ExecutionCommand.from_decision(
            platform="longbridge",
            account_scope="sg",
            strategy_profile="soxl_soxx_trend_income",
            execution_mode="paper",
            signal_date="2026-08-24",
            effective_date="2026-08-25",
            execution_timing_contract="next_trading_day",
            decision_digest="sha256:decision-v1",
            intent=tampered_intent,
        )
        invalid = evaluate_paper_execution_admission(command=tampered, expected_strategy_release=self.release)
        self.assertEqual(invalid.disposition, PaperRiskAdmissionDisposition.HALTED)
        self.assertEqual(
            invalid.integrity_findings,
            (PaperExecutionAdmissionFinding.RECEIPT_INVALID.value,),
        )

    def test_command_release_and_policy_bindings_are_exact(self) -> None:
        command_mismatch = evaluate_paper_execution_admission(
            command=_command(strategy_profile="different_strategy_profile"),
            expected_strategy_release=self.release,
        )
        self.assertEqual(
            command_mismatch.integrity_findings,
            (PaperExecutionAdmissionFinding.COMMAND_BINDING_MISMATCH.value,),
        )

        release_receipt = _receipt().to_dict()
        release_receipt["release_id"] = "other-p2-v3.20260824"
        release_receipt["receipt_sha256"] = calculate_paper_risk_admission_receipt_sha256(release_receipt)
        release_mismatch = evaluate_paper_execution_admission(
            command=_command(receipt=PaperRiskAdmissionReceipt.from_dict(release_receipt)),
            expected_strategy_release=self.release,
        )
        self.assertEqual(
            release_mismatch.integrity_findings,
            (PaperExecutionAdmissionFinding.RELEASE_BINDING_MISMATCH.value,),
        )

        policy_receipt = _receipt().to_dict()
        policy_receipt["risk_policy_sha256"] = "f" * 64
        policy_receipt["receipt_sha256"] = calculate_paper_risk_admission_receipt_sha256(policy_receipt)
        policy_mismatch = evaluate_paper_execution_admission(
            command=_command(receipt=PaperRiskAdmissionReceipt.from_dict(policy_receipt)),
            expected_strategy_release=self.release,
        )
        self.assertEqual(
            policy_mismatch.integrity_findings,
            (PaperExecutionAdmissionFinding.RISK_POLICY_MISMATCH.value,),
        )

    def test_receipt_must_be_inside_the_content_addressed_command(self) -> None:
        object.__setattr__(self.command, "decision_digest", "sha256:mutated-after-store")

        decision = evaluate_paper_execution_admission(
            command=self.command,
            expected_strategy_release=self.release,
        )

        self.assertEqual(decision.disposition, PaperRiskAdmissionDisposition.HALTED)
        self.assertEqual(
            decision.integrity_findings,
            (PaperExecutionAdmissionFinding.COMMAND_IMMUTABILITY_INVALID.value,),
        )

    def test_reducing_only_and_halted_receipts_compose_with_runtime_gate(self) -> None:
        reducing = evaluate_paper_execution_admission(
            command=_command(
                receipt=_receipt(
                    disposition=PaperRiskAdmissionDisposition.REDUCING_ONLY,
                    reason_codes=("DAILY_LOSS_LIMIT_EXCEEDED",),
                )
            ),
            expected_strategy_release=self.release,
        )
        halted = evaluate_paper_execution_admission(
            command=_command(
                receipt=_receipt(
                    disposition=PaperRiskAdmissionDisposition.HALTED,
                    reason_codes=("CIRCUIT_BREAKER_OPEN",),
                )
            ),
            expected_strategy_release=self.release,
        )
        runtime_receipt = build_runtime_loaded_receipt(strategy_release=self.release)
        strict_policy = RuntimeCommandGatePolicy(enforcement=RuntimeCommandGateEnforcement.ENFORCE)

        reducing_gate = evaluate_runtime_command_gate(
            action=RuntimeCommandAction.SUBMIT,
            exposure_effect=RuntimeCommandExposureEffect.REDUCES,
            command=_command(
                receipt=_receipt(
                    disposition=PaperRiskAdmissionDisposition.REDUCING_ONLY,
                    reason_codes=("DAILY_LOSS_LIMIT_EXCEEDED",),
                )
            ),
            as_of_session="2026-08-25",
            runtime_release_receipt=runtime_receipt,
            expected_strategy_release=self.release,
            integrity_findings=reducing.integrity_findings,
            policy=strict_policy,
        )
        halted_gate = evaluate_runtime_command_gate(
            action=RuntimeCommandAction.SUBMIT,
            exposure_effect=RuntimeCommandExposureEffect.REDUCES,
            command=_command(
                receipt=_receipt(
                    disposition=PaperRiskAdmissionDisposition.HALTED,
                    reason_codes=("CIRCUIT_BREAKER_OPEN",),
                )
            ),
            as_of_session="2026-08-25",
            runtime_release_receipt=runtime_receipt,
            expected_strategy_release=self.release,
            integrity_findings=halted.integrity_findings,
            policy=strict_policy,
        )

        self.assertEqual(reducing.disposition, PaperRiskAdmissionDisposition.REDUCING_ONLY)
        self.assertTrue(reducing.requires_exposure_reduction)
        self.assertEqual(reducing_gate.mode, RuntimeCommandGateMode.REDUCING)
        self.assertTrue(reducing_gate.broker_write_allowed)
        self.assertEqual(halted.disposition, PaperRiskAdmissionDisposition.HALTED)
        self.assertEqual(halted_gate.mode, RuntimeCommandGateMode.HALTED)
        self.assertFalse(halted_gate.broker_write_allowed)

    def test_non_paper_or_invalid_expected_release_fails_closed(self) -> None:
        non_paper = evaluate_paper_execution_admission(
            command=_command(execution_mode="live"),
            expected_strategy_release=self.release,
        )
        invalid_release = evaluate_paper_execution_admission(
            command=self.command,
            expected_strategy_release={"release_id": "not-a-full-identity"},
        )

        self.assertEqual(
            non_paper.integrity_findings,
            (PaperExecutionAdmissionFinding.COMMAND_MODE_INVALID.value,),
        )
        self.assertEqual(invalid_release.integrity_findings, ("release_identity_invalid",))


if __name__ == "__main__":
    unittest.main()
