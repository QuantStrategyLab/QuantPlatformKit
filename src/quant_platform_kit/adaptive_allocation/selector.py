"""Deterministic, read-only candidate ranking for adaptive-allocation Shadow runs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from quant_platform_kit.adaptive_allocation.contracts import (
    SHADOW_ONLY_AUTHORITY,
    AdaptiveSelectionPolicy,
    CandidateDecision,
    MarketContextSnapshot,
    PlatformHealthSnapshot,
    PluginRiskAdjustment,
    SelectionDecision,
    StrategyCandidate,
    _SHADOW_ELIGIBLE_STAGES,
)


def _global_rejections(
    context: MarketContextSnapshot, policy: AdaptiveSelectionPolicy
) -> tuple[str, ...]:
    reasons: list[str] = []
    if context.data_freshness_days > policy.max_data_freshness_days:
        reasons.append("market_data_stale")
    if context.regime_confidence < policy.minimum_regime_confidence:
        reasons.append("regime_confidence_below_policy")
    if policy.fail_closed_on_unknown_regime and context.regime.lower() == "unknown":
        reasons.append("market_regime_unknown")
    return tuple(reasons)


def _healthy_platforms(
    candidate: StrategyCandidate,
    platform_health: dict[str, PlatformHealthSnapshot],
) -> list[PlatformHealthSnapshot]:
    return sorted(
        (
            health
            for platform_id in candidate.allowed_platform_ids
            if (health := platform_health.get(platform_id)) is not None
            and health.healthy
            and health.shadow_capable
            and health.reconciliation_ok
        ),
        key=lambda item: (-item.capacity_score, item.expected_cost_bps, item.platform_id),
    )


def select_shadow(
    *,
    decision_id: str,
    market_context: MarketContextSnapshot,
    candidates: Iterable[StrategyCandidate],
    platform_health: Iterable[PlatformHealthSnapshot],
    plugin_adjustments: Iterable[PluginRiskAdjustment],
    policy: AdaptiveSelectionPolicy,
    created_at: datetime | None = None,
) -> SelectionDecision:
    """Rank immutable candidates without allocating capital or changing a runtime.

    `base_score` and `factor_exposures` must come from a separately validated,
    versioned research pipeline.  This function intentionally has no market-data
    fetcher and does not infer financial features from narratives.
    """

    health_by_platform = {item.platform_id: item for item in platform_health}
    plugin_by_id = {item.plugin_id: item for item in plugin_adjustments}
    global_rejections = _global_rejections(market_context, policy)
    decisions: list[CandidateDecision] = []

    for candidate in sorted(candidates, key=lambda item: item.strategy_profile):
        reasons: list[str] = []
        risk_multiplier = 1.0
        reasons.extend(global_rejections)
        if not candidate.approved_for_shadow:
            reasons.append("candidate_not_approved_for_shadow")
        if candidate.lifecycle_stage not in _SHADOW_ELIGIBLE_STAGES:
            reasons.append("lifecycle_stage_not_shadow_eligible")

        for plugin_id in candidate.required_plugins:
            adjustment = plugin_by_id.get(plugin_id)
            if adjustment is None or not adjustment.approved:
                reasons.append(f"required_plugin_unavailable:{plugin_id}")
            else:
                risk_multiplier *= adjustment.risk_multiplier

        eligible_platforms = _healthy_platforms(candidate, health_by_platform)
        if not eligible_platforms:
            reasons.append("no_healthy_reconciled_shadow_platform")

        platform = eligible_platforms[0] if eligible_platforms else None
        raw_score = candidate.base_score + sum(
            candidate.factor_exposures.get(name, 0.0) * value
            for name, value in market_context.factors.items()
        )
        if platform is not None:
            raw_score -= policy.volatility_penalty * candidate.estimated_volatility
            raw_score -= policy.cost_penalty * platform.expected_cost_bps
        score = raw_score * risk_multiplier
        if score < policy.minimum_score:
            reasons.append("score_below_policy")

        decisions.append(
            CandidateDecision(
                strategy_profile=candidate.strategy_profile,
                release_digest=candidate.release_digest,
                selected_platform_id=platform.platform_id if platform else None,
                score=score,
                risk_multiplier=risk_multiplier,
                accepted=not reasons,
                reasons=tuple(reasons or ("shadow_candidate_ranked",)),
            )
        )

    accepted = sorted(
        (item for item in decisions if item.accepted),
        key=lambda item: (-(item.score or float("-inf")), item.strategy_profile, item.selected_platform_id or ""),
    )[: policy.max_recommendations]
    recommended = accepted[0] if accepted else None
    return SelectionDecision(
        decision_id=decision_id,
        created_at=created_at or datetime.now(timezone.utc),
        market_context=market_context,
        policy_id=policy.policy_id,
        candidate_decisions=tuple(decisions),
        recommended_strategy_profile=recommended.strategy_profile if recommended else None,
        recommended_platform_id=recommended.selected_platform_id if recommended else None,
        authority=SHADOW_ONLY_AUTHORITY,
        no_order=True,
    )
