from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from quant_platform_kit.common.broker_reconciliation import build_broker_reconciliation_evidence
from quant_platform_kit.common.broker_reconciliation_enrollment import evaluate_broker_reconciliation_baseline_enrollment
from quant_platform_kit.common.reconciliation_recovery import (
    ReconciliationRecoveryActivationFinding,
    ReconciliationRecoveryConfirmation,
    ReconciliationRecoveryDualReview,
    ReconciliationRecoverySourceSnapshot,
    ReconciliationRecoveryTransitionPlan,
    build_reconciliation_recovery_record,
    calculate_reconciliation_recovery_confirmation_sha256,
    evaluate_reconciliation_recovery_activation,
)


def _digest(character: str) -> str:
    return character * 64


def _evidence(*, observed_at: datetime, reconciled: bool, **overrides: object):
    payload: dict[str, object] = {
        "platform_id": "interactive-brokers",
        "strategy_profile": "soxl_soxx_trend_income",
        "account_scope_sha256": _digest("a"),
        "baseline_id": "soxl-ibkr-lkg-20260830",
        "baseline_target_sha256": _digest("b"),
        "runtime_target_sha256": _digest("b"),
        "observed_at": observed_at,
        "broker_connected": True,
        "account_identity_match": True,
        "positions_match": reconciled,
        "cash_match": reconciled,
        "open_orders_match": reconciled,
        "recent_executions_match": reconciled,
        "local_execution_ledger_match": reconciled,
        "positions_sha256": _digest("c"),
        "cash_sha256": _digest("d"),
        "open_orders_sha256": _digest("e"),
        "recent_executions_sha256": _digest("f"),
        "local_execution_ledger_sha256": _digest("0"),
    }
    payload.update(overrides)
    return build_broker_reconciliation_evidence(**payload)


def _candidate(start: datetime):
    result = evaluate_broker_reconciliation_baseline_enrollment(
        [_evidence(observed_at=start, reconciled=True), _evidence(observed_at=start + timedelta(minutes=2), reconciled=True)],
        now=start + timedelta(minutes=3),
        source_receipts_sha256=_digest("1"),
    )
    assert result.candidate is not None
    return result.candidate


def _confirmation(*, candidate_sha256: str, confirmed_at: datetime):
    payload: dict[str, object] = {
        "schema_version": "qsl_reconciliation_recovery_confirmation.v1",
        "recovery_id": "ibkr-soxl-live-recovery",
        "candidate_sha256": candidate_sha256,
        "dual_review_binding_sha256": candidate_sha256,
        "confirmed_at": confirmed_at.isoformat().replace("+00:00", "Z"),
        "confirmed_by": "recovery-admin",
        "no_order": True,
        "execution_authority_granted": False,
        "confirmation_sha256": "0" * 64,
    }
    payload["confirmation_sha256"] = calculate_reconciliation_recovery_confirmation_sha256(payload)
    return ReconciliationRecoveryConfirmation.from_dict(payload)


def test_redacted_source_record_preserves_candidate_timing_and_bound_review() -> None:
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    candidate = _candidate(start)
    review = ReconciliationRecoveryDualReview(
        outcome="approved",
        reviewer_count=2,
        evidence_binding_sha256=candidate.candidate_sha256,
    )

    record = build_reconciliation_recovery_record(
        recovery_id="ibkr-soxl-live-recovery",
        console_platform="ibkr",
        candidate=candidate,
        dual_review=review,
        now=start + timedelta(minutes=3),
    )
    source = ReconciliationRecoverySourceSnapshot(
        source_id="ibkr.reconciliation_recovery",
        generated_at=start + timedelta(minutes=3),
        computed_at=start + timedelta(minutes=3),
        records=(record,),
    ).to_dict()

    assert source["schema_version"] == "qsl_reconciliation_recovery_source_snapshot.v1"
    assert source["recoveries"][0]["readiness"] == "awaiting_human_confirmation"
    assert source["recoveries"][0]["platform"] == "ibkr"
    assert "account_scope_sha256" not in source["recoveries"][0]
    assert "positions_sha256" not in source["recoveries"][0]


def test_activation_requires_post_confirmation_evidence_not_model_recheck() -> None:
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    candidate = _candidate(start)
    confirmation = _confirmation(candidate_sha256=candidate.candidate_sha256, confirmed_at=start + timedelta(minutes=3))
    current = _evidence(observed_at=start + timedelta(minutes=4), reconciled=True)

    result = evaluate_reconciliation_recovery_activation(
        recovery_id="ibkr-soxl-live-recovery",
        candidate=candidate,
        confirmation=confirmation,
        current_evidence=current,
        current_live_continuity_state="RECONCILE_ONLY",
        dual_review_binding_reverified=True,
        now=start + timedelta(minutes=5),
    )

    assert result.ready_for_atomic_state_transition is True
    assert result.transition_plan is not None
    assert result.transition_plan.next_live_continuity_state == "ACTIVE_LKG"
    assert result.transition_plan.no_order is True
    assert result.transition_plan.execution_authority_granted is False
    assert result.transition_plan.requires_atomic_compare_and_set is True
    assert set(result.transition_plan.expected_digests) == {
        "positions_sha256", "cash_sha256", "open_orders_sha256", "recent_executions_sha256",
        "local_execution_ledger_sha256",
    }

    stale_receipt = evaluate_reconciliation_recovery_activation(
        recovery_id="ibkr-soxl-live-recovery",
        candidate=candidate,
        confirmation=confirmation,
        current_evidence=_evidence(observed_at=start + timedelta(minutes=2), reconciled=True),
        current_live_continuity_state="RECONCILE_ONLY",
        dual_review_binding_reverified=False,
        now=start + timedelta(minutes=5),
    )
    assert stale_receipt.ready_for_atomic_state_transition is False
    assert ReconciliationRecoveryActivationFinding.EVIDENCE_NOT_REOBSERVED_AFTER_CONFIRMATION.value in stale_receipt.findings
    assert ReconciliationRecoveryActivationFinding.DUAL_REVIEW_NOT_REVERIFIED.value not in stale_receipt.findings

    same_second_receipt = evaluate_reconciliation_recovery_activation(
        recovery_id="ibkr-soxl-live-recovery",
        candidate=candidate,
        confirmation=confirmation,
        current_evidence=_evidence(observed_at=start + timedelta(minutes=3), reconciled=True),
        current_live_continuity_state="RECONCILE_ONLY",
        dual_review_binding_reverified=True,
        now=start + timedelta(minutes=5),
    )
    assert same_second_receipt.ready_for_atomic_state_transition is False
    assert ReconciliationRecoveryActivationFinding.EVIDENCE_NOT_REOBSERVED_AFTER_CONFIRMATION.value in same_second_receipt.findings


def test_activation_keeps_target_frozen_when_current_broker_state_drifts() -> None:
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    candidate = _candidate(start)
    confirmation = _confirmation(candidate_sha256=candidate.candidate_sha256, confirmed_at=start + timedelta(minutes=3))

    result = evaluate_reconciliation_recovery_activation(
        recovery_id="ibkr-soxl-live-recovery",
        candidate=candidate,
        confirmation=confirmation,
        current_evidence=_evidence(observed_at=start + timedelta(minutes=4), reconciled=True, cash_sha256=_digest("9")),
        current_live_continuity_state="RECONCILE_ONLY",
        dual_review_binding_reverified=True,
        now=start + timedelta(minutes=5),
    )

    assert result.ready_for_atomic_state_transition is False
    assert "broker_reconciliation_cash_mismatch" in result.findings


def test_transition_plan_round_trip_requires_every_non_executable_guard() -> None:
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    candidate = _candidate(start)
    confirmation = _confirmation(candidate_sha256=candidate.candidate_sha256, confirmed_at=start + timedelta(minutes=3))
    result = evaluate_reconciliation_recovery_activation(
        recovery_id="ibkr-soxl-live-recovery",
        candidate=candidate,
        confirmation=confirmation,
        current_evidence=_evidence(observed_at=start + timedelta(minutes=4), reconciled=True),
        current_live_continuity_state="RECONCILE_ONLY",
        dual_review_binding_reverified=True,
        now=start + timedelta(minutes=5),
    )
    assert result.transition_plan is not None

    payload = result.transition_plan.to_dict()
    decoded = ReconciliationRecoveryTransitionPlan.from_dict(payload)

    assert decoded == result.transition_plan
    assert decoded.to_dict() == payload

    payload.pop("requires_atomic_compare_and_set")
    with pytest.raises(ValueError, match="invalid fields"):
        ReconciliationRecoveryTransitionPlan.from_dict(payload)


def test_transition_plan_decoder_rejects_extra_or_executable_fields() -> None:
    plan = ReconciliationRecoveryTransitionPlan(
        recovery_id="ibkr-soxl-live-recovery",
        candidate_sha256=_digest("a"),
        confirmation_sha256=_digest("b"),
        baseline_id="soxl-ibkr-lkg-20260830",
        baseline_target_sha256=_digest("c"),
        expected_digests={
            "positions_sha256": _digest("d"),
            "cash_sha256": _digest("e"),
            "open_orders_sha256": _digest("f"),
            "recent_executions_sha256": _digest("0"),
            "local_execution_ledger_sha256": _digest("1"),
        },
        verified_at=datetime(2026, 8, 30, 8, 5, tzinfo=timezone.utc),
    )
    payload = plan.to_dict()
    payload["unexpected"] = True

    with pytest.raises(ValueError, match="invalid fields"):
        ReconciliationRecoveryTransitionPlan.from_dict(payload)

    payload = plan.to_dict()
    payload["execution_authority_granted"] = True
    with pytest.raises(ValueError, match="must remain non-executable and atomic"):
        ReconciliationRecoveryTransitionPlan.from_dict(payload)


def _source_bound_candidate(start):
    from quant_platform_kit.common.broker_reconciliation_enrollment import (
        BrokerReconciliationBaselineCandidate,
        calculate_broker_reconciliation_baseline_candidate_sha256,
    )
    payload = _candidate(start).to_dict()
    payload.update(schema_version="broker_reconciliation_baseline_candidate.v2", source_receipts_sha256=_digest("1"))
    payload["candidate_sha256"] = calculate_broker_reconciliation_baseline_candidate_sha256(payload)
    return BrokerReconciliationBaselineCandidate.from_dict(payload)


@pytest.mark.parametrize("outcome", [None, "unavailable", "rejected", "approved"])
def test_source_bound_record_keeps_review_advisory_and_honest(outcome):
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    candidate = _source_bound_candidate(start)
    kwargs = {} if outcome is None else {"dual_review": ReconciliationRecoveryDualReview(
        outcome=outcome, reviewer_count=0 if outcome == "unavailable" else 1,
        evidence_binding_sha256=candidate.candidate_sha256,
    )}
    record = build_reconciliation_recovery_record(
        recovery_id="ibkr-soxl-live-recovery", console_platform="ibkr", candidate=candidate,
        now=start + timedelta(minutes=3), **kwargs,
    )
    assert record.readiness == "awaiting_human_confirmation"
    assert record.dual_review.outcome == (outcome or "unavailable")
    assert record.dual_review.reviewer_count == (0 if outcome in (None, "unavailable") else 1)


def test_unbound_historical_v1_cannot_enter_new_confirmation():
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    candidate = evaluate_broker_reconciliation_baseline_enrollment(
        [_evidence(observed_at=start, reconciled=True), _evidence(observed_at=start + timedelta(minutes=1), reconciled=True)],
        now=start + timedelta(minutes=2),
    ).candidate
    record = build_reconciliation_recovery_record(
        recovery_id="ibkr-soxl-live-recovery", console_platform="ibkr", candidate=candidate,
        dual_review=ReconciliationRecoveryDualReview("approved", 2, candidate.candidate_sha256),
        now=start + timedelta(minutes=3),
    )
    assert record.readiness == "blocked"
    assert "reconciliation_recovery_source_binding_missing" in record.blocker_codes


@pytest.mark.parametrize("reverified", [None, False, True])
def test_source_bound_activation_does_not_require_model_reverification(reverified):
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    candidate = _source_bound_candidate(start)
    confirmation = _confirmation(candidate_sha256=candidate.candidate_sha256, confirmed_at=start + timedelta(minutes=3))
    result = evaluate_reconciliation_recovery_activation(
        recovery_id="ibkr-soxl-live-recovery", candidate=candidate, confirmation=confirmation,
        current_evidence=_evidence(observed_at=start + timedelta(minutes=4), reconciled=True),
        current_live_continuity_state="RECONCILE_ONLY", now=start + timedelta(minutes=5),
        **({} if reverified is None else {"dual_review_binding_reverified": reverified}),
    )
    assert result.ready_for_atomic_state_transition
    assert result.transition_plan.no_order is True
    assert result.transition_plan.execution_authority_granted is False


@pytest.mark.parametrize("case", ["confirmation_missing", "candidate_mismatch", "source_tampered", "v1", "account_mismatch", "runtime_mismatch"])
def test_advisory_review_cannot_bypass_source_confirmation_or_identity(case):
    from quant_platform_kit.common.broker_reconciliation_enrollment import BrokerReconciliationBaselineCandidate
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    candidate = _source_bound_candidate(start)
    confirmation = _confirmation(candidate_sha256=candidate.candidate_sha256, confirmed_at=start + timedelta(minutes=3))
    evidence_overrides = {}
    if case == "confirmation_missing":
        confirmation = None
    elif case == "candidate_mismatch":
        confirmation = _confirmation(candidate_sha256=_digest("9"), confirmed_at=start + timedelta(minutes=3))
    elif case == "source_tampered":
        # Simulate tampering across a boundary; activation must revalidate the object.
        object.__setattr__(candidate, "source_receipts_sha256", _digest("9"))
    elif case == "v1":
        candidate = evaluate_broker_reconciliation_baseline_enrollment(
            [_evidence(observed_at=start, reconciled=True), _evidence(observed_at=start + timedelta(minutes=1), reconciled=True)],
            now=start + timedelta(minutes=2),
        ).candidate
        assert BrokerReconciliationBaselineCandidate.from_dict(candidate.to_dict()) == candidate
        confirmation = _confirmation(candidate_sha256=candidate.candidate_sha256, confirmed_at=start + timedelta(minutes=3))
    elif case == "account_mismatch":
        evidence_overrides["account_scope_sha256"] = _digest("9")
    elif case == "runtime_mismatch":
        evidence_overrides["runtime_target_sha256"] = _digest("9")
    result = evaluate_reconciliation_recovery_activation(
        recovery_id="ibkr-soxl-live-recovery", candidate=candidate, confirmation=confirmation,
        current_evidence=_evidence(observed_at=start + timedelta(minutes=4), reconciled=True, **evidence_overrides),
        current_live_continuity_state="RECONCILE_ONLY", now=start + timedelta(minutes=5),
    )
    assert not result.ready_for_atomic_state_transition
    assert result.transition_plan is None


def test_single_source_bound_sample_can_enter_confirmation_without_model_call():
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    candidate = evaluate_broker_reconciliation_baseline_enrollment(
        [_evidence(observed_at=start, reconciled=True)], now=start, source_receipts_sha256=_digest("1"),
    ).candidate
    record = build_reconciliation_recovery_record(
        recovery_id="ibkr-soxl-live-recovery", console_platform="ibkr", candidate=candidate, now=start,
    )
    assert record.readiness == "awaiting_human_confirmation"
    assert record.to_console_dict()["evidence_sample_count"] == 1
    assert record.dual_review.outcome == "unavailable"
    assert record.dual_review.reviewer_count == 0


@pytest.mark.parametrize("case", ["review_binding", "candidate_stale"])
def test_advisory_record_preserves_binding_and_freshness_guards(case):
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    candidate = _source_bound_candidate(start)
    review = ReconciliationRecoveryDualReview(
        "rejected", 1, _digest("9") if case == "review_binding" else candidate.candidate_sha256,
    )
    record = build_reconciliation_recovery_record(
        recovery_id="ibkr-soxl-live-recovery", console_platform="ibkr", candidate=candidate,
        dual_review=review, now=start + timedelta(minutes=40 if case == "candidate_stale" else 3),
    )
    assert record.readiness == "blocked"
    assert record.dual_review == review
