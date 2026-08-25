"""Fail-closed broker command policy shared by platform runtimes.

The platform provides broker-specific and reconciled facts. This pure function
then produces a durable decision immediately before an adapter is invoked; it
never calculates targets, infers exposure from an order side, or calls a broker.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import date
from enum import Enum
from typing import Any

from .execution_commands import ExecutionCommand, ExecutionCommandState
from .strategy_release import (
    StrategyReleaseIdentity,
    validate_runtime_loaded_receipt,
)


RUNTIME_COMMAND_GATE_RECEIPT_SCHEMA_VERSION = "runtime_command_gate_receipt.v1"


class RuntimeCommandGateMode(str, Enum):
    """The highest permitted broker-operation class for a runtime session."""

    ACTIVE = "active"
    REDUCING = "reducing"
    HALTED = "halted"


class RuntimeCommandGateEnforcement(str, Enum):
    """Whether a policy decision is recorded only or blocks a broker write."""

    OBSERVE = "observe"
    ENFORCE = "enforce"


class RuntimeCommandAction(str, Enum):
    """Normalized broker operation requested by a platform adapter."""

    QUERY = "query"
    CANCEL = "cancel"
    SUBMIT = "submit"
    MODIFY = "modify"


class RuntimeCommandExposureEffect(str, Enum):
    """Net-exposure effect established from reconciled positions.

    It cannot be inferred from ``buy`` or ``sell`` because that is unsafe for
    short books, options, combinations, and partially filled orders.
    """

    REDUCES = "reduces"
    NEUTRAL = "neutral"
    INCREASES = "increases"
    UNKNOWN = "unknown"


class RuntimeCommandIntegrityFinding(str, Enum):
    """Stable, redacted integrity signals accepted by the runtime gate.

    Strategy and plugin code may report these codes to a platform adapter, but
    they never acquire broker or allocation authority by doing so.  Unknown
    values are deliberately normalized to one opaque fail-closed code.
    """

    ACCOUNT_IDENTITY_CONFIGURATION_INVALID = "account_identity_configuration_invalid"
    ACCOUNT_IDENTITY_EVIDENCE_UNAVAILABLE = "account_identity_evidence_unavailable"
    ACCOUNT_IDENTITY_ID_MISMATCH = "account_identity_id_mismatch"
    ACCOUNT_IDENTITY_MODE_MISMATCH = "account_identity_mode_mismatch"
    ACCOUNT_IDENTITY_PLATFORM_MISMATCH = "account_identity_platform_mismatch"
    ACCOUNT_IDENTITY_TYPE_MISMATCH = "account_identity_type_mismatch"
    BROKER_OUTCOME_UNKNOWN = "broker_outcome_unknown"
    COMMAND_DIGEST_MISMATCH = "command_digest_mismatch"
    DATA_ARTIFACT_INVALID = "data_artifact_invalid"
    DATA_STALE = "data_stale"
    DATA_UNAVAILABLE = "data_unavailable"
    DURABLE_EVENT_HISTORY_INVALID = "durable_event_history_invalid"
    EXECUTION_REPLAY_DETECTED = "execution_replay_detected"
    INVALID_EFFECTIVE_SESSION = "invalid_effective_session"
    MANUAL_KILL_SWITCH = "manual_kill_switch"
    PLUGIN_INVALID = "plugin_invalid"
    POSITION_RECONCILIATION_MISMATCH = "position_reconciliation_mismatch"
    PAPER_EXECUTION_MODE_INVALID = "paper_execution_mode_invalid"
    PAPER_RISK_ADMISSION_COMMAND_MISMATCH = "paper_risk_admission_command_mismatch"
    PAPER_RISK_ADMISSION_HALTED = "paper_risk_admission_halted"
    PAPER_RISK_ADMISSION_POLICY_MISMATCH = "paper_risk_admission_policy_mismatch"
    PAPER_RISK_ADMISSION_RECEIPT_INVALID = "paper_risk_admission_receipt_invalid"
    PAPER_RISK_ADMISSION_RECEIPT_MISSING = "paper_risk_admission_receipt_missing"
    PAPER_RISK_ADMISSION_RELEASE_MISMATCH = "paper_risk_admission_release_mismatch"
    PAPER_RISK_ADMISSION_REDUCING_ONLY = "paper_risk_admission_reducing_only"
    RELEASE_IDENTITY_INVALID = "release_identity_invalid"
    RELEASE_IDENTITY_MISMATCH = "release_identity_mismatch"
    RELEASE_RECEIPT_MISSING = "release_receipt_missing"
    SIGNAL_TIMING_INVALID = "signal_timing_invalid"
    UNKNOWN_INTEGRITY_FINDING = "unknown_integrity_finding"


_MODE_PRIORITY = {
    RuntimeCommandGateMode.ACTIVE: 0,
    RuntimeCommandGateMode.REDUCING: 1,
    RuntimeCommandGateMode.HALTED: 2,
}
_HALTING_FINDINGS = frozenset(
    {
        RuntimeCommandIntegrityFinding.ACCOUNT_IDENTITY_CONFIGURATION_INVALID.value,
        RuntimeCommandIntegrityFinding.ACCOUNT_IDENTITY_EVIDENCE_UNAVAILABLE.value,
        RuntimeCommandIntegrityFinding.ACCOUNT_IDENTITY_ID_MISMATCH.value,
        RuntimeCommandIntegrityFinding.ACCOUNT_IDENTITY_MODE_MISMATCH.value,
        RuntimeCommandIntegrityFinding.ACCOUNT_IDENTITY_PLATFORM_MISMATCH.value,
        RuntimeCommandIntegrityFinding.ACCOUNT_IDENTITY_TYPE_MISMATCH.value,
        RuntimeCommandIntegrityFinding.BROKER_OUTCOME_UNKNOWN.value,
        RuntimeCommandIntegrityFinding.COMMAND_DIGEST_MISMATCH.value,
        RuntimeCommandIntegrityFinding.DURABLE_EVENT_HISTORY_INVALID.value,
        RuntimeCommandIntegrityFinding.EXECUTION_REPLAY_DETECTED.value,
        RuntimeCommandIntegrityFinding.INVALID_EFFECTIVE_SESSION.value,
        RuntimeCommandIntegrityFinding.MANUAL_KILL_SWITCH.value,
        RuntimeCommandIntegrityFinding.PAPER_EXECUTION_MODE_INVALID.value,
        RuntimeCommandIntegrityFinding.PAPER_RISK_ADMISSION_COMMAND_MISMATCH.value,
        RuntimeCommandIntegrityFinding.PAPER_RISK_ADMISSION_HALTED.value,
        RuntimeCommandIntegrityFinding.PAPER_RISK_ADMISSION_POLICY_MISMATCH.value,
        RuntimeCommandIntegrityFinding.PAPER_RISK_ADMISSION_RECEIPT_INVALID.value,
        RuntimeCommandIntegrityFinding.PAPER_RISK_ADMISSION_RECEIPT_MISSING.value,
        RuntimeCommandIntegrityFinding.PAPER_RISK_ADMISSION_RELEASE_MISMATCH.value,
        RuntimeCommandIntegrityFinding.PLUGIN_INVALID.value,
        RuntimeCommandIntegrityFinding.POSITION_RECONCILIATION_MISMATCH.value,
        RuntimeCommandIntegrityFinding.RELEASE_IDENTITY_INVALID.value,
        RuntimeCommandIntegrityFinding.RELEASE_IDENTITY_MISMATCH.value,
        RuntimeCommandIntegrityFinding.RELEASE_RECEIPT_MISSING.value,
        RuntimeCommandIntegrityFinding.SIGNAL_TIMING_INVALID.value,
    }
)
_REDUCING_FINDINGS = frozenset(
    {
        RuntimeCommandIntegrityFinding.DATA_ARTIFACT_INVALID.value,
        RuntimeCommandIntegrityFinding.DATA_UNAVAILABLE.value,
        RuntimeCommandIntegrityFinding.DATA_STALE.value,
        RuntimeCommandIntegrityFinding.PAPER_RISK_ADMISSION_REDUCING_ONLY.value,
    }
)
_KNOWN_INTEGRITY_FINDINGS = _HALTING_FINDINGS | _REDUCING_FINDINGS


def _normalize_enum(value: object, enum_type: type[Enum], *, field_name: str) -> Enum:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(str(value or "").strip().lower())
    except ValueError as exc:
        supported = ", ".join(str(item.value) for item in enum_type)
        raise ValueError(f"{field_name} must be one of: {supported}") from exc


def _normalize_date(value: object, *, field_name: str) -> str:
    try:
        return date.fromisoformat(str(value or "").strip()[:10]).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field_name} must start with an ISO date") from exc


def _append_reason(reasons: list[str], reason: str) -> None:
    if reason not in reasons:
        reasons.append(reason)


def _raise_mode(mode: RuntimeCommandGateMode, candidate: RuntimeCommandGateMode) -> RuntimeCommandGateMode:
    return candidate if _MODE_PRIORITY[candidate] > _MODE_PRIORITY[mode] else mode


@dataclass(frozen=True)
class RuntimeCommandGatePolicy:
    """Reviewed static policy; strict checks are observation-only by default."""

    mode: RuntimeCommandGateMode = RuntimeCommandGateMode.ACTIVE
    enforcement: RuntimeCommandGateEnforcement = RuntimeCommandGateEnforcement.OBSERVE
    require_durable_command: bool = True
    require_due_session: bool = True
    require_release_attestation: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "mode",
            _normalize_enum(self.mode, RuntimeCommandGateMode, field_name="mode"),
        )
        object.__setattr__(
            self,
            "enforcement",
            _normalize_enum(
                self.enforcement,
                RuntimeCommandGateEnforcement,
                field_name="enforcement",
            ),
        )


@dataclass(frozen=True)
class RuntimeCommandGateDecision:
    """Deterministic policy result and redacted receipt for a runtime audit."""

    command_id: str | None
    action: RuntimeCommandAction
    exposure_effect: RuntimeCommandExposureEffect
    mode: RuntimeCommandGateMode
    enforcement: RuntimeCommandGateEnforcement
    policy_allows: bool
    reasons: tuple[str, ...]
    release_id: str | None = None
    effective_session: str | None = None
    as_of_session: str | None = None

    @property
    def broker_write_allowed(self) -> bool:
        """Whether an adapter may proceed in the selected enforcement mode."""

        return self.policy_allows or self.enforcement is RuntimeCommandGateEnforcement.OBSERVE

    @property
    def would_block(self) -> bool:
        return not self.policy_allows

    def to_receipt(self) -> dict[str, object]:
        """Return safe audit data without copying order intent or account details."""

        payload = asdict(self)
        payload.update(
            {
                "schema_version": RUNTIME_COMMAND_GATE_RECEIPT_SCHEMA_VERSION,
                "action": self.action.value,
                "exposure_effect": self.exposure_effect.value,
                "mode": self.mode.value,
                "enforcement": self.enforcement.value,
                "reasons": list(self.reasons),
                "broker_write_allowed": self.broker_write_allowed,
                "would_block": self.would_block,
            }
        )
        return payload


def normalize_runtime_command_integrity_findings(
    findings: Iterable[object],
) -> tuple[str, ...]:
    """Return only stable gate codes and fail closed for every unknown value.

    This is the shared boundary for platform monitors and strategy plugins. It
    prevents an untrusted plugin error string from leaking into a durable gate
    receipt while still making the resulting broker write fail closed.
    """

    normalized_findings: list[str] = []
    for finding in findings:
        normalized = str(finding.value if isinstance(finding, Enum) else finding or "").strip().lower()
        if not normalized:
            continue
        safe_code = (
            normalized
            if normalized in _KNOWN_INTEGRITY_FINDINGS
            else RuntimeCommandIntegrityFinding.UNKNOWN_INTEGRITY_FINDING.value
        )
        _append_reason(normalized_findings, safe_code)
    return tuple(normalized_findings)


def evaluate_runtime_command_gate(
    *,
    action: RuntimeCommandAction | str,
    exposure_effect: RuntimeCommandExposureEffect | str = RuntimeCommandExposureEffect.UNKNOWN,
    command: ExecutionCommand | None = None,
    command_state: ExecutionCommandState | str | None = None,
    as_of_session: object | None = None,
    runtime_release_receipt: Mapping[str, Any] | None = None,
    expected_strategy_release: StrategyReleaseIdentity | Mapping[str, object] | None = None,
    integrity_findings: Iterable[object] = (),
    policy: RuntimeCommandGatePolicy | None = None,
) -> RuntimeCommandGateDecision:
    """Classify a broker operation without touching a broker.

    ``CANCEL`` and ``QUERY`` remain allowed in ``HALTED``. ``REDUCING`` accepts
    only orders whose reconciled net exposure effect is ``REDUCES``.
    """

    resolved_policy = policy or RuntimeCommandGatePolicy()
    resolved_action = _normalize_enum(action, RuntimeCommandAction, field_name="action")
    resolved_effect = _normalize_enum(
        exposure_effect,
        RuntimeCommandExposureEffect,
        field_name="exposure_effect",
    )
    mode = resolved_policy.mode
    reasons: list[str] = []
    for normalized in normalize_runtime_command_integrity_findings(integrity_findings):
        if normalized in _HALTING_FINDINGS:
            mode = _raise_mode(mode, RuntimeCommandGateMode.HALTED)
            _append_reason(reasons, normalized)
        elif normalized in _REDUCING_FINDINGS:
            mode = _raise_mode(mode, RuntimeCommandGateMode.REDUCING)
            _append_reason(reasons, normalized)
        else:
            mode = _raise_mode(mode, RuntimeCommandGateMode.HALTED)
            _append_reason(reasons, normalized)

    if command_state is not None:
        resolved_state = _normalize_enum(
            command_state,
            ExecutionCommandState,
            field_name="command_state",
        )
        if resolved_state is ExecutionCommandState.RECONCILIATION_REQUIRED:
            mode = _raise_mode(mode, RuntimeCommandGateMode.HALTED)
            _append_reason(reasons, "broker_outcome_unknown")

    as_of_date: str | None = None
    if as_of_session:
        try:
            as_of_date = _normalize_date(as_of_session, field_name="as_of_session")
        except ValueError:
            mode = _raise_mode(mode, RuntimeCommandGateMode.HALTED)
            _append_reason(reasons, "invalid_effective_session")
    is_write = resolved_action in {RuntimeCommandAction.SUBMIT, RuntimeCommandAction.MODIFY}
    if is_write and resolved_policy.require_durable_command and command is None:
        mode = _raise_mode(mode, RuntimeCommandGateMode.HALTED)
        _append_reason(reasons, "durable_command_missing")
    if is_write and resolved_policy.require_due_session:
        if command is None or as_of_date is None or not command.is_due_on(as_of_date):
            mode = _raise_mode(mode, RuntimeCommandGateMode.HALTED)
            _append_reason(reasons, "signal_timing_invalid")

    release_verification = validate_runtime_loaded_receipt(
        runtime_release_receipt,
        expected_strategy_release=expected_strategy_release,
        required=resolved_policy.require_release_attestation and is_write,
    )
    for reason in release_verification.findings:
        mode = _raise_mode(mode, RuntimeCommandGateMode.HALTED)
        _append_reason(reasons, reason)

    if resolved_action in {RuntimeCommandAction.QUERY, RuntimeCommandAction.CANCEL}:
        policy_allows = True
    else:
        if resolved_effect is RuntimeCommandExposureEffect.UNKNOWN:
            _append_reason(reasons, "exposure_effect_unknown")
        if mode is RuntimeCommandGateMode.HALTED:
            policy_allows = False
        elif resolved_effect is RuntimeCommandExposureEffect.UNKNOWN:
            policy_allows = False
        elif mode is RuntimeCommandGateMode.REDUCING:
            policy_allows = resolved_effect is RuntimeCommandExposureEffect.REDUCES
        else:
            policy_allows = True
        if not policy_allows:
            if mode is RuntimeCommandGateMode.REDUCING:
                _append_reason(reasons, "reducing_mode_requires_exposure_reduction")

    return RuntimeCommandGateDecision(
        command_id=command.command_id if command is not None else None,
        action=resolved_action,
        exposure_effect=resolved_effect,
        mode=mode,
        enforcement=resolved_policy.enforcement,
        policy_allows=policy_allows,
        reasons=tuple(reasons),
        release_id=release_verification.release_id,
        effective_session=command.effective_date if command is not None else None,
        as_of_session=as_of_date,
    )


__all__ = [
    "RUNTIME_COMMAND_GATE_RECEIPT_SCHEMA_VERSION",
    "RuntimeCommandAction",
    "RuntimeCommandExposureEffect",
    "RuntimeCommandGateDecision",
    "RuntimeCommandGateEnforcement",
    "RuntimeCommandIntegrityFinding",
    "RuntimeCommandGateMode",
    "RuntimeCommandGatePolicy",
    "evaluate_runtime_command_gate",
    "normalize_runtime_command_integrity_findings",
]
