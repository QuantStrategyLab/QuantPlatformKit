"""Fail-closed automation policy for non-live forward observation.

This is deliberately a pure decision module.  A strategy-specific scheduler
may use the returned non-live intent to start or continue *shadow* and
*paper* observation, but this module has no broker, order, runtime-target, or
deployment dependency.  In particular, completing a forward window never
produces live authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


FORWARD_OBSERVATION_POLICY_SCHEMA_VERSION = "forward_observation_policy.v1"

_NON_LIVE_MODES = frozenset({"shadow", "paper"})
_NON_LIVE_EVIDENCE_MODES = frozenset(
    {"shadow_decision", "simulated_replay", "broker_paper"}
)
_DATA_STATUSES = frozenset({"ready", "stale", "unavailable"})
_MODE_STATUSES = frozenset({"healthy", "mismatch", "unavailable"})
_RISK_STATUSES = frozenset({"pass", "blocked"})
_WINDOW_TYPES = frozenset({"fixed", "rolling"})
_CONTROL_STATUSES = frozenset(
    {"clear", "manual_hold", "identity_mismatch", "revoked", "superseded"}
)
_PREVIOUS_STATES = frozenset(
    {
        "not_started",
        "active",
        "paused",
        "complete",
        "manual_hold",
        "identity_mismatch",
        "risk_blocked",
        "revoked",
        "superseded",
    }
)
_STOPPED_ACTIONS = ("keep_shadow_stopped", "keep_paper_stopped")
_PERMANENT_PREVIOUS_STATES = frozenset(
    {"manual_hold", "identity_mismatch", "risk_blocked", "revoked", "superseded"}
)


class ForwardObservationPolicyError(ValueError):
    """Raised when a forward-observation policy or snapshot is ambiguous."""


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ForwardObservationPolicyError(f"{label} must be a non-empty string")
    return value.strip()


def _non_negative_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ForwardObservationPolicyError(f"{label} must be a non-negative integer")
    return value


def _session_date(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ForwardObservationPolicyError(f"{label} must be an ISO-8601 date")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ForwardObservationPolicyError(
            f"{label} must be an ISO-8601 date"
        ) from exc


@dataclass(frozen=True)
class ForwardObservationPolicy:
    """Candidate-specific rules for a no-capital forward-observation window.

    A caller must provide this explicitly for every frozen candidate rather
    than relying on a generic strategy default.  That prevents a new strategy
    from silently inheriting SOXL's 252-session standard or execution modes.
    """

    candidate_id: str
    strategy_profile: str
    domain: str
    benchmark_symbol: str
    required_trading_sessions: int
    review_milestones: tuple[int, ...]
    automatic_non_live_modes: tuple[str, ...]
    auto_resume_clean_sessions: int
    observation_calendar: str
    observation_window_type: str
    observation_start_session: str | None
    window_rationale_ref: str
    non_live_evidence_modes: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "candidate_id",
            "strategy_profile",
            "domain",
            "benchmark_symbol",
            "observation_calendar",
            "window_rationale_ref",
        ):
            _required_text(getattr(self, field_name), field_name)
        required = _non_negative_int(
            self.required_trading_sessions, "required_trading_sessions"
        )
        if required <= 0:
            raise ForwardObservationPolicyError(
                "required_trading_sessions must be greater than zero"
            )
        _non_negative_int(self.auto_resume_clean_sessions, "auto_resume_clean_sessions")
        if self.auto_resume_clean_sessions <= 0:
            raise ForwardObservationPolicyError(
                "auto_resume_clean_sessions must be greater than zero"
            )

        modes = tuple(str(mode).strip().lower() for mode in self.automatic_non_live_modes)
        if not modes or set(modes) != _NON_LIVE_MODES or len(modes) != len(_NON_LIVE_MODES):
            raise ForwardObservationPolicyError(
                "automatic_non_live_modes must contain shadow and paper exactly once"
            )
        milestones = tuple(self.review_milestones)
        if tuple(sorted(milestones)) != milestones or len(set(milestones)) != len(milestones):
            raise ForwardObservationPolicyError(
                "review_milestones must be strictly increasing"
            )
        if any(
            not isinstance(value, int)
            or isinstance(value, bool)
            or value <= 0
            or value >= required
            for value in milestones
        ):
            raise ForwardObservationPolicyError(
                "review_milestones must be positive integers below required_trading_sessions"
            )
        window_type = _required_text(
            self.observation_window_type, "observation_window_type"
        ).lower()
        if window_type not in _WINDOW_TYPES:
            raise ForwardObservationPolicyError(
                "observation_window_type must be fixed or rolling"
            )
        if window_type == "fixed":
            _session_date(self.observation_start_session, "observation_start_session")
        elif self.observation_start_session is not None:
            raise ForwardObservationPolicyError(
                "rolling observation_window_type must not set observation_start_session"
            )

        evidence_modes = tuple(
            str(mode).strip().lower() for mode in self.non_live_evidence_modes
        )
        if (
            len(evidence_modes) != 2
            or len(set(evidence_modes)) != 2
            or set(evidence_modes) - _NON_LIVE_EVIDENCE_MODES
            or "shadow_decision" not in evidence_modes
            or not ({"simulated_replay", "broker_paper"} & set(evidence_modes))
        ):
            raise ForwardObservationPolicyError(
                "non_live_evidence_modes must contain shadow_decision and exactly one paper mode"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": FORWARD_OBSERVATION_POLICY_SCHEMA_VERSION,
            "candidate_id": self.candidate_id,
            "strategy_profile": self.strategy_profile,
            "domain": self.domain,
            "benchmark_symbol": self.benchmark_symbol,
            "required_trading_sessions": self.required_trading_sessions,
            "review_milestones": list(self.review_milestones),
            "automatic_non_live_modes": list(self.automatic_non_live_modes),
            "auto_resume_clean_sessions": self.auto_resume_clean_sessions,
            "observation_calendar": self.observation_calendar,
            "observation_window_type": self.observation_window_type,
            "observation_start_session": self.observation_start_session,
            "window_rationale_ref": self.window_rationale_ref,
            "non_live_evidence_modes": list(self.non_live_evidence_modes),
            "live_authority_granted": False,
        }


@dataclass(frozen=True)
class ForwardObservationSnapshot:
    """Verified runtime facts supplied by a candidate's observation adapter."""

    historical_evidence_verified: bool
    historical_evidence_ref: str = ""
    observations_completed: int = 0
    previous_observations_completed: int = 0
    previous_state: str = "not_started"
    clean_sessions_since_pause: int = 0
    data_status: str = "ready"
    shadow_status: str = "healthy"
    paper_status: str = "healthy"
    risk_status: str = "pass"
    control_status: str = "clear"

    def __post_init__(self) -> None:
        if not isinstance(self.historical_evidence_verified, bool):
            raise ForwardObservationPolicyError(
                "historical_evidence_verified must be a boolean"
            )
        if self.historical_evidence_verified:
            _required_text(self.historical_evidence_ref, "historical_evidence_ref")
        current = _non_negative_int(
            self.observations_completed, "observations_completed"
        )
        previous = _non_negative_int(
            self.previous_observations_completed,
            "previous_observations_completed",
        )
        if previous > current:
            raise ForwardObservationPolicyError(
                "previous_observations_completed cannot exceed observations_completed"
            )
        _non_negative_int(self.clean_sessions_since_pause, "clean_sessions_since_pause")
        if self.previous_state not in _PREVIOUS_STATES:
            raise ForwardObservationPolicyError("unsupported previous_state")
        if self.data_status not in _DATA_STATUSES:
            raise ForwardObservationPolicyError("unsupported data_status")
        if self.shadow_status not in _MODE_STATUSES:
            raise ForwardObservationPolicyError("unsupported shadow_status")
        if self.paper_status not in _MODE_STATUSES:
            raise ForwardObservationPolicyError("unsupported paper_status")
        if self.risk_status not in _RISK_STATUSES:
            raise ForwardObservationPolicyError("unsupported risk_status")
        if self.control_status not in _CONTROL_STATUSES:
            raise ForwardObservationPolicyError("unsupported control_status")


@dataclass(frozen=True)
class ForwardObservationDecision:
    """A scheduler-safe result; it cannot grant live or broker authority."""

    candidate_id: str
    strategy_profile: str
    domain: str
    benchmark_symbol: str
    state: str
    non_live_actions: tuple[str, ...]
    notifications: tuple[str, ...]
    reasons: tuple[str, ...]
    observations_completed: int
    required_trading_sessions: int
    historical_evidence_ref: str | None
    live_action: str = "human_approval_required"
    no_order: bool = True
    live_authority_granted: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": FORWARD_OBSERVATION_POLICY_SCHEMA_VERSION,
            "candidate_id": self.candidate_id,
            "strategy_profile": self.strategy_profile,
            "domain": self.domain,
            "benchmark_symbol": self.benchmark_symbol,
            "state": self.state,
            "non_live_actions": list(self.non_live_actions),
            "notifications": list(self.notifications),
            "reasons": list(self.reasons),
            "observations_completed": self.observations_completed,
            "required_trading_sessions": self.required_trading_sessions,
            "historical_evidence_ref": self.historical_evidence_ref,
            "live_action": self.live_action,
            "no_order": self.no_order,
            "live_authority_granted": self.live_authority_granted,
        }


def evaluate_forward_observation(
    policy: ForwardObservationPolicy,
    snapshot: ForwardObservationSnapshot,
) -> ForwardObservationDecision:
    """Evaluate one non-live forward-observation cycle, fail closed by default.

    ``non_live_actions`` are declarative scheduler intents only.  An adapter
    still has to prove that it is a paper/shadow target; a live target must
    reject every action from this decision.
    """

    if not snapshot.historical_evidence_verified:
        return _decision(
            policy,
            snapshot,
            state="PARKED",
            actions=_STOPPED_ACTIONS,
            notifications=("historical_evidence_required",),
            reasons=("verified P3 historical evidence is required before P4",),
        )

    controlled = _controlled_stop(snapshot)
    if controlled is not None:
        state, notification, reason = controlled
        return _decision(
            policy,
            snapshot,
            state=state,
            actions=_STOPPED_ACTIONS,
            notifications=(notification,) if notification else (),
            reasons=(reason,),
        )

    if snapshot.risk_status == "blocked":
        return _decision(
            policy,
            snapshot,
            state="RISK_BLOCKED",
            actions=_STOPPED_ACTIONS,
            notifications=(
                ("forward_observation_risk_blocked",)
                if snapshot.previous_state != "risk_blocked"
                else ()
            ),
            reasons=("risk_status=blocked; explicit human review is required",),
        )

    health_reasons = _health_reasons(snapshot)
    if health_reasons:
        return _decision(
            policy,
            snapshot,
            state="PAUSED",
            actions=("pause_shadow", "pause_paper"),
            notifications=("forward_observation_paused",),
            reasons=tuple(health_reasons),
        )

    if (
        snapshot.previous_state == "paused"
        and snapshot.clean_sessions_since_pause < policy.auto_resume_clean_sessions
    ):
        return _decision(
            policy,
            snapshot,
            state="PAUSED",
            actions=("keep_shadow_paused", "keep_paper_paused"),
            notifications=(),
            reasons=(
                "recovery observation is still collecting clean sessions "
                f"({snapshot.clean_sessions_since_pause}/{policy.auto_resume_clean_sessions})",
            ),
        )

    if snapshot.observations_completed >= policy.required_trading_sessions:
        notifications = list(_crossed_milestones(policy, snapshot))
        if snapshot.previous_observations_completed < policy.required_trading_sessions:
            notifications.append("forward_window_complete_human_live_review_required")
        return _decision(
            policy,
            snapshot,
            state="FORWARD_COMPLETE_HUMAN_REVIEW",
            actions=_STOPPED_ACTIONS,
            notifications=tuple(notifications),
            reasons=(
                "forward window is complete; non-live observation is stopped and live remains blocked pending explicit human approval",
            ),
        )

    actions = (
        ("resume_shadow", "resume_paper")
        if snapshot.previous_state == "paused"
        else (
            ("start_shadow", "start_paper")
            if snapshot.previous_state == "not_started"
            else ("continue_shadow", "continue_paper")
        )
    )
    notifications = list(_crossed_milestones(policy, snapshot))
    state = "FORWARD_ACTIVE"
    reasons = [
        "P3 evidence is verified; non-live shadow and paper observation may run automatically"
    ]
    return _decision(
        policy,
        snapshot,
        state=state,
        actions=actions,
        notifications=tuple(notifications),
        reasons=tuple(reasons),
    )


def _health_reasons(snapshot: ForwardObservationSnapshot) -> list[str]:
    reasons: list[str] = []
    if snapshot.data_status != "ready":
        reasons.append(f"data_status={snapshot.data_status}")
    if snapshot.shadow_status != "healthy":
        reasons.append(f"shadow_status={snapshot.shadow_status}")
    if snapshot.paper_status != "healthy":
        reasons.append(f"paper_status={snapshot.paper_status}")
    return reasons


def _controlled_stop(
    snapshot: ForwardObservationSnapshot,
) -> tuple[str, str | None, str] | None:
    control = snapshot.control_status
    if control == "clear" and snapshot.previous_state in _PERMANENT_PREVIOUS_STATES:
        control = snapshot.previous_state
    if control == "clear":
        return None
    state, notification = {
        "manual_hold": ("MANUAL_HOLD", "forward_observation_manual_hold"),
        "identity_mismatch": (
            "IDENTITY_MISMATCH",
            "forward_observation_identity_mismatch",
        ),
        "revoked": ("REVOKED", "forward_observation_revoked"),
        "superseded": ("SUPERSEDED", "forward_observation_superseded"),
        "risk_blocked": ("RISK_BLOCKED", "forward_observation_risk_blocked"),
    }[control]
    should_notify = control != snapshot.previous_state
    return state, notification if should_notify else None, f"control_status={control}"


def _crossed_milestones(
    policy: ForwardObservationPolicy, snapshot: ForwardObservationSnapshot
) -> tuple[str, ...]:
    return tuple(
        f"forward_review_{milestone}_sessions"
        for milestone in policy.review_milestones
        if snapshot.previous_observations_completed < milestone <= snapshot.observations_completed
    )


def _decision(
    policy: ForwardObservationPolicy,
    snapshot: ForwardObservationSnapshot,
    *,
    state: str,
    actions: tuple[str, ...],
    notifications: tuple[str, ...],
    reasons: tuple[str, ...],
) -> ForwardObservationDecision:
    return ForwardObservationDecision(
        candidate_id=policy.candidate_id,
        strategy_profile=policy.strategy_profile,
        domain=policy.domain,
        benchmark_symbol=policy.benchmark_symbol,
        state=state,
        non_live_actions=actions,
        notifications=notifications,
        reasons=reasons,
        observations_completed=snapshot.observations_completed,
        required_trading_sessions=policy.required_trading_sessions,
        historical_evidence_ref=(
            snapshot.historical_evidence_ref
            if snapshot.historical_evidence_verified
            else None
        ),
    )


__all__ = [
    "FORWARD_OBSERVATION_POLICY_SCHEMA_VERSION",
    "ForwardObservationDecision",
    "ForwardObservationPolicy",
    "ForwardObservationPolicyError",
    "ForwardObservationSnapshot",
    "evaluate_forward_observation",
]
