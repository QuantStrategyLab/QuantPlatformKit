"""Shared vocabulary for B13-b shadow guards (no I/O)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class ExecutionMode(str, Enum):
    """Runtime mode presented to the guard (adapter-normalized)."""

    LIVE = "live"
    DRY_RUN = "dry_run"
    PAPER = "paper"


class SubmissionCertainty(str, Enum):
    """Shared submission certainty (B13-a §2). Does not replace broker strings."""

    KNOWN_FAILED = "known_failed"
    UNKNOWN = "unknown"
    FILLED_ACCOUNTING_PENDING = "filled_accounting_pending"
    TERMINAL = "terminal"
    NOT_APPLICABLE = "not_applicable"


DecisionLiteral = Literal["allow", "deny"]


@dataclass(frozen=True, slots=True)
class ExecutionGuardDecision:
    """Pure guard outcome. Not a broker ACK, fill proof, or digest health signal."""

    decision: DecisionLiteral
    reason_code: str
    certainty: SubmissionCertainty | None = None
    notes: str = ""

    @property
    def allowed(self) -> bool:
        return self.decision == "allow"


@dataclass(frozen=True, slots=True)
class LiveSubmitSnapshot:
    """Inputs for T1 — deny live submit without durable identity."""

    mode: ExecutionMode
    dry_run_bypass: bool
    identity_held: bool


@dataclass(frozen=True, slots=True)
class SubmissionUnknownSnapshot:
    """Inputs for T2 — deny new-cycle submit when submission is unknown."""

    submission_certainty: SubmissionCertainty
    requesting_new_cycle_submit: bool


@dataclass(frozen=True, slots=True)
class SubmissionRetrySnapshot:
    """Inputs for T3 — deny blind retry after uncertain transport."""

    transport_uncertain: bool
    reconciled: bool
    requesting_blind_retry: bool
