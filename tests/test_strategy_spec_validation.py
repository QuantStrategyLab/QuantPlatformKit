from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from quant_platform_kit.strategy_lifecycle.spec_validation import (
    OPTIMIZATION_SPEC_SCHEMA_VERSION,
    RESEARCH_SPEC_SCHEMA_VERSION,
    validate_optimization_spec,
    validate_research_spec,
    validate_strategy_spec_file,
)


ROOT = Path(__file__).resolve().parents[1]


def _research_spec() -> dict[str, object]:
    return {
        "schema_version": RESEARCH_SPEC_SCHEMA_VERSION,
        "spec_id": "research.global-etf-rotation.2026-07-11",
        "strategy_profile": "global_etf_rotation",
        "domain": "us_equity",
        "created_at": "2026-07-11T00:00:00Z",
        "hypothesis": {
            "economic_rationale": "Trend persistence compensates investors for bearing regime risk.",
            "falsification_conditions": ["Net OOS alpha disappears after realistic costs."],
        },
        "reproducibility": {
            "code_revision": "abc123",
            "config_artifact_id": "config.global-etf-rotation.v1",
            "random_seed": 7,
        },
        "data": {
            "manifest_id": "manifest.us-etf.2026-07-10",
            "revision": "vendor-2026-07-10",
            "as_of": "2026-07-10T23:00:00Z",
            "point_in_time_validated": True,
            "survivorship_bias_controlled": True,
        },
        "benchmarks": [
            {"benchmark_id": "cash.usd", "kind": "capital"},
            {"benchmark_id": "spy.buy-and-hold", "kind": "passive"},
            {"benchmark_id": "spy.vol-matched", "kind": "risk_matched"},
            {"benchmark_id": "monthly.6040", "kind": "simple_rule"},
        ],
        "cost_model": {
            "model_id": "us-etf-costs",
            "revision": "2026-07-01",
            "net_of_costs": True,
        },
        "evaluation": {
            "frozen_before_oos": True,
            "in_sample": {"start_date": "2016-01-01", "end_date": "2022-12-31"},
            "out_of_sample": {
                "start_date": "2023-01-01",
                "end_date": "2025-12-31",
                "locked": True,
            },
            "walk_forward": {"method": "expanding", "fold_count": 3},
        },
        "trial_ledger": {"artifact_id": "ledger.global-etf-rotation.v1", "record_all_trials": True},
    }


def _optimization_spec() -> dict[str, object]:
    return {
        "schema_version": OPTIMIZATION_SPEC_SCHEMA_VERSION,
        "spec_id": "optimization.global-etf-rotation.2026-07-11",
        "research_spec_id": "research.global-etf-rotation.2026-07-11",
        "strategy_profile": "global_etf_rotation",
        "created_at": "2026-07-11T00:00:00Z",
        "frozen_inputs": {
            "data_manifest_id": "manifest.us-etf.2026-07-10",
            "universe_id": "global-etf-universe.v3",
            "benchmark_ids": ["cash.usd", "spy.buy-and-hold", "spy.vol-matched", "monthly.6040"],
            "cost_model_id": "us-etf-costs@2026-07-01",
            "code_revision": "abc123",
        },
        "allowed_parameters": [
            {"name": "lookback_days", "kind": "integer", "bounds": [60, 252], "step": 21},
            {"name": "top_n", "kind": "integer", "bounds": [2, 8], "step": 1},
        ],
        "objective": {
            "primary_metric": "net_oos_utility",
            "secondary_metrics": ["conservative_sharpe", "active_return_stability"],
            "hard_constraints": ["max_drawdown <= mandate", "cost_stress_passed = true"],
        },
        "search": {"method": "grid", "max_trials": 72, "random_seed": 7},
        "validation": {
            "nested_walk_forward": {
                "enabled": True,
                "fold_count": 3,
                "selection_scope": "train_validation_only",
            },
            "locked_holdout": {"enabled": True, "reused_for_selection": False},
            "multiple_testing": {
                "method": "dsr",
                "trial_ledger_id": "ledger.global-etf-rotation.v1",
                "record_all_trials": True,
            },
            "cost_stress": {"multipliers": [1, 2, 3], "required_pass": True},
        },
        "stop_rules": ["Stop when locked holdout fails."],
        "promotion": {
            "requires_human_approval": True,
            "automatic_risk_increase_allowed": False,
            "full_kelly_allowed": False,
            "max_fractional_kelly": 0.25,
        },
    }


def test_valid_research_spec_passes() -> None:
    assert validate_research_spec(_research_spec()) == []


def test_versioned_json_schemas_match_validator_versions() -> None:
    for name, version in (
        ("research-spec.v1.schema.json", RESEARCH_SPEC_SCHEMA_VERSION),
        ("optimization-spec.v1.schema.json", OPTIMIZATION_SPEC_SCHEMA_VERSION),
    ):
        schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
        assert schema["properties"]["schema_version"]["const"] == version


def test_research_spec_rejects_unlocked_or_overlapping_oos() -> None:
    payload = _research_spec()
    evaluation = payload["evaluation"]
    assert isinstance(evaluation, dict)
    evaluation["out_of_sample"] = {
        "start_date": "2022-12-31",
        "end_date": "2025-12-31",
        "locked": False,
    }

    issues = validate_research_spec(payload)

    assert "evaluation.out_of_sample.locked must be True" in issues
    assert "evaluation.in_sample must end before evaluation.out_of_sample starts" in issues


def test_research_spec_rejects_numeric_boolean_stand_ins() -> None:
    payload = _research_spec()
    evaluation = payload["evaluation"]
    trial_ledger = payload["trial_ledger"]
    assert isinstance(evaluation, dict)
    assert isinstance(trial_ledger, dict)
    out_of_sample = evaluation["out_of_sample"]
    assert isinstance(out_of_sample, dict)
    out_of_sample["locked"] = 1
    trial_ledger["record_all_trials"] = 1

    issues = validate_research_spec(payload)

    assert "evaluation.out_of_sample.locked must be True" in issues
    assert "trial_ledger.record_all_trials must be True" in issues


def test_research_spec_rejects_naive_or_date_only_timestamps() -> None:
    payload = _research_spec()
    payload["created_at"] = "2026-07-11"
    data = payload["data"]
    assert isinstance(data, dict)
    data["as_of"] = "2026-07-10T23:00:00"

    issues = validate_research_spec(payload)

    assert "created_at must be an ISO date-time" in issues
    assert "data.as_of must be an ISO date-time" in issues


def test_research_spec_requires_four_layer_benchmarks() -> None:
    payload = _research_spec()
    payload["benchmarks"] = [{"benchmark_id": "spy", "kind": "passive"}]

    issues = validate_research_spec(payload)

    assert "benchmarks missing required kinds: capital, risk_matched, simple_rule" in issues


def test_research_spec_allows_multiple_comparators_of_the_same_kind() -> None:
    payload = _research_spec()
    benchmarks = payload["benchmarks"]
    assert isinstance(benchmarks, list)
    benchmarks.append({"benchmark_id": "qqq.buy-and-hold", "kind": "passive"})

    assert validate_research_spec(payload) == []


def test_valid_optimization_spec_passes() -> None:
    assert validate_optimization_spec(_optimization_spec()) == []


def test_optimization_spec_rejects_holdout_reuse_full_kelly_and_missing_cost_stress() -> None:
    payload = _optimization_spec()
    validation = payload["validation"]
    promotion = payload["promotion"]
    assert isinstance(validation, dict)
    assert isinstance(promotion, dict)
    validation["locked_holdout"] = {"enabled": True, "reused_for_selection": True}
    validation["cost_stress"] = {"multipliers": [1, 2], "required_pass": True}
    promotion["full_kelly_allowed"] = True

    issues = validate_optimization_spec(payload)

    assert "validation.locked_holdout.reused_for_selection must be False" in issues
    assert "validation.cost_stress.multipliers must include 1, 2, and 3" in issues
    assert "promotion.full_kelly_allowed must be False" in issues


def test_optimization_spec_rejects_non_scalar_choice_values() -> None:
    payload = _optimization_spec()
    parameters = payload["allowed_parameters"]
    assert isinstance(parameters, list)
    parameters.append({"name": "rebalance_rule", "kind": "choice", "choices": [{"weekly": 5}]})

    issues = validate_optimization_spec(payload)

    assert "allowed_parameters[2].choices must contain only strings, numbers, or booleans" in issues


def test_file_and_cli_validation_are_evidence_gate_friendly(tmp_path: Path) -> None:
    valid_path = tmp_path / "research-spec.json"
    valid_path.write_text(json.dumps(_research_spec()), encoding="utf-8")
    invalid_path = tmp_path / "invalid-spec.json"
    invalid_path.write_text(json.dumps({"schema_version": "unknown.v1"}), encoding="utf-8")
    non_standard_json_path = tmp_path / "non-standard.json"
    non_standard_json_path.write_text('{"schema_version": NaN}', encoding="utf-8")

    assert validate_strategy_spec_file(valid_path) == []
    assert validate_strategy_spec_file(invalid_path) == [
        "schema_version must be one of research_spec.v1, optimization_spec.v1"
    ]
    assert validate_strategy_spec_file(non_standard_json_path) == [
        "invalid JSON: non-standard JSON constant 'NaN'"
    ]

    valid_proc = subprocess.run(
        [sys.executable, "scripts/validate_strategy_spec.py", str(valid_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": ""},
        check=False,
    )
    invalid_proc = subprocess.run(
        [sys.executable, "scripts/validate_strategy_spec.py", str(invalid_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": ""},
        check=False,
    )

    assert valid_proc.returncode == 0
    assert valid_proc.stdout == ""
    assert valid_proc.stderr == ""
    assert invalid_proc.returncode == 1
    assert invalid_proc.stdout == ""
    assert "schema_version must be one of research_spec.v1, optimization_spec.v1" in invalid_proc.stderr
