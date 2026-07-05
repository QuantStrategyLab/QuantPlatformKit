"""Live candidate notification event builder for strategy lifecycle evidence gates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from quant_platform_kit.notifications.events import RenderedNotification

from .evidence_gate import EvidenceGateResult, LIVE_EVIDENCE_STAGES


@dataclass(frozen=True)
class LiveCandidateNotificationEvent:
    """Structured notification event for a live candidate evidence gate result."""

    strategy_profile: str
    domain: str
    stage: str
    reason: str
    evidence_summary: str
    approval_action: str
    alert_key: str
    severity: str

    subject: str
    body: str

    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "strategy_profile": self.strategy_profile,
            "domain": self.domain,
            "stage": self.stage,
            "reason": self.reason,
            "evidence_summary": self.evidence_summary,
            "approval_action": self.approval_action,
            "alert_key": self.alert_key,
            "severity": self.severity,
            "subject": self.subject,
            "body": self.body,
            **dict(self.metadata or {}),
        }
        return {key: value for key, value in payload.items() if value not in (None, "", (), [])}

    def to_rendered_notification(self) -> RenderedNotification:
        return RenderedNotification(detailed_text=self.body, compact_text=self.subject)


def build_live_candidate_notification(result: EvidenceGateResult) -> LiveCandidateNotificationEvent | None:
    """Build a notification event from an evidence gate result.

    Returns None when the requested stage is outside the live-candidate path.
    """
    package = result.package
    stage = str(package.requested_stage or "").strip()
    if stage not in LIVE_EVIDENCE_STAGES:
        return None

    strategy_profile = package.strategy_profile
    domain = package.domain
    valid = bool(result.valid)
    approval_action = "approve" if valid else "hold"
    severity = _severity_for(stage, valid)
    reason = _reason_for(result)
    evidence_summary = _build_evidence_summary(result)
    alert_key = _build_alert_key(strategy_profile, domain, stage, approval_action)
    subject = _build_subject(strategy_profile, domain, stage, approval_action, valid)
    body = _build_body(result, reason=reason, evidence_summary=evidence_summary, approval_action=approval_action)

    return LiveCandidateNotificationEvent(
        strategy_profile=strategy_profile,
        domain=domain,
        stage=stage,
        reason=reason,
        evidence_summary=evidence_summary,
        approval_action=approval_action,
        alert_key=alert_key,
        severity=severity,
        subject=subject,
        body=body,
        metadata={
            "valid": valid,
            "issues": tuple(result.issues),
            "warnings": tuple(result.warnings),
            "package": package.to_dict(),
        },
    )


def _severity_for(stage: str, valid: bool) -> str:
    if valid:
        return "info"
    if stage == "runtime_enabled":
        return "critical"
    return "warning"


def _reason_for(result: EvidenceGateResult) -> str:
    parts: list[str] = []
    if result.issues:
        parts.append("blocked: " + "; ".join(result.issues))
    if result.warnings:
        parts.append("warnings: " + "; ".join(result.warnings))
    if parts:
        return " | ".join(parts)
    return "evidence gate passed"


def _build_evidence_summary(result: EvidenceGateResult) -> str:
    package = result.package
    summary_parts = [
        _format_summary_item("backtest", _summarize_mapping(package.backtest_summary)),
        _format_summary_item("drift_notes", _summarize_value(package.drift_notes)),
        _format_summary_item("platform_compatibility", _summarize_mapping(package.platform_compatibility or {})),
        _format_summary_item("plugin_gate", _summarize_value(package.plugin_gate)),
        _format_summary_item("target_platforms", ", ".join(package.target_platforms) or "none"),
    ]
    if package.rollout_notes:
        summary_parts.append(_format_summary_item("rollout_notes", _summarize_value(package.rollout_notes)))
    if result.warnings:
        summary_parts.append(_format_summary_item("warnings", "; ".join(result.warnings)))
    return " | ".join(part for part in summary_parts if part)


def _build_alert_key(strategy_profile: str, domain: str, stage: str, approval_action: str) -> str:
    return f"lifecycle/live_candidate/{domain}/{strategy_profile}/{stage}/{approval_action}"


def _build_subject(strategy_profile: str, domain: str, stage: str, approval_action: str, valid: bool) -> str:
    outcome = "APPROVED" if valid else "HOLD"
    return f"[{domain}] {outcome} {stage}: {strategy_profile} ({approval_action})"


def _build_body(
    result: EvidenceGateResult,
    *,
    reason: str,
    evidence_summary: str,
    approval_action: str,
) -> str:
    package = result.package
    lines = [
        "Strategy Lifecycle Live Candidate Notification",
        "",
        f"Strategy: {package.strategy_profile}",
        f"Domain: {package.domain}",
        f"Stage: {package.requested_stage}",
        f"Approval Action: {approval_action}",
        f"Reason: {reason}",
        "",
        "Evidence Summary:",
        evidence_summary,
    ]
    return "\n".join(lines)


def _format_summary_item(label: str, value: str) -> str:
    value = str(value or "").strip()
    return f"{label}={value}" if value else ""


def _summarize_mapping(value: Mapping[str, Any]) -> str:
    if not value:
        return "empty"
    parts: list[str] = []
    for key in ("observation_count", "sharpe_ratio", "cagr", "max_drawdown", "total_return", "status", "verified"):
        if key in value and value[key] not in (None, ""):
            parts.append(f"{key}={value[key]}")
    if not parts:
        parts.append(f"keys={','.join(sorted(str(key) for key in value.keys()))}")
    return ", ".join(parts)


def _summarize_value(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, str):
        text = value.strip()
        return text or "empty"
    if isinstance(value, Mapping):
        return _summarize_mapping(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(items) if items else "empty"
    return str(value)
