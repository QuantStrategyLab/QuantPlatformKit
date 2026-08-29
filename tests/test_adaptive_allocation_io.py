import json

import pytest

from quant_platform_kit.adaptive_allocation import (
    SELECTION_INPUT_SCHEMA,
    build_shadow_selection,
    load_shadow_selection_input,
)
from quant_platform_kit.adaptive_allocation.cli import main


def _payload(**overrides):
    values = {
        "schema": SELECTION_INPUT_SCHEMA,
        "decision_id": "shadow-us-equity-001",
        "created_at": "2026-08-29T00:00:00Z",
        "market_context": {
            "schema": "qsl.market_context_snapshot.v1",
            "as_of": "2026-08-28",
            "domain": "us_equity",
            "data_version": "trusted-snapshot-sha",
            "data_freshness_days": 0,
            "regime": "normal",
            "regime_confidence": 0.9,
            "factors": {"momentum": 0.1},
        },
        "candidates": [
            {
                "strategy_profile": "candidate_a",
                "release_digest": "sha256:candidate-a",
                "lifecycle_stage": "shadow_active",
                "approved_for_shadow": True,
                "base_score": 0.4,
                "estimated_volatility": 0.2,
                "factor_exposures": {"momentum": 0.5},
                "required_plugins": ["market_regime_control"],
                "allowed_platform_ids": ["paper_platform"],
            }
        ],
        "platform_health": [
            {
                "schema": "qsl.platform_health_snapshot.v1",
                "platform_id": "paper_platform",
                "observed_at": "2026-08-29T00:00:00+00:00",
                "healthy": True,
                "shadow_capable": True,
                "reconciliation_ok": True,
                "capacity_score": 0.8,
                "expected_cost_bps": 1.0,
            }
        ],
        "plugin_adjustments": [
            {"plugin_id": "market_regime_control", "risk_multiplier": 0.8, "approved": True}
        ],
        "policy": {
            "policy_id": "shadow-policy-v1",
            "max_data_freshness_days": 1,
            "minimum_regime_confidence": 0.6,
            "minimum_score": 0.1,
            "volatility_penalty": 0.5,
            "cost_penalty": 0.01,
        },
    }
    return values | overrides


def test_build_shadow_selection_validates_a_versioned_bundle_and_keeps_no_order():
    decision = build_shadow_selection(_payload())

    result = decision.to_dict()
    assert result["authority"] == "shadow_only"
    assert result["no_order"] is True
    assert result["recommended_strategy_profile"] == "candidate_a"
    assert result["candidates"][0]["proposed_weight"] == 0.0


def test_build_shadow_selection_rejects_naive_platform_timestamp():
    payload = _payload()
    payload["platform_health"][0]["observed_at"] = "2026-08-29T00:00:00"

    with pytest.raises(ValueError, match="timezone"):
        build_shadow_selection(payload)


def test_build_shadow_selection_requires_versioned_context_and_integer_freshness():
    missing_schema = _payload()
    del missing_schema["market_context"]["schema"]
    fractional_freshness = _payload()
    fractional_freshness["market_context"]["data_freshness_days"] = 0.5

    with pytest.raises(ValueError, match="schema"):
        build_shadow_selection(missing_schema)
    with pytest.raises(ValueError, match="integer"):
        build_shadow_selection(fractional_freshness)


def test_cli_writes_only_a_json_decision_artifact(tmp_path):
    source = tmp_path / "input.json"
    output = tmp_path / "output" / "decision.json"
    source.write_text(json.dumps(_payload()), encoding="utf-8")

    assert main(["--input", str(source), "--output", str(output)]) == 0

    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["no_order"] is True
    assert result["candidates"][0]["proposed_weight"] == 0.0
    assert load_shadow_selection_input(source)["schema"] == SELECTION_INPUT_SCHEMA
