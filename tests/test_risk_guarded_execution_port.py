from datetime import datetime, timedelta, timezone

import pytest

from quant_platform_kit.common.models import ExecutionReport, OrderIntent
from quant_platform_kit.common.risk_guarded_execution_port import (
    RiskGuardedExecutionPort,
    RiskGuardedExecutionRejected,
)
from quant_platform_kit.risk.contracts import RiskGateAssessment


FIXED_NOW = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)
ORDER = OrderIntent(symbol="TEST", side="buy", quantity=1.0)


def _now() -> datetime:
    return FIXED_NOW


def _assessment(
    *,
    outcome: str = "APPROVE",
    evaluated_at: str = FIXED_NOW.isoformat(),
) -> RiskGateAssessment:
    return RiskGateAssessment(
        contract_version="synthetic-v1",
        scope="synthetic",
        evaluated_at=evaluated_at,
        policy_id="synthetic-policy",
        policy_version="1",
        qpk_source_revision=None,
        mandate_id=None,
        mandate_version=None,
        mandate_authority_receipt_sha256=None,
        mandate_scope=None,
        candidate_identity_sha256=None,
        decision_digest_sha256="a" * 64,
        portfolio_snapshot_digest_sha256="b" * 64,
        normalization_origin_digest_sha256=None,
        effective_exposure_cap=None,
        observed_effective_exposure=None,
        proposed_effective_exposure=None,
        outcome=outcome,
        reason_codes=(),
    )


class FakeDelegate:
    def __init__(self) -> None:
        self.calls: list[OrderIntent] = []
        self.report = ExecutionReport(
            symbol="TEST", side="buy", quantity=1.0, status="synthetic"
        )

    def submit_order(self, order: OrderIntent) -> ExecutionReport:
        self.calls.append(order)
        return self.report


@pytest.mark.parametrize(
    ("assessment", "reason"),
    [
        (_assessment(outcome="REJECT"), "RISK_GATE_NOT_APPROVED"),
        (None, "RISK_GATE_ASSESSMENT_MISSING"),
        (
            _assessment(evaluated_at=(FIXED_NOW - timedelta(seconds=301)).isoformat()),
            "RISK_GATE_ASSESSMENT_STALE",
        ),
        (
            _assessment(evaluated_at=(FIXED_NOW + timedelta(seconds=1)).isoformat()),
            "RISK_GATE_ASSESSMENT_CLOCK_INVALID",
        ),
        (
            _assessment(evaluated_at=FIXED_NOW.replace(tzinfo=None).isoformat()),
            "RISK_GATE_ASSESSMENT_INVALID",
        ),
        (_assessment(evaluated_at="invalid"), "RISK_GATE_ASSESSMENT_INVALID"),
        (_assessment(evaluated_at=None), "RISK_GATE_ASSESSMENT_INVALID"),
        (_assessment(evaluated_at=123), "RISK_GATE_ASSESSMENT_INVALID"),
    ],
)
def test_rejected_assessment_never_calls_delegate(assessment, reason) -> None:
    delegate = FakeDelegate()
    port = RiskGuardedExecutionPort(delegate, assessment, max_age_seconds=300.0, now=_now)

    with pytest.raises(RiskGuardedExecutionRejected) as caught:
        port.submit_order(ORDER)

    assert caught.value.reason == reason
    assert str(caught.value) == reason
    assert vars(caught.value) == {"reason": reason}
    assert delegate.calls == []


@pytest.mark.parametrize("max_age_seconds", [0.0, 300.0])
@pytest.mark.parametrize("use_z", [False, True])
def test_exact_age_boundary_calls_delegate_once_and_returns_same_report(
    max_age_seconds, use_z
) -> None:
    evaluated_at = (FIXED_NOW - timedelta(seconds=max_age_seconds)).isoformat()
    if use_z:
        evaluated_at = evaluated_at.replace("+00:00", "Z")
    delegate = FakeDelegate()
    port = RiskGuardedExecutionPort(
        delegate,
        _assessment(evaluated_at=evaluated_at),
        max_age_seconds=max_age_seconds,
        now=_now,
    )

    result = port.submit_order(ORDER)

    assert delegate.calls == [ORDER]
    assert delegate.calls[0] is ORDER
    assert result is delegate.report


def test_default_false_execution_authorized_is_ignored_without_adding_authority() -> None:
    delegate = FakeDelegate()
    assessment = _assessment()
    port = RiskGuardedExecutionPort(delegate, assessment, now=_now)

    result = port.submit_order(ORDER)

    assert assessment.execution_authorized is False
    assert delegate.calls == [ORDER]
    assert result is delegate.report
    assert vars(port) == {
        "delegate": delegate,
        "assessment": assessment,
        "max_age_seconds": 300.0,
        "now": _now,
    }


@pytest.mark.parametrize("max_age_seconds", [-1, True, float("nan"), float("inf"), "300", None])
def test_invalid_max_age_rejects_policy(max_age_seconds) -> None:
    delegate = FakeDelegate()

    with pytest.raises(TypeError, match="^RISK_GUARD_POLICY_INVALID$"):
        RiskGuardedExecutionPort(
            delegate, _assessment(), max_age_seconds=max_age_seconds, now=_now
        )

    assert delegate.calls == []


def test_non_callable_now_rejects_policy() -> None:
    delegate = FakeDelegate()

    with pytest.raises(TypeError, match="^RISK_GUARD_POLICY_INVALID$"):
        RiskGuardedExecutionPort(delegate, _assessment(), now=FIXED_NOW)

    assert delegate.calls == []
