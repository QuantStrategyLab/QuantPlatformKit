"""Update orchestrator — manages the full parameter update lifecycle."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quant_platform_kit.strategy_lifecycle.audit_log import record_audit_entry
from quant_platform_kit.strategy_lifecycle.config_writer import write_params_to_config
from quant_platform_kit.strategy_lifecycle.contracts import OptimizationProposal, UpdateStage
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore
from quant_platform_kit.strategy_lifecycle.shadow_validator import ShadowValidator
from quant_platform_kit.strategy_lifecycle.update_policy import UpdatePolicy


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_proposal(proposal_path: str) -> OptimizationProposal | None:
    """Load an OptimizationProposal from a JSON file or GCS URI."""
    if proposal_path.startswith("gs://"):
        # Cloud path — handled by store
        return None  # Caller should use store.load_proposal()

    path = Path(proposal_path)
    if not path.exists():
        raise FileNotFoundError(f"Proposal file not found: {proposal_path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    return _proposal_from_data(data)


def _proposal_from_data(data: Mapping[str, Any]) -> OptimizationProposal:
    return OptimizationProposal(
        strategy_profile=str(data.get("strategy_profile", "")),
        domain=str(data.get("domain", "")),
        current_params=dict(data.get("current_params", {})),
        proposed_params=dict(data.get("proposed_params", {})),
        improvement_score=float(data.get("improvement_score", 0)),
        confidence=float(data.get("confidence", 0)),
        winning_dimensions=tuple(data.get("winning_dimensions", ())),
        regressing_dimensions=tuple(data.get("regressing_dimensions", ())),
        recommendation=str(data.get("recommendation", "")),
        optimization_method=str(data.get("optimization_method", "")),
        search_iterations=int(data.get("search_iterations", 0)),
        computed_at=str(data.get("computed_at", "")),
    )


def _check_cooldown(
    strategy: str, domain: str, store: PerformanceStore, policy: UpdatePolicy,
) -> dict[str, Any] | None:
    """Check cooldown period. Returns deny response or None."""
    recent = store.load_audit_entries(strategy, limit=5)
    if not recent:
        return None
    try:
        ts = datetime.fromisoformat(recent[0].timestamp.replace("Z", "+00:00"))
        days = (datetime.now(timezone.utc) - ts).days
        if days < policy.cooldown_days:
            record_audit_entry(strategy, domain, UpdateStage.DENIED,
                reason=f"Cooldown: {days}d < {policy.cooldown_days}d")
            return {"stage": "denied", "reason": f"Cooldown active: {days}d"}
    except Exception:
        pass
    return None


def _run_shadow_validation(
    proposal: OptimizationProposal, domain: str, store: PerformanceStore, policy: UpdatePolicy,
) -> dict[str, Any] | None:
    """Run shadow validation. Returns reject response or None on pass/skip."""
    if not (proposal.recommendation == "promote" and proposal.improvement_score > 0.05):
        return None
    record_audit_entry(proposal.strategy_profile, domain, UpdateStage.SHADOW_VALIDATING)
    result = ShadowValidator(store=store).validate(proposal, domain=domain, shadow_days=policy.min_shadow_days)
    if not result["passed"]:
        record_audit_entry(proposal.strategy_profile, domain, UpdateStage.SHADOW_REJECTED,
            reason=result["reason"])
        return {"stage": "shadow_rejected", "reason": result["reason"]}
    record_audit_entry(proposal.strategy_profile, domain, UpdateStage.SHADOW_PASSED,
        reason=f"Passed after {result['days_evaluated']} days",
        shadow_days=int(result.get("days_evaluated", 0)))
    return None


def _check_approval(
    proposal: OptimizationProposal, domain: str, strategy: str,
    store: PerformanceStore, auto_approve: bool, policy: UpdatePolicy,
) -> tuple[bool, dict[str, Any] | None]:
    """Require human acceptance before a parameter patch can be created.

    ``auto_approve`` remains an accepted argument for backwards-compatible CLI
    callers, but it must never bypass the evidence/promotion boundary.  The
    automated lifecycle can monitor, freeze, and start non-live observation;
    it cannot alter a strategy's parameters on its own.
    """
    if proposal.recommendation == "promote":
        reason = (
            "Automatic approval is disabled; human approval needed"
            if auto_approve
            else "Human approval needed"
        )
        record_audit_entry(strategy, domain, UpdateStage.PENDING_APPROVAL, reason=reason)
        return False, {
            "stage": "pending_approval", "reason": reason,
            "proposal_summary": {"strategy": strategy, "improvement": proposal.improvement_score,
                "winning": list(proposal.winning_dimensions), "regressing": list(proposal.regressing_dimensions)},
        }
    record_audit_entry(strategy, domain, UpdateStage.DENIED, reason=f"Recommendation: {proposal.recommendation}")
    return False, {"stage": "denied", "reason": f"Recommendation: {proposal.recommendation}"}


def _deploy_params(
    proposal: OptimizationProposal, domain: str, strategy: str,
    current_version: int, store: PerformanceStore,
    can_auto_approve: bool,
) -> dict[str, Any]:
    """Create a config patch and require downstream deployment confirmation."""
    patch = write_params_to_config(proposal, dry_run=True)
    new_version = patch["params_overrides"]["version"]
    record_audit_entry(
        strategy, domain, UpdateStage.PATCH_CREATED,
        operator="auto_optimizer",
        param_version_from=current_version, param_version_to=new_version,
        params_before=proposal.current_params, params_after=proposal.proposed_params,
        reason=f"Config patch created for v{new_version}: improvement={proposal.improvement_score:.3f}",
        approval_source="auto" if can_auto_approve else "manual",
        improvement_score=proposal.improvement_score,
    )
    return {
        "stage": "patch_created", "strategy": strategy, "domain": domain,
        "from_version": current_version, "to_version": new_version,
        "improvement_score": proposal.improvement_score,
        "patch": patch,
        "reason": "Config patch created; deployment requires runtime confirmation before marking deployed.",
    }


def process_update(
    proposal_path: str,
    *,
    auto_approve: bool = False,
    store: PerformanceStore | None = None,
    policy: UpdatePolicy | None = None,
) -> dict[str, Any]:
    """Process a parameter update through the safe update lifecycle.

    Pipeline: load → cooldown check → shadow validation → approval → deploy.
    Each stage returns a response dict or None (continue).
    """
    store = store or PerformanceStore.from_env()
    policy = policy or UpdatePolicy.load_default()

    proposal = _load_proposal(proposal_path)
    if proposal is None:
        return {"stage": "error", "reason": f"Could not load proposal from {proposal_path}"}

    domain, strategy = proposal.domain, proposal.strategy_profile
    version = proposal.proposed_metrics.param_version if proposal.proposed_metrics else 1

    # Stage 1: cooldown
    if (r := _check_cooldown(strategy, domain, store, policy)):
        return r

    # Stage 2: shadow validation
    if (r := _run_shadow_validation(proposal, domain, store, policy)):
        return r

    # Stage 3: approval check
    approved, deny = _check_approval(proposal, domain, strategy, store, auto_approve, policy)
    if deny:
        return deny

    # Stage 4: deploy
    return _deploy_params(proposal, domain, strategy, version, store, approved)


def process_update_from_proposal(
    proposal: OptimizationProposal,
    *,
    auto_approve: bool = False,
    store: PerformanceStore | None = None,
    policy: UpdatePolicy | None = None,
) -> dict[str, Any]:
    """Process an in-memory proposal (no file path needed).

    Writes proposal to a temp file and delegates to process_update.
    Use this when the proposal is generated programmatically, not loaded from disk.
    """
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(proposal.to_dict(), f, ensure_ascii=False)
        tmp_path = f.name

    try:
        return process_update(
            proposal_path=tmp_path,
            auto_approve=auto_approve,
            store=store,
            policy=policy,
        )
    finally:
        import os as _os
        try:
            _os.unlink(tmp_path)
        except OSError:
            pass

