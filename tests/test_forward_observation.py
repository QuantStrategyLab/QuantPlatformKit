from __future__ import annotations

import pytest

from quant_platform_kit.strategy_lifecycle.forward_observation import (
    ForwardObservationPolicy,
    ForwardObservationPolicyError,
    ForwardObservationSnapshot,
    evaluate_forward_observation,
)


def _policy(**changes: object) -> ForwardObservationPolicy:
    values: dict[str, object] = {
        "candidate_id": "soxl-soxx-v7",
        "strategy_profile": "soxl_soxx_trend_income",
        "domain": "us_equity",
        "benchmark_symbol": "SOXX",
        "required_trading_sessions": 252,
    }
    values.update(changes)
    return ForwardObservationPolicy(**values)  # type: ignore[arg-type]


def _snapshot(**changes: object) -> ForwardObservationSnapshot:
    values: dict[str, object] = {
        "historical_evidence_verified": True,
        "historical_evidence_ref": "gs://research/soxl-v7/p3-evidence.json",
    }
    values.update(changes)
    return ForwardObservationSnapshot(**values)  # type: ignore[arg-type]


def test_verified_p3_starts_shadow_and_paper_without_live_authority() -> None:
    result = evaluate_forward_observation(_policy(), _snapshot())

    assert result.state == "FORWARD_ACTIVE"
    assert result.non_live_actions == ("start_shadow", "start_paper")
    assert result.live_action == "human_approval_required"
    assert result.no_order is True
    assert result.live_authority_granted is False
    assert "live" not in " ".join(result.non_live_actions)


def test_missing_p3_evidence_parks_without_starting_non_live_modes() -> None:
    result = evaluate_forward_observation(
        _policy(), _snapshot(historical_evidence_verified=False, historical_evidence_ref="")
    )

    assert result.state == "PARKED"
    assert result.non_live_actions == ("keep_shadow_stopped", "keep_paper_stopped")
    assert result.notifications == ("historical_evidence_required",)


def test_any_operational_or_risk_failure_pauses_both_non_live_modes() -> None:
    result = evaluate_forward_observation(
        _policy(),
        _snapshot(data_status="stale", paper_status="mismatch", risk_status="blocked"),
    )

    assert result.state == "PAUSED"
    assert result.non_live_actions == ("pause_shadow", "pause_paper")
    assert set(result.reasons) == {
        "data_status=stale",
        "paper_status=mismatch",
        "risk_status=blocked",
    }
    assert result.live_authority_granted is False


def test_non_live_pause_resumes_automatically_only_after_clean_recovery_window() -> None:
    waiting = evaluate_forward_observation(
        _policy(auto_resume_clean_sessions=3),
        _snapshot(previous_state="paused", clean_sessions_since_pause=2),
    )
    resumed = evaluate_forward_observation(
        _policy(auto_resume_clean_sessions=3),
        _snapshot(previous_state="paused", clean_sessions_since_pause=3),
    )

    assert waiting.state == "PAUSED"
    assert waiting.non_live_actions == ("keep_shadow_paused", "keep_paper_paused")
    assert resumed.state == "FORWARD_ACTIVE"
    assert resumed.non_live_actions == ("resume_shadow", "resume_paper")


def test_milestones_and_full_window_never_promote_live() -> None:
    policy = _policy()
    milestone = evaluate_forward_observation(
        policy,
        _snapshot(observations_completed=20, previous_observations_completed=19),
    )
    completed = evaluate_forward_observation(
        policy,
        _snapshot(observations_completed=252, previous_observations_completed=251),
    )

    assert milestone.notifications == ("forward_review_20_sessions",)
    assert completed.state == "FORWARD_COMPLETE_HUMAN_REVIEW"
    assert completed.notifications == ("forward_window_complete_human_live_review_required",)
    assert completed.live_action == "human_approval_required"
    assert completed.live_authority_granted is False


def test_policy_and_snapshot_reject_ambiguous_configuration() -> None:
    with pytest.raises(ForwardObservationPolicyError, match="automatic_non_live_modes"):
        _policy(automatic_non_live_modes=("shadow",))
    with pytest.raises(ForwardObservationPolicyError, match="review_milestones"):
        _policy(review_milestones=(60, 20))
    with pytest.raises(ForwardObservationPolicyError, match="cannot exceed"):
        _snapshot(observations_completed=20, previous_observations_completed=21)
