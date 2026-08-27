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
        "review_milestones": (20, 60),
        "automatic_non_live_modes": ("shadow", "paper"),
        "auto_resume_clean_sessions": 3,
        "observation_calendar": "XNYS",
        "observation_window_type": "fixed",
        "observation_start_session": "2026-08-26",
        "window_rationale_ref": "sha256:soxl-v7-forward-window-rationale",
        "non_live_evidence_modes": ("shadow_decision", "simulated_replay"),
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


def test_transient_operational_failure_pauses_both_non_live_modes() -> None:
    result = evaluate_forward_observation(
        _policy(),
        _snapshot(data_status="stale", paper_status="mismatch"),
    )

    assert result.state == "PAUSED"
    assert result.non_live_actions == ("pause_shadow", "pause_paper")
    assert set(result.reasons) == {
        "data_status=stale",
        "paper_status=mismatch",
    }
    assert result.live_authority_granted is False


def test_shadow_only_target_does_not_pause_for_unsupported_paper() -> None:
    policy = _policy(
        automatic_non_live_modes=("shadow",),
        non_live_evidence_modes=("shadow_decision",),
    )
    result = evaluate_forward_observation(policy, _snapshot(paper_status="unsupported"))

    assert policy.supports_paper is False
    assert result.state == "FORWARD_ACTIVE"
    assert result.non_live_actions == ("start_shadow",)
    assert all("paper_status" not in reason for reason in result.reasons)


def test_shadow_only_target_pauses_only_shadow_for_transient_data_failure() -> None:
    policy = _policy(
        automatic_non_live_modes=("shadow",),
        non_live_evidence_modes=("shadow_decision",),
    )
    result = evaluate_forward_observation(
        policy, _snapshot(data_status="stale", paper_status="unsupported")
    )

    assert result.state == "PAUSED"
    assert result.non_live_actions == ("pause_shadow",)
    assert result.reasons == ("data_status=stale",)


def test_risk_block_requires_human_review_and_never_auto_resumes() -> None:
    blocked = evaluate_forward_observation(_policy(), _snapshot(risk_status="blocked"))
    still_blocked = evaluate_forward_observation(
        _policy(), _snapshot(previous_state="risk_blocked")
    )

    assert blocked.state == "RISK_BLOCKED"
    assert blocked.non_live_actions == ("keep_shadow_stopped", "keep_paper_stopped")
    assert blocked.notifications == ("forward_observation_risk_blocked",)
    assert still_blocked.state == "RISK_BLOCKED"
    assert still_blocked.non_live_actions == ("keep_shadow_stopped", "keep_paper_stopped")


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
    assert completed.non_live_actions == ("keep_shadow_stopped", "keep_paper_stopped")
    assert completed.notifications == ("forward_window_complete_human_live_review_required",)
    assert completed.live_action == "human_approval_required"
    assert completed.live_authority_granted is False


def test_shadow_only_full_window_never_promotes_or_requires_paper() -> None:
    policy = _policy(
        automatic_non_live_modes=("shadow",),
        non_live_evidence_modes=("shadow_decision",),
    )
    completed = evaluate_forward_observation(
        policy,
        _snapshot(
            observations_completed=252,
            previous_observations_completed=251,
            paper_status="unsupported",
        ),
    )

    assert completed.state == "FORWARD_COMPLETE_HUMAN_REVIEW"
    assert completed.non_live_actions == ("keep_shadow_stopped",)
    assert completed.live_authority_granted is False


def test_each_candidate_supplies_its_own_forward_window_without_soxl_defaults() -> None:
    policy = ForwardObservationPolicy(
        candidate_id="global-etf-monthly-v1",
        strategy_profile="global_etf_rotation",
        domain="us_equity",
        benchmark_symbol="ACWI",
        required_trading_sessions=63,
        review_milestones=(15, 42),
        automatic_non_live_modes=("shadow", "paper"),
        auto_resume_clean_sessions=2,
        observation_calendar="XNYS",
        observation_window_type="fixed",
        observation_start_session="2026-08-26",
        window_rationale_ref="sha256:global-etf-monthly-v1-forward-window-rationale",
        non_live_evidence_modes=("shadow_decision", "simulated_replay"),
    )

    result = evaluate_forward_observation(
        policy,
        ForwardObservationSnapshot(
            historical_evidence_verified=True,
            historical_evidence_ref="sha256:global-etf-monthly-v1-p3",
            observations_completed=63,
            previous_observations_completed=62,
        ),
    )

    assert policy.to_dict()["required_trading_sessions"] == 63
    assert policy.to_dict()["review_milestones"] == [15, 42]
    assert result.benchmark_symbol == "ACWI"
    assert result.state == "FORWARD_COMPLETE_HUMAN_REVIEW"
    assert result.live_authority_granted is False


@pytest.mark.parametrize(
    ("control_status", "expected_state"),
    [
        ("manual_hold", "MANUAL_HOLD"),
        ("identity_mismatch", "IDENTITY_MISMATCH"),
        ("revoked", "REVOKED"),
        ("superseded", "SUPERSEDED"),
    ],
)
def test_non_transient_control_states_never_auto_resume(
    control_status: str, expected_state: str
) -> None:
    held = evaluate_forward_observation(_policy(), _snapshot(control_status=control_status))
    persisted = evaluate_forward_observation(
        _policy(), _snapshot(previous_state=control_status)
    )

    assert held.state == expected_state
    assert held.non_live_actions == ("keep_shadow_stopped", "keep_paper_stopped")
    assert persisted.state == expected_state
    assert persisted.non_live_actions == ("keep_shadow_stopped", "keep_paper_stopped")


def test_policy_and_snapshot_reject_ambiguous_configuration() -> None:
    with pytest.raises(ForwardObservationPolicyError, match="automatic_non_live_modes"):
        _policy(automatic_non_live_modes=("paper",))
    with pytest.raises(ForwardObservationPolicyError, match="review_milestones"):
        _policy(review_milestones=(60, 20))
    with pytest.raises(ForwardObservationPolicyError, match="paper mode"):
        _policy(non_live_evidence_modes=("shadow_decision", "broker_paper", "simulated_replay"))
    with pytest.raises(ForwardObservationPolicyError, match="paper mode"):
        _policy(
            automatic_non_live_modes=("shadow",),
            non_live_evidence_modes=("shadow_decision", "broker_paper"),
        )
    with pytest.raises(ForwardObservationPolicyError, match="rolling"):
        _policy(observation_window_type="rolling", observation_start_session="2026-08-26")
    with pytest.raises(ForwardObservationPolicyError, match="cannot exceed"):
        _snapshot(observations_completed=20, previous_observations_completed=21)
