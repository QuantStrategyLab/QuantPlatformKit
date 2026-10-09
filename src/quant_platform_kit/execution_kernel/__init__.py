"""Pure execution-kernel guards (B13-b T1–T3).

These helpers interpret an already-built snapshot and return allow/deny.
They never touch broker clients, GCS/Firestore claims, or platform locks.
Platform adapters remain responsible for durable identity storage.
"""

from .guards import (
    deny_blind_retry_after_uncertain_transport,
    deny_live_submit_without_durable_identity,
    deny_new_cycle_when_submission_unknown,
)
from .types import (
    ExecutionGuardDecision,
    ExecutionMode,
    LiveSubmitSnapshot,
    SubmissionCertainty,
    SubmissionRetrySnapshot,
    SubmissionUnknownSnapshot,
)

__all__ = [
    "ExecutionGuardDecision",
    "ExecutionMode",
    "LiveSubmitSnapshot",
    "SubmissionCertainty",
    "SubmissionRetrySnapshot",
    "SubmissionUnknownSnapshot",
    "deny_blind_retry_after_uncertain_transport",
    "deny_live_submit_without_durable_identity",
    "deny_new_cycle_when_submission_unknown",
]
