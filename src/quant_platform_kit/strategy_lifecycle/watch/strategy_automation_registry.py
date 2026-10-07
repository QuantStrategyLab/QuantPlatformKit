"""Strategy automation registry guardrails from QuantRuntimeSettings."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

ACTION_AUTO_MERGE, ACTION_AUTO_NOTIFY, ACTION_AUTO_PR, ACTION_ESCALATE = "auto_merge", "auto_notify", "auto_pr", "escalate"
ACTION_RANK = {action: index for index, action in enumerate((ACTION_ESCALATE, ACTION_AUTO_NOTIFY, ACTION_AUTO_PR, ACTION_AUTO_MERGE))}

STRATEGY_AUTOMATION_REGISTRY_SCHEMA_VERSION = "strategy_automation_registry.v1"
LANE_LIVE_EQUIVALENT = "live_equivalent_optimization"
LANE_PROMOTION_REVIEW = "promotion_review"
LANE_SHADOW_RESEARCH = "shadow_research"
LANE_RESEARCH_BACKLOG = "research_backlog"
SAFE_SUMMARY_SCALAR_KEYS = (
    "strategy_profile_count",
    "profile_count",
    "generated_at",
)
SAFE_SUMMARY_COUNTER_KEYS = (
    "automation_lane_counts",
    "domain_counts",
    "lifecycle_stage_counts",
)


def _registry_from_payload(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") == STRATEGY_AUTOMATION_REGISTRY_SCHEMA_VERSION:
        return payload
    registry = payload.get("automation_registry")
    if isinstance(registry, dict) and registry.get("schema_version") == STRATEGY_AUTOMATION_REGISTRY_SCHEMA_VERSION:
        return registry
    return None


def _registry_input_supplied(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    return "schema_version" in payload or "automation_registry" in payload


def _safe_summary_scalar(value: Any) -> str | int | float | bool | None:
    if isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return value[:200]
    return None


def _safe_registry_summary(registry: dict[str, Any]) -> dict[str, Any]:
    summary = registry.get("summary")
    if not isinstance(summary, dict):
        return {}
    safe: dict[str, Any] = {}
    for key in SAFE_SUMMARY_SCALAR_KEYS:
        value = _safe_summary_scalar(summary.get(key))
        if value is not None:
            safe[key] = value
    for key in SAFE_SUMMARY_COUNTER_KEYS:
        raw_counter = summary.get(key)
        if not isinstance(raw_counter, dict):
            continue
        counter: dict[str, str | int | float | bool] = {}
        for raw_name, raw_value in list(raw_counter.items())[:20]:
            value = _safe_summary_scalar(raw_value)
            if value is not None:
                counter[str(raw_name)[:80]] = value
        if counter:
            safe[key] = counter
    return safe


def _max_autonomy_action(max_autonomy: str, *, profile_binding_trusted: bool) -> str:
    value = str(max_autonomy or "").strip()
    if value == "human_review_required":
        return ACTION_ESCALATE
    if value == "auto_pr_research_only":
        return ACTION_AUTO_PR
    if value == "auto_pr_or_trusted_live_equivalent":
        return ACTION_AUTO_MERGE if profile_binding_trusted else ACTION_AUTO_PR
    return ACTION_ESCALATE


def _cap_direct_apply_action(guarded: dict[str, Any], reasons: list[str], reason: str) -> None:
    action = str(guarded.get("final_action") or "")
    if action == ACTION_AUTO_MERGE:
        guarded["final_action"] = ACTION_AUTO_PR
    elif action == ACTION_AUTO_NOTIFY:
        guarded["final_action"] = ACTION_ESCALATE
    else:
        return
    guarded["human_review_required"] = True
    reasons.append(reason)


def summarize_strategy_registry_context(payload: Any, profile: str | None = None) -> dict[str, Any]:
    """Return a small, safe-to-log registry context for a strategy profile."""
    profile_name = str(profile or "").strip()
    if not profile_name:
        if _registry_input_supplied(payload):
            return {
                "valid": False,
                "profile_required": True,
                "reason": "strategy_profile is missing for supplied strategy registry",
            }
        return {"valid": False, "reason": "strategy_profile is missing; strategy registry guard skipped"}
    registry = _registry_from_payload(payload)
    if registry is None:
        return {
            "valid": False,
            "profile": profile_name,
            "reason": "strategy automation registry is missing or unsupported",
        }
    profiles = registry.get("profiles")
    if not isinstance(profiles, list):
        return {
            "valid": False,
            "profile": profile_name,
            "reason": "strategy automation registry profiles are invalid",
        }
    profile_entry = None
    profile_entry = next(
        (item for item in profiles if isinstance(item, dict) and str(item.get("profile") or "") == profile_name),
        None,
    )
    if profile_entry is None:
        return {
            "valid": True,
            "schema_version": STRATEGY_AUTOMATION_REGISTRY_SCHEMA_VERSION,
            "profile": profile_name,
            "matched": False,
            "summary": _safe_registry_summary(registry),
        }
    context: dict[str, Any] = {
        "valid": True,
        "schema_version": STRATEGY_AUTOMATION_REGISTRY_SCHEMA_VERSION,
        "matched": profile_entry is not None,
        "summary": _safe_registry_summary(registry),
    }
    if isinstance(profile_entry, dict):
        context.update(
            {
                "profile": str(profile_entry.get("profile") or profile_name),
                "domain": str(profile_entry.get("domain") or ""),
                "lifecycle_stage": str(profile_entry.get("lifecycle_stage") or ""),
                "automation_lane": str(profile_entry.get("automation_lane") or ""),
                "max_autonomy": str(profile_entry.get("max_autonomy") or ""),
                "approval_required": profile_entry.get("approval_required") is True,
                "can_switch_live": profile_entry.get("can_switch_live") is True,
                "position_control_sensitive": profile_entry.get("position_control_sensitive") is True,
            }
        )
    return context


def apply_strategy_registry_guard(
    authority: dict[str, Any],
    context: dict[str, Any],
    *,
    profile_binding_trusted: bool = False,
) -> dict[str, Any]:
    """Cap authority based on strategy registry lane and sensitive controls."""
    guarded = deepcopy(authority)
    if not context.get("valid"):
        if context.get("profile") or context.get("profile_required"):
            guarded["final_action"] = ACTION_ESCALATE
            guarded["human_review_required"] = True
            reasons = list(guarded.get("reasons") if isinstance(guarded.get("reasons"), list) else [])
            reasons.append(str(context.get("reason") or "strategy registry is unavailable; human review required"))
            guarded["reasons"] = reasons
        guarded["strategy_registry_context"] = context
        return guarded
    reasons = list(guarded.get("reasons") if isinstance(guarded.get("reasons"), list) else [])
    if not context.get("matched"):
        guarded["final_action"] = ACTION_ESCALATE
        guarded["human_review_required"] = True
        reasons.append("strategy registry profile is missing or unmatched; human review required")
        guarded["reasons"] = reasons
        guarded["strategy_registry_context"] = context
        return guarded
    lane = str(context.get("automation_lane") or "")
    hard_stop_reason = ""
    if lane != LANE_LIVE_EQUIVALENT or context.get("approval_required") is True:
        guarded["final_action"] = ACTION_ESCALATE
        guarded["human_review_required"] = True
        hard_stop_reason = f"strategy registry lane {lane or 'unknown'} requires human review before live impact"
    elif context.get("can_switch_live") is not True:
        guarded["final_action"] = ACTION_ESCALATE
        guarded["human_review_required"] = True
        hard_stop_reason = "strategy registry blocks live switching; human review required"
    if hard_stop_reason:
        reasons.append(hard_stop_reason)
        guarded["reasons"] = reasons
        guarded["strategy_registry_context"] = context
        return guarded
    if not profile_binding_trusted:
        _cap_direct_apply_action(
            guarded,
            reasons,
            "untrusted strategy registry profile binding is capped to PR-only or review",
        )
    max_action = _max_autonomy_action(str(context.get("max_autonomy") or ""), profile_binding_trusted=profile_binding_trusted)
    if max_action == ACTION_AUTO_PR and str(guarded.get("final_action")) in {ACTION_AUTO_NOTIFY, ACTION_AUTO_MERGE}:
        _cap_direct_apply_action(
            guarded,
            reasons,
            f"strategy registry max_autonomy caps live-impact action at {max_action}",
        )
    elif ACTION_RANK.get(str(guarded.get("final_action")), 0) > ACTION_RANK[max_action]:
        guarded["final_action"] = max_action
        guarded["human_review_required"] = max_action != ACTION_AUTO_MERGE
        reasons.append(f"strategy registry max_autonomy caps action at {max_action}")
    if context.get("position_control_sensitive") is True and str(guarded.get("final_action")) in {ACTION_AUTO_NOTIFY, ACTION_AUTO_MERGE}:
        if guarded.get("trusted_position_control_proof") is not True:
            _cap_direct_apply_action(
                guarded,
                reasons,
                "position-control-sensitive strategy requires trusted proof before live-impact action",
            )
    guarded["reasons"] = reasons
    guarded["strategy_registry_context"] = context
    return guarded
