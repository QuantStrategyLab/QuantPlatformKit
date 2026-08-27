"""Broker-free, paper-only consumer for durable execution commands.

This module owns the platform-independent safety lifecycle for an immutable
command: release preflight, create-only claiming, paper-risk admission, runtime
gate receipts, and an append-only state chain.  A platform supplies only a
``reconcile_command`` callback.  That callback must obtain and reconcile its
own account/market evidence and return proposed *paper* orders; it is never
given an execution port and this module never imports a broker SDK.

The boundary deliberately does not attempt to normalize broker order types or
account semantics.  That would make an unsafe generic order router.  It
normalizes only the evidence and lifecycle that every platform must satisfy.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from .execution_commands import (
    ExecutionCommand,
    ExecutionCommandState,
    ExecutionCommandStore,
    validate_execution_command_release_binding,
)
from .paper_execution_admission import evaluate_paper_execution_admission
from .runtime_command_gate import (
    RuntimeCommandAction,
    RuntimeCommandExposureEffect,
    RuntimeCommandGateEnforcement,
    RuntimeCommandGatePolicy,
    normalize_runtime_command_integrity_findings,
    evaluate_runtime_command_gate,
)
from .strategy_release import (
    StrategyReleaseIdentity,
    build_strategy_release_identity,
    validate_runtime_loaded_receipt,
)


PAPER_EXECUTION_COMMAND_CONSUMER_SCHEMA_VERSION = "paper_execution_command_consumer.v1"
_PAPER_COMMAND_GATE_POLICY = RuntimeCommandGatePolicy(
    enforcement=RuntimeCommandGateEnforcement.ENFORCE,
)
_SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _safe_symbol(value: object) -> str:
    symbol = str(value or "").strip().upper()
    if not _SYMBOL_PATTERN.fullmatch(symbol):
        raise ValueError("proposal symbol must be a bounded broker-neutral identifier")
    return symbol


def _json_audit_mapping(value: Mapping[str, object]) -> dict[str, object]:
    """Normalize a JSON-safe, platform-supplied audit record.

    This is intentionally an audit boundary, not an order schema.  Platforms
    retain their own order semantics but must avoid account identifiers,
    credentials, or raw broker responses in the returned record.
    """

    if not isinstance(value, Mapping):
        raise ValueError("proposal details must be a mapping")
    try:
        encoded = json.dumps(dict(value), ensure_ascii=True, allow_nan=False, sort_keys=True)
        decoded = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise ValueError("proposal details must be JSON serializable") from exc
    if not isinstance(decoded, dict):  # Defensive for unusual Mapping implementations.
        raise ValueError("proposal details must be a JSON object")
    return decoded


@dataclass(frozen=True)
class PaperExecutionProposal:
    """One fully reconciled paper proposal supplied by a platform adapter."""

    symbol: str
    exposure_effect: RuntimeCommandExposureEffect | str
    details: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", _safe_symbol(self.symbol))
        try:
            effect = (
                self.exposure_effect
                if isinstance(self.exposure_effect, RuntimeCommandExposureEffect)
                else RuntimeCommandExposureEffect(str(self.exposure_effect or "").strip().lower())
            )
        except ValueError as exc:
            raise ValueError("proposal exposure_effect is invalid") from exc
        object.__setattr__(self, "exposure_effect", effect)
        object.__setattr__(self, "details", _json_audit_mapping(self.details))

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "exposure_effect": self.exposure_effect.value,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class PaperExecutionReconciliation:
    """Platform evidence after reconciling current positions and market data."""

    proposals: Sequence[PaperExecutionProposal]
    integrity_findings: Sequence[object] = ()

    def __post_init__(self) -> None:
        proposals = tuple(self.proposals)
        if any(not isinstance(proposal, PaperExecutionProposal) for proposal in proposals):
            raise ValueError("reconciliation proposals must be PaperExecutionProposal values")
        object.__setattr__(self, "proposals", proposals)
        object.__setattr__(
            self,
            "integrity_findings",
            normalize_runtime_command_integrity_findings(self.integrity_findings),
        )


PaperExecutionCommandReconciler = Callable[[ExecutionCommand], PaperExecutionReconciliation]


def _append_or_raise(
    store: ExecutionCommandStore,
    command: ExecutionCommand,
    *,
    next_state: ExecutionCommandState,
    expected_previous_state: ExecutionCommandState,
    details: Mapping[str, object],
) -> None:
    event = store.append_event(
        command,
        next_state=next_state,
        expected_previous_state=expected_previous_state,
        details=details,
    )
    if event is None:
        raise RuntimeError(f"failed to persist paper command event {next_state.value}")


def _attempt_reconciliation_required(
    store: ExecutionCommandStore,
    command: ExecutionCommand,
    *,
    error: Exception,
) -> None:
    """Leave claimed work visibly unresolved when its simulation cannot finish."""

    try:
        state = store.current_state(command)
        if state not in {
            ExecutionCommandState.CLAIMED,
            ExecutionCommandState.SUBMITTED,
            ExecutionCommandState.ACCEPTED,
            ExecutionCommandState.PARTIALLY_FILLED,
        }:
            return
        store.append_event(
            command,
            next_state=ExecutionCommandState.RECONCILIATION_REQUIRED,
            expected_previous_state=state,
            details={
                "paper_simulation": True,
                "reason": "consumer_exception_requires_manual_reconciliation",
                "error_type": type(error).__name__,
            },
        )
    except Exception:
        # Do not mask the original consumer/storage failure with a secondary
        # audit attempt.  The caller reports it as reconciliation-required.
        return


def _command_details(
    *,
    claimant: str,
    admission_disposition: str,
    admission_receipt_sha256: str | None,
    integrity_findings: Sequence[str],
    proposals: Sequence[PaperExecutionProposal],
    receipts: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    return {
        "paper_simulation": True,
        "claimant": claimant,
        "paper_execution_admission": {
            "disposition": admission_disposition,
            "receipt_sha256": admission_receipt_sha256,
        },
        "integrity_findings": list(integrity_findings),
        "proposals": [proposal.to_dict() for proposal in proposals],
        "runtime_command_gate_receipts": [dict(receipt) for receipt in receipts],
    }


def consume_due_paper_execution_commands(
    *,
    store: ExecutionCommandStore | None,
    as_of_session: date | str,
    claimant: str,
    reconcile_command: PaperExecutionCommandReconciler,
    runtime_release_receipt: Mapping[str, Any] | None,
    expected_strategy_release: StrategyReleaseIdentity | Mapping[str, object] | None,
) -> dict[str, object]:
    """Claim and simulate due paper commands without creating broker orders.

    The caller must point ``store`` at a dedicated create-only command prefix.
    No configuration has an implicit fallback: absent storage/release evidence
    blocks before a command is claimed, so an operator can correct it safely.
    """

    if store is None or (not store.cloud_prefix_uri and not store.local_dir):
        raise RuntimeError("paper durable execution command store is required")
    if not callable(reconcile_command):
        raise ValueError("reconcile_command must be callable")
    try:
        expected_release = build_strategy_release_identity(expected_strategy_release)
    except ValueError:
        return {
            "schema_version": PAPER_EXECUTION_COMMAND_CONSUMER_SCHEMA_VERSION,
            "status": "blocked",
            "reason": "release_identity_invalid",
            "commands": [],
        }
    release_preflight = validate_runtime_loaded_receipt(
        runtime_release_receipt,
        expected_strategy_release=expected_release,
    )
    if not release_preflight.is_valid:
        return {
            "schema_version": PAPER_EXECUTION_COMMAND_CONSUMER_SCHEMA_VERSION,
            "status": "blocked",
            "reason": release_preflight.findings[0],
            "commands": [],
        }

    as_of_date = str(as_of_session)[:10]
    commands: list[dict[str, object]] = []
    for command in store.list_due(as_of_date):
        if store.current_state(command) is not ExecutionCommandState.QUEUED:
            continue
        claim = store.claim_due(command, as_of_date=as_of_date, claimant=claimant)
        if claim is None:
            continue
        try:
            admission = evaluate_paper_execution_admission(
                command=command,
                expected_strategy_release=expected_release,
            )
            integrity_findings = list(admission.integrity_findings)
            integrity_findings.extend(
                validate_execution_command_release_binding(
                    command,
                    expected_strategy_release=expected_release,
                ).findings
            )
            reconciliation = reconcile_command(command)
            if not isinstance(reconciliation, PaperExecutionReconciliation):
                raise ValueError("reconcile_command must return PaperExecutionReconciliation")
            integrity_findings.extend(reconciliation.integrity_findings)
            integrity_findings = list(
                dict.fromkeys(normalize_runtime_command_integrity_findings(integrity_findings))
            )
            proposals = tuple(reconciliation.proposals)
            effects = [proposal.exposure_effect for proposal in proposals]
            if not effects:
                # A no-op still has to pass timing, release, and paper-risk
                # checks before its paper lifecycle can close.
                effects = [RuntimeCommandExposureEffect.NEUTRAL]
            receipts = [
                evaluate_runtime_command_gate(
                    action=RuntimeCommandAction.SUBMIT,
                    exposure_effect=effect,
                    command=command,
                    command_state=ExecutionCommandState.CLAIMED,
                    as_of_session=as_of_date,
                    runtime_release_receipt=runtime_release_receipt,
                    expected_strategy_release=expected_release,
                    integrity_findings=integrity_findings,
                    policy=_PAPER_COMMAND_GATE_POLICY,
                ).to_receipt()
                for effect in effects
            ]
            details = _command_details(
                claimant=str(claim.details["claimant"]),
                admission_disposition=admission.disposition.value,
                admission_receipt_sha256=admission.receipt_sha256,
                integrity_findings=integrity_findings,
                proposals=proposals,
                receipts=receipts,
            )
            if any(not bool(receipt["policy_allows"]) for receipt in receipts):
                _append_or_raise(
                    store,
                    command,
                    next_state=ExecutionCommandState.REJECTED,
                    expected_previous_state=ExecutionCommandState.CLAIMED,
                    details={**details, "reason": "paper_command_gate_would_block"},
                )
                commands.append(
                    {
                        "command_id": command.command_id,
                        "status": ExecutionCommandState.REJECTED.value,
                        "proposals_count": len(proposals),
                        "would_block": True,
                    }
                )
                continue

            _append_or_raise(
                store,
                command,
                next_state=ExecutionCommandState.SUBMITTED,
                expected_previous_state=ExecutionCommandState.CLAIMED,
                details=details,
            )
            _append_or_raise(
                store,
                command,
                next_state=ExecutionCommandState.ACCEPTED,
                expected_previous_state=ExecutionCommandState.SUBMITTED,
                details={"paper_simulation": True, "proposals_count": len(proposals)},
            )
            _append_or_raise(
                store,
                command,
                next_state=ExecutionCommandState.FILLED,
                expected_previous_state=ExecutionCommandState.ACCEPTED,
                details={"paper_simulation": True, "simulated_fill_count": len(proposals)},
            )
            commands.append(
                {
                    "command_id": command.command_id,
                    "status": ExecutionCommandState.FILLED.value,
                    "proposals_count": len(proposals),
                    "would_block": False,
                }
            )
        except Exception as exc:
            _attempt_reconciliation_required(store, command, error=exc)
            commands.append(
                {
                    "command_id": command.command_id,
                    "status": ExecutionCommandState.RECONCILIATION_REQUIRED.value,
                    "error_type": type(exc).__name__,
                }
            )

    return {
        "schema_version": PAPER_EXECUTION_COMMAND_CONSUMER_SCHEMA_VERSION,
        "status": "ok",
        "as_of_session": as_of_date,
        "commands": commands,
    }


__all__ = [
    "PAPER_EXECUTION_COMMAND_CONSUMER_SCHEMA_VERSION",
    "PaperExecutionCommandReconciler",
    "PaperExecutionProposal",
    "PaperExecutionReconciliation",
    "consume_due_paper_execution_commands",
]
