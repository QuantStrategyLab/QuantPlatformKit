"""Research promotion cycle orchestration and resumable saved-ticket phases."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from quant_platform_kit.strategy_lifecycle.contracts import (
    DriftResult,
    OptimizationProposal,
    PromotionBacktestRun,
)

from .budget import (
    _promotion_backtest_evidence_mapping,
    enforce_optimization_budget,
    enforce_promotion_backtest_gates,
)
from .console_client import (
    _canonical_ticket_value,
    _reconcile_saved_research_promotion_ticket,
)
from .models import (
    NewResearchRequest,
    PromotionConfirmation,
    ResearchPromotionBudget,
    ResearchPromotionState,
    ResearchPromotionTicket,
    _ACTIVE_DRIFT,
    _REAL_DATETIME,
    _RESEARCH_CANDIDATE_RECOMMENDATIONS,
    _TERMINAL,
    _is_paired_shadow_kind,
    _new_ticket_id,
    _now_iso,
    _resolve_clock_now,
    _shadow_kind,
    apply_human_promotion_decision,
)
from .notifications import build_human_promotion_notification
from .store import _research_directory_lock, load_research_promotion_ticket


def save_research_promotion_ticket(ticket: ResearchPromotionTicket, path: str | Path) -> Path:
    """Save through the compatibility facade so module-level patches still apply."""
    from quant_platform_kit.strategy_lifecycle import research_promotion_cycle as _compat

    return _compat.save_research_promotion_ticket(ticket, path)


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
_SUMMARY_SEGMENT_MAX = 240
_SUMMARY_OLD_KEYS = frozenset({"status", "provider", "model", "text"})
_SUMMARY_NEW_KEYS = frozenset({"status", "provider", "model", "locales"})
_SUMMARY_TASK_KEYS = frozenset({"status", "provider", "model_requested", "model_verification", "locales"})
_SUMMARY_LOCALE_FIELDS = ("question", "basis", "limits", "suggestion")
_SUMMARY_PROVIDERS = frozenset({"codex", "cursor"})
_HAN_RE = re.compile(r"[\u4e00-\u9fff]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_DIGIT_RE = re.compile(r"[0-9\uff10-\uff19]")
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
    return _resolve_clock_now()


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


def _same_ticket_material(left: Any, right: Any) -> bool:
    try:
        return _canonical_ticket_value(left) == _canonical_ticket_value(right)
    except (TypeError, ValueError, OverflowError):
        return False


def _candidate_summary_binding(
    ticket: ResearchPromotionTicket,
    proposal: OptimizationProposal | None,
    context: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Freeze candidate facts before a summary callback. None means do not call."""
    identity = context.get("identity")
    if not isinstance(identity, Mapping):
        return None
    if (identity.get("strategy_profile") != ticket.strategy_profile
            or identity.get("domain") != ticket.domain
            or not _same_ticket_material(identity.get("proposed_params"), ticket.proposed_params)):
        return None
    if proposal is not None and (
            proposal.strategy_profile != ticket.strategy_profile
            or proposal.domain != ticket.domain
            or not _same_ticket_material(proposal.proposed_params, ticket.proposed_params)):
        return None
    raw = {
        "ticket_id": ticket.ticket_id,
        "strategy_profile": ticket.strategy_profile,
        "domain": ticket.domain,
        "proposed_params": dict(ticket.proposed_params),
        "comparison": context.get("comparison"),
        "shadow_evidence_kind": ticket.shadow_evidence_kind,
        "shadow_passed": ticket.shadow_passed,
        "notes": list(ticket.notes),
    }
    try:
        frozen = json.loads(_canonical_ticket_value(raw))
    except (TypeError, ValueError, OverflowError):
        return None
    return frozen if isinstance(frozen, dict) else None


def _summary_segment(text: Any, *, chinese: bool) -> str | None:
    if not isinstance(text, str) or not text.strip() or len(text) > _SUMMARY_SEGMENT_MAX:
        return None
    if _DIGIT_RE.search(text):
        return None
    has_han = _HAN_RE.search(text) is not None
    if chinese:
        return text if has_han else None
    if has_han or _LATIN_RE.search(text) is None:
        return None
    return text


def _bilingual_summary_explanation(
    value: Mapping[str, Any], binding: Mapping[str, Any],
) -> dict[str, Any] | None:
    provider = value.get("provider")
    task_result = frozenset(value) == _SUMMARY_TASK_KEYS
    model = value.get("model_requested") if task_result else value.get("model")
    locales = value.get("locales")
    if (not isinstance(provider, str) or not provider.strip()
            or not task_result and provider not in _SUMMARY_PROVIDERS
            or task_result and value.get("model_verification") not in {"unavailable", "provider_reported"}
            or not isinstance(model, str) or not model.strip()
            or not isinstance(locales, Mapping) or frozenset(locales) != {"zh-CN", "en"}):
        return None
    saved_locales: dict[str, dict[str, str]] = {}
    for name, chinese in (("zh-CN", True), ("en", False)):
        section = locales[name]
        if not isinstance(section, Mapping) or frozenset(section) != frozenset(_SUMMARY_LOCALE_FIELDS):
            return None
        saved: dict[str, str] = {}
        for field_name in _SUMMARY_LOCALE_FIELDS:
            segment = _summary_segment(section.get(field_name), chinese=chinese)
            if segment is None:
                return None
            saved[field_name] = segment
        saved_locales[name] = saved
    saved = {
        "status": "available",
        "provider": provider,
        "model": model,
        "scope": "candidate",
        "locales": saved_locales,
        "binding": json.loads(_canonical_ticket_value(binding)),
    }
    if task_result:
        saved.pop("model")
        saved.update(model_requested=model, model_verification=value["model_verification"])
    return saved


def _accepted_summary_explanation(
    value: Any, binding: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(value, Mapping) or value.get("status") != "available":
        return None
    keys = frozenset(value)
    if keys in {_SUMMARY_NEW_KEYS, _SUMMARY_TASK_KEYS}:
        if binding is None:
            return None
        return _bilingual_summary_explanation(value, binding)
    if not keys <= _SUMMARY_OLD_KEYS or "text" not in value:
        return None
    text = value.get("text")
    provider = value.get("provider") or ""
    model = value.get("model") or ""
    if (isinstance(text, str) and text.strip() and len(text) <= _SUMMARY_MAX_TEXT
            and provider == "codex" and isinstance(model, str)):
        return {"status": "available", "text": text.strip(), "provider": "codex", "model": model}
    return None


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
    binding = _candidate_summary_binding(ticket, proposal, context) if callable(summarize) else None
    if callable(summarize) and binding is not None:
        try:
            value = summarize(copy.deepcopy(context))
            accepted = _accepted_summary_explanation(value, binding)
            if accepted is not None:
                explanation = accepted
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
    read_pending_diagnosis: Callable[[str], Mapping[str, Any]] | None = None,
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
                evaluation_day = _resolve_clock_now().date()
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
                        or retry > _resolve_clock_now().timestamp()):
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
                pending_task_id = None
                if old.get("status") == "ai_pending":
                    pending_task_id = old.get("task_id")
                    if not isinstance(pending_task_id, str) or not pending_task_id:
                        return output("research_checkpoint_invalid", status="parked")
                    if not callable(read_pending_diagnosis):
                        return {**output("ai_task_pending", status="deferred"), "task_id": pending_task_id}
                    del stages["diagnose"]
                if old.get("status") == "deferred":
                    retry = old.get("retry_at")
                    if type(retry) not in (int, float) or retry > _resolve_clock_now().timestamp():
                        return {**output("codex_research_deferred", status="deferred"), "retry_at": retry}
                    del stages["diagnose"]
                def checked_diagnosis():
                    value = dict(read_pending_diagnosis(pending_task_id) if pending_task_id is not None
                                 else diagnose(context, budget))
                    if value.get("reason") == "codex_research_deferred":
                        retry = value.get("retry_at")
                        # A reset already in the past is not a usable admission
                        # deadline. Preserve deferral without polling every run.
                        if type(retry) not in (int, float) or retry <= _resolve_clock_now().timestamp():
                            value["retry_at"] = None
                    return value

                decision = stage("diagnose", checked_diagnosis)
                if not isinstance(decision, Mapping):
                    raise ValueError("research_checkpoint_invalid")
                if decision.get("reason") == "ai_task_pending":
                    task_id = decision.get("task_id")
                    if (not isinstance(task_id, str) or not task_id
                            or pending_task_id is not None and task_id != pending_task_id):
                        return output("research_checkpoint_invalid", status="parked")
                    stages["diagnose"] = {"status": "ai_pending", "task_id": task_id}
                    save_research_promotion_ticket(ticket, path)
                    return {**output("ai_task_pending", status="deferred"), "task_id": task_id}
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
                                or retry <= _resolve_clock_now().timestamp()):
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
