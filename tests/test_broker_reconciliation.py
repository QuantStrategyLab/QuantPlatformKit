from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from quant_platform_kit.common.broker_reconciliation import (
    BrokerReconciliationEvidence,
    BrokerReconciliationFinding,
    build_broker_reconciliation_evidence,
    calculate_broker_observation_sha256,
    evaluate_broker_reconciliation_recovery,
)


def _digest(character: str) -> str:
    return character * 64


def _evidence(**overrides: object) -> BrokerReconciliationEvidence:
    payload: dict[str, object] = {
        "platform_id": "interactive-brokers",
        "strategy_profile": "soxl_soxx_trend_income",
        "account_scope_sha256": _digest("a"),
        "baseline_id": "soxl-ibkr-lkg-20260830",
        "baseline_target_sha256": _digest("b"),
        "runtime_target_sha256": _digest("b"),
        "observed_at": datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc),
        "broker_connected": True,
        "account_identity_match": True,
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


def test_fresh_complete_evidence_is_recovery_eligible() -> None:
    evidence = _evidence()

    assert evaluate_broker_reconciliation_recovery(
        evidence,
        now=datetime(2026, 8, 30, 8, 5, tzinfo=timezone.utc),
        expected_platform_id="interactive-brokers",
        expected_strategy_profile="soxl_soxx_trend_income",
        expected_account_scope_sha256=_digest("a"),
        expected_baseline_id="soxl-ibkr-lkg-20260830",
        expected_runtime_target_sha256=_digest("b"),
    ) == ()


def test_any_unmatched_broker_surface_fails_closed() -> None:
    evidence = _evidence(open_orders_match=False, local_execution_ledger_match=False)

    assert evaluate_broker_reconciliation_recovery(
        evidence,
        now=datetime(2026, 8, 30, 8, 5, tzinfo=timezone.utc),
    ) == (
        BrokerReconciliationFinding.OPEN_ORDERS_MISMATCH,
        BrokerReconciliationFinding.LOCAL_EXECUTION_LEDGER_MISMATCH,
    )


@pytest.mark.parametrize(
    ("field", "finding"),
    [
        ("positions_match", BrokerReconciliationFinding.POSITIONS_MISMATCH),
        ("cash_match", BrokerReconciliationFinding.CASH_MISMATCH),
        ("open_orders_match", BrokerReconciliationFinding.OPEN_ORDERS_MISMATCH),
        ("recent_executions_match", BrokerReconciliationFinding.RECENT_EXECUTIONS_MISMATCH),
        ("local_execution_ledger_match", BrokerReconciliationFinding.LOCAL_EXECUTION_LEDGER_MISMATCH),
        ("account_identity_match", BrokerReconciliationFinding.ACCOUNT_IDENTITY_MISMATCH),
    ],
)
def test_matching_digests_never_override_negative_comparisons(field, finding) -> None:
    evidence = _evidence(**{field: False})
    expected = {
        f"expected_{name}_sha256": getattr(evidence, f"{name}_sha256")
        for name in ("account_scope", "positions", "cash", "open_orders", "recent_executions", "local_execution_ledger")
    }

    assert evaluate_broker_reconciliation_recovery(
        evidence, now=evidence.observed_at, **expected,
    ) == (finding,)


def test_equal_state_digests_do_not_prove_the_expected_account() -> None:
    evidence = _evidence()

    assert evaluate_broker_reconciliation_recovery(
        evidence,
        now=evidence.observed_at,
        expected_account_scope_sha256=_digest("9"),
        expected_positions_sha256=evidence.positions_sha256,
        expected_cash_sha256=evidence.cash_sha256,
    ) == (BrokerReconciliationFinding.ACCOUNT_IDENTITY_MISMATCH,)


def test_explicit_missing_baseline_does_not_misreport_unknown_surfaces_as_mismatches() -> None:
    evidence = _evidence(
        broker_connected=False,
        account_identity_match=False,
        positions_match=False,
        cash_match=False,
        open_orders_match=False,
        recent_executions_match=False,
        local_execution_ledger_match=False,
    )

    assert evaluate_broker_reconciliation_recovery(
        evidence,
        now=datetime(2026, 8, 30, 8, 5, tzinfo=timezone.utc),
        baseline_reference_available=False,
    ) == (
        BrokerReconciliationFinding.BASELINE_UNAVAILABLE,
        BrokerReconciliationFinding.BROKER_CONNECTION_FAILED,
        BrokerReconciliationFinding.ACCOUNT_IDENTITY_MISMATCH,
    )


def test_explicit_missing_baseline_is_reported_when_evidence_is_unavailable() -> None:
    assert evaluate_broker_reconciliation_recovery(
        None,
        baseline_reference_available=False,
    ) == (
        BrokerReconciliationFinding.BASELINE_UNAVAILABLE,
        BrokerReconciliationFinding.BROKER_CONNECTION_FAILED,
    )


def test_independent_expected_snapshot_digests_are_checked() -> None:
    evidence = _evidence()

    assert evaluate_broker_reconciliation_recovery(
        evidence,
        now=datetime(2026, 8, 30, 8, 5, tzinfo=timezone.utc),
        expected_positions_sha256=_digest("9"),
        expected_cash_sha256=_digest("d"),
    ) == (BrokerReconciliationFinding.POSITIONS_MISMATCH,)


def test_stale_or_target_drift_evidence_cannot_resume_live_baseline() -> None:
    stale = _evidence(observed_at=datetime(2026, 8, 30, 7, 0, tzinfo=timezone.utc))
    drifted = _evidence(runtime_target_sha256=_digest("9"))

    assert evaluate_broker_reconciliation_recovery(
        stale,
        now=datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc),
        max_age=timedelta(minutes=30),
    ) == (BrokerReconciliationFinding.EVIDENCE_STALE,)
    assert evaluate_broker_reconciliation_recovery(
        drifted,
        now=datetime(2026, 8, 30, 8, 5, tzinfo=timezone.utc),
    ) == (BrokerReconciliationFinding.BASELINE_TARGET_MISMATCH,)


def test_evidence_is_content_addressed_and_redacted() -> None:
    evidence = _evidence()
    reloaded = BrokerReconciliationEvidence.from_dict(evidence.to_dict())

    assert reloaded == evidence
    assert "account_scope" not in evidence.to_dict()
    assert calculate_broker_observation_sha256({"B": [2, 1], "A": 1}) == calculate_broker_observation_sha256(
        {"A": 1, "B": [2, 1]}
    )


def test_tampered_evidence_is_rejected() -> None:
    payload = _evidence().to_dict()
    payload["cash_match"] = False

    with pytest.raises(ValueError, match="evidence_sha256 mismatch"):
        BrokerReconciliationEvidence.from_dict(payload)
