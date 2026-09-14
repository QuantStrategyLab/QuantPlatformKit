"""Research promotion cycle: drift → bounded reopt → shadow evidence → human gate.

This control plane may prepare non-live candidates and notify operators. It must
never enable live trading, enlarge capital, or treat AI/reviewer verdicts as
deployment authority.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import math
import re
import uuid
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from quant_platform_kit.strategy_lifecycle.contracts import (
    DriftResult,
    DriftStatus,
    OptimizationProposal,
    PromotionBacktestRun,
)
from quant_platform_kit.strategy_lifecycle.candidate_control import ResearchSourceReceiptRef


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
    return _clock_now().isoformat()


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


def _add_calendar_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _promotion_backtest_evidence_mapping(
    evidence: PromotionBacktestRun | Mapping[str, Any],
) -> Mapping[str, Any]:
    if isinstance(evidence, PromotionBacktestRun):
        return {
            "status": "PASS",
            "orchestrator": "BacktestOrchestrator",
            "protocol": "purged_walk_forward.v1",
            "locked_independent_oos": {
                "locked": True,
                "independent": True,
                "reused_for_selection": False,
            },
            "promotion_run": evidence.to_dict(),
        }
    return evidence


def enforce_promotion_backtest_gates(
    proposal: OptimizationProposal,
    evidence: PromotionBacktestRun | Mapping[str, Any] | None,
) -> tuple[bool, str]:
    """Validate the strict orchestrator/WFA/OOS summary before shadow.

    Callers may return the existing ``PromotionBacktestRun`` contract directly
    or an evidence-package-compatible backtest summary. Missing or malformed
    evidence always parks the candidate.
    """
    if evidence is None:
        return False, "missing_promotion_backtest_evidence"
    if not isinstance(evidence, (PromotionBacktestRun, Mapping)):
        return False, "invalid_promotion_backtest_evidence_type"

    summary = _promotion_backtest_evidence_mapping(evidence)
    if summary.get("status") != "PASS":
        return False, "promotion_backtest_status_not_pass"
    if summary.get("orchestrator") != "BacktestOrchestrator":
        return False, "promotion_backtest_orchestrator_required"
    if summary.get("protocol") != "purged_walk_forward.v1":
        return False, "purged_walk_forward_protocol_required"

    locked = summary.get("locked_independent_oos")
    if not isinstance(locked, Mapping):
        return False, "locked_independent_oos_required"
    if (
        locked.get("locked") is not True
        or locked.get("independent") is not True
        or locked.get("reused_for_selection") is not False
    ):
        return False, "locked_independent_oos_failed"

    run = summary.get("promotion_run")
    if not isinstance(run, Mapping):
        return False, "promotion_run_required"
    if run.get("strategy_profile") != proposal.strategy_profile:
        return False, "promotion_run_strategy_profile_mismatch"
    if run.get("domain") != proposal.domain:
        return False, "promotion_run_domain_mismatch"
    folds = run.get("folds")
    if not isinstance(folds, (list, tuple)) or len(folds) < 3:
        return False, "promotion_run_requires_three_folds"
    for field_name in ("purge_days", "embargo_days"):
        value = run.get(field_name)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            return False, f"promotion_run_{field_name}_must_be_positive"
    purge_days = int(run["purge_days"])
    embargo_days = int(run["embargo_days"])
    previous_test_end: date | None = None
    for index, fold in enumerate(folds):
        if not isinstance(fold, Mapping):
            return False, f"promotion_run_fold_{index}_invalid"
        try:
            train_start = date.fromisoformat(str(fold.get("train_start") or ""))
            train_end = date.fromisoformat(str(fold.get("train_end") or ""))
            test_start = date.fromisoformat(str(fold.get("test_start") or ""))
            test_end = date.fromisoformat(str(fold.get("test_end") or ""))
        except ValueError:
            return False, f"promotion_run_fold_{index}_dates_invalid"
        if train_start > train_end or test_start > test_end:
            return False, f"promotion_run_fold_{index}_dates_reversed"
        if train_end + timedelta(days=purge_days) >= test_start:
            return False, f"promotion_run_fold_{index}_purge_failed"
        if (
            previous_test_end is not None
            and previous_test_end + timedelta(days=embargo_days) >= train_start
        ):
            return False, f"promotion_run_fold_{index}_embargo_failed"
        previous_test_end = test_end
    try:
        oos_start = date.fromisoformat(str(run.get("locked_oos_start") or ""))
        oos_end = date.fromisoformat(str(run.get("locked_oos_end") or ""))
    except ValueError:
        return False, "promotion_run_locked_oos_dates_invalid"
    if (
        previous_test_end is None
        or previous_test_end + timedelta(days=embargo_days) >= oos_start
    ):
        return False, "promotion_run_locked_oos_embargo_failed"
    if oos_end < _add_calendar_months(oos_start, 12):
        return False, "promotion_run_locked_oos_under_12_months"
    return True, "promotion_backtest_gates_passed"


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
            f"suggested_risk_profile: {ticket.suggested_risk_profile}",
            "On accept choose: target_platform + execution_mode(live|paper) + risk_profile.",
            "paper only if the broker provides a real paper/sim account; no synthetic matching.",
            "Action required: accept or reject this ticket.",
            "Accept records operator intent only; it does not enable live trading.",
        ]
    )
    return subject, body



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


def make_telegram_research_promotion_notifier(
    *,
    bot_token: str | None = None,
    chat_ids: str | list[str] | None = None,
    printer: Any = print,
) -> Callable[[str, str], bool]:
    """Build notify(subject, body) using Telegram; soft-skip if unconfigured."""
    import os

    from quant_platform_kit.notifications.telegram import send_telegram_message

    token = str(
        bot_token
        or os.environ.get("TELEGRAM_TOKEN")
        or os.environ.get("STRATEGY_PLUGIN_ALERT_TELEGRAM_BOT_TOKEN")
        or ""
    ).strip()
    chats: str | list[str] | None = chat_ids
    if chats is None:
        chats = (
            os.environ.get("GLOBAL_TELEGRAM_CHAT_ID")
            or os.environ.get("STRATEGY_PLUGIN_ALERT_TELEGRAM_CHAT_IDS")
            or ""
        )

    def notify(subject: str, body: str) -> bool:
        if not token or not str(chats or "").strip():
            printer(
                "research promotion telegram notify skipped: token/chat not configured",
                flush=True,
            )
            return False
        message = subject + "\n\n" + body
        return bool(
            send_telegram_message(
                bot_token=token,
                chat_ids=chats,
                text=message,
                parse_mode=None,
                printer=printer,
            )
        )

    return notify


def make_console_research_promotion_sync(
    *,
    endpoint_url: str | None = None,
    sync_token: str | None = None,
    timeout_seconds: float = 5.0,
    printer: Any = print,
    post_json: Callable[..., Any] | None = None,
    pull_console: Callable[[str], Mapping[str, Any] | None] | None = None,
) -> Callable[[ResearchPromotionTicket], bool]:
    """Confirm an awaiting ticket by reading it back from the QRT console.

    Env defaults:
    - RESEARCH_PROMOTION_SYNC_URL
    - RESEARCH_PROMOTION_SYNC_TOKEN (must match QRT RESEARCH_PROMOTION_SYNC_TOKEN)

    Read before writing; only a confirmed absence permits one POST. A POST with
    an unknown outcome is followed by GET, never another POST. An injected pull
    must return None only for a confirmed 404 and raise for unavailable reads.
    Failures return False; HTTP success alone is not delivery confirmation.
    """
    import os
    import urllib.request

    url = str(
        endpoint_url or os.environ.get("RESEARCH_PROMOTION_SYNC_URL") or ""
    ).strip()
    token = str(
        sync_token or os.environ.get("RESEARCH_PROMOTION_SYNC_TOKEN") or ""
    ).strip()

    def _default_post_json(
        *,
        endpoint: str,
        bearer_token: str,
        payload: Mapping[str, Any],
        timeout: float,
    ) -> int:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {bearer_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(getattr(response, "status", 200) or 200)

    sender = post_json or _default_post_json
    reader = pull_console or make_console_research_promotion_pull(
        endpoint_url=_default_research_promotion_pull_url(url),
        sync_token=token, timeout_seconds=timeout_seconds, printer=printer,
        raise_on_unavailable=True,
    )
    attempted_ticket_ids: set[str] = set()

    def confirmed(ticket: ResearchPromotionTicket, remote: Mapping[str, Any]) -> bool:
        _require_matching_console_promotion_candidate(ticket, remote)
        return all(
            key in remote and _canonical_ticket_value(remote[key]) == _canonical_ticket_value(value)
            for key, value in ticket.to_dict().items()
        )

    def sync_console(ticket: ResearchPromotionTicket) -> bool:
        if not url or not token:
            printer(
                "research promotion console sync skipped: url/token not configured",
                flush=True,
            )
            return False
        if ticket.state != ResearchPromotionState.AWAITING_HUMAN:
            printer(
                "research promotion console sync skipped: ticket is not awaiting_human",
                flush=True,
            )
            return False
        if ticket.live_authority_granted:
            printer(
                "research promotion console sync refused: live_authority_granted=true",
                flush=True,
            )
            return False
        try:
            existing = reader(ticket.ticket_id)
            if existing is not None:
                return confirmed(ticket, existing)
        except Exception:
            printer("research promotion console sync soft-failed: readback_unavailable", flush=True)
            return False
        if ticket.ticket_id in attempted_ticket_ids:
            printer("research promotion console sync soft-failed: readback_unconfirmed", flush=True)
            return False
        payload = ticket.to_dict()
        payload["live_authority_granted"] = False
        attempted_ticket_ids.add(ticket.ticket_id)
        try:
            sender(
                endpoint=url,
                bearer_token=token,
                payload=payload,
                timeout=float(timeout_seconds),
            )
        except Exception:
            # A transport failure can occur after the server persisted the ticket.
            # Reconcile by reading, without automatically repeating this write.
            pass
        try:
            remote = reader(ticket.ticket_id)
            if remote is not None and confirmed(ticket, remote):
                return True
        except Exception:
            pass
        printer("research promotion console sync soft-failed: readback_unconfirmed", flush=True)
        return False

    return sync_console


def _default_research_promotion_pull_url(sync_url: str) -> str:
    base = str(sync_url or "").strip().rstrip("/")
    suffix = "/api/internal/sync-research-promotion-ticket"
    if base.endswith(suffix):
        return base[: -len(suffix)] + "/api/internal/research-promotion-ticket"
    if base.endswith("/sync-research-promotion-ticket"):
        return base[: -len("/sync-research-promotion-ticket")] + "/research-promotion-ticket"
    return ""


def make_console_research_promotion_pull(
    *,
    endpoint_url: str | None = None,
    sync_token: str | None = None,
    timeout_seconds: float = 5.0,
    printer: Any = print,
    get_json: Callable[..., Any] | None = None,
    raise_on_unavailable: bool = False,
) -> Callable[[str], Mapping[str, Any] | None]:
    """GET a console ticket by id; soft-skip if unconfigured.

    Env defaults:
    - RESEARCH_PROMOTION_PULL_URL (or derived from RESEARCH_PROMOTION_SYNC_URL)
    - RESEARCH_PROMOTION_SYNC_TOKEN

    Returns the remote ticket mapping, or None on soft-skip/soft-fail. With
    raise_on_unavailable, None means a confirmed 404; all other failures raise
    a sanitized ValueError so callers cannot mistake uncertainty for absence.
    Never grants live authority.
    """
    import os
    import urllib.error
    import urllib.parse
    import urllib.request

    sync_url = str(os.environ.get("RESEARCH_PROMOTION_SYNC_URL") or "").strip()
    url = str(
        endpoint_url
        or os.environ.get("RESEARCH_PROMOTION_PULL_URL")
        or _default_research_promotion_pull_url(sync_url)
        or ""
    ).strip()
    token = str(
        sync_token or os.environ.get("RESEARCH_PROMOTION_SYNC_TOKEN") or ""
    ).strip()

    def _default_get_json(
        *,
        endpoint: str,
        bearer_token: str,
        ticket_id: str,
        timeout: float,
    ) -> Mapping[str, Any]:
        query = urllib.parse.urlencode({"ticket_id": ticket_id})
        request = urllib.request.Request(
            f"{endpoint}?{query}",
            method="GET",
            headers={
                "Authorization": f"Bearer {bearer_token}",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("console pull response must be a JSON object")
        return payload

    fetcher = get_json or _default_get_json

    def unavailable(reason: str) -> None:
        if raise_on_unavailable:
            raise ValueError(reason) from None
        printer(f"research promotion console pull soft-failed: {reason}", flush=True)
        return None

    def pull_console(ticket_id: str) -> Mapping[str, Any] | None:
        tid = str(ticket_id or "").strip()
        if not tid:
            return unavailable("empty_ticket_id")
        if not url or not token:
            return unavailable("url/token not configured")
        try:
            payload = fetcher(
                endpoint=url,
                bearer_token=token,
                ticket_id=tid,
                timeout=float(timeout_seconds),
            )
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            return unavailable("console_read_unavailable")
        except Exception:
            return unavailable("console_read_unavailable")
        if (not isinstance(payload, Mapping) or payload.get("ok") is not True
                or payload.get("live_authority_granted") is not False):
            return unavailable("console_response_invalid")
        ticket = payload.get("ticket")
        if (not isinstance(ticket, Mapping) or ticket.get("ticket_id") != tid
                or ticket.get("live_authority_granted") is not False):
            return unavailable("console_ticket_invalid")
        return dict(ticket)

    return pull_console


def _canonical_ticket_value(value: Any) -> str:
    """Compare JSON material across Python/JS, with booleans distinct from numbers."""
    def normalize(item: Any) -> Any:
        if isinstance(item, float) and item.is_integer():
            return int(item)
        if isinstance(item, Mapping):
            return {key: normalize(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [normalize(child) for child in item]
        return item

    return json.dumps(normalize(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _require_matching_console_promotion_candidate(
    ticket: ResearchPromotionTicket,
    remote_ticket: Mapping[str, Any],
) -> None:
    """Match all fixed ticket material, including budget and shadow evidence."""
    if not isinstance(remote_ticket, Mapping) or remote_ticket.get("live_authority_granted") is not False:
        raise ValueError("console ticket must retain live_authority_granted=false")
    remote_id = str(remote_ticket.get("ticket_id") or "").strip()
    if not remote_id:
        raise ValueError("console ticket_id is required")
    if remote_id != ticket.ticket_id:
        raise ValueError(
            f"console ticket_id mismatch: local={ticket.ticket_id} remote={remote_id}"
        )
    remote_profile = str(remote_ticket.get("strategy_profile") or "").strip()
    if remote_profile != ticket.strategy_profile:
        raise ValueError(
            "console strategy_profile mismatch: "
            f"local={ticket.strategy_profile} remote={remote_profile}"
        )
    remote_domain = str(remote_ticket.get("domain") or "").strip()
    if remote_domain != ticket.domain:
        raise ValueError(
            f"console domain mismatch: local={ticket.domain} remote={remote_domain}"
        )
    remote_params = dict(remote_ticket.get("proposed_params") or {})
    local_params = dict(ticket.proposed_params)
    if _canonical_ticket_value(remote_params) != _canonical_ticket_value(local_params):
        raise ValueError(
            "console proposed_params mismatch with local ticket candidate"
        )
    decision_fields = {
        "state", "updated_at", "human_decision", "human_decided_at", "notes",
        "confirmation_target_platform", "confirmation_execution_mode", "confirmation_risk_profile",
    }
    for key, value in ticket.to_dict().items():
        if key not in decision_fields and (
            key not in remote_ticket
            or _canonical_ticket_value(remote_ticket[key]) != _canonical_ticket_value(value)
        ):
            raise ValueError(f"console candidate material mismatch: {key}")
    notes = remote_ticket.get("notes")
    if not isinstance(notes, (list, tuple)) or list(notes[:len(ticket.notes)]) != list(ticket.notes):
        raise ValueError("console candidate evidence notes mismatch")


def apply_console_research_promotion_decision(
    ticket: ResearchPromotionTicket,
    remote_ticket: Mapping[str, Any],
    *,
    decided_at: str | None = None,
) -> ResearchPromotionTicket:
    """Apply a console-stored decision onto a local awaiting ticket.

    Console is the intent ledger SoT for HITL accept/reject. Accept still never
    grants live authority. If the console already validated paper, trust that
    gate here (paper_supported follows remote execution_mode == paper).
    """
    if ticket.live_authority_granted or remote_ticket.get("live_authority_granted") is not False:
        raise ValueError("refusing to apply console decision with live_authority_granted=true")
    _require_matching_console_promotion_candidate(ticket, remote_ticket)
    state = str(remote_ticket.get("state") or "").strip()
    if state == ResearchPromotionState.AWAITING_HUMAN.value:
        raise ValueError("console ticket is still awaiting_human")
    if state == ResearchPromotionState.HUMAN_ACCEPTED.value:
        decision = "accept"
        confirmation = {
            "target_platform": str(remote_ticket.get("confirmation_target_platform") or ""),
            "execution_mode": str(remote_ticket.get("confirmation_execution_mode") or ""),
            "risk_profile": str(remote_ticket.get("confirmation_risk_profile") or ""),
        }
        paper_supported = confirmation["execution_mode"] == "paper"
    elif state == ResearchPromotionState.HUMAN_REJECTED.value:
        decision = "reject"
        confirmation = None
        paper_supported = False
    else:
        raise ValueError(f"unsupported console ticket state={state}")
    if remote_ticket.get("human_decision") != decision:
        raise ValueError("console decision/state mismatch")
    remote_decided_at = str(remote_ticket.get("human_decided_at") or "").strip()
    if not remote_decided_at:
        raise ValueError("console decision time unavailable")
    if datetime.fromisoformat(remote_decided_at.replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("console decision time requires timezone")
    decided = apply_human_promotion_decision(
        ResearchPromotionTicket.from_dict(ticket.to_dict(include_progress=True)),
        decision=decision,
        confirmation=confirmation,
        paper_supported=paper_supported,
        decided_at=decided_at or remote_decided_at,
    )
    if list(remote_ticket["notes"]) != list(decided.notes):
        raise ValueError("console decision evidence notes mismatch")
    decided.notes = decided.notes + ("console_decision_applied",)
    decided.live_authority_granted = False
    return decided


def reconcile_saved_research_promotion_ticket(
    ticket_path: str | Path,
    *,
    pull_console: Callable[[str], Mapping[str, Any] | None] | None = None,
    output_path: str | Path | None = None,
    domain: str | None = None,
) -> dict[str, Any]:
    """Serialize decision recovery with research and manual decisions."""
    result = {"ticket_id": None, "strategy_profile": None, "state": None,
              "status": "unavailable", "reason": "local_ticket_unavailable",
              "live_authority_granted": False}
    try:
        with _research_directory_lock(Path(ticket_path).parent) as acquired:
            if not acquired:
                return {**result, "status": "deferred", "reason": "research_in_progress"}
            return _reconcile_saved_research_promotion_ticket(
                ticket_path, pull_console=pull_console, output_path=output_path, domain=domain,
            )
    except (OSError, TypeError, ValueError):
        return result


def _reconcile_saved_research_promotion_ticket(
    ticket_path: str | Path,
    *,
    pull_console: Callable[[str], Mapping[str, Any] | None] | None = None,
    output_path: str | Path | None = None,
    domain: str | None = None,
) -> dict[str, Any]:
    """Recover one saved human decision without starting research or applying it.

    Terminal local tickets are idempotent no-ops. Callers retain each returned
    status and serialize work for the same ticket. No POST, model or platform
    action is performed; failures leave the original ticket unchanged.
    """
    result: dict[str, Any] = {"ticket_id": None, "strategy_profile": None,
        "status": "rejected", "state": None, "reason": "local_ticket_invalid",
        "live_authority_granted": False}
    try:
        ticket = load_research_promotion_ticket(ticket_path)
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return result
    result.update(ticket_id=ticket.ticket_id, strategy_profile=ticket.strategy_profile, state=ticket.state.value)
    if domain is not None and ticket.domain != domain:
        return {**result, "status": "skipped", "reason": "ticket_domain_mismatch"}
    if ticket.live_authority_granted:
        return {**result, "reason": "local_live_authority_rejected"}
    if ticket.state in _TERMINAL:
        return {**result, "status": "already_terminal", "reason": "local_ticket_terminal"}
    if ticket.state is not ResearchPromotionState.AWAITING_HUMAN:
        return {**result, "status": "skipped", "reason": "ticket_not_awaiting_human"}
    result["delivery_unstarted"] = (
        isinstance(ticket.research_progress.get("identity"), Mapping)
        and "console_delivery" not in ticket.research_progress
    )
    try:
        remote = (pull_console or make_console_research_promotion_pull())(ticket.ticket_id)
    except Exception:
        return {**result, "status": "unavailable", "reason": "console_read_unavailable"}
    if remote is None:
        return {**result, "status": "unavailable", "reason": "console_ticket_unavailable"}
    try:
        _require_matching_console_promotion_candidate(ticket, remote)
        if remote.get("state") == ResearchPromotionState.AWAITING_HUMAN.value:
            if any(key not in remote or _canonical_ticket_value(remote[key]) != _canonical_ticket_value(value)
                   for key, value in ticket.to_dict().items()):
                raise ValueError("awaiting ticket mismatch")
            return {**result, "status": "awaiting_human", "reason": "human_decision_pending"}
        decided = apply_console_research_promotion_decision(ticket, remote)
    except (ValueError, TypeError, KeyError):
        return {**result, "reason": "console_candidate_or_decision_mismatch"}
    try:
        save_research_promotion_ticket(decided, output_path or ticket_path)
    except (OSError, ValueError, TypeError):
        return {**result, "status": "unavailable", "reason": "local_ticket_save_failed"}
    return {**result, "status": "updated", "state": decided.state.value, "reason": "human_intent_reconciled"}


def _deliver_awaiting_human_ticket(
    ticket: ResearchPromotionTicket,
    *,
    notify: Callable[[str, str], None] | None = None,
    sync_console: Callable[[ResearchPromotionTicket], bool] | None = None,
) -> ResearchPromotionTicket:
    """Finalize awaiting_human delivery: notify humans, then soft-sync console."""
    subject, body = build_human_promotion_notification(ticket)
    ticket.notification_subject = subject
    ticket.notification_body = body
    ticket.updated_at = _now_iso()
    if notify is not None:
        notify(subject, body)
    if sync_console is not None:
        sync_console(ticket)
    return ticket


def _attach_shadow_or_park(
    ticket: ResearchPromotionTicket,
    shadow: Mapping[str, Any],
    *,
    budget: ResearchPromotionBudget,
    require_passed: bool,
) -> ResearchPromotionTicket | None:
    """Fill shadow fields. Return parked ticket when rejected; else None."""
    kind = _shadow_kind(shadow)
    ticket.shadow_evidence_kind = kind
    ticket.shadow_passed = bool(shadow.get("passed", False))
    if (shadow.get("status") == "pending" and shadow.get("passed") is False
            and shadow.get("no_order") is True and shadow.get("live_authority_granted") is False):
        ticket.state = ResearchPromotionState.SHADOW_RECORDED
        ticket.notes = ticket.notes + ("paired_shadow_observation_pending",)
        return ticket
    digest = str(shadow.get("paired_shadow_evidence_sha256") or "").strip()
    if digest:
        ticket.notes = ticket.notes + (f"paired_shadow_evidence_sha256={digest}",)
    if budget.require_paired_shadow and not _is_paired_shadow_kind(kind):
        ticket.state = ResearchPromotionState.PARKED
        ticket.notes = ticket.notes + ("paired_shadow_required", f"got={kind}")
        ticket.updated_at = _now_iso()
        return ticket
    if require_passed and not ticket.shadow_passed:
        ticket.state = ResearchPromotionState.PARKED
        ticket.notes = ticket.notes + ("shadow_failed",)
        ticket.updated_at = _now_iso()
        return ticket
    return None


def run_research_promotion_cycle(
    context: DriftResult | NewResearchRequest,
    *,
    optimize: Callable[[DriftResult, ResearchPromotionBudget], OptimizationProposal],
    record_shadow: Callable[[OptimizationProposal], Mapping[str, Any]],
    enforce_backtest_gates: (
        Callable[
            [OptimizationProposal],
            PromotionBacktestRun | Mapping[str, Any] | None,
        ]
        | None
    ) = None,
    notify: Callable[[str, str], None] | None = None,
    sync_console: Callable[[ResearchPromotionTicket], bool] | None = None,
    budget: ResearchPromotionBudget | None = None,
    ticket_id: str | None = None,
) -> ResearchPromotionTicket:
    """Execute the non-live research promotion slice and stop for humans."""
    budget = budget or ResearchPromotionBudget()
    is_new = isinstance(context, NewResearchRequest)
    if not is_new and not isinstance(context, DriftResult):
        raise TypeError("research context must be DriftResult or NewResearchRequest")
    strategy_profile = context.strategy_profile
    domain = context.domain
    now = _now_iso()
    ticket = ResearchPromotionTicket(
        ticket_id=ticket_id or _new_ticket_id(),
        strategy_profile=strategy_profile,
        domain=domain,
        state=ResearchPromotionState.PARKED,
        drift_status="new_research" if is_new else context.status.value,
        drift_score=None if is_new else float(context.drift_score),
        created_at=now,
        updated_at=now,
        budget={
            "max_search_iterations": budget.max_search_iterations,
            "max_param_keys": budget.max_param_keys,
            "allow_live_enablement": False,
            "require_paired_shadow": bool(budget.require_paired_shadow),
        },
        live_authority_granted=False,
    )

    if not is_new and context.status not in _ACTIVE_DRIFT:
        ticket.notes = ("drift_not_actionable",)
        ticket.updated_at = _now_iso()
        return ticket

    ticket.state = ResearchPromotionState.BOUNDED_REOPT
    proposal = optimize(context, budget)
    if (proposal.strategy_profile != strategy_profile or proposal.domain != domain):
        ticket.state = ResearchPromotionState.PARKED
        ticket.notes = ("proposal_target_mismatch",)
        return ticket
    ok, reason = enforce_optimization_budget(proposal, budget)
    ticket.search_iterations = int(proposal.search_iterations)
    ticket.proposed_params = dict(proposal.proposed_params or {})
    if not ok:
        ticket.state = ResearchPromotionState.PARKED
        ticket.notes = ("budget_exceeded", reason)
        ticket.updated_at = _now_iso()
        return ticket

    if proposal.recommendation not in _RESEARCH_CANDIDATE_RECOMMENDATIONS:
        ticket.state = ResearchPromotionState.PARKED
        ticket.notes = (f"recommendation={proposal.recommendation}",)
        ticket.updated_at = _now_iso()
        return ticket

    try:
        backtest_evidence = (
            enforce_backtest_gates(proposal)
            if enforce_backtest_gates is not None
            else None
        )
    except Exception as exc:
        ticket.state = ResearchPromotionState.PARKED
        ticket.notes = (
            "promotion_backtest_gate_failed",
            f"promotion_backtest_gate_error={type(exc).__name__}",
        )
        ticket.updated_at = _now_iso()
        return ticket
    gates_ok, gate_reason = enforce_promotion_backtest_gates(
        proposal, backtest_evidence
    )
    if not gates_ok:
        ticket.state = ResearchPromotionState.PARKED
        ticket.notes = ("promotion_backtest_gate_failed", gate_reason)
        ticket.updated_at = _now_iso()
        return ticket
    ticket.notes = ticket.notes + (gate_reason,)

    shadow = dict(record_shadow(proposal))
    ticket.state = ResearchPromotionState.SHADOW_RECORDED
    parked = _attach_shadow_or_park(
        ticket, shadow, budget=budget, require_passed=True
    )
    if parked is not None:
        return parked

    ticket.state = ResearchPromotionState.AWAITING_HUMAN
    return _deliver_awaiting_human_ticket(
        ticket, notify=notify, sync_console=sync_console
    )


def open_awaiting_human_ticket(
    *,
    drift: DriftResult,
    proposal: OptimizationProposal,
    shadow: Mapping[str, Any],
    budget: ResearchPromotionBudget | None = None,
    notify: Callable[[str, str], None] | None = None,
    sync_console: Callable[[ResearchPromotionTicket], bool] | None = None,
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
            "require_paired_shadow": bool(budget.require_paired_shadow),
        },
        proposed_params=dict(proposal.proposed_params or {}),
        search_iterations=int(proposal.search_iterations),
        live_authority_granted=False,
    )
    if not ok:
        ticket.notes = ("budget_exceeded", reason)
        return ticket
    parked = _attach_shadow_or_park(
        ticket, shadow, budget=budget, require_passed=True
    )
    if parked is not None:
        return parked

    ticket.state = ResearchPromotionState.AWAITING_HUMAN
    return _deliver_awaiting_human_ticket(
        ticket, notify=notify, sync_console=sync_console
    )


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


def save_research_promotion_ticket(
    ticket: ResearchPromotionTicket,
    path: str | Path,
) -> Path:
    """Replace a complete ticket atomically; failed writes retain the old file."""
    import os
    import tempfile

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(ticket.to_dict(include_progress=True), indent=2, sort_keys=True, allow_nan=False) + "\n"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent,
            prefix=f".{target.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target


def load_research_promotion_ticket(path: str | Path) -> ResearchPromotionTicket:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("ticket file must contain a JSON object")
    ticket = ResearchPromotionTicket.from_dict(raw)
    if ticket.live_authority_granted:
        raise ValueError("refusing to load ticket with live_authority_granted=true")
    return ticket


@contextmanager
def _research_directory_lock(directory: Path):
    """One process at a time for this shared directory, never a global queue."""
    import os

    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".research.lock").open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                yield False
                return
            try:
                yield True
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _saved_proposal(raw: Mapping[str, Any]) -> OptimizationProposal:
    from quant_platform_kit.strategy_lifecycle.contracts import BacktestValidationIdentity
    from quant_platform_kit.strategy_lifecycle.performance_store import _backtest_from_dict

    values = dict(raw)
    for key in ("current_metrics", "proposed_metrics"):
        if values.get(key) is not None:
            stored = values[key]
            validation = stored.get("validation_identity")
            if validation is not None:
                validation = dict(validation)
                for date_key in ("train_start", "train_end", "test_start", "test_end",
                                 "locked_oos_start", "locked_oos_end"):
                    validation[date_key] = date.fromisoformat(validation[date_key]) if validation[date_key] else None
                validation = BacktestValidationIdentity(**validation)
            values[key] = replace(_backtest_from_dict(stored), validation_identity=validation,
                                  cost_inputs=dict(stored.get("cost_inputs") or {}))
    for key in ("winning_dimensions", "regressing_dimensions"):
        values[key] = tuple(values.get(key) or ())
    proposal = OptimizationProposal(**values)
    if _canonical_ticket_value(proposal.to_dict()) != _canonical_ticket_value(raw):
        raise ValueError("saved_proposal_invalid")
    return proposal


_MAX_NO_IMPROVEMENT_ROUNDS = 3
_MAX_IDLE_DAYS = 30
_SUMMARY_MAX_TEXT = 2000
_RESEARCH_OWNER_FIELDS = frozenset({"repository", "issue_number", "watcher_issue_key"})
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_RESEARCH_OWNER_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class _ResearchScopeArchived(Exception):
    """Internal short circuit after a scope reaches its research limit."""


def _normalize_research_owner(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != _RESEARCH_OWNER_FIELDS:
        return None
    repository = value.get("repository")
    issue_number = value.get("issue_number")
    watcher_issue_key = value.get("watcher_issue_key")
    if (not isinstance(repository, str) or not _REPOSITORY_RE.fullmatch(repository)
            or type(issue_number) is not int or issue_number <= 0
            or not isinstance(watcher_issue_key, str)
            or not _RESEARCH_OWNER_KEY_RE.fullmatch(watcher_issue_key)):
        return None
    return {
        "repository": repository,
        "issue_number": issue_number,
        "watcher_issue_key": watcher_issue_key,
    }


def _progress_now() -> datetime:
    """Use wall-clock time for lifecycle elapsed time, never observation dates."""
    return _clock_now()


def _clock_now() -> datetime:
    return datetime.now(timezone.utc)


def _scope_identity(identity: Mapping[str, Any]) -> dict[str, Any]:
    drift = identity.get("drift") if isinstance(identity, Mapping) else None
    request = identity.get("request") if isinstance(identity, Mapping) else None
    revisions = identity.get("revisions") if isinstance(identity, Mapping) else None
    context = drift if isinstance(drift, Mapping) else request
    if not isinstance(context, Mapping) or not isinstance(revisions, Mapping):
        return {}
    owner = identity.get("owner") if isinstance(identity, Mapping) else None
    revision_keys = ("cost_model_revision", "validator_revision") if isinstance(owner, Mapping) else (
        "code_revision", "cost_model_revision", "validator_revision",
    )
    result = {
        "revisions": {key: revisions.get(key) for key in revision_keys},
        ("drift" if isinstance(drift, Mapping) else "request"): ({key: context.get(key) for key in (
            "strategy_profile", "domain", "baseline_param_set_id",
            "baseline_param_version", "baseline_artifact_id",
        )} if isinstance(drift, Mapping) else {
            key: context.get(key) for key in ("strategy_profile", "domain", "research_intent", "source_receipt_refs")
        }),
    }
    if isinstance(owner, Mapping):
        result["owner"] = dict(owner)
    return result


def _scope_key(identity: Mapping[str, Any]) -> str:
    scope = _scope_identity(identity)
    if not scope or any(value is None for value in scope["revisions"].values()):
        return ""
    return hashlib.sha256(_canonical_ticket_value(scope).encode()).hexdigest()


def _exact_identity(identity: Mapping[str, Any]) -> dict[str, Any]:
    scope = _scope_identity(identity)
    revisions = identity.get("revisions") if isinstance(identity, Mapping) else None
    if not scope or not isinstance(revisions, Mapping):
        return {}
    scope["revisions"].update({key: revisions.get(key) for key in (
        "code_revision", "input_revision", "param_space_revision",
    )})
    request = identity.get("request") if isinstance(identity, Mapping) else None
    if isinstance(request, Mapping):
        scope["request_exact"] = {
            "source_revision": request.get("source_revision"),
        }
    return scope


def _exact_key(identity: Mapping[str, Any]) -> str:
    exact = _exact_identity(identity)
    if not exact or any(value is None for value in exact["revisions"].values()):
        return ""
    return hashlib.sha256(_canonical_ticket_value(exact).encode()).hexdigest()


def _parse_progress_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = _REAL_DATETIME.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _lifecycle(progress: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    value = progress.get("lifecycle") if isinstance(progress, Mapping) else None
    result = dict(value) if isinstance(value, Mapping) else {}
    result.setdefault("first_observed_at", now.isoformat())
    result.setdefault("last_substantive_progress_at", now.isoformat())
    result["no_improvement_count"] = max(0, int(result.get("no_improvement_count") or 0))
    result["counted_result_digests"] = [
        str(item) for item in (result.get("counted_result_digests") or ()) if str(item)
    ]
    result.setdefault("paused", False)
    result.setdefault("archived", False)
    return result


def _touch_progress(progress: dict[str, Any], now: datetime) -> dict[str, Any]:
    value = _lifecycle(progress, now)
    value["last_substantive_progress_at"] = now.isoformat()
    value["paused"] = False
    value.pop("paused_since", None)
    value.pop("pause_reason", None)
    progress["lifecycle"] = value
    return value


def _pause_progress(progress: dict[str, Any], now: datetime, reason: str) -> None:
    value = _lifecycle(progress, now)
    value["paused"] = True
    value["paused_since"] = value.get("paused_since") or now.isoformat()
    value["pause_reason"] = str(reason)
    progress["lifecycle"] = value


def _proposal_no_improvement(proposal: OptimizationProposal) -> bool:
    if not _proposal_comparable(proposal):
        return False
    current = proposal.current_metrics
    proposed = proposal.proposed_metrics
    if not (float(proposed.cagr) <= float(current.cagr)
            and abs(float(proposed.max_drawdown)) >= abs(float(current.max_drawdown))):
        return False
    score = proposal.improvement_score
    return (proposal.recommendation == "reject"
            and not proposal.winning_dimensions
            and isinstance(score, (int, float)) and not isinstance(score, bool)
            and math.isfinite(float(score)) and float(score) <= 0.0)


def _record_no_improvement(progress: dict[str, Any], proposal: OptimizationProposal, now: datetime) -> bool:
    value = _touch_progress(progress, now)
    digest = hashlib.sha256(_canonical_ticket_value(proposal.to_dict()).encode()).hexdigest()
    if digest in value["counted_result_digests"]:
        return False
    value["counted_result_digests"].append(digest)
    value["no_improvement_count"] = len(value["counted_result_digests"])
    progress["lifecycle"] = value
    return True


def _summary_context(proposal: OptimizationProposal) -> dict[str, Any]:
    current = proposal.current_metrics
    proposed = proposal.proposed_metrics
    comparison: dict[str, Any] = {
        "status": "unavailable", "start_date": None, "end_date": None,
        "cost_model": "", "baseline": None, "candidate": None,
    }
    if _proposal_comparable(proposal):
        comparison.update(
            status="comparable", start_date=current.start_date.isoformat(),
            end_date=current.end_date.isoformat(), cost_model=current.cost_model,
            baseline={"cagr": current.cagr, "max_drawdown": current.max_drawdown},
            candidate={"cagr": proposed.cagr, "max_drawdown": proposed.max_drawdown},
        )
    return {
        "identity": {
            "strategy_profile": proposal.strategy_profile,
            "domain": proposal.domain,
            "proposed_params": dict(proposal.proposed_params),
        },
        "strategy_description": "",
        "plugins": None,
        "comparison": comparison,
        "limitations": [] if comparison["status"] == "comparable" else [
            "尚无同一条件下的收益对比"
        ],
    }


def _proposal_comparable(proposal: OptimizationProposal) -> bool:
    current = proposal.current_metrics
    proposed = proposal.proposed_metrics
    if current is None or proposed is None:
        return False
    if (current.strategy_profile != proposal.strategy_profile
            or proposed.strategy_profile != proposal.strategy_profile
            or current.domain != proposal.domain or proposed.domain != proposal.domain
            or current.start_date is None or current.end_date is None
            or current.start_date != proposed.start_date or current.end_date != proposed.end_date
            or current.cost_model != proposed.cost_model or not current.cost_model
            or dict(current.cost_inputs) != dict(proposed.cost_inputs)
            or not current.cost_inputs or current.source_revision != proposed.source_revision
            or not current.source_revision or dict(current.params) != dict(proposal.current_params)
            or dict(proposed.params) != dict(proposal.proposed_params)):
        return False
    values = (current.cagr, current.max_drawdown, proposed.cagr, proposed.max_drawdown)
    if not all(value is not None and not isinstance(value, bool) and isinstance(value, (int, float))
               and math.isfinite(float(value)) for value in values):
        return False
    if current.start_date > current.end_date:
        return False
    return all(isinstance(value, (int, float)) and not isinstance(value, bool)
               and math.isfinite(float(value)) and float(value) >= 0.0
               for value in current.cost_inputs.values())


def _attach_research_summary(
    ticket: ResearchPromotionTicket,
    proposal: OptimizationProposal | None,
    summarize: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None,
    persist: Callable[[], None] | None = None,
) -> None:
    if "ai_explanation" in ticket.research_summary:
        return
    context = _summary_context(proposal) if proposal is not None else {
        "identity": {"strategy_profile": ticket.strategy_profile, "domain": ticket.domain,
                     "proposed_params": dict(ticket.proposed_params)},
        "strategy_description": "", "plugins": None,
        "comparison": {"status": "unavailable", "start_date": None, "end_date": None,
                       "cost_model": "", "baseline": None,
                       "candidate": None},
        "limitations": ["尚无同一条件下的收益对比"],
    }
    explanation: dict[str, Any] = {"status": "unavailable", "text": "暂无法生成 AI 简述。",
                                    "provider": "", "model": ""}
    ticket.research_summary = {**context, "ai_explanation": explanation}
    if persist is not None:
        persist()
    if callable(summarize):
        try:
            value = summarize(context)
            if isinstance(value, Mapping) and value.get("status") == "available":
                text = value.get("text")
                provider = value.get("provider") or ""
                model = value.get("model") or ""
                if (isinstance(text, str) and text.strip() and len(text) <= _SUMMARY_MAX_TEXT
                        and provider == "codex" and isinstance(model, str)):
                    explanation = {"status": "available", "text": text.strip(),
                                   "provider": "codex", "model": model}
        except Exception:
            pass
    ticket.research_summary = {**context, "ai_explanation": explanation}
    if persist is not None:
        persist()


def _saved_scope_records(directory: Path, scope_key: str) -> list[tuple[Path, ResearchPromotionTicket]]:
    records: list[tuple[Path, ResearchPromotionTicket]] = []
    if not directory.exists():
        return records
    for candidate in directory.glob("*.json"):
        try:
            ticket = load_research_promotion_ticket(candidate)
            progress = ticket.research_progress
            candidate_scope = str(progress.get("scope_key") or _scope_key(progress.get("identity", {})))
            if candidate_scope == scope_key:
                records.append((candidate, ticket))
        except (OSError, ValueError, TypeError, KeyError, OverflowError):
            raise ValueError("research_scope_checkpoint_unavailable") from None
    return records


def _saved_exact_record(
    records: list[tuple[Path, ResearchPromotionTicket]], exact_key: str,
) -> tuple[Path, ResearchPromotionTicket] | None:
    for path, ticket in records:
        progress = ticket.research_progress
        identity = progress.get("identity", {})
        if str(progress.get("exact_key") or _exact_key(identity)) == exact_key:
            return path, ticket
    return None


def _scope_lifecycle(records: list[tuple[Path, ResearchPromotionTicket]], now: datetime) -> dict[str, Any]:
    digests: list[str] = []
    last_progress: datetime | None = None
    first_observed: datetime | None = None
    paused = False
    archived = False
    latest_state_at: datetime | None = None
    for _, ticket in records:
        value = _lifecycle(ticket.research_progress, now)
        for digest in value["counted_result_digests"]:
            if digest not in digests:
                digests.append(digest)
        current_last = _parse_progress_time(value.get("last_substantive_progress_at"))
        current_first = _parse_progress_time(value.get("first_observed_at"))
        if current_last is not None and (last_progress is None or current_last > last_progress):
            last_progress = current_last
        if current_first is not None and (first_observed is None or current_first < first_observed):
            first_observed = current_first
        archived = archived or value.get("archived") is True
        state_at = current_last or current_first
        if state_at is not None and (latest_state_at is None or state_at >= latest_state_at):
            latest_state_at = state_at
            paused = value.get("paused") is True
    return {
        "first_observed_at": (first_observed or now).isoformat(),
        "last_substantive_progress_at": (last_progress or now).isoformat(),
        "no_improvement_count": len(digests),
        "counted_result_digests": digests,
        "paused": paused,
        "archived": archived,
    }


def _scope_is_protected(records: list[tuple[Path, ResearchPromotionTicket]]) -> bool:
    for _, ticket in records:
        progress = ticket.research_progress
        stages = progress.get("stages", {})
        if any(isinstance(value, Mapping) and value.get("status") in {"running", "unknown"}
               for value in stages.values()):
            return True
        if ticket.state in {ResearchPromotionState.SHADOW_RECORDED,
                            ResearchPromotionState.AWAITING_HUMAN,
                            ResearchPromotionState.HUMAN_ACCEPTED}:
            return True
    return False


def _archive_ticket(ticket: ResearchPromotionTicket, progress: dict[str, Any], now: datetime, reason: str) -> None:
    lifecycle = _lifecycle(progress, now)
    lifecycle.update({"archived": True, "archived_at": now.isoformat(), "archive_reason": reason})
    progress["lifecycle"] = lifecycle
    ticket.state = ResearchPromotionState.PARKED
    ticket.notes = tuple(ticket.notes) + ("research_archived", f"archive_reason={reason}")
    ticket.updated_at = now.isoformat()
    ticket.research_progress = progress


def run_saved_research_promotion_cycle(
    drift: DriftResult | None = None,
    *,
    new_request: NewResearchRequest | None = None,
    research_identity: Mapping[str, str],
    ticket_dir: str | Path,
    optimize: Callable,
    enforce_backtest_gates: Callable,
    record_shadow: Callable,
    diagnose: Callable | None = None,
    sync_console: Callable | None = None,
    pull_console: Callable | None = None,
    budget: ResearchPromotionBudget | None = None,
    evaluation_date: date | str | None = None,
    max_age_days: int = 7,
    resume_delivery_only: bool = False,
    admit_new_research: Callable[[Path, str], bool] | None = None,
    read_pending_shadow: Callable[[OptimizationProposal], Mapping[str, Any]] | None = None,
    summarize: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    research_owner: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resume a bound experiment using the existing ticket's local progress.

    Revisions refer to the caller's validated, frozen input, code, parameter
    space (including baseline/fixed parameters), cost model and validator. They
    are not evidence validation themselves. Only processes sharing ticket_dir
    share the nonblocking lock; the dispatcher owns cross-host admission.

    Each side-effecting stage is saved as running BEFORE invocation. Completed
    results are reused; running/unknown outcomes never get automatically called
    again. A definite diagnosis deferral may run again only after retry_at.
    Console writes are attempted once and thereafter recovered only by GET.
    Optional admission runs under this lock only for a new ticket; its directory
    and UTC created_at match the eventual ticket. It must not acquire this lock
    again or maintain a second counter. Only literal True permits creation.
    Explicit pending shadow may use read_pending_shadow after its deadline.
    A stale original observation only permits this already-computed, identity-
    matched tail; it never permits new AI, optimization or backtest calls.
    """
    from quant_platform_kit.strategy_lifecycle.production_drift_health_probe import (
        probe_production_drift_health,
    )

    base = {"status": "parked", "reason": "research_input_invalid", "resumed": False,
            "console_synced": None, "live_authority_granted": False}
    if not all(callable(fn) for fn in (optimize, enforce_backtest_gates, record_shadow)):
        return {**base, "reason": "research_bindings_unavailable"}
    if (drift is None) == (new_request is None):
        return {**base, "reason": "research_context_invalid"}
    context: DriftResult | NewResearchRequest = drift if drift is not None else new_request  # type: ignore[assignment]
    is_new = isinstance(context, NewResearchRequest)
    strategy_profile = context.strategy_profile
    domain = context.domain
    source_revision = context.source_revision
    fields = {"code_revision", "input_revision", "param_space_revision",
              "cost_model_revision", "validator_revision"}
    if (not isinstance(research_identity, Mapping) or set(research_identity) != fields
            or any(not isinstance(v, str) or not v.strip() for v in research_identity.values())
            or not isinstance(source_revision, str) or not source_revision.strip()):
        return {**base, "reason": "research_identity_unavailable"}
    owner = _normalize_research_owner(research_owner)
    if research_owner is not None and owner is None:
        return {**base, "reason": "research_owner_invalid"}
    budget = budget or ResearchPromotionBudget(require_paired_shadow=True)
    if (type(budget.max_search_iterations) is not int or not 1 <= budget.max_search_iterations <= 25
            or type(budget.max_param_keys) is not int or not 1 <= budget.max_param_keys <= 4
            or budget.require_paired_shadow is not True or budget.allow_live_enablement):
        return {**base, "reason": "research_budget_invalid"}
    try:
        health = (None if is_new else probe_production_drift_health(
            strategy_profile=strategy_profile, domain=domain,
            as_of=context.as_of, drift_score=context.drift_score,
            evaluation_date=evaluation_date, max_age_days=max_age_days,
        ))
    except (ValueError, TypeError, OverflowError):
        return base
    if is_new:
        try:
            evaluation_day = evaluation_date
            if evaluation_day is None:
                evaluation_day = _clock_now().date()
            elif isinstance(evaluation_day, str):
                evaluation_day = date.fromisoformat(evaluation_day)
            if not isinstance(evaluation_day, date):
                return {**base, "reason": "new_research_evaluation_date_invalid"}
        except (TypeError, ValueError):
            return {**base, "reason": "new_research_evaluation_date_invalid"}
        if context.as_of > evaluation_day:
            return {**base, "reason": "new_research_as_of_future"}
        request_stale = evaluation_day - context.as_of > timedelta(days=max_age_days)
    else:
        request_stale = False
    stale = bool((health and health.get("reason") == "observation_stale") or request_stale)
    if (not is_new and ((not health["actionable"] and not stale)
            or context.status not in _ACTIVE_DRIFT or context.alert_suppressed)):
        return {**base, "reason": health.get("reason", "drift_not_actionable")}
    context_identity = (context.to_dict() if is_new else {
        key: context.to_dict()[key] for key in (
            "strategy_profile", "domain", "as_of", "source_revision", "drift_score",
            "baseline_param_set_id", "baseline_param_version", "baseline_artifact_id")
    })
    identity = {"revisions": dict(research_identity),
                ("request" if is_new else "drift"): context_identity,
                "budget": asdict(budget)}
    if owner is not None:
        identity["owner"] = owner
    try:
        canonical = _canonical_ticket_value(identity)
        research_key = hashlib.sha256(canonical.encode()).hexdigest()
        scope_key = _scope_key(identity)
        exact_key = _exact_key(identity)
        directory = Path(ticket_dir)
    except (ValueError, TypeError):
        return base
    if not scope_key or not exact_key:
        return {**base, "reason": "research_identity_unavailable"}
    ticket_id = f"rpt_{research_key}"
    path = directory / f"{ticket_id}.json"
    base.update(research_key=research_key, ticket_path=str(path))

    try:
        with _research_directory_lock(directory) as acquired:
            if not acquired:
                return {**base, "status": "deferred", "reason": "research_in_progress"}
            now_value = _progress_now()
            records = _saved_scope_records(directory, scope_key)
            reused_exact = False
            if not path.exists():
                exact_record = _saved_exact_record(records, exact_key)
                if exact_record is not None:
                    existing_path, existing_ticket = exact_record
                    path = existing_path
                    ticket_id = existing_ticket.ticket_id
                    reused_exact = True
                    base.update(
                        research_key=ticket_id.removeprefix("rpt_"),
                        ticket_path=str(path),
                    )
            if path.exists():
                ticket = load_research_promotion_ticket(path)
                progress = dict(ticket.research_progress)
                saved_identity = progress.get("identity")
                identity_matches = _canonical_ticket_value(saved_identity) == canonical
                exact_identity_matches = _exact_key(saved_identity) == exact_key
                if (ticket.ticket_id != ticket_id or ticket.strategy_profile != strategy_profile
                        or ticket.domain != domain
                        or (not identity_matches and not exact_identity_matches)):
                    return {**base, "reason": "research_checkpoint_mismatch"}
                progress.setdefault("scope_key", scope_key)
                progress.setdefault("exact_key", exact_key)
                if "lifecycle" not in progress:
                    progress["lifecycle"] = _lifecycle({}, now_value)
                    ticket.research_progress = progress
                    save_research_promotion_ticket(ticket, path)
                current_lifecycle = _lifecycle(progress, now_value)
                if (ticket.state is not ResearchPromotionState.HUMAN_REJECTED
                        and not _scope_is_protected([(path, ticket)])
                        and not current_lifecycle.get("paused")
                        and now_value - (_parse_progress_time(current_lifecycle["last_substantive_progress_at"]) or now_value)
                        >= timedelta(days=_MAX_IDLE_DAYS)):
                    _archive_ticket(ticket, progress, now_value, "idle_timeout")
                    save_research_promotion_ticket(ticket, path)
                    return {**base, "status": "parked", "reason": "research_scope_archived",
                            "ticket": ticket.to_dict()}
                base["resumed"] = True
            else:
                if stale:
                    return {**base, "reason": "observation_stale"}
                if resume_delivery_only:
                    return {**base, "reason": "saved_research_ticket_pending"}
                archived_record = next(
                    (item for item in records
                     if _lifecycle(item[1].research_progress, now_value).get("archived") is True),
                    None,
                )
                if archived_record is not None:
                    base["ticket_path"] = str(archived_record[0])
                    return {**base, "status": "parked", "reason": "research_scope_archived",
                            "ticket": archived_record[1].to_dict()}
                aggregate = _scope_lifecycle(records, now_value)
                if _scope_is_protected(records):
                    # Active shadow, human gates, and unknown work suppress idle
                    # archival, while a materially new exact trial may proceed.
                    aggregate["paused"] = True
                if (aggregate["archived"]
                        or aggregate["no_improvement_count"] >= _MAX_NO_IMPROVEMENT_ROUNDS
                        or (not aggregate["paused"] and
                            now_value - _parse_progress_time(aggregate["last_substantive_progress_at"]) >= timedelta(days=_MAX_IDLE_DAYS))):
                    if records:
                        old_path, old_ticket = records[-1]
                        old_progress = dict(old_ticket.research_progress)
                        _archive_ticket(old_ticket, old_progress, now_value, "no_improvement_limit" if aggregate["no_improvement_count"] >= _MAX_NO_IMPROVEMENT_ROUNDS else "idle_timeout")
                        save_research_promotion_ticket(old_ticket, old_path)
                        base["ticket_path"] = str(old_path)
                        return {**base, "status": "parked", "reason": "research_scope_archived",
                                "ticket": old_ticket.to_dict()}
                now = now_value.isoformat()
                if admit_new_research is not None:
                    try:
                        admitted = admit_new_research(directory, now)
                    except Exception:
                        return {**base, "reason": "research_admission_unavailable"}
                    if admitted is not True:
                        return {**base, "status": "deferred", "reason": "new_research_not_admitted"}
                progress = {"identity": identity, "scope_key": scope_key, "exact_key": exact_key,
                            "stages": {}, "diagnosis_required": diagnose is not None,
                            "lifecycle": aggregate}
                ticket = ResearchPromotionTicket(
                    ticket_id=ticket_id, strategy_profile=strategy_profile,
                    domain=domain, state=ResearchPromotionState.BOUNDED_REOPT,
                    drift_status="new_research" if is_new else context.status.value,
                    drift_score=None if is_new else context.drift_score,
                    created_at=now, updated_at=now, budget=asdict(budget),
                    research_progress=progress, research_summary={},
                )
                save_research_promotion_ticket(ticket, path)

            def output(reason: str, *, status: str | None = None) -> dict[str, Any]:
                return {**base, "status": status or ticket.state.value, "reason": reason,
                        "ticket": ticket.to_dict()}

            def deliver_saved_ticket() -> None:
                if (ticket.state != ResearchPromotionState.AWAITING_HUMAN or sync_console is None
                        or progress.get("console_delivery") is not None):
                    return
                progress["console_delivery"] = "running"
                save_research_promotion_ticket(ticket, path)
                try:
                    candidate = ResearchPromotionTicket.from_dict(ticket.to_dict())
                    confirmed = sync_console(candidate) is True
                    base["console_synced"] = (
                        confirmed and _canonical_ticket_value(candidate.to_dict())
                        == _canonical_ticket_value(ticket.to_dict())
                    )
                except Exception:
                    base["console_synced"] = False
                progress["console_delivery"] = "confirmed" if base["console_synced"] else "unconfirmed"
                save_research_promotion_ticket(ticket, path)

            def attach_summary(proposal: OptimizationProposal | None = None) -> None:
                _attach_research_summary(
                    ticket, proposal, summarize,
                    persist=lambda: save_research_promotion_ticket(ticket, path),
                )

            if resume_delivery_only and ticket.state != ResearchPromotionState.AWAITING_HUMAN:
                return output("saved_research_ticket_pending", status="parked")
            stages = progress["stages"]
            if not isinstance(stages, dict):
                return output("research_checkpoint_invalid")
            if _lifecycle(progress, now_value).get("archived") is True:
                return output("research_scope_archived", status="parked")
            if any(value.get("status") in {"running", "unknown"} for value in stages.values()):
                return output("research_outcome_unknown", status="parked")
            if ticket.state in _TERMINAL:
                return output("saved_research_ticket_reused" if reused_exact else "saved_research_ticket_terminal")
            shadow_pending = stages.get("shadow", {}).get("status") == "pending"
            shadow_completed = (ticket.state == ResearchPromotionState.SHADOW_RECORDED
                                and stages.get("shadow", {}).get("status") == "completed"
                                and stages["shadow"].get("result", {}).get("status") == "complete")
            awaiting_recovery = stale and ticket.state == ResearchPromotionState.AWAITING_HUMAN
            if shadow_pending or shadow_completed or awaiting_recovery:
                # A pending observation never permits incomplete earlier work
                # to restart, even while the original drift is still fresh.
                required = ("optimize", "backtest") + (("diagnose",) if progress.get("diagnosis_required") else ())
                if (ticket.state not in {ResearchPromotionState.SHADOW_RECORDED, ResearchPromotionState.AWAITING_HUMAN}
                        or any(stages.get(name, {}).get("status") != "completed" for name in required)):
                    return output("research_checkpoint_invalid", status="parked")
                proposal = _saved_proposal(stages["optimize"]["result"])
                if awaiting_recovery:
                    recorded = stages.get("shadow", {})
                    shadow = recorded.get("result", {})
                    if (recorded.get("status") != "completed" or shadow.get("passed") is not True
                            or not _is_paired_shadow_kind(_shadow_kind(shadow))
                            or shadow.get("live_authority_granted") is True or ticket.shadow_passed is not True
                            or _canonical_ticket_value(ticket.proposed_params) != _canonical_ticket_value(proposal.proposed_params)):
                        return output("research_checkpoint_invalid", status="parked")
                gates_ok, _ = enforce_promotion_backtest_gates(proposal, stages["backtest"]["result"])
                budget_ok, _ = enforce_optimization_budget(proposal, budget)
                if (not gates_ok or not budget_ok or proposal.recommendation not in _RESEARCH_CANDIDATE_RECOMMENDATIONS
                        or proposal.strategy_profile != strategy_profile or proposal.domain != domain
                        or (progress.get("diagnosis_required")
                            and stages["diagnose"]["result"].get("optimization_needed") is not True)):
                    return output("research_checkpoint_invalid", status="parked")
            if shadow_pending:
                pending_result = stages["shadow"].get("result", {})
                if (pending_result.get("status") != "pending" or pending_result.get("passed") is not False
                        or pending_result.get("no_order") is not True or pending_result.get("live_authority_granted") is not False):
                    return output("research_checkpoint_invalid", status="parked")
                retry = pending_result.get("retry_at")
                if (type(retry) not in (int, float) or not math.isfinite(retry)
                        or retry > _clock_now().timestamp()):
                    return {**output("paired_shadow_observation_pending", status="deferred"), "retry_at": retry}
                if not callable(read_pending_shadow):
                    return output("shadow_reader_unavailable", status="deferred")
            elif stale and not (shadow_completed or awaiting_recovery):
                return output("new_research_stale" if is_new else "observation_stale", status="parked")
            if ticket.state == ResearchPromotionState.AWAITING_HUMAN:
                stored_proposal = None
                if isinstance(stages.get("optimize", {}).get("result"), Mapping):
                    try:
                        stored_proposal = _saved_proposal(stages["optimize"]["result"])
                    except (ValueError, TypeError, KeyError):
                        stored_proposal = None
                attach_summary(stored_proposal)
                reconciliation = _reconcile_saved_research_promotion_ticket(path, pull_console=pull_console)
                ticket = load_research_promotion_ticket(path)
                progress = ticket.research_progress
                if not stale:
                    deliver_saved_ticket()
                return {**output("saved_research_ticket_reused"), "reconciliation": reconciliation}

            def stage(name: str, callback: Callable, encode: Callable = lambda value: value):
                existing = stages.get(name)
                if existing is not None:
                    if existing.get("status") == "completed":
                        return existing["result"]
                    if not (name == "shadow" and shadow_pending and existing.get("status") == "pending"):
                        raise ValueError("research_checkpoint_invalid")
                stages[name] = {"status": "running"}
                save_research_promotion_ticket(ticket, path)
                try:
                    result = json.loads(_canonical_ticket_value(encode(callback())))
                except Exception:
                    stages[name] = {"status": "unknown"}
                    save_research_promotion_ticket(ticket, path)
                    raise ValueError("research_outcome_unknown") from None
                status = ("pending" if name == "shadow" and isinstance(result, Mapping)
                          and result.get("status") == "pending" else "completed")
                completed_at = _progress_now()
                stages[name] = {"status": status, "result": result,
                                "completed_at": completed_at.isoformat()}
                _touch_progress(progress, completed_at)
                if name == "shadow" and isinstance(result, Mapping) and result.get("status") in {"pending", "complete"}:
                    # Save the resumable state with the result, not in a later
                    # write after the caller may already have stopped.
                    ticket.state = ResearchPromotionState.SHADOW_RECORDED
                save_research_promotion_ticket(ticket, path)
                return result

            if progress.get("diagnosis_required") is True:
                if diagnose is None:
                    return output("research_bindings_unavailable", status="parked")
                old = stages.get("diagnose", {})
                if old.get("status") == "deferred":
                    retry = old.get("retry_at")
                    if type(retry) not in (int, float) or retry > _clock_now().timestamp():
                        return {**output("codex_research_deferred", status="deferred"), "retry_at": retry}
                    del stages["diagnose"]
                def checked_diagnosis():
                    value = dict(diagnose(context, budget))
                    if value.get("reason") == "codex_research_deferred":
                        retry = value.get("retry_at")
                        # A reset already in the past is not a usable admission
                        # deadline. Preserve deferral without polling every run.
                        if type(retry) not in (int, float) or retry <= _clock_now().timestamp():
                            value["retry_at"] = None
                    return value

                decision = stage("diagnose", checked_diagnosis)
                if not isinstance(decision, Mapping):
                    raise ValueError("research_checkpoint_invalid")
                if decision.get("reason") == "codex_research_deferred":
                    retry = decision.get("retry_at")
                    stages["diagnose"] = {"status": "deferred", "retry_at": retry}
                    save_research_promotion_ticket(ticket, path)
                    return {**output("codex_research_deferred", status="deferred"), "retry_at": retry}
                if decision.get("optimization_needed") is not True:
                    ticket.state = ResearchPromotionState.PARKED
                    ticket.notes = ("codex_did_not_recommend_research",)
                    save_research_promotion_ticket(ticket, path)
                    return output("codex_did_not_recommend_research")

            def cached_optimize(*_):
                raw = stage("optimize", lambda: optimize(context, budget), lambda value: value.to_dict())
                return _saved_proposal(raw)

            def count_no_improvement_or_archive(proposal: OptimizationProposal) -> None:
                if (proposal.strategy_profile != strategy_profile
                        or proposal.domain != domain):
                    return
                try:
                    budget_ok, _ = enforce_optimization_budget(proposal, budget)
                except (TypeError, ValueError, KeyError):
                    return
                if not budget_ok:
                    return
                if not _proposal_no_improvement(proposal) or not _record_no_improvement(progress, proposal, now_value):
                    return
                ticket.research_progress = progress
                if progress["lifecycle"]["no_improvement_count"] >= _MAX_NO_IMPROVEMENT_ROUNDS:
                    _archive_ticket(ticket, progress, now_value, "no_improvement_limit")
                    save_research_promotion_ticket(ticket, path)
                    raise _ResearchScopeArchived
                save_research_promotion_ticket(ticket, path)

            def checked_backtest(proposal):
                value = stage("backtest", lambda: enforce_backtest_gates(proposal),
                               lambda result: _promotion_backtest_evidence_mapping(result) if result is not None else None)
                if not isinstance(value, Mapping) or value.get("status") != "PASS":
                    _pause_progress(progress, now_value, "backtest_evidence_unavailable")
                    ticket.research_progress = progress
                    save_research_promotion_ticket(ticket, path)
                else:
                    count_no_improvement_or_archive(proposal)
                return value

            def shadow_result(proposal):
                # The first callback may create an external observation. Only
                # the dedicated, caller-owned read-only callback can be polled.
                callback = read_pending_shadow if shadow_pending else record_shadow

                def encode(value):
                    value = dict(value)
                    if value.get("live_authority_granted") is True:
                        raise ValueError("shadow_live_authority_refused")
                    if value.get("status") == "pending":
                        if (value.get("passed") is not False or value.get("no_order") is not True
                                or value.get("live_authority_granted") is not False):
                            raise ValueError("invalid_shadow_pending")
                        retry = value.get("retry_at")
                        if (type(retry) not in (int, float) or not math.isfinite(retry)
                                or retry <= _clock_now().timestamp()):
                            retry = None
                        return {"status": "pending", "retry_at": retry, "evidence_kind": "paired_shadow_pending",
                                "passed": False, "no_order": True, "live_authority_granted": False}
                    if value.get("status") == "complete":
                        from quant_platform_kit.strategy_lifecycle.paired_shadow_adapter import (
                            PairedShadowObservation, collect_paired_shadow_for_promotion,
                        )
                        observation = value["observation"]
                        policy = observation.policy if isinstance(observation, PairedShadowObservation) else observation["policy"]
                        receipt = (observation.forward_observation_receipt if isinstance(observation, PairedShadowObservation)
                                   else observation["forward_observation_receipt"])
                        if (policy.strategy_profile != proposal.strategy_profile or policy.domain != proposal.domain
                                or receipt["observation_index"] < policy.required_trading_sessions):
                            raise ValueError("shadow_window_not_complete")
                        # The owner also validates the frozen candidate/params/
                        # source and full window. A bare passed flag is not proof.
                        return {**collect_paired_shadow_for_promotion(observation), "status": "complete"}
                    if shadow_pending and value.get("passed") is not False:
                        raise ValueError("shadow_completion_evidence_required")
                    return value

                return stage("shadow", lambda: callback(proposal), encode)

            result = run_research_promotion_cycle(
                context, budget=budget, ticket_id=ticket_id, optimize=cached_optimize,
                enforce_backtest_gates=checked_backtest,
                record_shadow=shadow_result,
            )
            if any(value.get("status") in {"running", "unknown"} for value in stages.values()):
                return output("research_outcome_unknown", status="parked")
            result.created_at = ticket.created_at
            result.research_progress = progress
            ticket = result
            saved_proposal_for_count = None
            if isinstance(stages.get("optimize", {}).get("result"), Mapping):
                saved_proposal_for_count = _saved_proposal(stages["optimize"]["result"])
            backtest_result = stages.get("backtest", {}).get("result")
            if (ticket.state == ResearchPromotionState.PARKED
                    and saved_proposal_for_count is not None
                    and (saved_proposal_for_count.recommendation == "reject"
                         or (isinstance(backtest_result, Mapping)
                             and backtest_result.get("status") == "PASS"))):
                count_no_improvement_or_archive(saved_proposal_for_count)
            save_research_promotion_ticket(ticket, path)
            if ticket.state == ResearchPromotionState.AWAITING_HUMAN:
                proposal = _saved_proposal(stages["optimize"]["result"])
                attach_summary(proposal)
            deliver_saved_ticket()
            if stages.get("shadow", {}).get("status") == "pending":
                return {**output("paired_shadow_observation_pending", status="deferred"),
                        "retry_at": stages["shadow"]["result"]["retry_at"]}
            return output("promotion_cycle_completed")
    except _ResearchScopeArchived:
        return {**base, "status": "parked", "reason": "research_scope_archived",
                "ticket": ticket.to_dict()}
    except Exception:
        # Persisted running stage is deliberately left as unknown. Never include
        # exceptions, input rows, credentials or a provider's response text.
        try:
            saved = load_research_promotion_ticket(path)
            if any(value.get("status") in {"running", "unknown"}
                   for value in saved.research_progress.get("stages", {}).values()):
                return {**base, "reason": "research_outcome_unknown"}
        except Exception:
            pass
        return {**base, "reason": "research_checkpoint_unavailable"}


def decide_saved_research_promotion_ticket(
    ticket_path: str | Path,
    *,
    decision: str,
    confirmation: PromotionConfirmation | Mapping[str, Any] | None = None,
    paper_supported: bool = False,
    output_path: str | Path | None = None,
) -> ResearchPromotionTicket:
    """Record explicit local human intent under the same research-directory lock."""
    with _research_directory_lock(Path(ticket_path).parent) as acquired:
        if not acquired:
            raise ValueError("research_in_progress")
        ticket = load_research_promotion_ticket(ticket_path)
        decided = apply_human_promotion_decision(
            ticket, decision=decision, confirmation=confirmation, paper_supported=paper_supported,
        )
        save_research_promotion_ticket(decided, output_path or ticket_path)
        return decided


__all__ = [
    "DEFAULT_SUGGESTED_RISK_PROFILE",
    "EXECUTION_MODES",
    "PromotionConfirmation",
    "RISK_PROFILE_IDS",
    "ResearchPromotionBudget",
    "NewResearchRequest",
    "ResearchPromotionState",
    "ResearchPromotionTicket",
    "apply_console_research_promotion_decision",
    "apply_human_promotion_decision",
    "build_human_promotion_notification",
    "decide_saved_research_promotion_ticket",
    "enforce_optimization_budget",
    "enforce_promotion_backtest_gates",
    "load_research_promotion_ticket",
    "make_console_research_promotion_pull",
    "make_console_research_promotion_sync",
    "make_telegram_research_promotion_notifier",
    "open_awaiting_human_ticket",
    "reconcile_saved_research_promotion_ticket",
    "run_research_promotion_cycle",
    "run_saved_research_promotion_cycle",
    "save_research_promotion_ticket",
    "shadow_record_from_paired_evidence",
    "validate_promotion_confirmation",
]
