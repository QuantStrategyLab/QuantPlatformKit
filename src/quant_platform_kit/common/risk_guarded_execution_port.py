"""An APPROVE assessment only permits the delegate call inside the freshness window.

It does not grant live authority, funds, or execution permission.
``execution_authorized=False`` on the assessment is expected and ignored.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import math
from numbers import Real

from ..risk.contracts import RiskGateAssessment
from .models import ExecutionReport, OrderIntent
from .ports import ExecutionPort


class RiskGuardedExecutionRejected(RuntimeError):
    """The assessment does not permit the delegate call."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason: str = reason


class RiskGuardedExecutionPort:
    """An APPROVE assessment only permits the delegate call inside the freshness window.

    It does not grant live authority, funds, or execution permission.
    ``execution_authorized=False`` on the assessment is expected and ignored.
    """

    def __init__(
        self,
        delegate: ExecutionPort,
        assessment: RiskGateAssessment | None,
        *,
        max_age_seconds: float = 300.0,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if (
            isinstance(max_age_seconds, bool)
            or not isinstance(max_age_seconds, Real)
            or not math.isfinite(max_age_seconds)
            or max_age_seconds < 0
        ):
            raise TypeError("RISK_GUARD_POLICY_INVALID")
        if now is not None and not callable(now):
            raise TypeError("RISK_GUARD_POLICY_INVALID")
        self.delegate = delegate
        self.assessment = assessment
        self.max_age_seconds = max_age_seconds
        self.now = now if now is not None else lambda: datetime.now(timezone.utc)

    def submit_order(self, order: OrderIntent) -> ExecutionReport:
        if self.assessment is None:
            raise RiskGuardedExecutionRejected("RISK_GATE_ASSESSMENT_MISSING")
        if self.assessment.outcome != "APPROVE":
            raise RiskGuardedExecutionRejected("RISK_GATE_NOT_APPROVED")

        timestamp = self.assessment.evaluated_at
        if not isinstance(timestamp, str):
            raise RiskGuardedExecutionRejected("RISK_GATE_ASSESSMENT_INVALID")
        if timestamp.endswith("Z"):
            timestamp = timestamp[:-1] + "+00:00"
        try:
            evaluated_at = datetime.fromisoformat(timestamp)
        except ValueError:
            raise RiskGuardedExecutionRejected("RISK_GATE_ASSESSMENT_INVALID") from None
        if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
            raise RiskGuardedExecutionRejected("RISK_GATE_ASSESSMENT_INVALID")

        age = (self.now() - evaluated_at).total_seconds()
        if age < 0:
            raise RiskGuardedExecutionRejected("RISK_GATE_ASSESSMENT_CLOCK_INVALID")
        if age > self.max_age_seconds:
            raise RiskGuardedExecutionRejected("RISK_GATE_ASSESSMENT_STALE")
        return self.delegate.submit_order(order)
