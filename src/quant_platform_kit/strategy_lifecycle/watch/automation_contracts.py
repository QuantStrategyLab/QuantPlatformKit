"""Minimal shared contracts for automation strategy data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _validate_non_empty(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass
class TriggerRecord:
    source: str
    kind: str
    severity: str
    reason: str
    subject: str
    metrics: dict[str, Any] = field(default_factory=dict)
    evidence: list[Any] = field(default_factory=list)
    created_at: float | None = None

    def __post_init__(self) -> None:
        _validate_non_empty(self.severity, "severity")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "kind": self.kind,
            "severity": self.severity,
            "reason": self.reason,
            "subject": self.subject,
            "metrics": dict(self.metrics),
            "evidence": list(self.evidence),
            "created_at": self.created_at,
        }


@dataclass
class EvidenceBundle:
    summary: str
    artifacts: list[Any] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    risks: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "artifacts": list(self.artifacts),
            "metrics": dict(self.metrics),
            "risks": list(self.risks),
        }


@dataclass
class ProposedAction:
    action: str
    lane: str
    target: str
    rationale: str
    requires_human_review: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_non_empty(self.action, "action")

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "lane": self.lane,
            "target": self.target,
            "rationale": self.rationale,
            "requires_human_review": self.requires_human_review,
            "metadata": dict(self.metadata),
        }


@dataclass
class GateDecision:
    allowed: bool
    reason: str
    required_checks: list[Any] = field(default_factory=list)
    human_review_required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "required_checks": list(self.required_checks),
            "human_review_required": self.human_review_required,
            "metadata": dict(self.metadata),
        }


@dataclass
class AutomationTask:
    trigger: TriggerRecord
    evidence: EvidenceBundle
    proposed_action: ProposedAction
    gate_decision: GateDecision
    status: str = "proposed"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_non_empty(self.status, "status")

    @property
    def is_actionable(self) -> bool:
        return (
            self.gate_decision.allowed
            and bool(self.proposed_action.action.strip())
            and not self.gate_decision.human_review_required
            and not self.proposed_action.requires_human_review
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger": self.trigger.to_dict(),
            "evidence": self.evidence.to_dict(),
            "proposed_action": self.proposed_action.to_dict(),
            "gate_decision": self.gate_decision.to_dict(),
            "status": self.status,
            "metadata": dict(self.metadata),
        }
