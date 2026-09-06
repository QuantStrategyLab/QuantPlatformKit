"""Tests for non-live paired-shadow promotion adapter."""

from __future__ import annotations

from datetime import date

import pytest

from quant_platform_kit.strategy_lifecycle.contracts import (
    DriftResult,
    DriftStatus,
    OptimizationProposal,
)
from quant_platform_kit.strategy_lifecycle.paired_shadow_adapter import (
    PairedShadowObservation,
    collect_paired_shadow_for_promotion,
    resolve_promotion_shadow_record,
)
from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import (
    ResearchPromotionBudget,
    ResearchPromotionState,
    run_research_promotion_cycle,
)
from tests.test_paired_shadow_evidence import _evidence, _forward_receipt, _leg, _policy


def _proposal() -> OptimizationProposal:
    return OptimizationProposal(
        strategy_profile="demo_strategy",
        domain="us_equity",
        current_params={"a": 1},
        proposed_params={"a": 2},
        recommendation="promote",
        search_iterations=2,
    )


def _drift() -> DriftResult:
    return DriftResult(
        strategy_profile="demo_strategy",
        domain="us_equity",
        as_of=date(2026, 9, 7),
        drift_score=0.8,
        status=DriftStatus.REVIEW,
    )


def _observation() -> PairedShadowObservation:
    return PairedShadowObservation(
        policy=_policy(),
        forward_observation_receipt=_forward_receipt(),
        baseline_id="soxl-v6-live-baseline",
        observed_at="2026-08-26T20:00:00-04:00",
        input_snapshot_sha256="a" * 64,
        candidate=_leg("candidate"),
        baseline=_leg("baseline"),
    )


def test_collect_paired_shadow_builds_promotion_record() -> None:
    record = collect_paired_shadow_for_promotion(_observation())
    assert record["evidence_kind"] == "paired_shadow"
    assert record["passed"] is True
    assert record["live_authority_granted"] is False
    assert record["no_order"] is True
    assert record["adapter"] == "paired_shadow_adapter.v1"
    assert record["paired_shadow_evidence_sha256"]


def test_resolve_falls_back_to_proxy_when_collector_empty() -> None:
    record = resolve_promotion_shadow_record(
        proposal=_proposal(),
        drift=_drift(),
        collector=lambda **_: None,
        allow_proxy_fallback=True,
    )
    assert record["evidence_kind"] == "proxy_shadow_pending_paired"
    assert record["passed"] is True
    assert record["live_authority_granted"] is False


def test_resolve_fails_closed_without_proxy_fallback() -> None:
    record = resolve_promotion_shadow_record(
        proposal=_proposal(),
        collector=lambda **_: None,
        allow_proxy_fallback=False,
    )
    assert record["passed"] is False
    assert record["evidence_kind"] == "paired_shadow_missing"


def test_cycle_accepts_adapter_paired_record() -> None:
    def collector(*, proposal, drift):  # noqa: ARG001
        return _observation()

    ticket = run_research_promotion_cycle(
        _drift(),
        optimize=lambda drift, budget: _proposal(),
        record_shadow=lambda proposal: resolve_promotion_shadow_record(
            proposal=proposal,
            drift=_drift(),
            collector=collector,
            allow_proxy_fallback=False,
        ),
        budget=ResearchPromotionBudget(require_paired_shadow=True),
    )
    assert ticket.state is ResearchPromotionState.AWAITING_HUMAN
    assert ticket.shadow_evidence_kind == "paired_shadow"
    assert ticket.live_authority_granted is False
    assert _evidence()["live_authority_granted"] is False


def test_collect_rejects_live_authority_on_built_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    import quant_platform_kit.strategy_lifecycle.paired_shadow_adapter as adapter

    def _fake_build(**kwargs):  # noqa: ARG001
        evidence = dict(_evidence())
        evidence["live_authority_granted"] = True
        return evidence

    monkeypatch.setattr(adapter, "build_paired_shadow_evidence", _fake_build)
    with pytest.raises(ValueError, match="live_authority_granted"):
        collect_paired_shadow_for_promotion(_observation())
