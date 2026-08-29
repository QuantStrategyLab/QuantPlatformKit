from datetime import date, datetime, timezone

import pytest

from quant_platform_kit.adaptive_allocation import (
    AdaptiveSelectionPolicy,
    MarketContextSnapshot,
    PlatformHealthSnapshot,
    PluginRiskAdjustment,
    StrategyCandidate,
    select_shadow,
)


def _context(**overrides):
    values = {
        "as_of": date(2026, 8, 28),
        "domain": "us_equity",
        "data_version": "market-context-test-v1",
        "data_freshness_days": 0,
        "regime": "normal",
        "regime_confidence": 0.9,
        "factors": {"momentum": 0.8},
    }
    return MarketContextSnapshot(**(values | overrides))


def _policy(**overrides):
    values = {
        "policy_id": "shadow-policy-v1",
        "max_data_freshness_days": 1,
        "minimum_regime_confidence": 0.6,
        "minimum_score": 0.1,
        "volatility_penalty": 0.5,
        "cost_penalty": 0.01,
        "max_platform_health_age_seconds": 3600,
    }
    return AdaptiveSelectionPolicy(**(values | overrides))


def _health(**overrides):
    values = {
        "platform_id": "paper_platform",
        "observed_at": datetime(2026, 8, 28, tzinfo=timezone.utc),
        "healthy": True,
        "shadow_capable": True,
        "reconciliation_ok": True,
        "capacity_score": 0.8,
        "expected_cost_bps": 1.0,
    }
    return PlatformHealthSnapshot(**(values | overrides))


def _candidate(profile, score, **overrides):
    values = {
        "strategy_profile": profile,
        "release_digest": f"sha256:{profile}",
        "lifecycle_stage": "shadow_active",
        "approved_for_shadow": True,
        "base_score": score,
        "estimated_volatility": 0.2,
        "factor_exposures": {"momentum": 1.0},
        "required_plugins": ("market_regime_control",),
        "allowed_platform_ids": ("paper_platform",),
    }
    return StrategyCandidate(**(values | overrides))


def test_shadow_selector_ranks_admitted_candidates_and_keeps_zero_weight():
    decision = select_shadow(
        decision_id="decision-001",
        market_context=_context(),
        candidates=[_candidate("strategy_a", 0.3), _candidate("strategy_b", 0.5)],
        platform_health=[_health()],
        plugin_adjustments=[PluginRiskAdjustment("market_regime_control", 0.8)],
        policy=_policy(),
        created_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
    )

    assert decision.recommended_strategy_profile == "strategy_b"
    assert decision.recommended_platform_id == "paper_platform"
    assert all(item.proposed_weight == 0.0 for item in decision.candidate_decisions)
    payload = decision.to_dict()
    assert payload["authority"] == "shadow_only"
    assert payload["no_order"] is True
    assert len(str(payload["input_digest"])) == 64
    assert len(str(payload["decision_digest"])) == 64


def test_shadow_selector_fails_closed_for_unknown_or_stale_market_context():
    decision = select_shadow(
        decision_id="decision-002",
        market_context=_context(regime="unknown", data_freshness_days=2),
        candidates=[_candidate("strategy_a", 0.7)],
        platform_health=[_health()],
        plugin_adjustments=[PluginRiskAdjustment("market_regime_control", 1.0)],
        policy=_policy(),
        created_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
    )

    assert decision.recommended_strategy_profile is None
    assert "market_data_stale" in decision.candidate_decisions[0].reasons
    assert "market_regime_unknown" in decision.candidate_decisions[0].reasons


def test_shadow_selector_rejects_unhealthy_platform_or_missing_required_plugin():
    decision = select_shadow(
        decision_id="decision-003",
        market_context=_context(),
        candidates=[_candidate("strategy_a", 0.7)],
        platform_health=[_health(healthy=False)],
        plugin_adjustments=[],
        policy=_policy(),
        created_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
    )

    item = decision.candidate_decisions[0]
    assert item.accepted is False
    assert "required_plugin_unavailable:market_regime_control" in item.reasons
    assert "no_healthy_reconciled_shadow_platform" in item.reasons


def test_shadow_selector_can_rank_an_approved_shadow_candidate_without_starting_it():
    decision = select_shadow(
        decision_id="decision-004",
        market_context=_context(),
        candidates=[_candidate("candidate_a", 0.7, lifecycle_stage="shadow_candidate")],
        platform_health=[_health()],
        plugin_adjustments=[PluginRiskAdjustment("market_regime_control", 1.0)],
        policy=_policy(),
        created_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
    )

    assert decision.recommended_strategy_profile == "candidate_a"
    assert decision.no_order is True
    assert decision.candidate_decisions[0].proposed_weight == 0.0


def test_plugin_risk_adjustment_cannot_increase_risk():
    with pytest.raises(ValueError, match="risk_multiplier"):
        PluginRiskAdjustment("market_regime_control", 1.01)


def test_shadow_selector_rejects_stale_or_future_platform_health():
    created_at = datetime(2026, 8, 28, 2, tzinfo=timezone.utc)
    stale = select_shadow(
        decision_id="decision-stale",
        market_context=_context(),
        candidates=[_candidate("strategy_a", 0.7)],
        platform_health=[_health(observed_at=datetime(2026, 8, 28, tzinfo=timezone.utc))],
        plugin_adjustments=[PluginRiskAdjustment("market_regime_control", 1.0)],
        policy=_policy(max_platform_health_age_seconds=3599),
        created_at=created_at,
    )
    future = select_shadow(
        decision_id="decision-future",
        market_context=_context(),
        candidates=[_candidate("strategy_a", 0.7)],
        platform_health=[_health(observed_at=datetime(2026, 8, 28, 3, tzinfo=timezone.utc))],
        plugin_adjustments=[PluginRiskAdjustment("market_regime_control", 1.0)],
        policy=_policy(),
        created_at=created_at,
    )

    assert "platform_health_stale" in stale.candidate_decisions[0].reasons
    assert "platform_health_from_future" in future.candidate_decisions[0].reasons


def test_selection_digests_are_deterministic_and_bind_the_full_input():
    common = {
        "decision_id": "decision-digest",
        "market_context": _context(),
        "candidates": [_candidate("strategy_a", 0.7)],
        "platform_health": [_health()],
        "plugin_adjustments": [PluginRiskAdjustment("market_regime_control", 1.0)],
        "policy": _policy(),
        "created_at": datetime(2026, 8, 28, tzinfo=timezone.utc),
    }
    first = select_shadow(**common).to_dict()
    second = select_shadow(**common).to_dict()
    changed = select_shadow(**(common | {"market_context": _context(factors={"momentum": 0.7})})).to_dict()

    assert first == second
    assert first["input_digest"] != changed["input_digest"]
    assert first["decision_digest"] != changed["decision_digest"]
