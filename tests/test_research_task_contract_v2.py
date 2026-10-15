"""Shared task shape is generic; business parameter policy stays with callers."""
import copy
import pytest
from quant_platform_kit.strategy_lifecycle.research_task import (
    ResearchTaskError, build_strategy_diagnosis_task, calculate_task_sha256,
    validate_strategy_diagnosis_task,
)


def task(**kwargs):
    return build_strategy_diagnosis_task(
        event_key="a" * 12, created_at="2026-10-08T00:00:00Z", candidate_id="generic_candidate",
        candidate_kind="individual", domain="cn_equity", strategy_repository="Example/Strategy",
        evidence={"p1_input_digest": "1" * 64, "p2_config_digest": "2" * 64,
                  "p3_evidence_id": "3" * 64, "producer_revision": "a" * 40,
                  "strategy_revision": "b" * 40}, **kwargs,
    )


def test_generic_contract_has_no_implicit_strategy_policy():
    value = task()
    assert validate_strategy_diagnosis_task(value) == value
    assert value["experiment"]["parameter_bounds_sha256"] is None
    assert value["authority"]["p4_p5_p6_authorized"] is False


def test_bounds_require_explicit_caller_policy():
    value = task(parameter_bounds_sha256="f" * 64)
    with pytest.raises(ResearchTaskError):
        validate_strategy_diagnosis_task(value)
    assert validate_strategy_diagnosis_task(value, allowed_parameter_bounds=frozenset({"f" * 64})) == value


@pytest.mark.parametrize("section,key,bad", [
    ("authority", "no_order", 1), ("authority", "p4_p5_p6_authorized", 0),
    ("experiment", "max_runs", True), ("experiment", "max_wall_seconds", 3600.0),
])
def test_typed_authority_and_run_bounds_reject_equal_numeric_values(section, key, bad):
    value = copy.deepcopy(task())
    value[section][key] = bad
    value["task_sha256"] = calculate_task_sha256(value)
    with pytest.raises(ResearchTaskError):
        validate_strategy_diagnosis_task(value)
