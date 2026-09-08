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


def _promotion_backtest_evidence() -> dict:
    fold_dates = (
        ("2019-01-01", "2019-12-31", "2020-01-02", "2020-06-30"),
        ("2020-07-02", "2021-06-30", "2021-07-02", "2021-12-31"),
        ("2022-01-02", "2022-12-31", "2023-01-02", "2023-06-30"),
    )
    return {
        "status": "PASS",
        "orchestrator": "BacktestOrchestrator",
        "protocol": "purged_walk_forward.v1",
        "locked_independent_oos": {
            "locked": True,
            "independent": True,
            "reused_for_selection": False,
        },
        "promotion_run": {
            "strategy_profile": "demo_strategy",
            "domain": "us_equity",
            "folds": [
                dict(
                    zip(
                        ("train_start", "train_end", "test_start", "test_end"),
                        boundaries,
                    )
                )
                for boundaries in fold_dates
            ],
            "locked_oos_start": "2023-07-02",
            "locked_oos_end": "2024-07-02",
            "purge_days": 1,
            "embargo_days": 1,
        },
    }


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
        enforce_backtest_gates=lambda proposal: _promotion_backtest_evidence(),
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


def test_collect_advances_three_actual_receipt_pairs() -> None:
    previous = previous_receipt = None
    for index, session in enumerate(("2026-08-26", "2026-08-27", "2026-08-28"), 1):
        receipt = _forward_receipt(previous=previous_receipt, index=index, session=session)
        record = collect_paired_shadow_for_promotion(PairedShadowObservation(
            policy=_policy(), forward_observation_receipt=receipt,
            baseline_id="soxl-v6-live-baseline", observed_at=session + "T20:00:00-04:00",
            input_snapshot_sha256="a" * 64, candidate=_leg("candidate"), baseline=_leg("baseline"),
            previous_evidence=previous, previous_forward_observation_receipt=previous_receipt,
        ))
        assert record["passed"] is True
        assert record["no_order"] is True and record["live_authority_granted"] is False
        assert record["evidence"]["observation_index"] == index
        previous, previous_receipt = record["evidence"], receipt
