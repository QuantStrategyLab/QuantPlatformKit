from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from quant_platform_kit.common.broker_reconciliation import build_broker_reconciliation_evidence
from quant_platform_kit.common.broker_reconciliation_enrollment import (
    BrokerReconciliationBaselineCandidate,
    BrokerReconciliationEnrollmentFinding,
    evaluate_broker_reconciliation_baseline_enrollment,
)


def _digest(character: str) -> str:
    return character * 64


def _evidence(*, observed_at: datetime, **overrides: object):
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
        # A legacy enrollment has no expected digests yet, so these remain
        # false even when the independently observed digests agree.
        "positions_match": False,
        "cash_match": False,
        "open_orders_match": False,
        "recent_executions_match": False,
        "local_execution_ledger_match": False,
        "positions_sha256": _digest("c"),
        "cash_sha256": _digest("d"),
        "open_orders_sha256": _digest("e"),
        "recent_executions_sha256": _digest("f"),
        "local_execution_ledger_sha256": _digest("0"),
    }
    payload.update(overrides)
    return build_broker_reconciliation_evidence(**payload)


def test_two_matching_read_only_samples_create_a_redacted_review_candidate() -> None:
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    evaluation = evaluate_broker_reconciliation_baseline_enrollment(
        [_evidence(observed_at=start), _evidence(observed_at=start + timedelta(minutes=2))],
        now=start + timedelta(minutes=3),
    )

    assert evaluation.ready_for_independent_review is True
    assert evaluation.findings == ()
    assert evaluation.candidate is not None
    assert evaluation.candidate.expected_digests == {
        "positions_sha256": _digest("c"),
        "cash_sha256": _digest("d"),
        "open_orders_sha256": _digest("e"),
        "recent_executions_sha256": _digest("f"),
        "local_execution_ledger_sha256": _digest("0"),
    }
    assert "account_scope" not in evaluation.candidate.to_dict()
    assert BrokerReconciliationBaselineCandidate.from_dict(evaluation.candidate.to_dict()) == evaluation.candidate


def test_any_state_difference_or_identity_failure_remains_blocked() -> None:
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    mismatch = evaluate_broker_reconciliation_baseline_enrollment(
        [
            _evidence(observed_at=start),
            _evidence(observed_at=start + timedelta(minutes=2), cash_sha256=_digest("9")),
        ],
        now=start + timedelta(minutes=3),
    )
    identity = evaluate_broker_reconciliation_baseline_enrollment(
        [
            _evidence(observed_at=start),
            _evidence(observed_at=start + timedelta(minutes=2), account_identity_match=False),
        ],
        now=start + timedelta(minutes=3),
    )

    assert mismatch.candidate is None
    assert mismatch.findings == (BrokerReconciliationEnrollmentFinding.OBSERVATION_MISMATCH,)
    assert identity.candidate is None
    assert identity.findings == (BrokerReconciliationEnrollmentFinding.ACCOUNT_IDENTITY_MISMATCH,)


@pytest.mark.parametrize(
    ("second_observed_at", "expected"),
    [
        (timedelta(seconds=30), BrokerReconciliationEnrollmentFinding.EVIDENCE_NOT_TIME_SEPARATED),
        (timedelta(minutes=16), BrokerReconciliationEnrollmentFinding.EVIDENCE_WINDOW_EXCEEDED),
    ],
)
def test_samples_must_be_time_separated_and_bounded(second_observed_at, expected) -> None:
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    evaluation = evaluate_broker_reconciliation_baseline_enrollment(
        [_evidence(observed_at=start), _evidence(observed_at=start + second_observed_at)],
        now=start + second_observed_at,
    )

    assert evaluation.candidate is None
    assert expected in evaluation.findings


def test_candidate_tampering_is_rejected() -> None:
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    candidate = evaluate_broker_reconciliation_baseline_enrollment(
        [_evidence(observed_at=start), _evidence(observed_at=start + timedelta(minutes=2))],
        now=start + timedelta(minutes=3),
    ).candidate
    assert candidate is not None
    payload = candidate.to_dict()
    payload["positions_sha256"] = _digest("9")

    with pytest.raises(ValueError, match="candidate_sha256 mismatch"):
        BrokerReconciliationBaselineCandidate.from_dict(payload)
