"""Research promotion domain states, tickets and validation."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

from quant_platform_kit.strategy_lifecycle.candidate_control import ResearchSourceReceiptRef
from quant_platform_kit.strategy_lifecycle.contracts import DriftStatus


_REAL_DATETIME = datetime


class ResearchPromotionState(str, Enum):
    """ADR-0005 research substates reduced to the enforceable HITL slice."""

    PARKED = "parked"
    BOUNDED_REOPT = "bounded_reopt"
    SHADOW_RECORDED = "shadow_recorded"
    AWAITING_HUMAN = "awaiting_human"
    HUMAN_ACCEPTED = "human_accepted"
    HUMAN_REJECTED = "human_rejected"


_ACTIVE_DRIFT = {DriftStatus.REVIEW, DriftStatus.CRITICAL}
_RESEARCH_CANDIDATE_RECOMMENDATIONS = frozenset({"promote", "needs_review", "research_candidate"})
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
    require_paired_shadow: bool = False

    def __post_init__(self) -> None:
        if self.max_search_iterations < 1:
            raise ValueError("max_search_iterations must be >= 1")
        if self.max_param_keys < 1:
            raise ValueError("max_param_keys must be >= 1")
        if self.allow_live_enablement:
            raise ValueError(
                "ResearchPromotionBudget.allow_live_enablement must remain False"
            )


@dataclass(frozen=True)
class NewResearchRequest:
    """Source-bound request for a new research design.

    This is deliberately separate from :class:`DriftResult`: a new strategy
    has no observed drift score and must never acquire one by construction.
    """

    strategy_profile: str
    domain: str
    as_of: date
    source_revision: str
    research_intent: str
    source_receipt_refs: tuple[ResearchSourceReceiptRef, ...]

    def __post_init__(self) -> None:
        for name in ("strategy_profile", "domain", "source_revision", "research_intent"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.as_of, date):
            raise ValueError("as_of must be a date")
        if (not isinstance(self.source_receipt_refs, tuple)
                or not self.source_receipt_refs
                or any(type(item) is not ResearchSourceReceiptRef for item in self.source_receipt_refs)):
            raise ValueError("source_receipt_refs must contain at least one receipt reference")
        digests = tuple(item.receipt_sha256 for item in self.source_receipt_refs)
        if digests != tuple(sorted(set(digests))):
            raise ValueError("source_receipt_refs must be unique and sorted")

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_profile": self.strategy_profile,
            "domain": self.domain,
            "as_of": self.as_of.isoformat(),
            "source_revision": self.source_revision,
            "research_intent": self.research_intent,
            "source_receipt_refs": [item.to_dict() for item in self.source_receipt_refs],
        }


RISK_PROFILE_IDS = (
    "CAPITAL_PRESERVATION",
    "BALANCED_COMPOUNDING",
    "GROWTH_COMPOUNDING",
)
DEFAULT_SUGGESTED_RISK_PROFILE = "CAPITAL_PRESERVATION"
EXECUTION_MODES = ("live", "paper")


@dataclass(frozen=True)
class PromotionConfirmation:
    """Human intent for where/how to proceed after shadow — never live authority.

    paper is allowed only when the target platform actually offers a broker
    paper/sim account. Synthetic matching is intentionally unsupported.
    """

    target_platform: str
    execution_mode: str
    risk_profile: str

    def __post_init__(self) -> None:
        platform = str(self.target_platform or "").strip()
        mode = str(self.execution_mode or "").strip().lower()
        profile = str(self.risk_profile or "").strip().upper()
        if not platform:
            raise ValueError("target_platform is required")
        if mode not in EXECUTION_MODES:
            raise ValueError("execution_mode must be 'live' or 'paper'")
        if profile not in RISK_PROFILE_IDS:
            raise ValueError(
                "risk_profile must be CAPITAL_PRESERVATION, "
                "BALANCED_COMPOUNDING, or GROWTH_COMPOUNDING"
            )
        object.__setattr__(self, "target_platform", platform)
        object.__setattr__(self, "execution_mode", mode)
        object.__setattr__(self, "risk_profile", profile)

    def to_dict(self) -> dict[str, str]:
        return {
            "target_platform": self.target_platform,
            "execution_mode": self.execution_mode,
            "risk_profile": self.risk_profile,
        }


def validate_promotion_confirmation(
    confirmation: PromotionConfirmation | Mapping[str, Any],
    *,
    paper_supported: bool,
) -> PromotionConfirmation:
    """Validate confirmation and reject paper when the broker has no paper lane."""
    if not isinstance(confirmation, PromotionConfirmation):
        confirmation = PromotionConfirmation(
            target_platform=str(confirmation.get("target_platform") or ""),
            execution_mode=str(confirmation.get("execution_mode") or ""),
            risk_profile=str(confirmation.get("risk_profile") or ""),
        )
    if confirmation.execution_mode == "paper" and not paper_supported:
        raise ValueError(
            "paper is unavailable for this platform; do not invent synthetic "
            "matching — choose live after human review or keep observing"
        )
    return confirmation


@dataclass
class ResearchPromotionTicket:
    """Durable operator work item for one drift-triggered research candidate."""

    ticket_id: str
    strategy_profile: str
    domain: str
    state: ResearchPromotionState
    drift_status: str
    drift_score: float | None
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
    suggested_risk_profile: str = DEFAULT_SUGGESTED_RISK_PROFILE
    confirmation_target_platform: str = ""
    confirmation_execution_mode: str = ""
    confirmation_risk_profile: str = ""
    notes: tuple[str, ...] = ()
    # Local checkpoint only. QRT's candidate contract must not carry job state.
    research_progress: Mapping[str, Any] = field(default_factory=dict, repr=False)
    # Local/operator-facing summary. It is advisory and never grants authority.
    research_summary: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_progress: bool = False) -> dict[str, Any]:
        payload = asdict(self)
        if not include_progress:
            payload.pop("research_progress")
        if not self.research_summary:
            payload.pop("research_summary", None)
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
            drift_score=(
                None
                if raw.get("drift_score") is None and raw.get("drift_status") == "new_research"
                else float(raw.get("drift_score") or 0.0)
            ),
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
            suggested_risk_profile=str(
                raw.get("suggested_risk_profile") or DEFAULT_SUGGESTED_RISK_PROFILE
            ),
            confirmation_target_platform=str(
                raw.get("confirmation_target_platform") or ""
            ),
            confirmation_execution_mode=str(
                raw.get("confirmation_execution_mode") or ""
            ),
            confirmation_risk_profile=str(raw.get("confirmation_risk_profile") or ""),
            notes=tuple(str(item) for item in (raw.get("notes") or ())),
            research_progress=dict(raw.get("research_progress") or {}),
            research_summary=dict(raw.get("research_summary") or {}),
        )


def _now_iso() -> str:
    return _resolve_clock_now().isoformat()


def _new_ticket_id() -> str:
    return f"rpt_{uuid.uuid4().hex[:12]}"


def _clock_now() -> datetime:
    """Read the clock through the compatibility facade so module patches apply."""
    from quant_platform_kit.strategy_lifecycle import research_promotion_cycle as _compat

    return _compat.datetime.now(timezone.utc)


def _resolve_clock_now() -> datetime:
    """Resolve ``_clock_now`` through the compatibility facade for test patches."""
    from quant_platform_kit.strategy_lifecycle import research_promotion_cycle as _compat

    return _compat._clock_now()


def _shadow_kind(shadow: Mapping[str, Any]) -> str:
    return str(
        shadow.get("evidence_kind")
        or shadow.get("kind")
        or shadow.get("evidence_type")
        or "proxy_shadow"
    )


def _is_paired_shadow_kind(kind: str) -> bool:
    normalized = str(kind or "").strip().lower()
    return normalized == "paired_shadow" or normalized.startswith("paired_shadow")


def shadow_record_from_paired_evidence(
    evidence: Mapping[str, Any],
    *,
    policy: Any | None = None,
    forward_observation_receipt: Mapping[str, Any] | None = None,
    previous_evidence: Mapping[str, Any] | None = None,
    previous_forward_observation_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate paired-shadow evidence into a non-live cycle shadow record."""
    from quant_platform_kit.strategy_lifecycle.paired_shadow_evidence import (
        PAIRED_SHADOW_EVIDENCE_KIND,
        validate_paired_shadow_evidence,
    )

    validated = validate_paired_shadow_evidence(
        evidence,
        policy=policy,
        forward_observation_receipt=forward_observation_receipt,
        previous_evidence=previous_evidence,
        previous_forward_observation_receipt=previous_forward_observation_receipt,
    )
    if validated.get("live_authority_granted") is True:
        raise ValueError("paired shadow evidence must not grant live authority")
    if validated.get("no_order") is not True:
        raise ValueError("paired shadow evidence must declare no_order=true")
    digest = str(validated.get("paired_shadow_evidence_sha256") or "")
    return {
        "evidence_kind": PAIRED_SHADOW_EVIDENCE_KIND,
        "passed": True,
        "paired_shadow_evidence_sha256": digest,
        "no_order": True,
        "live_authority_granted": False,
        "evidence": validated,
    }


def apply_human_promotion_decision(
    ticket: ResearchPromotionTicket,
    *,
    decision: str,
    confirmation: PromotionConfirmation | Mapping[str, Any] | None = None,
    paper_supported: bool = False,
    decided_at: str | None = None,
) -> ResearchPromotionTicket:
    """Record human accept/reject. Accept never grants live authority.

    Accept requires explicit platform, execution mode, and risk profile.
    paper_supported must be true only for a real broker paper/sim account.
    """
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
        if confirmation is None:
            raise ValueError(
                "accept requires confirmation "
                "(target_platform, execution_mode, risk_profile)"
            )
        confirmed = validate_promotion_confirmation(
            confirmation, paper_supported=bool(paper_supported)
        )
        ticket.confirmation_target_platform = confirmed.target_platform
        ticket.confirmation_execution_mode = confirmed.execution_mode
        ticket.confirmation_risk_profile = confirmed.risk_profile
        ticket.state = ResearchPromotionState.HUMAN_ACCEPTED
        ticket.notes = ticket.notes + (
            "human_accepted_intent_only_no_live_authority",
            f"confirmation_platform={confirmed.target_platform}",
            f"confirmation_mode={confirmed.execution_mode}",
            f"confirmation_risk_profile={confirmed.risk_profile}",
        )
    else:
        ticket.state = ResearchPromotionState.HUMAN_REJECTED
        ticket.notes = ticket.notes + ("human_rejected",)
    ticket.updated_at = _now_iso()
    return ticket
