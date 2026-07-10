"""Validation for immutable research and optimization specification artifacts.

These validators intentionally have no dependency on a JSON Schema runtime so
they can run in strategy repositories and evidence gates with the base QPK
installation.  The matching JSON Schema files remain the interchange contract.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any


RESEARCH_SPEC_SCHEMA_VERSION = "research_spec.v1"
OPTIMIZATION_SPEC_SCHEMA_VERSION = "optimization_spec.v1"

_RESEARCH_REQUIRED_BENCHMARK_KINDS = {
    "capital",
    "passive",
    "risk_matched",
    "simple_rule",
}
_OPTIMIZATION_PARAMETER_KINDS = {"integer", "number", "choice", "boolean"}
_SEARCH_METHODS = {"grid", "random", "bayesian"}
_MULTIPLE_TESTING_METHODS = {"dsr", "pbo", "spa", "reality_check", "fdr", "other_equivalent"}
_RFC3339_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


def validate_research_spec(payload: Any) -> list[str]:
    """Return human-readable contract violations for a ``research_spec.v1`` payload."""

    issues = _validate_top_level(
        payload,
        schema_version=RESEARCH_SPEC_SCHEMA_VERSION,
        required=(
            "spec_id",
            "strategy_profile",
            "domain",
            "created_at",
            "hypothesis",
            "reproducibility",
            "data",
            "benchmarks",
            "cost_model",
            "evaluation",
            "trial_ledger",
        ),
    )
    if not isinstance(payload, dict):
        return issues

    for field in ("spec_id", "strategy_profile", "domain"):
        _check_non_empty_string(payload, field, issues)
    _check_datetime(payload, "created_at", issues)

    hypothesis = _check_object(payload, "hypothesis", issues)
    if hypothesis is not None:
        _check_non_empty_string(hypothesis, "economic_rationale", issues, prefix="hypothesis")
        _check_non_empty_string_list(hypothesis, "falsification_conditions", issues, prefix="hypothesis")

    reproducibility = _check_object(payload, "reproducibility", issues)
    if reproducibility is not None:
        _check_non_empty_string(reproducibility, "code_revision", issues, prefix="reproducibility")
        _check_non_empty_string(reproducibility, "config_artifact_id", issues, prefix="reproducibility")
        if not _is_int(reproducibility.get("random_seed")):
            issues.append("reproducibility.random_seed must be an integer")

    data = _check_object(payload, "data", issues)
    if data is not None:
        _check_non_empty_string(data, "manifest_id", issues, prefix="data")
        _check_non_empty_string(data, "revision", issues, prefix="data")
        _check_datetime(data, "as_of", issues, prefix="data")
        _check_const(data, "point_in_time_validated", True, issues, prefix="data")
        _check_const(data, "survivorship_bias_controlled", True, issues, prefix="data")

    _validate_benchmarks(payload.get("benchmarks"), issues)

    cost_model = _check_object(payload, "cost_model", issues)
    if cost_model is not None:
        _check_non_empty_string(cost_model, "model_id", issues, prefix="cost_model")
        _check_non_empty_string(cost_model, "revision", issues, prefix="cost_model")
        _check_const(cost_model, "net_of_costs", True, issues, prefix="cost_model")

    evaluation = _check_object(payload, "evaluation", issues)
    if evaluation is not None:
        _check_const(evaluation, "frozen_before_oos", True, issues, prefix="evaluation")
        in_sample = _validate_date_window(evaluation.get("in_sample"), "evaluation.in_sample", issues)
        out_of_sample = _validate_date_window(evaluation.get("out_of_sample"), "evaluation.out_of_sample", issues)
        if isinstance(evaluation.get("out_of_sample"), dict):
            _check_const(evaluation["out_of_sample"], "locked", True, issues, prefix="evaluation.out_of_sample")
        if in_sample is not None and out_of_sample is not None and in_sample[1] >= out_of_sample[0]:
            issues.append("evaluation.in_sample must end before evaluation.out_of_sample starts")
        _validate_walk_forward(evaluation.get("walk_forward"), "evaluation.walk_forward", issues)

    trial_ledger = _check_object(payload, "trial_ledger", issues)
    if trial_ledger is not None:
        _check_non_empty_string(trial_ledger, "artifact_id", issues, prefix="trial_ledger")
        _check_const(trial_ledger, "record_all_trials", True, issues, prefix="trial_ledger")

    return issues


def validate_optimization_spec(payload: Any) -> list[str]:
    """Return human-readable contract violations for an ``optimization_spec.v1`` payload."""

    issues = _validate_top_level(
        payload,
        schema_version=OPTIMIZATION_SPEC_SCHEMA_VERSION,
        required=(
            "spec_id",
            "research_spec_id",
            "strategy_profile",
            "created_at",
            "frozen_inputs",
            "allowed_parameters",
            "objective",
            "search",
            "validation",
            "stop_rules",
            "promotion",
        ),
    )
    if not isinstance(payload, dict):
        return issues

    for field in ("spec_id", "research_spec_id", "strategy_profile"):
        _check_non_empty_string(payload, field, issues)
    _check_datetime(payload, "created_at", issues)

    frozen_inputs = _check_object(payload, "frozen_inputs", issues)
    if frozen_inputs is not None:
        for field in ("data_manifest_id", "universe_id", "cost_model_id", "code_revision"):
            _check_non_empty_string(frozen_inputs, field, issues, prefix="frozen_inputs")
        _check_non_empty_string_list(frozen_inputs, "benchmark_ids", issues, prefix="frozen_inputs")

    _validate_parameters(payload.get("allowed_parameters"), issues)

    objective = _check_object(payload, "objective", issues)
    if objective is not None:
        _check_non_empty_string(objective, "primary_metric", issues, prefix="objective")
        _check_non_empty_string_list(objective, "hard_constraints", issues, prefix="objective")
        if "secondary_metrics" in objective:
            _check_non_empty_string_list(
                objective,
                "secondary_metrics",
                issues,
                prefix="objective",
                allow_empty=True,
            )

    search = _check_object(payload, "search", issues)
    if search is not None:
        method = search.get("method")
        if method not in _SEARCH_METHODS:
            issues.append("search.method must be one of grid, random, bayesian")
        if not _is_int(search.get("max_trials")) or search["max_trials"] < 1:
            issues.append("search.max_trials must be an integer >= 1")
        if not _is_int(search.get("random_seed")):
            issues.append("search.random_seed must be an integer")

    validation = _check_object(payload, "validation", issues)
    if validation is not None:
        _validate_nested_walk_forward(validation.get("nested_walk_forward"), issues)
        _validate_locked_holdout(validation.get("locked_holdout"), issues)
        _validate_multiple_testing(validation.get("multiple_testing"), issues)
        _validate_cost_stress(validation.get("cost_stress"), issues)

    _check_non_empty_string_list(payload, "stop_rules", issues)

    promotion = _check_object(payload, "promotion", issues)
    if promotion is not None:
        _check_const(promotion, "requires_human_approval", True, issues, prefix="promotion")
        _check_const(promotion, "automatic_risk_increase_allowed", False, issues, prefix="promotion")
        _check_const(promotion, "full_kelly_allowed", False, issues, prefix="promotion")
        fractional_kelly = promotion.get("max_fractional_kelly")
        if not _is_number(fractional_kelly) or not 0 < fractional_kelly <= 1:
            issues.append("promotion.max_fractional_kelly must be a number in (0, 1]")

    return issues


def validate_strategy_spec(payload: Any) -> list[str]:
    """Dispatch validation from the artifact's versioned ``schema_version``."""

    if not isinstance(payload, dict):
        return ["top-level JSON must be an object"]
    schema_version = payload.get("schema_version")
    if schema_version == RESEARCH_SPEC_SCHEMA_VERSION:
        return validate_research_spec(payload)
    if schema_version == OPTIMIZATION_SPEC_SCHEMA_VERSION:
        return validate_optimization_spec(payload)
    return [
        "schema_version must be one of "
        f"{RESEARCH_SPEC_SCHEMA_VERSION}, {OPTIMIZATION_SPEC_SCHEMA_VERSION}"
    ]


def validate_strategy_spec_file(path: str | Path) -> list[str]:
    """Load and validate a JSON ResearchSpec or OptimizationSpec file."""

    spec_path = Path(path)
    try:
        payload = json.loads(
            spec_path.read_text(encoding="utf-8"),
            parse_constant=_reject_non_json_constant,
        )
    except FileNotFoundError:
        return [f"file not found: {spec_path}"]
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})"]
    except ValueError as exc:
        return [f"invalid JSON: {exc}"]
    except OSError as exc:
        return [f"failed to read file: {exc}"]
    return validate_strategy_spec(payload)


def _validate_top_level(payload: Any, *, schema_version: str, required: tuple[str, ...]) -> list[str]:
    if not isinstance(payload, dict):
        return ["top-level JSON must be an object"]

    issues = [f"missing required field: {field}" for field in ("schema_version", *required) if field not in payload]
    if payload.get("schema_version") != schema_version:
        issues.append(f"schema_version must be {schema_version!r}")
    return issues


def _validate_benchmarks(value: Any, issues: list[str]) -> None:
    if not isinstance(value, list):
        issues.append("benchmarks must be an array")
        return

    kinds: set[str] = set()
    for index, benchmark in enumerate(value):
        label = f"benchmarks[{index}]"
        if not isinstance(benchmark, dict):
            issues.append(f"{label} must be an object")
            continue
        _check_non_empty_string(benchmark, "benchmark_id", issues, prefix=label)
        kind = benchmark.get("kind")
        if kind not in _RESEARCH_REQUIRED_BENCHMARK_KINDS | {"production"}:
            issues.append(f"{label}.kind must be capital, passive, risk_matched, simple_rule, or production")
        else:
            kinds.add(kind)

    missing = sorted(_RESEARCH_REQUIRED_BENCHMARK_KINDS - kinds)
    if missing:
        issues.append(f"benchmarks missing required kinds: {', '.join(missing)}")


def _validate_date_window(value: Any, label: str, issues: list[str]) -> tuple[date, date] | None:
    if not isinstance(value, dict):
        issues.append(f"{label} must be an object")
        return None
    start = _parse_date(value.get("start_date"))
    end = _parse_date(value.get("end_date"))
    if start is None:
        issues.append(f"{label}.start_date must be an ISO date")
    if end is None:
        issues.append(f"{label}.end_date must be an ISO date")
    if start is not None and end is not None and start > end:
        issues.append(f"{label}.start_date must be on or before {label}.end_date")
    if start is None or end is None:
        return None
    return start, end


def _validate_walk_forward(value: Any, label: str, issues: list[str]) -> None:
    if not isinstance(value, dict):
        issues.append(f"{label} must be an object")
        return
    if value.get("method") not in {"rolling", "expanding", "purged"}:
        issues.append(f"{label}.method must be rolling, expanding, or purged")
    if not _is_int(value.get("fold_count")) or value["fold_count"] < 3:
        issues.append(f"{label}.fold_count must be an integer >= 3")
    if "embargo_days" in value and (not _is_int(value["embargo_days"]) or value["embargo_days"] < 0):
        issues.append(f"{label}.embargo_days must be an integer >= 0")


def _validate_parameters(value: Any, issues: list[str]) -> None:
    if not isinstance(value, list) or not value:
        issues.append("allowed_parameters must be a non-empty array")
        return

    names: set[str] = set()
    for index, parameter in enumerate(value):
        label = f"allowed_parameters[{index}]"
        if not isinstance(parameter, dict):
            issues.append(f"{label} must be an object")
            continue
        name = parameter.get("name")
        if not isinstance(name, str) or not name.strip():
            issues.append(f"{label}.name must be a non-empty string")
        elif name in names:
            issues.append(f"{label}.name must not duplicate {name!r}")
        else:
            names.add(name)

        kind = parameter.get("kind")
        if kind not in _OPTIMIZATION_PARAMETER_KINDS:
            issues.append(f"{label}.kind must be integer, number, choice, or boolean")
            continue
        if kind in {"integer", "number"}:
            bounds = parameter.get("bounds")
            if not isinstance(bounds, list) or len(bounds) != 2 or not all(_is_number(item) for item in bounds):
                issues.append(f"{label}.bounds must contain two numbers")
            elif bounds[0] >= bounds[1]:
                issues.append(f"{label}.bounds lower value must be less than upper value")
            elif kind == "integer" and not all(_is_int(item) for item in bounds):
                issues.append(f"{label}.bounds must contain integers for kind=integer")
            if "step" in parameter and (not _is_number(parameter["step"]) or parameter["step"] <= 0):
                issues.append(f"{label}.step must be a number > 0")
        elif kind == "choice":
            choices = parameter.get("choices")
            if not isinstance(choices, list) or not choices:
                issues.append(f"{label}.choices must be a non-empty array for kind=choice")
            elif not all(isinstance(item, (str, bool)) or _is_number(item) for item in choices):
                issues.append(f"{label}.choices must contain only strings, numbers, or booleans")


def _validate_nested_walk_forward(value: Any, issues: list[str]) -> None:
    label = "validation.nested_walk_forward"
    if not isinstance(value, dict):
        issues.append(f"{label} must be an object")
        return
    _check_const(value, "enabled", True, issues, prefix=label)
    if not _is_int(value.get("fold_count")) or value["fold_count"] < 3:
        issues.append(f"{label}.fold_count must be an integer >= 3")
    _check_const(value, "selection_scope", "train_validation_only", issues, prefix=label)


def _validate_locked_holdout(value: Any, issues: list[str]) -> None:
    label = "validation.locked_holdout"
    if not isinstance(value, dict):
        issues.append(f"{label} must be an object")
        return
    _check_const(value, "enabled", True, issues, prefix=label)
    _check_const(value, "reused_for_selection", False, issues, prefix=label)


def _validate_multiple_testing(value: Any, issues: list[str]) -> None:
    label = "validation.multiple_testing"
    if not isinstance(value, dict):
        issues.append(f"{label} must be an object")
        return
    if value.get("method") not in _MULTIPLE_TESTING_METHODS:
        issues.append(f"{label}.method must be dsr, pbo, spa, reality_check, fdr, or other_equivalent")
    _check_non_empty_string(value, "trial_ledger_id", issues, prefix=label)
    _check_const(value, "record_all_trials", True, issues, prefix=label)


def _validate_cost_stress(value: Any, issues: list[str]) -> None:
    label = "validation.cost_stress"
    if not isinstance(value, dict):
        issues.append(f"{label} must be an object")
        return
    multipliers = value.get("multipliers")
    if not isinstance(multipliers, list) or not all(_is_number(item) and item >= 1 for item in multipliers):
        issues.append(f"{label}.multipliers must be an array of numbers >= 1")
    elif not {1, 2, 3}.issubset(set(multipliers)):
        issues.append(f"{label}.multipliers must include 1, 2, and 3")
    _check_const(value, "required_pass", True, issues, prefix=label)


def _check_object(payload: dict[str, Any], field: str, issues: list[str]) -> dict[str, Any] | None:
    value = payload.get(field)
    if not isinstance(value, dict):
        issues.append(f"{field} must be an object")
        return None
    return value


def _check_non_empty_string(
    payload: dict[str, Any],
    field: str,
    issues: list[str],
    *,
    prefix: str | None = None,
) -> None:
    value = payload.get(field)
    label = f"{prefix}.{field}" if prefix else field
    if not isinstance(value, str) or not value.strip():
        issues.append(f"{label} must be a non-empty string")


def _check_non_empty_string_list(
    payload: dict[str, Any],
    field: str,
    issues: list[str],
    *,
    prefix: str | None = None,
    allow_empty: bool = False,
) -> None:
    value = payload.get(field)
    label = f"{prefix}.{field}" if prefix else field
    if not isinstance(value, list) or (not allow_empty and not value) or not all(isinstance(item, str) and item.strip() for item in value):
        suffix = "an array of non-empty strings" if allow_empty else "a non-empty array of non-empty strings"
        issues.append(f"{label} must be {suffix}")


def _check_datetime(
    payload: dict[str, Any],
    field: str,
    issues: list[str],
    *,
    prefix: str | None = None,
) -> None:
    value = payload.get(field)
    label = f"{prefix}.{field}" if prefix else field
    if not isinstance(value, str) or _parse_datetime(value) is None:
        issues.append(f"{label} must be an ISO date-time")


def _check_const(payload: dict[str, Any], field: str, expected: object, issues: list[str], *, prefix: str) -> None:
    value = payload.get(field)
    if type(value) is not type(expected) or value != expected:
        issues.append(f"{prefix}.{field} must be {expected!r}")


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_datetime(value: str) -> datetime | None:
    candidate = value.strip()
    if not _RFC3339_DATETIME.fullmatch(candidate):
        return None
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _reject_non_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant {value!r}")
