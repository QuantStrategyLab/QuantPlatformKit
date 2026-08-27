from __future__ import annotations

import copy

import pytest

from quant_platform_kit.strategy_lifecycle.forward_observation import (
    ForwardObservationPolicy,
)
from quant_platform_kit.strategy_lifecycle.forward_observation_receipt import (
    FORWARD_OBSERVATION_DEPENDENCY_DIGESTS,
    InvalidForwardObservationReceipt,
    build_forward_observation_receipt,
    forward_observation_policy_sha256,
    forward_observation_receipt_sha256,
    validate_forward_observation_receipt,
)


def _policy(**changes: object) -> ForwardObservationPolicy:
    values: dict[str, object] = {
        "candidate_id": "global-etf-monthly-v1",
        "strategy_profile": "global_etf_rotation",
        "domain": "us_equity",
        "benchmark_symbol": "ACWI",
        "required_trading_sessions": 63,
        "review_milestones": (15, 42),
        "automatic_non_live_modes": ("shadow", "paper"),
        "auto_resume_clean_sessions": 2,
        "observation_calendar": "XNYS",
        "observation_window_type": "fixed",
        "observation_start_session": "2026-08-26",
        "window_rationale_ref": "sha256:global-etf-monthly-v1-forward-window-rationale",
        "non_live_evidence_modes": ("shadow_decision", "simulated_replay"),
    }
    values.update(changes)
    return ForwardObservationPolicy(**values)  # type: ignore[arg-type]


def _dependencies() -> dict[str, str]:
    return {
        field: character * 64
        for field, character in zip(sorted(FORWARD_OBSERVATION_DEPENDENCY_DIGESTS), "abcdef")
    }


def _receipt(*, previous=None, index: int = 1, session: str = "2026-08-26"):
    return build_forward_observation_receipt(
        policy=_policy(),
        observation_session=session,
        observation_index=index,
        dependency_digests=_dependencies(),
        evidence_modes=("shadow_decision", "simulated_replay"),
        previous_receipt=previous,
    )


def test_receipt_binds_exact_policy_dependencies_and_sanitized_modes() -> None:
    receipt = _receipt()

    assert receipt["policy_sha256"] == forward_observation_policy_sha256(_policy())
    assert receipt["evidence_modes"] == ["shadow_decision", "simulated_replay"]
    assert set(receipt["dependency_digests"]) == FORWARD_OBSERVATION_DEPENDENCY_DIGESTS
    assert forward_observation_receipt_sha256(receipt) == receipt["receipt_sha256"]
    assert all(token not in str(receipt).lower() for token in ("account", "order", "price"))


def test_shadow_only_policy_emits_a_receipt_without_paper_evidence() -> None:
    policy = _policy(
        automatic_non_live_modes=("shadow",),
        non_live_evidence_modes=("shadow_decision",),
    )
    receipt = build_forward_observation_receipt(
        policy=policy,
        observation_session="2026-08-26",
        observation_index=1,
        dependency_digests=_dependencies(),
        evidence_modes=("shadow_decision",),
    )

    assert receipt["evidence_modes"] == ["shadow_decision"]
    assert validate_forward_observation_receipt(receipt, policy=policy) == receipt


def test_receipts_append_only_with_a_stable_candidate_policy_and_hash_chain() -> None:
    first = _receipt()
    second = _receipt(previous=first, index=2, session="2026-08-27")

    assert second["previous_receipt_sha256"] == first["receipt_sha256"]
    assert validate_forward_observation_receipt(second, policy=_policy(), previous_receipt=first) == second

    tampered = copy.deepcopy(second)
    tampered["previous_receipt_sha256"] = "0" * 64
    with pytest.raises(InvalidForwardObservationReceipt, match="receipt_sha256"):
        validate_forward_observation_receipt(tampered, policy=_policy(), previous_receipt=first)

    changed_dependencies = _dependencies()
    changed_dependencies["p2_config"] = "f" * 64
    with pytest.raises(InvalidForwardObservationReceipt, match="frozen dependency"):
        build_forward_observation_receipt(
            policy=_policy(),
            observation_session="2026-08-27",
            observation_index=2,
            dependency_digests=changed_dependencies,
            evidence_modes=("shadow_decision", "simulated_replay"),
            previous_receipt=first,
        )


@pytest.mark.parametrize(
    ("index", "session", "error"),
    [
        (0, "2026-08-26", "positive integer"),
        (1, "2026-08-25", "precedes"),
        (64, "2026-11-23", "exceeds"),
    ],
)
def test_receipt_rejects_invalid_frozen_window(index: int, session: str, error: str) -> None:
    with pytest.raises(InvalidForwardObservationReceipt, match=error):
        _receipt(index=index, session=session)


def test_receipt_rejects_ambiguous_modes_missing_digests_and_content_tampering() -> None:
    with pytest.raises(InvalidForwardObservationReceipt, match="exactly match"):
        build_forward_observation_receipt(
            policy=_policy(),
            observation_session="2026-08-26",
            observation_index=1,
            dependency_digests=_dependencies(),
            evidence_modes=("shadow_decision", "broker_paper"),
        )

    with pytest.raises(InvalidForwardObservationReceipt, match="at most one paper mode"):
        build_forward_observation_receipt(
            policy=_policy(),
            observation_session="2026-08-26",
            observation_index=1,
            dependency_digests=_dependencies(),
            evidence_modes=("shadow_decision", "broker_paper", "simulated_replay"),
        )

    missing = _dependencies()
    missing.pop("plugin_bundle")
    with pytest.raises(InvalidForwardObservationReceipt, match="closed digest set"):
        build_forward_observation_receipt(
            policy=_policy(),
            observation_session="2026-08-26",
            observation_index=1,
            dependency_digests=missing,
            evidence_modes=("shadow_decision", "simulated_replay"),
        )

    tampered = _receipt()
    tampered["dependency_digests"]["p1_manifest"] = "f" * 64
    with pytest.raises(InvalidForwardObservationReceipt, match="receipt_sha256"):
        validate_forward_observation_receipt(tampered, policy=_policy())
