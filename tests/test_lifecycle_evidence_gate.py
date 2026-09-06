"""Tests for strategy_lifecycle.evidence_gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quant_platform_kit.strategy_lifecycle.cli import main
from quant_platform_kit.strategy_lifecycle.evidence_gate import (
    load_evidence_package,
    validate_evidence_package,
    validate_evidence_package_file,
)


def test_research_package_valid() -> None:
    result = validate_evidence_package(
        {
            "profile": "cn_equity_combo",
            "market": "cn_equity",
            "requested_stage": "research_backtest_only",
            "backtest_summary": {"observation_count": 252, "sharpe_ratio": 1.2},
        }
    )

    assert result.valid
    assert result.package.strategy_profile == "cn_equity_combo"


@pytest.mark.parametrize("accepted", [False, True])
def test_v3_gate_preserves_canonical_payload_and_non_live_truth(tmp_path: Path, accepted: bool) -> None:
    from test_strategy_evidence_package_v2_contract import _v3_payload

    payload = _v3_payload(tmp_path, accepted=accepted)
    result = validate_evidence_package(payload, base_dir=tmp_path)
    assert result.valid
    assert result.package.to_dict() == payload
    assert result.package.evidence_version == payload["schema_version"]
    assert result.to_dict()["promotion_status"] == (
        "PROMOTION_ELIGIBLE" if accepted else "HUMAN_REQUIRED"
    )
    assert result.promotion_eligible is accepted
    assert result.live_ready is False
    assert result.size_zero_required is True
    assert result.no_order is True


def test_unknown_canonical_revision_cannot_fall_back_to_legacy() -> None:
    result = validate_evidence_package({
        "schema_version": "strategy_evidence_package.v999",
        "profile": "legacy_profile", "market": "us_equity",
        "requested_stage": "research_backtest_only",
        "backtest_summary": {"observation_count": 252},
    })
    assert not result.valid


@pytest.mark.parametrize("stage", ["live_candidate", "live_enabled", "runtime_enabled"])
def test_v3_live_requests_still_build_only_a_hold(tmp_path: Path, stage: str) -> None:
    from test_strategy_evidence_package_v2_contract import _refresh_digests, _v3_payload
    from quant_platform_kit.strategy_lifecycle.live_candidate_notifications import (
        build_live_candidate_notification,
    )

    payload = _v3_payload(tmp_path, accepted=True)
    payload["requested_stage"] = stage
    _refresh_digests(payload)
    result = validate_evidence_package(payload, base_dir=tmp_path)
    assert result.valid
    assert result.no_order and result.size_zero_required and not result.live_ready
    event = build_live_candidate_notification(result)
    assert event is not None
    assert event.approval_action == "hold"
    assert "HOLD" in event.subject


def test_canonical_research_active_package_is_supported() -> None:
    result = validate_evidence_package(
        {
            "profile": "cn_equity_combo",
            "market": "cn_equity",
            "requested_stage": "research_active",
            "backtest_summary": {"observation_count": 252, "sharpe_ratio": 1.2},
        }
    )

    assert result.valid
    assert result.no_order is True


def test_live_package_requires_compatibility_and_drift() -> None:
    result = validate_evidence_package(
        {
            "strategy_profile": "cn_chinext_growth_momentum_quality",
            "domain": "cn_equity",
            "requested_stage": "live_candidate",
            "target_platforms": ["qmt"],
            "backtest_summary": {"observation_count": 252, "sharpe_ratio": 1.1},
        }
    )

    assert not result.valid
    assert "drift_notes" in " ".join(result.issues)
    assert "platform_compatibility" in " ".join(result.issues)


def test_live_package_valid_when_required_sections_present() -> None:
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

    assert result.valid
    assert result.promotion_eligible is False
    assert result.live_ready is False
    assert result.size_zero_required is True
    assert result.no_order is True
    assert result.promotion_status == "LEGACY_RESEARCH_ONLY"


def test_legacy_plugin_position_control_cannot_satisfy_gate() -> None:
    result = validate_evidence_package(
        {
            "strategy_profile": "legacy_profile",
            "domain": "us_equity",
            "requested_stage": "live_candidate",
            "target_platforms": ["ibkr"],
            "backtest_summary": {"observation_count": 252},
            "drift_notes": {"status": "stable"},
            "platform_compatibility": {"verified": True},
            "plugin_gate": {
                "status": "automation_approved",
                "position_control_allowed": True,
            },
        }
    )

    assert not result.valid
    assert "plugin_gate evidence is incomplete or unsupported" in result.issues


def test_file_loader_and_cli(tmp_path: Path) -> None:
    payload = {
        "strategy_profile": "cn_equity_combo",
        "domain": "cn_equity",
        "requested_stage": "research_backtest_only",
        "backtest_summary": {"observation_count": 126, "total_return": 0.12},
    }
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_evidence_package(path)
    assert loaded["strategy_profile"] == "cn_equity_combo"

    result = validate_evidence_package_file(path)
    assert result.valid

    exit_code = main(["evidence", "--file", str(path)])
    assert exit_code == 0


def test_live_and_legacy_runtime_requests_are_research_only_holds() -> None:
    for stage in ("live_candidate", "live_enabled", "runtime_enabled"):
        result = validate_evidence_package(
            {
                "strategy_profile": "legacy_profile",
                "domain": "us_equity",
                "requested_stage": stage,
                "target_platforms": ["ibkr"],
                "backtest_summary": {"observation_count": 252},
                "drift_notes": {"status": "stable"},
                "platform_compatibility": {"verified": True},
            }
        )

        assert result.valid
        assert result.promotion_eligible is False
        assert result.live_ready is False
        assert result.promotion_status == "LEGACY_RESEARCH_ONLY"
