"""Research promotion cycle: drift → bounded reopt → shadow evidence → human gate.

This control plane may prepare non-live candidates and notify operators. It must
never enable live trading, enlarge capital, or treat AI/reviewer verdicts as
deployment authority.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from quant_platform_kit.strategy_lifecycle.contracts import (
    DriftResult,
    DriftStatus,
    OptimizationProposal,
)


class ResearchPromotionState(str, Enum):
    """ADR-0005 research substates reduced to the enforceable HITL slice."""

    PARKED = "parked"
    BOUNDED_REOPT = "bounded_reopt"
    SHADOW_RECORDED = "shadow_recorded"
    AWAITING_HUMAN = "awaiting_human"
    HUMAN_ACCEPTED = "human_accepted"
    HUMAN_REJECTED = "human_rejected"


_ACTIVE_DRIFT = {DriftStatus.REVIEW, DriftStatus.CRITICAL}
_TERMINAL = {
    ResearchPromotionState.PARKED,
    ResearchPromotionState.HUMAN_ACCEPTED,
    ResearchPromotionState.HUMAN_REJECTED,
}


@dataclass(frozen=True)
class ResearchPromotionBudget:
    """Hard caps for automated research work after drift."""

    max_search_iterations: int = 25
    max_param_keys: int = 4
    allow_live_enablement: bool = False

    def __post_init__(self) -> None:
        if self.max_search_iterations < 1:
            raise ValueError("max_search_iterations must be >= 1")
        if self.max_param_keys < 1:
            raise ValueError("max_param_keys must be >= 1")
        if self.allow_live_enablement:
            raise ValueError(
                "ResearchPromotionBudget.allow_live_enablement must remain False"
            )


@dataclass
class ResearchPromotionTicket:
    """Durable operator work item for one drift-triggered research candidate."""

    ticket_id: str
    strategy_profile: str
    domain: str
    state: ResearchPromotionState
    drift_status: str
    drift_score: float
    created_at: str
    updated_at: str
    budget: Mapping[str, Any] = field(default_factory=dict)
    proposed_params: Mapping[str, Any] = field(default_factory=dict)
    search_iterations: int = 0
    shadow_evidence_kind: str = ""
    shadow_passed: bool | None = None
    notification_subject: str = ""
    notification_body: str = ""
    human_decision: str = ""
    human_decided_at: str = ""
    live_authority_granted: bool = False
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["notes"] = list(self.notes)
        payload["proposed_params"] = dict(self.proposed_params)
        payload["budget"] = dict(self.budget)
        return payload

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> ResearchPromotionTicket:
        return cls(
            ticket_id=str(raw["ticket_id"]),
            strategy_profile=str(raw["strategy_profile"]),
            domain=str(raw["domain"]),
            state=ResearchPromotionState(str(raw["state"])),
            drift_status=str(raw.get("drift_status") or ""),
            drift_score=float(raw.get("drift_score") or 0.0),
            created_at=str(raw["created_at"]),
            updated_at=str(raw["updated_at"]),
            budget=dict(raw.get("budget") or {}),
            proposed_params=dict(raw.get("proposed_params") or {}),
            search_iterations=int(raw.get("search_iterations") or 0),
            shadow_evidence_kind=str(raw.get("shadow_evidence_kind") or ""),
            shadow_passed=(
                None
                if raw.get("shadow_passed") is None
                else bool(raw.get("shadow_passed"))
            ),
            notification_subject=str(raw.get("notification_subject") or ""),
            notification_body=str(raw.get("notification_body") or ""),
            human_decision=str(raw.get("human_decision") or ""),
            human_decided_at=str(raw.get("human_decided_at") or ""),
            live_authority_granted=bool(raw.get("live_authority_granted") or False),
            notes=tuple(str(item) for item in (raw.get("notes") or ())),
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_ticket_id() -> str:
    return f"rpt_{uuid.uuid4().hex[:12]}"


def enforce_optimization_budget(
    proposal: OptimizationProposal,
    budget: ResearchPromotionBudget,
) -> tuple[bool, str]:
    """Return (ok, reason) for a proposal against hard research caps."""
    if proposal.search_iterations > budget.max_search_iterations:
        return (
            False,
            (
                f"search_iterations={proposal.search_iterations} exceeds "
                f"budget max_search_iterations={budget.max_search_iterations}"
            ),
        )
    param_keys = len(dict(proposal.proposed_params or {}))
    if param_keys > budget.max_param_keys:
        return (
            False,
            (
                f"proposed_params keys={param_keys} exceeds "
                f"budget max_param_keys={budget.max_param_keys}"
            ),
        )
    return True, "within_budget"


def build_human_promotion_notification(
    ticket: ResearchPromotionTicket,
) -> tuple[str, str]:
    """Build operator-facing subject/body. Never claims live authority."""
    subject = (
        f"[AWAITING_HUMAN] {ticket.strategy_profile}/{ticket.domain} "
        f"ticket={ticket.ticket_id}"
    )
    body = "\n".join(
        [
            "Research promotion candidate is ready for human decision.",
            f"ticket_id: {ticket.ticket_id}",
            f"strategy_profile: {ticket.strategy_profile}",
            f"domain: {ticket.domain}",
            f"drift_status: {ticket.drift_status}",
            f"drift_score: {ticket.drift_score}",
            f"search_iterations: {ticket.search_iterations}",
            f"shadow_evidence_kind: {ticket.shadow_evidence_kind or 'none'}",
            f"shadow_passed: {ticket.shadow_passed}",
            f"proposed_params: {json.dumps(dict(ticket.proposed_params), sort_keys=True)}",
            "live_authority_granted: false",
            "Action required: accept or reject this ticket.",
            "Accept records operator intent only; it does not enable live trading.",
        ]
    )
    return subject, body


def run_research_promotion_cycle(
    drift: DriftResult,
    *,
    optimize: Callable[[DriftResult, ResearchPromotionBudget], OptimizationProposal],
    record_shadow: Callable[[OptimizationProposal], Mapping[str, Any]],
    notify: Callable[[str, str], None] | None = None,
    budget: ResearchPromotionBudget | None = None,
    ticket_id: str | None = None,
) -> ResearchPromotionTicket:
    """Execute the non-live research promotion slice and stop for humans."""
    budget = budget or ResearchPromotionBudget()
    now = _now_iso()
    ticket = ResearchPromotionTicket(
        ticket_id=ticket_id or _new_ticket_id(),
        strategy_profile=drift.strategy_profile,
        domain=drift.domain,
        state=ResearchPromotionState.PARKED,
        drift_status=drift.status.value,
        drift_score=float(drift.drift_score),
        created_at=now,
        updated_at=now,
        budget={
            "max_search_iterations": budget.max_search_iterations,
            "max_param_keys": budget.max_param_keys,
            "allow_live_enablement": False,
        },
        live_authority_granted=False,
    )

    if drift.status not in _ACTIVE_DRIFT:
        ticket.notes = ("drift_not_actionable",)
        ticket.updated_at = _now_iso()
        return ticket

    ticket.state = ResearchPromotionState.BOUNDED_REOPT
    proposal = optimize(drift, budget)
    ok, reason = enforce_optimization_budget(proposal, budget)
    ticket.search_iterations = int(proposal.search_iterations)
    ticket.proposed_params = dict(proposal.proposed_params or {})
    if not ok:
        ticket.state = ResearchPromotionState.PARKED
        ticket.notes = ("budget_exceeded", reason)
        ticket.updated_at = _now_iso()
        return ticket

    if proposal.recommendation not in {"promote", "needs_review", "research_candidate"}:
        ticket.state = ResearchPromotionState.PARKED
        ticket.notes = (f"recommendation={proposal.recommendation}",)
        ticket.updated_at = _now_iso()
        return ticket

    shadow = dict(record_shadow(proposal))
    ticket.shadow_evidence_kind = str(
        shadow.get("evidence_kind") or shadow.get("kind") or "proxy_shadow"
    )
    ticket.shadow_passed = bool(shadow.get("passed", False))
    ticket.state = ResearchPromotionState.SHADOW_RECORDED
    if not ticket.shadow_passed:
        ticket.state = ResearchPromotionState.PARKED
        ticket.notes = ("shadow_failed",)
        ticket.updated_at = _now_iso()
        return ticket

    ticket.state = ResearchPromotionState.AWAITING_HUMAN
    subject, body = build_human_promotion_notification(ticket)
    ticket.notification_subject = subject
    ticket.notification_body = body
    ticket.updated_at = _now_iso()
    if notify is not None:
        notify(subject, body)
    return ticket


def open_awaiting_human_ticket(
    *,
    drift: DriftResult,
    proposal: OptimizationProposal,
    shadow: Mapping[str, Any],
    budget: ResearchPromotionBudget | None = None,
    notify: Callable[[str, str], None] | None = None,
    ticket_id: str | None = None,
) -> ResearchPromotionTicket:
    """Open a human gate from an already-produced proposal + shadow evidence."""
    budget = budget or ResearchPromotionBudget()
    ok, reason = enforce_optimization_budget(proposal, budget)
    now = _now_iso()
    ticket = ResearchPromotionTicket(
        ticket_id=ticket_id or _new_ticket_id(),
        strategy_profile=drift.strategy_profile,
        domain=drift.domain,
        state=ResearchPromotionState.PARKED,
        drift_status=drift.status.value,
        drift_score=float(drift.drift_score),
        created_at=now,
        updated_at=now,
        budget={
            "max_search_iterations": budget.max_search_iterations,
            "max_param_keys": budget.max_param_keys,
            "allow_live_enablement": False,
        },
        proposed_params=dict(proposal.proposed_params or {}),
        search_iterations=int(proposal.search_iterations),
        live_authority_granted=False,
    )
    if not ok:
        ticket.notes = ("budget_exceeded", reason)
        return ticket
    if not bool(shadow.get("passed", False)):
        ticket.notes = ("shadow_failed",)
        return ticket

    ticket.shadow_evidence_kind = str(
        shadow.get("evidence_kind") or shadow.get("kind") or "proxy_shadow"
    )
    ticket.shadow_passed = True
    ticket.state = ResearchPromotionState.AWAITING_HUMAN
    subject, body = build_human_promotion_notification(ticket)
    ticket.notification_subject = subject
    ticket.notification_body = body
    ticket.updated_at = _now_iso()
    if notify is not None:
        notify(subject, body)
    return ticket


def apply_human_promotion_decision(
    ticket: ResearchPromotionTicket,
    *,
    decision: str,
    decided_at: str | None = None,
) -> ResearchPromotionTicket:
    """Record human accept/reject. Accept never grants live authority."""
    if ticket.state != ResearchPromotionState.AWAITING_HUMAN:
        raise ValueError(
            f"ticket {ticket.ticket_id} is not awaiting human "
            f"(state={ticket.state.value})"
        )

    normalized = str(decision or "").strip().lower()
    if normalized not in {"accept", "reject"}:
        raise ValueError("decision must be 'accept' or 'reject'")

    ticket.human_decision = normalized
    ticket.human_decided_at = decided_at or _now_iso()
    ticket.live_authority_granted = False
    if normalized == "accept":
        ticket.state = ResearchPromotionState.HUMAN_ACCEPTED
        ticket.notes = ticket.notes + (
            "human_accepted_intent_only_no_live_authority",
        )
    else:
        ticket.state = ResearchPromotionState.HUMAN_REJECTED
        ticket.notes = ticket.notes + ("human_rejected",)
    ticket.updated_at = _now_iso()
    return ticket


def save_research_promotion_ticket(
    ticket: ResearchPromotionTicket,
    path: str | Path,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(ticket.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def load_research_promotion_ticket(path: str | Path) -> ResearchPromotionTicket:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("ticket file must contain a JSON object")
    ticket = ResearchPromotionTicket.from_dict(raw)
    if ticket.live_authority_granted:
        raise ValueError("refusing to load ticket with live_authority_granted=true")
    return ticket


__all__ = [
    "ResearchPromotionBudget",
    "ResearchPromotionState",
    "ResearchPromotionTicket",
    "apply_human_promotion_decision",
    "build_human_promotion_notification",
    "enforce_optimization_budget",
    "load_research_promotion_ticket",
    "open_awaiting_human_ticket",
    "run_research_promotion_cycle",
    "save_research_promotion_ticket",
]
