from __future__ import annotations

import pytest

from quant_platform_kit.common.strategy_risk_state import (
    StrategyRiskStateChainError,
    StrategyRiskStateIdentity,
    StrategyRiskStateTransition,
    build_strategy_risk_state_transition,
    validate_strategy_risk_state_chain,
)


def _identity(*, candidate_id: str = "soxl_soxx_core_only_p2_v3") -> StrategyRiskStateIdentity:
    return StrategyRiskStateIdentity(
        strategy_profile="soxl_soxx_trend_income",
        account_scope="paper",
        candidate_id=candidate_id,
        config_sha256="a" * 64,
    )


def _transition(*, session: str = "2026-08-24", previous: StrategyRiskStateTransition | None = None):
    return build_strategy_risk_state_transition(
        identity=_identity(),
        effective_session=session,
        input_sha256="b" * 64,
        state={"cooldown_remaining_sessions": 2, "reentry_allowed": False},
        previous_transition=previous,
    )


def test_transition_is_content_addressed_and_round_trips() -> None:
    transition = _transition()
    same = _transition()

    assert transition.transition_sha256 == same.transition_sha256
    assert transition.state == {"cooldown_remaining_sessions": 2, "reentry_allowed": False}
    assert StrategyRiskStateTransition.from_dict(transition.to_dict()) == transition


def test_transition_rejects_tampered_state() -> None:
    payload = _transition().to_dict()
    payload["state"] = {"cooldown_remaining_sessions": 0, "reentry_allowed": True}

    with pytest.raises(ValueError, match="transition_sha256 mismatch"):
        StrategyRiskStateTransition.from_dict(payload)


def test_chain_requires_exact_prior_digest_and_advancing_session() -> None:
    first = _transition(session="2026-08-24")
    second = _transition(session="2026-08-25", previous=first)

    validate_strategy_risk_state_chain([first, second])

    with pytest.raises(StrategyRiskStateChainError, match="advance"):
        _transition(session="2026-08-24", previous=first)

    alternate_root = build_strategy_risk_state_transition(
        identity=_identity(),
        effective_session="2026-08-24",
        input_sha256="c" * 64,
        state={"cooldown_remaining_sessions": 3, "reentry_allowed": False},
    )
    with pytest.raises(StrategyRiskStateChainError, match="prior transition digest"):
        validate_strategy_risk_state_chain([alternate_root, second])


def test_chain_cannot_cross_candidate_or_config_scope() -> None:
    first = _transition(session="2026-08-24")
    other_identity = _identity(candidate_id="soxl_soxx_core_only_p2_v4")

    with pytest.raises(StrategyRiskStateChainError, match="identity"):
        build_strategy_risk_state_transition(
            identity=other_identity,
            effective_session="2026-08-25",
            input_sha256="b" * 64,
            state={"cooldown_remaining_sessions": 1, "reentry_allowed": False},
            previous_transition=first,
        )


def test_root_transition_cannot_claim_a_previous_digest() -> None:
    root = _transition()
    child = _transition(session="2026-08-25", previous=root)

    with pytest.raises(StrategyRiskStateChainError, match="root transition"):
        validate_strategy_risk_state_chain([child])
