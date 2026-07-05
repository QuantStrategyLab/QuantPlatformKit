"""Tests for strategy_lifecycle.evidence_gate."""

from __future__ import annotations

import json
from pathlib import Path

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
