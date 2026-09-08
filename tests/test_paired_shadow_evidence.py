from __future__ import annotations

import copy
from datetime import date
from hashlib import sha256
import json

import pytest

from quant_platform_kit.strategy_lifecycle.contracts import StrategyPerformanceSnapshot
from quant_platform_kit.strategy_lifecycle.forward_observation import (
    ForwardObservationPolicy,
)
from quant_platform_kit.strategy_lifecycle.forward_observation_receipt import (
    FORWARD_OBSERVATION_DEPENDENCY_DIGESTS,
    build_forward_observation_receipt,
)
from quant_platform_kit.strategy_lifecycle.paired_shadow_evidence import (
    PAIRED_SHADOW_EVIDENCE_KIND,
    PAIRED_SHADOW_EVIDENCE_SCHEMA_VERSION,
    InvalidPairedShadowEvidence,
    build_paired_shadow_evidence,
    build_paired_shadow_evidence_report_artifacts,
    canonical_paired_shadow_evidence_bytes,
    paired_shadow_evidence_sha256,
    validate_paired_shadow_evidence,
)
from quant_platform_kit.common.runtime_reports import build_runtime_report_base


def _policy(**changes: object) -> ForwardObservationPolicy:
    values: dict[str, object] = {
        "candidate_id": "soxl-v7-volatility-budget",
        "strategy_profile": "soxl_tactical",
        "domain": "us_equity",
        "benchmark_symbol": "SOXX",
        "required_trading_sessions": 63,
        "review_milestones": (15, 42),
        "automatic_non_live_modes": ("shadow", "paper"),
        "auto_resume_clean_sessions": 2,
        "observation_calendar": "XNYS",
        "observation_window_type": "fixed",
        "observation_start_session": "2026-08-26",
        "window_rationale_ref": "sha256:soxl-v7-forward-window-rationale",
        "non_live_evidence_modes": ("shadow_decision", "simulated_replay"),
    }
    values.update(changes)
    return ForwardObservationPolicy(**values)  # type: ignore[arg-type]


def _dependencies() -> dict[str, str]:
    return {
        field: character * 64
        for field, character in zip(
            sorted(FORWARD_OBSERVATION_DEPENDENCY_DIGESTS), "abcdef"
        )
    }


def _forward_receipt(*, previous=None, index: int = 1, session: str = "2026-08-26"):
    return build_forward_observation_receipt(
        policy=_policy(),
        observation_session=session,
        observation_index=index,
        dependency_digests=_dependencies(),
        evidence_modes=("shadow_decision", "simulated_replay"),
        previous_receipt=previous,
    )


def _leg(name: str) -> dict[str, object]:
    return {
        "signal": {"kind": "target_weight", "source": name},
        "hypothetical_order": {"kind": "rebalance_preview", "source": name},
        "position": {"kind": "end_of_snapshot", "source": name},
        "cost": {"kind": "configured_cost_model", "source": name},
        "return": {"kind": "one_snapshot_return", "source": name},
    }


def _evidence(**changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "policy": _policy(),
        "forward_observation_receipt": _forward_receipt(),
        "baseline_id": "soxl-v6-live-baseline",
        "observed_at": "2026-08-26T20:00:00-04:00",
        "input_snapshot_sha256": "a" * 64,
        "candidate": _leg("candidate"),
        "baseline": _leg("baseline"),
    }
    values.update(changes)
    return build_paired_shadow_evidence(**values)  # type: ignore[arg-type]


def test_evidence_binds_both_legs_to_one_timestamp_snapshot_and_p4_receipt() -> None:
    receipt = _forward_receipt()
    evidence = _evidence(forward_observation_receipt=receipt)

    assert evidence["schema_version"] == PAIRED_SHADOW_EVIDENCE_SCHEMA_VERSION
    assert evidence["evidence_kind"] == PAIRED_SHADOW_EVIDENCE_KIND
    assert evidence["candidate_id"] == _policy().candidate_id
    assert evidence["forward_observation_receipt_sha256"] == receipt["receipt_sha256"]
    assert evidence["observed_at"] == "2026-08-27T00:00:00Z"
    assert evidence["input_snapshot_sha256"] == "a" * 64
    assert set(evidence["candidate"]) == {
        "signal",
        "hypothetical_order",
        "position",
        "cost",
        "return",
    }
    assert set(evidence["baseline"]) == set(evidence["candidate"])
    assert evidence["no_order"] is True
    assert evidence["live_authority_granted"] is False
    assert paired_shadow_evidence_sha256(evidence) == evidence[
        "paired_shadow_evidence_sha256"
    ]
    assert canonical_paired_shadow_evidence_bytes(evidence)
    assert (
        validate_paired_shadow_evidence(
            evidence,
            policy=_policy(),
            forward_observation_receipt=receipt,
        )
        == evidence
    )


def test_evidence_and_forward_receipt_chains_advance_together() -> None:
    first_receipt = _forward_receipt()
    first = _evidence(forward_observation_receipt=first_receipt)
    second_receipt = _forward_receipt(
        previous=first_receipt, index=2, session="2026-08-27"
    )
    second = _evidence(
        forward_observation_receipt=second_receipt,
        observed_at="2026-08-27T20:00:00-04:00",
        previous_evidence=first,
        previous_forward_observation_receipt=first_receipt,
    )

    assert second["previous_paired_shadow_evidence_sha256"] == first[
        "paired_shadow_evidence_sha256"
    ]
    assert (
        validate_paired_shadow_evidence(
            second,
            policy=_policy(),
            forward_observation_receipt=second_receipt,
            previous_evidence=first,
            previous_forward_observation_receipt=first_receipt,
        )
        == second
    )

    with pytest.raises(InvalidPairedShadowEvidence, match="identity changed"):
        _evidence(
            forward_observation_receipt=second_receipt,
            observed_at="2026-08-27T20:00:00-04:00",
            baseline_id="another-baseline",
            previous_evidence=first,
            previous_forward_observation_receipt=first_receipt,
        )


def test_evidence_rejects_tampering_and_any_live_authority() -> None:
    evidence = _evidence()

    tampered = copy.deepcopy(evidence)
    tampered["candidate"]["cost"]["source"] = "modified"  # type: ignore[index]
    with pytest.raises(InvalidPairedShadowEvidence, match="canonical evidence"):
        validate_paired_shadow_evidence(tampered)

    live = copy.deepcopy(evidence)
    live["live_authority_granted"] = True
    with pytest.raises(InvalidPairedShadowEvidence, match="live_authority_granted"):
        validate_paired_shadow_evidence(live)

    absent_order_guard = copy.deepcopy(evidence)
    absent_order_guard["no_order"] = False
    with pytest.raises(InvalidPairedShadowEvidence, match="no_order"):
        validate_paired_shadow_evidence(absent_order_guard)


def test_production_performance_snapshot_cannot_be_relabelled_as_paired_shadow() -> None:
    snapshot = StrategyPerformanceSnapshot(
        strategy_profile="soxl_tactical",
        domain="us_equity",
        platform="production",
        as_of=date(2026, 8, 26),
        latest_return=0.01,
    )

    with pytest.raises(InvalidPairedShadowEvidence, match="closed paired-shadow"):
        validate_paired_shadow_evidence(snapshot.to_dict())


def test_continuous_validation_requires_the_matching_forward_receipt_chain() -> None:
    first_receipt = _forward_receipt()
    first = _evidence(forward_observation_receipt=first_receipt)
    second_receipt = _forward_receipt(
        previous=first_receipt, index=2, session="2026-08-27"
    )

    with pytest.raises(InvalidPairedShadowEvidence, match="previous evidence requires"):
        _evidence(
            forward_observation_receipt=second_receipt,
            observed_at="2026-08-27T20:00:00-04:00",
            previous_evidence=first,
        )


def test_report_artifacts_embed_the_validated_evidence_without_runtime_changes() -> None:
    receipt = _forward_receipt()
    evidence = _evidence(forward_observation_receipt=receipt)
    artifacts = build_paired_shadow_evidence_report_artifacts(
        evidence,
        policy=_policy(),
        forward_observation_receipt=receipt,
    )

    report = build_runtime_report_base(
        platform="platform-neutral",
        deploy_target="non-live",
        service_name="paired-shadow-observer",
        strategy_profile="soxl_tactical",
        run_id="paired-shadow-001",
        run_source="shadow",
        dry_run=True,
        artifacts=artifacts,
    )
    serialized = json.loads(json.dumps(report, ensure_ascii=False, sort_keys=True))

    assert json.loads(artifacts["paired_shadow_evidence_json"]) == evidence
    assert artifacts["paired_shadow_evidence_no_order"] is True
    assert artifacts["paired_shadow_evidence_live_authority_granted"] is False
    assert serialized["runtime_target"] == {}
    assert (
        serialized["artifacts"]["paired_shadow_evidence_json"]
        == artifacts["paired_shadow_evidence_json"]
    )
    assert (
        json.loads(serialized["artifacts"]["paired_shadow_evidence_json"])
        == evidence
    )


def _three_session_chain():
    chain = []
    for index, session in enumerate(("2026-08-26", "2026-08-27", "2026-08-28"), 1):
        previous, previous_receipt = chain[-1] if chain else (None, None)
        receipt = _forward_receipt(previous=previous_receipt, index=index, session=session)
        evidence = _evidence(
            forward_observation_receipt=receipt,
            observed_at=session + "T20:00:00-04:00",
            previous_evidence=previous,
            previous_forward_observation_receipt=previous_receipt,
        )
        chain.append((evidence, receipt))
    return chain


def test_three_sessions_validate_serialize_and_preserve_no_order_guards() -> None:
    chain = _three_session_chain()
    for index, (evidence, receipt) in enumerate(chain):
        previous, previous_receipt = chain[index - 1] if index else (None, None)
        assert validate_paired_shadow_evidence(
            evidence, policy=_policy(), forward_observation_receipt=receipt,
            previous_evidence=previous, previous_forward_observation_receipt=previous_receipt,
        ) == evidence
        assert json.loads(canonical_paired_shadow_evidence_bytes(evidence)) == evidence
        assert paired_shadow_evidence_sha256(evidence) == evidence["paired_shadow_evidence_sha256"]
        artifacts = build_paired_shadow_evidence_report_artifacts(
            evidence, policy=_policy(), forward_observation_receipt=receipt,
            previous_evidence=previous, previous_forward_observation_receipt=previous_receipt,
        )
        assert json.loads(artifacts["paired_shadow_evidence_json"]) == evidence
        assert artifacts["paired_shadow_evidence_no_order"] is True
        assert artifacts["paired_shadow_evidence_live_authority_granted"] is False
        assert evidence["observation_index"] < _policy().required_trading_sessions


@pytest.mark.parametrize("failure", ["missing", "tampered", "wrong_receipt", "wrong_candidate"])
def test_three_session_chain_rejects_missing_or_invalid_predecessor(failure) -> None:
    chain = _three_session_chain()
    current, receipt = chain[-1]
    previous, previous_receipt = copy.deepcopy(chain[-2])
    if failure == "missing":
        previous = previous_receipt = None
    elif failure == "tampered":
        previous["candidate"]["cost"]["source"] = "changed"
    elif failure == "wrong_receipt":
        previous_receipt = chain[0][1]
    else:
        previous["candidate_id"] = "another-candidate"
        previous["paired_shadow_evidence_sha256"] = sha256(json.dumps(
            {k: v for k, v in previous.items() if k != "paired_shadow_evidence_sha256"},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
        ).encode()).hexdigest()
    with pytest.raises(ValueError):
        validate_paired_shadow_evidence(
            current, policy=_policy(), forward_observation_receipt=receipt,
            previous_evidence=previous, previous_forward_observation_receipt=previous_receipt,
        )


def test_full_chain_walk_rejects_changed_ancestor() -> None:
    chain = _three_session_chain()
    changed = copy.deepcopy(chain)
    first = changed[0][0]
    first["baseline_id"] = "changed-historical-baseline"
    first["paired_shadow_evidence_sha256"] = sha256(json.dumps(
        {k: v for k, v in first.items() if k != "paired_shadow_evidence_sha256"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode()).hexdigest()
    # The full-window consumer walks from the first actual record, so a later
    # internally valid pair cannot hide a changed ancestor.
    previous = previous_receipt = None
    with pytest.raises(ValueError, match="predecessor|identity changed"):
        for evidence, receipt in changed:
            previous = validate_paired_shadow_evidence(
                evidence, policy=_policy(), forward_observation_receipt=receipt,
                previous_evidence=previous, previous_forward_observation_receipt=previous_receipt,
            )
            previous_receipt = receipt
