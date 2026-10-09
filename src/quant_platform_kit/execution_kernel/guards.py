"""B13-b T1–T3 pure guards. Table-driven; no storage side effects."""

from __future__ import annotations

from .types import (
    ExecutionGuardDecision,
    ExecutionMode,
    LiveSubmitSnapshot,
    SubmissionCertainty,
    SubmissionRetrySnapshot,
    SubmissionUnknownSnapshot,
)

REASON_MISSING_DURABLE_IDENTITY = "missing_durable_identity"
REASON_SUBMISSION_UNCERTAIN = "submission_uncertain"
REASON_RECONCILE_REQUIRED = "reconcile_required"
REASON_OK = "ok"


def deny_live_submit_without_durable_identity(
    snapshot: LiveSubmitSnapshot,
) -> ExecutionGuardDecision:
    """T1 / G1: live ∧ ¬bypass ∧ ¬identity → deny.

    Dry-run / paper / configured bypass do not require durable identity here;
    adapters still must keep broker writes closed on those paths.
    """
    requires_identity = (
        snapshot.mode is ExecutionMode.LIVE and not snapshot.dry_run_bypass
    )
    if requires_identity and not snapshot.identity_held:
        return ExecutionGuardDecision(
            decision="deny",
            reason_code=REASON_MISSING_DURABLE_IDENTITY,
            notes="live submit requires adapter-held durable identity",
        )
    return ExecutionGuardDecision(decision="allow", reason_code=REASON_OK)


def deny_new_cycle_when_submission_unknown(
    snapshot: SubmissionUnknownSnapshot,
) -> ExecutionGuardDecision:
    """T2 / G2: certainty=unknown ∧ new-cycle submit → deny."""
    if (
        snapshot.requesting_new_cycle_submit
        and snapshot.submission_certainty is SubmissionCertainty.UNKNOWN
    ):
        return ExecutionGuardDecision(
            decision="deny",
            reason_code=REASON_SUBMISSION_UNCERTAIN,
            certainty=SubmissionCertainty.UNKNOWN,
            notes="unknown submission blocks a new cycle submit",
        )
    return ExecutionGuardDecision(
        decision="allow",
        reason_code=REASON_OK,
        certainty=snapshot.submission_certainty,
    )


def deny_blind_retry_after_uncertain_transport(
    snapshot: SubmissionRetrySnapshot,
) -> ExecutionGuardDecision:
    """T3 / G4: transport uncertain ∧ unreconciled ∧ blind retry → deny."""
    if (
        snapshot.requesting_blind_retry
        and snapshot.transport_uncertain
        and not snapshot.reconciled
    ):
        return ExecutionGuardDecision(
            decision="deny",
            reason_code=REASON_RECONCILE_REQUIRED,
            certainty=SubmissionCertainty.UNKNOWN,
            notes="uncertain transport requires reconcile before retry",
        )
    return ExecutionGuardDecision(decision="allow", reason_code=REASON_OK)
