"""Tests for research promotion HITL cycle."""

from __future__ import annotations

from datetime import date

import pytest

from quant_platform_kit.strategy_lifecycle.contracts import (
    DriftResult,
    DriftStatus,
    OptimizationProposal,
)
from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import (
    ResearchPromotionBudget,
    ResearchPromotionState,
    PromotionConfirmation,
    apply_human_promotion_decision,
    validate_promotion_confirmation,
    load_research_promotion_ticket,
    run_research_promotion_cycle,
    save_research_promotion_ticket,
)


def _drift(status: DriftStatus = DriftStatus.REVIEW) -> DriftResult:
    return DriftResult(
        strategy_profile="demo_strategy",
        domain="us_equity",
        as_of=date(2026, 9, 7),
        drift_score=0.8,
        status=status,
    )


def _proposal(
    *,
    recommendation: str = "promote",
    search_iterations: int = 3,
    params: dict | None = None,
) -> OptimizationProposal:
    return OptimizationProposal(
        strategy_profile="demo_strategy",
        domain="us_equity",
        current_params={"a": 1},
        proposed_params=params or {"a": 2, "b": 3},
        recommendation=recommendation,
        search_iterations=search_iterations,
    )


def test_budget_rejects_live_enablement_flag() -> None:
    with pytest.raises(ValueError, match="allow_live_enablement"):
        ResearchPromotionBudget(allow_live_enablement=True)


def test_cycle_parks_non_actionable_drift() -> None:
    ticket = run_research_promotion_cycle(
        _drift(DriftStatus.WATCH),
        optimize=lambda *_: (_ for _ in ()).throw(AssertionError("should not optimize")),
        record_shadow=lambda *_: (_ for _ in ()).throw(AssertionError("no shadow")),
    )
    assert ticket.state is ResearchPromotionState.PARKED
    assert ticket.live_authority_granted is False


def test_cycle_stops_at_awaiting_human_and_notifies() -> None:
    notes: list[tuple[str, str]] = []

    ticket = run_research_promotion_cycle(
        _drift(),
        optimize=lambda drift, budget: _proposal(),
        record_shadow=lambda proposal: {
            "evidence_kind": "proxy_shadow",
            "passed": True,
        },
        notify=lambda subject, body: notes.append((subject, body)),
        budget=ResearchPromotionBudget(max_search_iterations=10, max_param_keys=4),
        ticket_id="rpt_test001",
    )

    assert ticket.state is ResearchPromotionState.AWAITING_HUMAN
    assert ticket.live_authority_granted is False
    assert ticket.shadow_passed is True
    assert ticket.notification_subject.startswith("[AWAITING_HUMAN]")
    assert notes and "live_authority_granted: false" in notes[0][1]


def test_cycle_parks_when_budget_exceeded() -> None:
    ticket = run_research_promotion_cycle(
        _drift(),
        optimize=lambda drift, budget: _proposal(search_iterations=99),
        record_shadow=lambda proposal: {"passed": True},
        budget=ResearchPromotionBudget(max_search_iterations=5, max_param_keys=4),
    )
    assert ticket.state is ResearchPromotionState.PARKED
    assert ticket.notes[0] == "budget_exceeded"


def test_human_accept_does_not_grant_live_authority(tmp_path) -> None:
    ticket = run_research_promotion_cycle(
        _drift(),
        optimize=lambda drift, budget: _proposal(),
        record_shadow=lambda proposal: {"evidence_kind": "proxy_shadow", "passed": True},
    )
    decided = apply_human_promotion_decision(
        ticket,
        decision="accept",
        confirmation=PromotionConfirmation(
            target_platform="ibkr",
            execution_mode="live",
            risk_profile="CAPITAL_PRESERVATION",
        ),
    )
    assert decided.state is ResearchPromotionState.HUMAN_ACCEPTED
    assert decided.live_authority_granted is False
    assert "human_accepted_intent_only_no_live_authority" in decided.notes

    path = save_research_promotion_ticket(decided, tmp_path / "ticket.json")
    loaded = load_research_promotion_ticket(path)
    assert loaded.state is ResearchPromotionState.HUMAN_ACCEPTED
    assert loaded.live_authority_granted is False


def test_human_reject_is_terminal() -> None:
    ticket = run_research_promotion_cycle(
        _drift(),
        optimize=lambda drift, budget: _proposal(),
        record_shadow=lambda proposal: {"passed": True},
    )
    decided = apply_human_promotion_decision(ticket, decision="reject")
    assert decided.state is ResearchPromotionState.HUMAN_REJECTED
    with pytest.raises(ValueError, match="not awaiting human"):
        apply_human_promotion_decision(decided, decision="accept")


def test_require_paired_shadow_parks_proxy() -> None:
    ticket = run_research_promotion_cycle(
        _drift(),
        optimize=lambda drift, budget: _proposal(),
        record_shadow=lambda proposal: {"evidence_kind": "proxy_shadow", "passed": True},
        budget=ResearchPromotionBudget(require_paired_shadow=True),
    )
    assert ticket.state is ResearchPromotionState.PARKED
    assert "paired_shadow_required" in ticket.notes
    assert ticket.live_authority_granted is False


def test_paired_shadow_record_reaches_awaiting_human() -> None:
    from tests.test_paired_shadow_evidence import _evidence
    from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import (
        shadow_record_from_paired_evidence,
    )

    shadow = shadow_record_from_paired_evidence(_evidence())
    notes: list[tuple[str, str]] = []
    ticket = run_research_promotion_cycle(
        _drift(),
        optimize=lambda drift, budget: _proposal(),
        record_shadow=lambda proposal: shadow,
        notify=lambda subject, body: notes.append((subject, body)),
        budget=ResearchPromotionBudget(require_paired_shadow=True),
    )
    assert ticket.state is ResearchPromotionState.AWAITING_HUMAN
    assert ticket.shadow_evidence_kind == "paired_shadow"
    assert ticket.live_authority_granted is False
    assert notes and "live_authority_granted: false" in notes[0][1]


def test_telegram_notifier_soft_skips_without_credentials() -> None:
    from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import (
        make_telegram_research_promotion_notifier,
    )

    skipped: list[str] = []
    notify = make_telegram_research_promotion_notifier(
        bot_token="",
        chat_ids="",
        printer=lambda *args, **kwargs: skipped.append(" ".join(str(a) for a in args)),
    )
    assert notify("subject", "body") is False
    assert skipped and "skipped" in skipped[0]


def test_console_sync_soft_skips_without_credentials() -> None:
    from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import (
        make_console_research_promotion_sync,
    )

    skipped: list[str] = []
    sync = make_console_research_promotion_sync(
        endpoint_url="",
        sync_token="",
        printer=lambda *args, **kwargs: skipped.append(" ".join(str(a) for a in args)),
    )
    ticket = run_research_promotion_cycle(
        _drift(),
        optimize=lambda drift, budget: _proposal(),
        record_shadow=lambda proposal: {"evidence_kind": "proxy_shadow", "passed": True},
    )
    assert sync(ticket) is False
    assert skipped and "url/token not configured" in skipped[0]


def test_console_sync_posts_awaiting_ticket_payload() -> None:
    from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import (
        make_console_research_promotion_sync,
    )

    calls: list[dict] = []

    def _post_json(*, endpoint, bearer_token, payload, timeout):
        calls.append(
            {
                "endpoint": endpoint,
                "bearer_token": bearer_token,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return 200

    sync = make_console_research_promotion_sync(
        endpoint_url="https://console.example/api/internal/sync-research-promotion-ticket",
        sync_token="sync-secret",
        post_json=_post_json,
    )
    ticket = run_research_promotion_cycle(
        _drift(),
        optimize=lambda drift, budget: _proposal(),
        record_shadow=lambda proposal: {"evidence_kind": "proxy_shadow", "passed": True},
        ticket_id="rpt_sync001",
    )
    assert sync(ticket) is True
    assert len(calls) == 1
    assert calls[0]["endpoint"].endswith("/sync-research-promotion-ticket")
    assert calls[0]["bearer_token"] == "sync-secret"
    assert calls[0]["payload"]["ticket_id"] == "rpt_sync001"
    assert calls[0]["payload"]["state"] == "awaiting_human"
    assert calls[0]["payload"]["live_authority_granted"] is False
    assert calls[0]["payload"]["suggested_risk_profile"] == "CAPITAL_PRESERVATION"


def test_cycle_invokes_console_sync_at_awaiting_human() -> None:
    synced: list[str] = []

    ticket = run_research_promotion_cycle(
        _drift(),
        optimize=lambda drift, budget: _proposal(),
        record_shadow=lambda proposal: {"evidence_kind": "proxy_shadow", "passed": True},
        sync_console=lambda t: synced.append(t.ticket_id) or True,
        ticket_id="rpt_sync_cycle",
    )
    assert ticket.state is ResearchPromotionState.AWAITING_HUMAN
    assert synced == ["rpt_sync_cycle"]
    assert ticket.notification_subject.startswith("[AWAITING_HUMAN]")


def test_console_sync_soft_fails_on_transport_error() -> None:
    from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import (
        make_console_research_promotion_sync,
    )
    import urllib.error

    skipped: list[str] = []

    def _boom(**_kwargs):
        raise urllib.error.URLError("down")

    sync = make_console_research_promotion_sync(
        endpoint_url="https://console.example/api/internal/sync-research-promotion-ticket",
        sync_token="sync-secret",
        post_json=_boom,
        printer=lambda *args, **kwargs: skipped.append(" ".join(str(a) for a in args)),
    )
    ticket = run_research_promotion_cycle(
        _drift(),
        optimize=lambda drift, budget: _proposal(),
        record_shadow=lambda proposal: {"evidence_kind": "proxy_shadow", "passed": True},
    )
    assert sync(ticket) is False
    assert skipped and "soft-failed" in skipped[0]


def test_accept_requires_confirmation() -> None:
    ticket = run_research_promotion_cycle(
        _drift(),
        optimize=lambda drift, budget: _proposal(),
        record_shadow=lambda proposal: {"evidence_kind": "proxy_shadow", "passed": True},
    )
    with pytest.raises(ValueError, match="confirmation"):
        apply_human_promotion_decision(ticket, decision="accept")


def test_accept_records_confirmation_without_live_authority() -> None:
    ticket = run_research_promotion_cycle(
        _drift(),
        optimize=lambda drift, budget: _proposal(),
        record_shadow=lambda proposal: {"evidence_kind": "proxy_shadow", "passed": True},
    )
    assert ticket.suggested_risk_profile == "CAPITAL_PRESERVATION"
    decided = apply_human_promotion_decision(
        ticket,
        decision="accept",
        confirmation={
            "target_platform": "longbridge",
            "execution_mode": "live",
            "risk_profile": "BALANCED_COMPOUNDING",
        },
    )
    assert decided.confirmation_target_platform == "longbridge"
    assert decided.confirmation_execution_mode == "live"
    assert decided.confirmation_risk_profile == "BALANCED_COMPOUNDING"
    assert decided.live_authority_granted is False


def test_paper_rejected_without_broker_paper_support() -> None:
    with pytest.raises(ValueError, match="synthetic"):
        validate_promotion_confirmation(
            PromotionConfirmation(
                target_platform="firstrade",
                execution_mode="paper",
                risk_profile="CAPITAL_PRESERVATION",
            ),
            paper_supported=False,
        )
    ok = validate_promotion_confirmation(
        PromotionConfirmation(
            target_platform="ibkr",
            execution_mode="paper",
            risk_profile="CAPITAL_PRESERVATION",
        ),
        paper_supported=True,
    )
    assert ok.execution_mode == "paper"


def test_console_pull_soft_skips_without_credentials() -> None:
    from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import (
        make_console_research_promotion_pull,
    )

    skipped: list[str] = []
    pull = make_console_research_promotion_pull(
        endpoint_url="",
        sync_token="",
        printer=lambda *args, **kwargs: skipped.append(" ".join(str(a) for a in args)),
    )
    assert pull("rpt_x") is None
    assert skipped and "url/token not configured" in skipped[0]


def test_console_pull_and_apply_accept_decision() -> None:
    from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import (
        apply_console_research_promotion_decision,
        make_console_research_promotion_pull,
    )

    calls: list[dict] = []

    def _get_json(*, endpoint, bearer_token, ticket_id, timeout):
        calls.append(
            {
                "endpoint": endpoint,
                "bearer_token": bearer_token,
                "ticket_id": ticket_id,
                "timeout": timeout,
            }
        )
        return {
            "ok": True,
            "live_authority_granted": False,
            "ticket": {
                "ticket_id": "rpt_pull001",
                "state": "human_accepted",
                "live_authority_granted": False,
                "human_decision": "accept",
                "human_decided_at": "2026-09-07T01:00:00Z",
                "confirmation_target_platform": "ibkr",
                "confirmation_execution_mode": "live",
                "confirmation_risk_profile": "BALANCED_COMPOUNDING",
            },
        }

    pull = make_console_research_promotion_pull(
        endpoint_url="https://console.example/api/internal/research-promotion-ticket",
        sync_token="sync-secret",
        get_json=_get_json,
    )
    remote = pull("rpt_pull001")
    assert remote is not None
    assert calls[0]["ticket_id"] == "rpt_pull001"
    assert calls[0]["bearer_token"] == "sync-secret"

    local = run_research_promotion_cycle(
        _drift(),
        optimize=lambda drift, budget: _proposal(),
        record_shadow=lambda proposal: {"evidence_kind": "proxy_shadow", "passed": True},
        ticket_id="rpt_pull001",
    )
    decided = apply_console_research_promotion_decision(local, remote)
    assert decided.state is ResearchPromotionState.HUMAN_ACCEPTED
    assert decided.live_authority_granted is False
    assert decided.confirmation_target_platform == "ibkr"
    assert decided.confirmation_execution_mode == "live"
    assert decided.confirmation_risk_profile == "BALANCED_COMPOUNDING"
    assert "console_decision_applied" in decided.notes


def test_console_apply_reject_decision() -> None:
    from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import (
        apply_console_research_promotion_decision,
    )

    local = run_research_promotion_cycle(
        _drift(),
        optimize=lambda drift, budget: _proposal(),
        record_shadow=lambda proposal: {"evidence_kind": "proxy_shadow", "passed": True},
        ticket_id="rpt_pull002",
    )
    decided = apply_console_research_promotion_decision(
        local,
        {
            "ticket_id": "rpt_pull002",
            "state": "human_rejected",
            "live_authority_granted": False,
            "human_decision": "reject",
        },
    )
    assert decided.state is ResearchPromotionState.HUMAN_REJECTED
    assert decided.live_authority_granted is False
    assert "console_decision_applied" in decided.notes
