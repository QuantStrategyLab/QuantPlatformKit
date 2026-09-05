from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from quant_platform_kit.common import (
    BROKER_RECONCILIATION_BASELINE_CANDIDATE_V2_SCHEMA_VERSION as EXPORTED_V2_SCHEMA_VERSION,
)
from quant_platform_kit.common.broker_reconciliation import build_broker_reconciliation_evidence
from quant_platform_kit.common.broker_reconciliation_enrollment import (
    BROKER_RECONCILIATION_BASELINE_CANDIDATE_SCHEMA_VERSION,
    BROKER_RECONCILIATION_BASELINE_CANDIDATE_V2_SCHEMA_VERSION,
    BrokerReconciliationBaselineCandidate,
    BrokerReconciliationEnrollmentFinding,
    calculate_broker_reconciliation_baseline_candidate_sha256,
    canonical_broker_reconciliation_baseline_candidate_json,
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
        # Valid synthetic receipt; unreconciled surfaces are tested explicitly.
        "positions_match": True,
        "cash_match": True,
        "open_orders_match": True,
        "recent_executions_match": True,
        "local_execution_ledger_match": True,
        "positions_sha256": _digest("c"),
        "cash_sha256": _digest("d"),
        "open_orders_sha256": _digest("e"),
        "recent_executions_sha256": _digest("f"),
        "local_execution_ledger_sha256": _digest("0"),
    }
    payload.update(overrides)
    return build_broker_reconciliation_evidence(**payload)


@pytest.mark.parametrize(
    "unmatched_fields",
    [
        ("positions_match",),
        ("cash_match",),
        ("open_orders_match",),
        ("recent_executions_match",),
        ("local_execution_ledger_match",),
        (
            "positions_match", "cash_match", "open_orders_match",
            "recent_executions_match", "local_execution_ledger_match",
        ),
    ],
)
@pytest.mark.parametrize("unmatched_sample", [0, 1])
def test_identical_digests_cannot_enroll_unreconciled_observations(
    unmatched_fields, unmatched_sample,
) -> None:
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    matches = dict.fromkeys(
        (
            "positions_match", "cash_match", "open_orders_match",
            "recent_executions_match", "local_execution_ledger_match",
        ),
        True,
    )
    samples = [
        _evidence(
            observed_at=start + timedelta(minutes=2 * index),
            **(matches | (dict.fromkeys(unmatched_fields, False) if index == unmatched_sample else {})),
        )
        for index in range(2)
    ]

    evaluation = evaluate_broker_reconciliation_baseline_enrollment(
        samples, now=start + timedelta(minutes=3),
    )

    assert evaluation.candidate is None
    assert evaluation.ready_for_independent_review is False
    assert evaluation.findings == (BrokerReconciliationEnrollmentFinding.OBSERVATION_MISMATCH,)


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
        (timedelta(minutes=16), BrokerReconciliationEnrollmentFinding.EVIDENCE_WINDOW_EXCEEDED),
    ],
)
def test_samples_must_have_bounded_window(second_observed_at, expected) -> None:
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


def test_v2_candidate_binds_private_source_receipts_root_without_upgrading_v1() -> None:
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    v1_candidate = evaluate_broker_reconciliation_baseline_enrollment(
        [_evidence(observed_at=start), _evidence(observed_at=start + timedelta(minutes=2))],
        now=start + timedelta(minutes=3),
    ).candidate
    assert v1_candidate is not None
    assert EXPORTED_V2_SCHEMA_VERSION == BROKER_RECONCILIATION_BASELINE_CANDIDATE_V2_SCHEMA_VERSION
    assert v1_candidate.schema_version == BROKER_RECONCILIATION_BASELINE_CANDIDATE_SCHEMA_VERSION
    assert v1_candidate.source_receipts_sha256 is None

    payload = v1_candidate.to_dict()
    payload["schema_version"] = BROKER_RECONCILIATION_BASELINE_CANDIDATE_V2_SCHEMA_VERSION
    payload["source_receipts_sha256"] = _digest("1")
    payload["candidate_sha256"] = calculate_broker_reconciliation_baseline_candidate_sha256(payload)

    candidate = BrokerReconciliationBaselineCandidate.from_dict(payload)

    assert candidate.source_receipts_sha256 == _digest("1")
    assert candidate.to_dict() == payload
    assert '"source_receipts_sha256":"' + _digest("1") + '"' in (
        canonical_broker_reconciliation_baseline_candidate_json(payload)
    )

    tampered = candidate.to_dict()
    tampered["source_receipts_sha256"] = _digest("2")
    with pytest.raises(ValueError, match="candidate_sha256 mismatch"):
        BrokerReconciliationBaselineCandidate.from_dict(tampered)


def test_candidate_schema_versions_do_not_silently_change_provenance_semantics() -> None:
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    candidate = evaluate_broker_reconciliation_baseline_enrollment(
        [_evidence(observed_at=start), _evidence(observed_at=start + timedelta(minutes=2))],
        now=start + timedelta(minutes=3),
    ).candidate
    assert candidate is not None

    v1_with_provenance = candidate.to_dict()
    v1_with_provenance["source_receipts_sha256"] = _digest("1")
    with pytest.raises(ValueError, match="invalid fields"):
        BrokerReconciliationBaselineCandidate.from_dict(v1_with_provenance)

    v2_without_provenance = candidate.to_dict()
    v2_without_provenance["schema_version"] = BROKER_RECONCILIATION_BASELINE_CANDIDATE_V2_SCHEMA_VERSION
    with pytest.raises(ValueError, match="invalid fields"):
        BrokerReconciliationBaselineCandidate.from_dict(v2_without_provenance)


@pytest.mark.parametrize("separation", [None, timedelta(seconds=1)])
def test_source_bound_v2_does_not_require_repeated_or_separated_samples(separation):
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    samples = [_evidence(observed_at=start)]
    if separation is not None:
        samples.append(_evidence(observed_at=start + separation))
    result = evaluate_broker_reconciliation_baseline_enrollment(
        samples, now=start + timedelta(seconds=2), source_receipts_sha256=_digest("1"),
    )
    assert result.ready_for_independent_review
    assert result.candidate.schema_version == "broker_reconciliation_baseline_candidate.v2"
    assert result.candidate.source_receipts_sha256 == _digest("1")
    assert len(result.candidate.source_evidence_sha256) == len(samples)


@pytest.mark.parametrize("field", [
    "broker_connected", "account_identity_match", "positions_match", "cash_match",
    "open_orders_match", "recent_executions_match", "local_execution_ledger_match",
])
def test_source_root_never_overrides_unreconciled_single_sample(field):
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    result = evaluate_broker_reconciliation_baseline_enrollment(
        [_evidence(observed_at=start, **{field: False})], now=start,
        source_receipts_sha256=_digest("1"),
    )
    assert result.candidate is None
    assert result.findings


@pytest.mark.parametrize("root", ["", "not-a-digest", True])
def test_single_sample_rejects_invalid_source_binding(root):
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    result = evaluate_broker_reconciliation_baseline_enrollment(
        [_evidence(observed_at=start)], now=start, source_receipts_sha256=root,
    )
    assert result.candidate is None
    assert result.findings == (BrokerReconciliationEnrollmentFinding.EVIDENCE_INVALID,)


@pytest.mark.parametrize("offset", [timedelta(minutes=-31), timedelta(seconds=1)])
def test_source_bound_single_sample_must_be_current(offset):
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    result = evaluate_broker_reconciliation_baseline_enrollment(
        [_evidence(observed_at=start + offset)], now=start, source_receipts_sha256=_digest("1"),
    )
    assert result.candidate is None
    assert BrokerReconciliationEnrollmentFinding.EVIDENCE_STALE in result.findings


def test_single_sample_without_source_root_is_not_silently_upgraded():
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    result = evaluate_broker_reconciliation_baseline_enrollment([_evidence(observed_at=start)], now=start)
    assert result.candidate is None


def test_source_bound_single_sample_rejects_runtime_mismatch():
    start = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    result = evaluate_broker_reconciliation_baseline_enrollment(
        [_evidence(observed_at=start, runtime_target_sha256=_digest("9"))], now=start,
        source_receipts_sha256=_digest("1"),
    )
    assert result.candidate is None
    assert BrokerReconciliationEnrollmentFinding.BASELINE_TARGET_MISMATCH in result.findings
