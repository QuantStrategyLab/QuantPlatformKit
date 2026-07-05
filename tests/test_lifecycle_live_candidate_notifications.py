"""Tests for strategy_lifecycle live candidate notification events."""

from __future__ import annotations

from quant_platform_kit.strategy_lifecycle.evidence_gate import validate_evidence_package
from quant_platform_kit.strategy_lifecycle.live_candidate_notifications import (
    build_live_candidate_notification,
)


def test_builds_live_candidate_notification_for_valid_package() -> None:
    result = validate_evidence_package(
        {
            "strategy_profile": "cn_chinext_growth_momentum_quality",
            "domain": "cn_equity",
            "requested_stage": "live_candidate",
            "target_platforms": ["qmt"],
            "backtest_summary": {"observation_count": 252, "sharpe_ratio": 1.1},
            "drift_notes": {"status": "watch", "summary": "stable"},
            "platform_compatibility": {"verified": True},
            "plugin_gate": {"status": "notification_only"},
        }
    )

    event = build_live_candidate_notification(result)

    assert event is not None
    assert event.strategy_profile == "cn_chinext_growth_momentum_quality"
    assert event.domain == "cn_equity"
    assert event.stage == "live_candidate"
    assert event.approval_action == "approve"
    assert event.severity == "info"
    assert event.alert_key == "lifecycle/live_candidate/cn_equity/cn_chinext_growth_momentum_quality/live_candidate/approve"
    assert "backtest=observation_count=252" in event.evidence_summary
    assert "platform_compatibility=verified=True" in event.evidence_summary
    rendered = event.to_rendered_notification()
    assert rendered.compact_text == event.subject
    assert "Approval Action: approve" in rendered.detailed_text


def test_builds_hold_notification_for_invalid_live_package() -> None:
    result = validate_evidence_package(
        {
            "strategy_profile": "cn_chinext_growth_momentum_quality",
            "domain": "cn_equity",
            "requested_stage": "live_candidate",
            "target_platforms": ["qmt"],
            "backtest_summary": {"observation_count": 252, "sharpe_ratio": 1.1},
        }
    )

    event = build_live_candidate_notification(result)

    assert event is not None
    assert event.approval_action == "hold"
    assert event.severity == "warning"
    assert "blocked:" in event.reason
    assert "drift_notes" in event.reason
    assert event.metadata["valid"] is False


def test_skips_non_live_stage_packages() -> None:
    result = validate_evidence_package(
        {
            "strategy_profile": "cn_equity_combo",
            "domain": "cn_equity",
            "requested_stage": "research_backtest_only",
            "backtest_summary": {"observation_count": 252, "sharpe_ratio": 1.2},
        }
    )

    assert build_live_candidate_notification(result) is None
