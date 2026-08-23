"""Canonical, dependency-free strategy evidence package v2 validation."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from calendar import monthrange
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any


STRATEGY_EVIDENCE_PACKAGE_SCHEMA_VERSION = "strategy_evidence_package.v2"

_SOURCE_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CORE_FIELDS = (
    "schema_version",
    "evidence_package_id",
    "generated_at",
    "requested_stage",
    "strategy",
    "input_provenance",
    "backtest",
    "artifacts",
    "metrics",
    "cost_stress",
    "risk_assessment",
)
_TOP_LEVEL_FIELDS = frozenset(
    (*_CORE_FIELDS, "digests", "human_acceptance", "lifecycle_claims")
)
_ARTIFACT_DIGEST_FIELDS = {
    "config": "config_sha256",
    "data_manifest": "data_manifest_sha256",
    "backtest": "backtest_sha256",
    "risk": "risk_sha256",
    "information_coefficient": "information_coefficient_sha256",
    "cost_model": "cost_model_sha256",
}
_METRIC_FIELDS = (
    "sharpe_ratio",
    "sortino_ratio",
    "max_drawdown",
    "annualized_return",
    "annualized_volatility",
    "calmar_ratio",
    "information_ratio",
    "information_coefficient",
    "var_95",
    "cvar_95",
    "turnover",
    "trade_count",
    "win_rate",
    "profit_factor",
)
_RESULT_NUMBER_FIELDS = (
    "sharpe_ratio",
    "calmar_ratio",
    "sortino_ratio",
    "max_drawdown",
    "cagr",
    "volatility",
    "win_rate",
    "total_return",
    "observation_count",
    "benchmark_cagr",
    "benchmark_max_drawdown",
    "excess_cagr",
    "oos_sharpe",
    "oos_calmar",
    "oos_max_drawdown",
    "walk_forward_stability",
    "run_duration_seconds",
)
_RESULT_FIELDS = frozenset(
    {
        "strategy_profile",
        "domain",
        "param_set_id",
        "params",
        "param_version",
        "start_date",
        "end_date",
        "benchmark_symbol",
        "run_id",
        "source_script",
        "computed_at",
        "source_revision",
        "cost_model",
        "validation_identity",
        "cost_inputs",
        *_RESULT_NUMBER_FIELDS,
    }
)
_LEGACY_ALLOWED_REQUESTED_STAGES = {
    "research_active",
    "shadow_active",
    "paper_active",
    "live_enabled",
    "research_backtest_only",
    "ai_monitored_candidate",
    "shadow_candidate",
    "live_candidate",
    "runtime_enabled",
}
_LEGACY_KELLY_LEVELS = {"K0", "K1", "K2", "K3", "K4"}
_LEGACY_ARTIFACTS = (
    "returns",
    "trades",
    "positions",
    "config",
    "data_manifest",
    "candidate_registry",
    "benchmark_registry",
    "cost_model",
    "risk_report",
    "kelly_readiness_report",
)
_LEGACY_METRICS = (
    "sharpe_ratio",
    "sortino_ratio",
    "max_drawdown",
    "annualized_return",
    "annualized_volatility",
    "calmar_ratio",
    "information_ratio",
    "var_95",
    "cvar_95",
    "turnover",
    "trade_count",
    "win_rate",
    "profit_factor",
)


def canonical_evidence_package_v2_bytes(payload: Mapping[str, Any]) -> bytes:
    """Return deterministic UTF-8 JSON bytes and reject non-finite values."""

    if not isinstance(payload, Mapping):
        raise TypeError("evidence package must be a mapping")
    return json.dumps(
        dict(payload),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def read_evidence_package_v2_json(path: str | Path) -> dict[str, Any]:
    """Read strict JSON: UTF-8 only, no duplicate keys or non-finite numbers."""

    evidence_path = Path(path)
    try:
        raw = evidence_path.read_bytes()
    except FileNotFoundError:
        raise ValueError(f"file not found: {evidence_path}") from None
    except OSError as exc:
        raise ValueError(f"failed to read file: {exc}") from exc
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"invalid UTF-8: byte {exc.start}") from exc

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"invalid JSON: duplicate key: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise ValueError(f"invalid JSON: non-finite number: {value}")

    try:
        payload = json.loads(
            text,
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError("top-level JSON must be an object")
    return payload


def validate_evidence_package_v2(
    payload: Mapping[str, Any], *, base_dir: str | Path | None = None
) -> tuple[str, ...]:
    """Validate the closed v2 contract without optional runtime dependencies."""

    issues: list[str] = []
    if not isinstance(payload, Mapping):
        return ("top-level evidence package must be an object",)
    _closed_object(payload, "top-level", _TOP_LEVEL_FIELDS, _TOP_LEVEL_FIELDS, issues)

    if payload.get("schema_version") != STRATEGY_EVIDENCE_PACKAGE_SCHEMA_VERSION:
        issues.append("schema_version must equal strategy_evidence_package.v2")
    _non_empty_string(payload.get("evidence_package_id"), "evidence_package_id", issues)
    generated_at = _timezone_datetime(
        payload.get("generated_at"), "generated_at", issues
    )
    if payload.get("requested_stage") not in _LEGACY_ALLOWED_REQUESTED_STAGES:
        issues.append("requested_stage is unsupported")

    strategy = _object(payload.get("strategy"), "strategy", issues)
    if strategy is not None:
        _closed_object(
            strategy,
            "strategy",
            {"profile", "domain", "source_revision"},
            {"profile", "domain", "source_revision"},
            issues,
        )
        _non_empty_string(strategy.get("profile"), "strategy.profile", issues)
        _non_empty_string(strategy.get("domain"), "strategy.domain", issues)
        _source_revision(
            strategy.get("source_revision"), "strategy.source_revision", issues
        )

    input_provenance = _object(
        payload.get("input_provenance"), "input_provenance", issues
    )
    if input_provenance is not None:
        allowed = {
            "source",
            "source_revision",
            "license",
            "usage_scope",
            "range",
            "timestamp",
            "manifest_sha256",
        }
        _closed_object(input_provenance, "input_provenance", allowed, allowed, issues)
        for field in ("source", "source_revision", "license", "usage_scope"):
            _non_empty_string(
                input_provenance.get(field), f"input_provenance.{field}", issues
            )
        input_range = _object(
            input_provenance.get("range"), "input_provenance.range", issues
        )
        if input_range is not None:
            _closed_object(
                input_range,
                "input_provenance.range",
                {"start", "end"},
                {"start", "end"},
                issues,
            )
            start = _calendar_date(
                input_range.get("start"), "input_provenance.range.start", issues
            )
            end = _calendar_date(
                input_range.get("end"), "input_provenance.range.end", issues
            )
            if start is not None and end is not None and start > end:
                issues.append("input_provenance.range boundaries are reversed")
        input_timestamp = _timezone_datetime(
            input_provenance.get("timestamp"), "input_provenance.timestamp", issues
        )
        if (
            generated_at is not None
            and input_timestamp is not None
            and input_timestamp > generated_at
        ):
            issues.append("input_provenance.timestamp cannot be after generated_at")
        _sha256(
            input_provenance.get("manifest_sha256"),
            "input_provenance.manifest_sha256",
            issues,
        )

    artifacts = _validate_artifacts(payload.get("artifacts"), base_dir, issues)
    metrics = _object(payload.get("metrics"), "metrics", issues)
    if metrics is not None:
        _closed_object(
            metrics, "metrics", set(_METRIC_FIELDS), set(_METRIC_FIELDS), issues
        )
        for field in _METRIC_FIELDS:
            if field == "trade_count":
                _finite_integer(
                    metrics.get(field), f"metrics.{field}", issues, minimum=0
                )
            else:
                _finite_number(metrics.get(field), f"metrics.{field}", issues)
        win_rate = metrics.get("win_rate")
        if _is_finite_number(win_rate) and not 0 <= float(win_rate) <= 1:
            issues.append("metrics.win_rate must be between 0 and 1")

    cost_stress = _validate_cost_stress(payload.get("cost_stress"), issues)
    _validate_risk_assessment(payload.get("risk_assessment"), issues)
    _validate_backtest(
        payload.get("backtest"),
        strategy,
        input_provenance,
        cost_stress,
        issues,
    )

    digests = _object(payload.get("digests"), "digests", issues)
    digest_fields = {
        *_ARTIFACT_DIGEST_FIELDS.values(),
        "evidence_core_sha256",
        "package_sha256",
    }
    if digests is not None:
        _closed_object(digests, "digests", digest_fields, digest_fields, issues)
        for field in sorted(digest_fields):
            _sha256(digests.get(field), f"digests.{field}", issues)
        for artifact_name, digest_field in _ARTIFACT_DIGEST_FIELDS.items():
            artifact = artifacts.get(artifact_name) if artifacts is not None else None
            if isinstance(artifact, Mapping) and digests.get(
                digest_field
            ) != artifact.get("sha256"):
                issues.append(
                    f"digests.{digest_field} must match artifacts.{artifact_name}.sha256"
                )
        if input_provenance is not None and digests.get(
            "data_manifest_sha256"
        ) != input_provenance.get("manifest_sha256"):
            issues.append(
                "input_provenance.manifest_sha256 must match digests.data_manifest_sha256"
            )

    expected_core_sha256: str | None = None
    try:
        core = {field: payload[field] for field in _CORE_FIELDS}
        expected_core_sha256 = hashlib.sha256(
            canonical_evidence_package_v2_bytes(core)
        ).hexdigest()
    except (KeyError, TypeError, ValueError) as exc:
        issues.append(f"evidence core cannot be canonicalized: {exc}")
    if (
        expected_core_sha256 is not None
        and digests is not None
        and digests.get("evidence_core_sha256") != expected_core_sha256
    ):
        issues.append("digests.evidence_core_sha256 mismatch")

    acceptance_ok = _validate_human_acceptance(
        payload.get("human_acceptance"),
        generated_at=generated_at,
        evidence_core_sha256=expected_core_sha256,
        issues=issues,
    )
    _validate_lifecycle_claims(
        payload.get("lifecycle_claims"), acceptance_ok=acceptance_ok, issues=issues
    )

    if digests is not None and _SHA256_RE.fullmatch(
        str(digests.get("package_sha256") or "")
    ):
        try:
            package_projection = copy.deepcopy(dict(payload))
            package_projection["digests"].pop("package_sha256", None)
            expected_package_sha256 = hashlib.sha256(
                canonical_evidence_package_v2_bytes(package_projection)
            ).hexdigest()
            if digests.get("package_sha256") != expected_package_sha256:
                issues.append("digests.package_sha256 mismatch")
        except (TypeError, ValueError) as exc:
            issues.append(f"package cannot be canonicalized: {exc}")

    return tuple(dict.fromkeys(issues))


def validate_strategy_evidence_payload(
    payload: Any, *, base_dir: Path | None = None
) -> list[str]:
    """Compatibility dispatcher; v2 and legacy lanes share one implementation."""

    if (
        isinstance(payload, Mapping)
        and payload.get("schema_version") == STRATEGY_EVIDENCE_PACKAGE_SCHEMA_VERSION
    ):
        return list(validate_evidence_package_v2(payload, base_dir=base_dir))
    return _validate_legacy_payload(payload, base_dir=base_dir)


def validate_strategy_evidence_file(path: str | Path) -> list[str]:
    evidence_path = Path(path)
    try:
        payload = read_evidence_package_v2_json(evidence_path)
    except ValueError as exc:
        return [str(exc)]
    return validate_strategy_evidence_payload(payload, base_dir=evidence_path.parent)


def _validate_artifacts(
    value: Any, base_dir: str | Path | None, issues: list[str]
) -> Mapping[str, Any] | None:
    artifacts = _object(value, "artifacts", issues)
    required = set(_ARTIFACT_DIGEST_FIELDS)
    if artifacts is None:
        return None
    _closed_object(artifacts, "artifacts", required, required, issues)
    root = Path(base_dir).resolve() if base_dir is not None else None
    for name in sorted(required):
        label = f"artifacts.{name}"
        artifact = _object(artifacts.get(name), label, issues)
        if artifact is None:
            continue
        _closed_object(artifact, label, {"path", "sha256"}, {"path", "sha256"}, issues)
        raw_path = artifact.get("path")
        expected_sha256 = artifact.get("sha256")
        _artifact_path(raw_path, f"{label}.path", issues)
        _sha256(expected_sha256, f"{label}.sha256", issues)
        if (
            root is None
            or not isinstance(raw_path, str)
            or not _valid_artifact_path(raw_path)
        ):
            continue
        candidate = root / raw_path
        try:
            resolved = candidate.resolve(strict=False)
            resolved.relative_to(root)
        except (OSError, ValueError):
            issues.append(
                f"{label}.path must stay within the evidence package directory"
            )
            continue
        if not resolved.is_file():
            issues.append(f"{label}.path does not exist: {raw_path}")
            continue
        try:
            actual_sha256 = hashlib.sha256(resolved.read_bytes()).hexdigest()
        except OSError as exc:
            issues.append(f"{label}.path cannot be read: {exc}")
            continue
        if isinstance(expected_sha256, str) and actual_sha256 != expected_sha256:
            issues.append(
                f"{label}.sha256 mismatch: expected {expected_sha256}, got {actual_sha256}"
            )
    return artifacts


def _validate_cost_stress(value: Any, issues: list[str]) -> Mapping[str, Any] | None:
    cost_stress = _object(value, "cost_stress", issues)
    if cost_stress is None:
        return None
    _closed_object(
        cost_stress,
        "cost_stress",
        {"scenarios", "status"},
        {"scenarios", "status"},
        issues,
    )
    if cost_stress.get("status") != "PASS":
        issues.append("cost_stress.status must equal PASS")
    scenarios = cost_stress.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != 3:
        issues.append(
            "cost_stress.scenarios must contain ordered 1x, 2x, and 3x scenarios"
        )
        return cost_stress
    for index, (scenario, multiplier) in enumerate(zip(scenarios, (1, 2, 3))):
        label = f"cost_stress.scenarios[{index}]"
        item = _object(scenario, label, issues)
        if item is None:
            continue
        _closed_object(
            item,
            label,
            {"multiplier", "total_cost_bps"},
            {"multiplier", "total_cost_bps"},
            issues,
        )
        if item.get("multiplier") != multiplier or isinstance(
            item.get("multiplier"), bool
        ):
            issues.append(f"{label}.multiplier must equal {multiplier}")
        _finite_number(
            item.get("total_cost_bps"), f"{label}.total_cost_bps", issues, minimum=0
        )
    return cost_stress


def _validate_risk_assessment(value: Any, issues: list[str]) -> None:
    risk = _object(value, "risk_assessment", issues)
    if risk is None:
        return
    allowed = {"status", "standard_id", "standard_sha256"}
    _closed_object(risk, "risk_assessment", allowed, allowed, issues)
    if risk.get("status") != "PASS":
        issues.append("risk_assessment.status must equal PASS")
    _non_empty_string(risk.get("standard_id"), "risk_assessment.standard_id", issues)
    _sha256(risk.get("standard_sha256"), "risk_assessment.standard_sha256", issues)


def _validate_backtest(
    value: Any,
    strategy: Mapping[str, Any] | None,
    input_provenance: Mapping[str, Any] | None,
    cost_stress: Mapping[str, Any] | None,
    issues: list[str],
) -> None:
    backtest = _object(value, "backtest", issues)
    if backtest is None:
        return
    allowed = {
        "orchestrator",
        "protocol",
        "calendar",
        "timezone",
        "signal_timing",
        "execution_timing",
        "locked_independent_oos",
        "promotion_run",
    }
    _closed_object(backtest, "backtest", allowed, allowed, issues)
    if backtest.get("orchestrator") != "BacktestOrchestrator":
        issues.append("backtest.orchestrator must equal BacktestOrchestrator")
    if backtest.get("protocol") != "purged_walk_forward.v1":
        issues.append("backtest.protocol must equal purged_walk_forward.v1")
    for field in ("calendar", "timezone", "signal_timing", "execution_timing"):
        _non_empty_string(backtest.get(field), f"backtest.{field}", issues)
    locked = _object(
        backtest.get("locked_independent_oos"),
        "backtest.locked_independent_oos",
        issues,
    )
    if locked is not None:
        fields = {"locked", "independent", "reused_for_selection"}
        _closed_object(
            locked, "backtest.locked_independent_oos", fields, fields, issues
        )
        if locked.get("locked") is not True:
            issues.append("backtest.locked_independent_oos.locked must be true")
        if locked.get("independent") is not True:
            issues.append("backtest.locked_independent_oos.independent must be true")
        if locked.get("reused_for_selection") is not False:
            issues.append(
                "backtest.locked_independent_oos.reused_for_selection must be false"
            )
    run = _object(backtest.get("promotion_run"), "backtest.promotion_run", issues)
    if run is None:
        return
    run_fields = {
        "strategy_profile",
        "domain",
        "folds",
        "fold_results",
        "locked_oos_result",
        "locked_oos_start",
        "locked_oos_end",
        "purge_days",
        "embargo_days",
        "source_revision",
        "cost_model",
    }
    _closed_object(run, "backtest.promotion_run", run_fields, run_fields, issues)
    if strategy is not None:
        if run.get("strategy_profile") != strategy.get("profile"):
            issues.append(
                "backtest.promotion_run.strategy_profile must match strategy.profile"
            )
        if run.get("domain") != strategy.get("domain"):
            issues.append("backtest.promotion_run.domain must match strategy.domain")
        if run.get("source_revision") != strategy.get("source_revision"):
            issues.append(
                "backtest.promotion_run.source_revision must match strategy.source_revision"
            )
    _source_revision(
        run.get("source_revision"), "backtest.promotion_run.source_revision", issues
    )
    purge_days = _finite_integer(
        run.get("purge_days"), "backtest.promotion_run.purge_days", issues, minimum=1
    )
    embargo_days = _finite_integer(
        run.get("embargo_days"),
        "backtest.promotion_run.embargo_days",
        issues,
        minimum=1,
    )
    locked_start = _calendar_date(
        run.get("locked_oos_start"), "backtest.promotion_run.locked_oos_start", issues
    )
    locked_end = _calendar_date(
        run.get("locked_oos_end"), "backtest.promotion_run.locked_oos_end", issues
    )
    if (
        locked_start is not None
        and locked_end is not None
        and locked_end < _add_calendar_months(locked_start, 12)
    ):
        issues.append(
            "backtest.promotion_run locked OOS must span at least 12 calendar months"
        )

    cost_model = _object(
        run.get("cost_model"), "backtest.promotion_run.cost_model", issues
    )
    cost_values: dict[str, float] = {}
    if cost_model is not None:
        cost_fields = {
            "model_id",
            "commission_bps",
            "slippage_bps",
            "market_impact_bps",
        }
        _closed_object(
            cost_model,
            "backtest.promotion_run.cost_model",
            cost_fields,
            cost_fields,
            issues,
        )
        _non_empty_string(
            cost_model.get("model_id"),
            "backtest.promotion_run.cost_model.model_id",
            issues,
        )
        for field in ("commission_bps", "slippage_bps", "market_impact_bps"):
            number = _finite_number(
                cost_model.get(field),
                f"backtest.promotion_run.cost_model.{field}",
                issues,
                minimum=0,
            )
            if number is not None:
                cost_values[field] = number
    if len(cost_values) == 3 and cost_stress is not None:
        scenarios = cost_stress.get("scenarios")
        if isinstance(scenarios, list) and len(scenarios) == 3:
            base_cost = sum(cost_values.values())
            for index, multiplier in enumerate((1, 2, 3)):
                scenario = scenarios[index]
                if isinstance(scenario, Mapping) and _is_finite_number(
                    scenario.get("total_cost_bps")
                ):
                    if not math.isclose(
                        float(scenario["total_cost_bps"]),
                        base_cost * multiplier,
                        rel_tol=0,
                        abs_tol=1e-12,
                    ):
                        issues.append(
                            f"cost_stress.scenarios[{index}].total_cost_bps must match {multiplier}x declared costs"
                        )

    folds = run.get("folds")
    fold_results = run.get("fold_results")
    if not isinstance(folds, list) or len(folds) < 3:
        issues.append(
            "backtest.promotion_run.folds must contain at least three ordered folds"
        )
        folds = []
    if not isinstance(fold_results, list) or len(fold_results) < 3:
        issues.append(
            "backtest.promotion_run.fold_results must contain at least three results"
        )
        fold_results = []
    if len(folds) != len(fold_results):
        issues.append("backtest.promotion_run fold/result counts must match")

    parsed_folds: list[tuple[date, date, date, date]] = []
    previous_test_end: date | None = None
    for index, fold_value in enumerate(folds):
        fold = _object(fold_value, f"backtest.promotion_run.folds[{index}]", issues)
        if fold is None:
            continue
        fold_fields = {"train_start", "train_end", "test_start", "test_end"}
        _closed_object(
            fold,
            f"backtest.promotion_run.folds[{index}]",
            fold_fields,
            fold_fields,
            issues,
        )
        boundaries = tuple(
            _calendar_date(
                fold.get(field),
                f"backtest.promotion_run.folds[{index}].{field}",
                issues,
            )
            for field in ("train_start", "train_end", "test_start", "test_end")
        )
        if any(boundary is None for boundary in boundaries):
            continue
        train_start, train_end, test_start, test_end = boundaries
        assert train_start and train_end and test_start and test_end
        if train_start > train_end or test_start > test_end:
            issues.append(
                f"backtest.promotion_run.folds[{index}] boundaries are reversed"
            )
        if (
            purge_days is not None
            and train_end + timedelta(days=purge_days) >= test_start
        ):
            issues.append(f"backtest.promotion_run.folds[{index}] violates purge")
        if (
            previous_test_end is not None
            and embargo_days is not None
            and previous_test_end + timedelta(days=embargo_days) >= train_start
        ):
            issues.append(
                f"backtest.promotion_run.folds[{index}] violates ordered embargo"
            )
        parsed_folds.append((train_start, train_end, test_start, test_end))
        previous_test_end = test_end
    if (
        previous_test_end is not None
        and locked_start is not None
        and embargo_days is not None
        and previous_test_end + timedelta(days=embargo_days) >= locked_start
    ):
        issues.append("backtest.promotion_run locked OOS overlaps folds or embargo")
    if input_provenance is not None and parsed_folds and locked_end is not None:
        input_range = input_provenance.get("range")
        if isinstance(input_range, Mapping):
            try:
                input_start = date.fromisoformat(str(input_range.get("start")))
                input_end = date.fromisoformat(str(input_range.get("end")))
            except ValueError:
                pass
            else:
                if input_start > parsed_folds[0][0] or input_end < locked_end:
                    issues.append(
                        "input_provenance.range must cover every fold and locked OOS window"
                    )

    for index, result in enumerate(fold_results):
        fold = parsed_folds[index] if index < len(parsed_folds) else None
        _validate_backtest_result(
            result,
            label=f"backtest.promotion_run.fold_results[{index}]",
            strategy=strategy,
            run=run,
            cost_values=cost_values,
            fold_role="test",
            fold=fold,
            locked_start=locked_start,
            locked_end=locked_end,
            issues=issues,
        )
    _validate_backtest_result(
        run.get("locked_oos_result"),
        label="backtest.promotion_run.locked_oos_result",
        strategy=strategy,
        run=run,
        cost_values=cost_values,
        fold_role="locked_oos",
        fold=(None, None, locked_start, locked_end)
        if locked_start is not None and locked_end is not None
        else None,
        locked_start=locked_start,
        locked_end=locked_end,
        issues=issues,
    )


def _validate_backtest_result(
    value: Any,
    *,
    label: str,
    strategy: Mapping[str, Any] | None,
    run: Mapping[str, Any],
    cost_values: Mapping[str, float],
    fold_role: str,
    fold: tuple[date | None, date | None, date | None, date | None] | None,
    locked_start: date | None,
    locked_end: date | None,
    issues: list[str],
) -> None:
    result = _object(value, label, issues)
    if result is None:
        return
    required = {
        "strategy_profile",
        "domain",
        "start_date",
        "end_date",
        "source_revision",
        "cost_model",
        "cost_inputs",
        "validation_identity",
        "sharpe_ratio",
        "max_drawdown",
        "cagr",
        "observation_count",
        "run_duration_seconds",
    }
    _closed_object(result, label, required, _RESULT_FIELDS, issues)
    if strategy is not None:
        if result.get("strategy_profile") != strategy.get("profile"):
            issues.append(f"{label}.strategy_profile mismatch")
        if result.get("domain") != strategy.get("domain"):
            issues.append(f"{label}.domain mismatch")
        if result.get("source_revision") != strategy.get("source_revision"):
            issues.append(f"{label}.source_revision mismatch")
    cost_model = run.get("cost_model")
    model_id = cost_model.get("model_id") if isinstance(cost_model, Mapping) else None
    if result.get("cost_model") != model_id:
        issues.append(f"{label}.cost_model mismatch")
    for field in _RESULT_NUMBER_FIELDS:
        if field not in result:
            continue
        if field in {"observation_count", "param_version"}:
            _finite_integer(result.get(field), f"{label}.{field}", issues, minimum=0)
        elif result.get(field) is not None:
            _finite_number(result.get(field), f"{label}.{field}", issues)
    if (
        _is_finite_number(result.get("observation_count"))
        and int(result["observation_count"]) <= 0
    ):
        issues.append(f"{label}.observation_count must be positive")
    if (
        _is_finite_number(result.get("run_duration_seconds"))
        and float(result["run_duration_seconds"]) < 0
    ):
        issues.append(f"{label}.run_duration_seconds must be non-negative")
    start_date = _calendar_date(result.get("start_date"), f"{label}.start_date", issues)
    end_date = _calendar_date(result.get("end_date"), f"{label}.end_date", issues)
    if fold is not None and (start_date, end_date) != (fold[2], fold[3]):
        issues.append(f"{label} dates must match the orchestrator window")
    inputs = _object(result.get("cost_inputs"), f"{label}.cost_inputs", issues)
    if inputs is not None:
        fields = {"commission_bps", "slippage_bps", "market_impact_bps"}
        _closed_object(inputs, f"{label}.cost_inputs", fields, fields, issues)
        for field in fields:
            number = _finite_number(
                inputs.get(field), f"{label}.cost_inputs.{field}", issues, minimum=0
            )
            if (
                number is not None
                and field in cost_values
                and number != cost_values[field]
            ):
                issues.append(f"{label}.cost_inputs.{field} mismatch")
    identity = _object(
        result.get("validation_identity"), f"{label}.validation_identity", issues
    )
    if identity is None:
        return
    identity_fields = {
        "protocol",
        "fold_id",
        "fold_role",
        "train_start",
        "train_end",
        "test_start",
        "test_end",
        "locked_oos_start",
        "locked_oos_end",
        "purge_days",
        "embargo_days",
    }
    _closed_object(
        identity,
        f"{label}.validation_identity",
        identity_fields,
        identity_fields,
        issues,
    )
    if identity.get("protocol") != "purged_walk_forward.v1":
        issues.append(f"{label}.validation_identity.protocol mismatch")
    _non_empty_string(
        identity.get("fold_id"), f"{label}.validation_identity.fold_id", issues
    )
    if identity.get("fold_role") != fold_role:
        issues.append(f"{label}.validation_identity.fold_role mismatch")
    identity_dates = {
        name: _calendar_date(
            identity.get(name), f"{label}.validation_identity.{name}", issues
        )
        for name in ("test_start", "test_end", "locked_oos_start", "locked_oos_end")
    }
    for name in ("train_start", "train_end"):
        if fold_role == "locked_oos":
            if identity.get(name) is not None:
                issues.append(f"{label}.validation_identity.{name} must be null")
        else:
            identity_dates[name] = _calendar_date(
                identity.get(name), f"{label}.validation_identity.{name}", issues
            )
    if fold is not None:
        expected = {
            "train_start": fold[0],
            "train_end": fold[1],
            "test_start": fold[2],
            "test_end": fold[3],
        }
        for name, expected_value in expected.items():
            if fold_role != "locked_oos" or name.startswith("test"):
                if identity_dates.get(name) != expected_value:
                    issues.append(f"{label}.validation_identity.{name} mismatch")
    if (
        identity_dates.get("locked_oos_start") != locked_start
        or identity_dates.get("locked_oos_end") != locked_end
    ):
        issues.append(f"{label}.validation_identity locked OOS mismatch")
    for name in ("purge_days", "embargo_days"):
        value_number = _finite_integer(
            identity.get(name), f"{label}.validation_identity.{name}", issues, minimum=1
        )
        if value_number is not None and value_number != run.get(name):
            issues.append(f"{label}.validation_identity.{name} mismatch")


def _validate_human_acceptance(
    value: Any,
    *,
    generated_at: datetime | None,
    evidence_core_sha256: str | None,
    issues: list[str],
) -> bool:
    if value is None:
        return False
    acceptance = _object(value, "human_acceptance", issues)
    if acceptance is None:
        return False
    fields = {
        "decision",
        "acceptance_id",
        "actor",
        "accepted_at",
        "authority_receipt_sha256",
        "evidence_core_sha256",
    }
    _closed_object(acceptance, "human_acceptance", fields, fields, issues)
    if acceptance.get("decision") not in {"ACCEPTED", "REJECTED"}:
        issues.append("human_acceptance.decision must be ACCEPTED or REJECTED")
    _non_empty_string(
        acceptance.get("acceptance_id"), "human_acceptance.acceptance_id", issues
    )
    _non_empty_string(acceptance.get("actor"), "human_acceptance.actor", issues)
    accepted_at = _timezone_datetime(
        acceptance.get("accepted_at"), "human_acceptance.accepted_at", issues
    )
    _sha256(
        acceptance.get("authority_receipt_sha256"),
        "human_acceptance.authority_receipt_sha256",
        issues,
    )
    _sha256(
        acceptance.get("evidence_core_sha256"),
        "human_acceptance.evidence_core_sha256",
        issues,
    )
    matches = (
        evidence_core_sha256 is not None
        and acceptance.get("evidence_core_sha256") == evidence_core_sha256
    )
    if not matches:
        issues.append("human_acceptance.evidence_core_sha256 mismatch")
    current = (
        generated_at is not None
        and accepted_at is not None
        and accepted_at >= generated_at
    )
    return acceptance.get("decision") == "ACCEPTED" and matches and current


def _validate_lifecycle_claims(
    value: Any, *, acceptance_ok: bool, issues: list[str]
) -> None:
    claims = _object(value, "lifecycle_claims", issues)
    if claims is None:
        return
    fields = {
        "learning_only",
        "promotion_eligible",
        "live_ready",
        "size_zero_required",
        "no_order",
    }
    _closed_object(claims, "lifecycle_claims", fields, fields, issues)
    for field in fields:
        if not isinstance(claims.get(field), bool):
            issues.append(f"lifecycle_claims.{field} must be a boolean")
    if claims.get("live_ready") is not False:
        issues.append("lifecycle_claims.live_ready must remain false")
    if claims.get("size_zero_required") is not True:
        issues.append("lifecycle_claims.size_zero_required must remain true")
    if claims.get("no_order") is not True:
        issues.append("lifecycle_claims.no_order must remain true")
    if (
        claims.get("learning_only") is True
        and claims.get("promotion_eligible") is not False
    ):
        issues.append("learning_only requires promotion_eligible=false")
    if claims.get("promotion_eligible") is True:
        if claims.get("learning_only") is True:
            issues.append("learning_only evidence cannot be promotion_eligible")
        if not acceptance_ok:
            issues.append(
                "promotion_eligible=true requires current bound human_acceptance"
            )


def _validate_legacy_payload(payload: Any, *, base_dir: Path | None) -> list[str]:
    issues: list[str] = []
    if not isinstance(payload, dict):
        return ["top-level JSON must be an object"]
    required = (
        "schema_version",
        "profile",
        "market",
        "requested_stage",
        "generated_at",
        "evidence_package_id",
        "artifacts",
        "validation",
        "risk",
        "kelly_readiness",
        "ai_optimization",
    )
    for field in required:
        if field not in payload:
            issues.append(f"missing required field: {field}")
    for field in ("schema_version", "profile", "market", "evidence_package_id"):
        _legacy_non_empty(payload, field, issues)
    requested_stage = payload.get("requested_stage")
    if not isinstance(requested_stage, str) or not requested_stage.strip():
        issues.append("requested_stage must be a non-empty string")
    elif requested_stage not in _LEGACY_ALLOWED_REQUESTED_STAGES:
        issues.append(f"unsupported requested_stage: {requested_stage!r}")
    generated_at = payload.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.strip():
        issues.append("generated_at must be a non-empty string")
    elif _parse_legacy_datetime(generated_at) is None:
        issues.append(f"generated_at is not a valid date-time: {generated_at!r}")
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        issues.append("artifacts must be an object")
    else:
        for name in _LEGACY_ARTIFACTS:
            artifact = artifacts.get(name)
            if not isinstance(artifact, dict):
                issues.append(f"artifacts.{name} must be an object")
                continue
            _legacy_non_empty(artifact, "path", issues, prefix=f"artifacts.{name}")
            sha = artifact.get("sha256")
            if not isinstance(sha, str) or not re.fullmatch(r"[A-Fa-f0-9]{64}", sha):
                issues.append(
                    f"artifacts.{name}.sha256 must be a 64-character hex string"
                )
            elif base_dir is not None:
                _legacy_artifact_file(name, artifact, sha, base_dir, issues)
    validation = payload.get("validation")
    if not isinstance(validation, dict):
        issues.append("validation must be an object")
    else:
        for flag in ("oos_passed", "overfit_report_present"):
            if not isinstance(validation.get(flag), bool):
                issues.append(f"validation.{flag} must be a boolean")
            if (
                requested_stage in {"live_candidate", "live_enabled", "runtime_enabled"}
                and validation.get(flag) is not True
            ):
                issues.append(f"{requested_stage} requires validation.{flag}=true")
    risk = payload.get("risk")
    if not isinstance(risk, dict):
        issues.append("risk must be an object")
    else:
        metrics = risk.get("metrics")
        if not isinstance(metrics, dict):
            issues.append("risk.metrics must be an object")
        else:
            for field in _LEGACY_METRICS:
                value = metrics.get(field)
                if field == "trade_count":
                    if not _is_integer(value):
                        issues.append("risk.metrics.trade_count must be an integer")
                    elif value < 0:
                        issues.append("risk.metrics.trade_count must be >= 0")
                elif not _is_finite_number(value):
                    issues.append(f"risk.metrics.{field} must be a number")
            if (
                _is_finite_number(metrics.get("win_rate"))
                and not 0 <= metrics["win_rate"] <= 1
            ):
                issues.append("risk.metrics.win_rate must be between 0 and 1")
        benchmark = risk.get("benchmark")
        if not isinstance(benchmark, dict):
            issues.append("risk.benchmark must be an object")
        else:
            _legacy_non_empty(benchmark, "name", issues, prefix="risk.benchmark")
            for field in ("alpha", "beta"):
                if not _is_finite_number(benchmark.get(field)):
                    issues.append(f"risk.benchmark.{field} must be a number")
        cost = risk.get("cost_stress")
        if not isinstance(cost, dict):
            issues.append("risk.cost_stress must be an object")
        else:
            for field in ("slippage_bps", "commission_bps"):
                if not _is_finite_number(cost.get(field)):
                    issues.append(f"risk.cost_stress.{field} must be a number")
            if not isinstance(cost.get("passed"), bool):
                issues.append("risk.cost_stress.passed must be a boolean")
        oos = risk.get("oos")
        if not isinstance(oos, dict):
            issues.append("risk.oos must be an object")
        else:
            for field in ("window_start", "window_end"):
                _legacy_non_empty(oos, field, issues, prefix="risk.oos")
            if not isinstance(oos.get("locked"), bool):
                issues.append("risk.oos.locked must be a boolean")
    kelly = payload.get("kelly_readiness")
    if not isinstance(kelly, dict):
        issues.append("kelly_readiness must be an object")
    else:
        if kelly.get("level") not in _LEGACY_KELLY_LEVELS:
            issues.append("kelly_readiness.level must be one of K0, K1, K2, K3, K4")
        if kelly.get("full_kelly_allowed") is not False:
            issues.append("kelly_readiness.full_kelly_allowed must be false")
    if not isinstance(payload.get("ai_optimization"), dict):
        issues.append("ai_optimization must be an object")
    return issues


def _legacy_artifact_file(
    name: str,
    artifact: Mapping[str, Any],
    expected_sha256: str,
    base_dir: Path,
    issues: list[str],
) -> None:
    raw_path = str(artifact.get("path") or "").strip()
    label = f"artifacts.{name}"
    if not raw_path:
        return
    if not _valid_artifact_path(raw_path):
        if Path(raw_path).is_absolute():
            issues.append(f"{label}.path must be repo-relative, got absolute path")
        else:
            issues.append(
                f"{label}.path must stay within the evidence package directory"
            )
        return
    root = base_dir.resolve()
    resolved = (root / raw_path).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError:
        issues.append(f"{label}.path must stay within the evidence package directory")
        return
    if not resolved.is_file():
        issues.append(f"{label}.path does not exist: {raw_path}")
        return
    actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
    if actual.lower() != expected_sha256.lower():
        issues.append(
            f"{label}.sha256 mismatch: expected {expected_sha256.lower()}, got {actual.lower()}"
        )


def _closed_object(
    value: Mapping[str, Any],
    label: str,
    required: set[str] | frozenset[str],
    allowed: set[str] | frozenset[str],
    issues: list[str],
) -> None:
    for field in sorted(required - set(value)):
        issues.append(f"{label} missing required field: {field}")
    for field in sorted(set(value) - allowed):
        issues.append(f"{label} contains unexpected field: {field}")


def _object(value: Any, label: str, issues: list[str]) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        issues.append(f"{label} must be an object")
        return None
    return value


def _non_empty_string(value: Any, label: str, issues: list[str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        issues.append(f"{label} must be a non-empty string")
        return None
    return value


def _source_revision(value: Any, label: str, issues: list[str]) -> str | None:
    if not isinstance(value, str) or not _SOURCE_REVISION_RE.fullmatch(value):
        issues.append(f"{label} must be a lowercase 40-character Git revision")
        return None
    return value


def _sha256(value: Any, label: str, issues: list[str]) -> str | None:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        issues.append(f"{label} must be a lowercase SHA-256")
        return None
    return value


def _finite_number(
    value: Any, label: str, issues: list[str], *, minimum: float | None = None
) -> float | None:
    if not _is_finite_number(value):
        issues.append(f"{label} must be a finite non-boolean number")
        return None
    number = float(value)
    if minimum is not None and number < minimum:
        issues.append(f"{label} must be >= {minimum:g}")
        return None
    return number


def _finite_integer(
    value: Any, label: str, issues: list[str], *, minimum: int | None = None
) -> int | None:
    if not _is_integer(value):
        issues.append(f"{label} must be an integer")
        return None
    if minimum is not None and value < minimum:
        issues.append(f"{label} must be >= {minimum}")
        return None
    return value


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _calendar_date(value: Any, label: str, issues: list[str]) -> date | None:
    if not isinstance(value, str):
        issues.append(f"{label} must be an ISO calendar date")
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        issues.append(f"{label} must be an ISO calendar date")
        return None
    if parsed.isoformat() != value:
        issues.append(f"{label} must use canonical YYYY-MM-DD form")
        return None
    return parsed


def _parse_timezone_datetime(value: str) -> datetime | None:
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _parse_legacy_datetime(value: str) -> datetime | None:
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _timezone_datetime(value: Any, label: str, issues: list[str]) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        issues.append(f"{label} must be a timezone-qualified date-time")
        return None
    parsed = _parse_timezone_datetime(value)
    if parsed is None:
        issues.append(f"{label} must be a timezone-qualified date-time")
    return parsed


def _artifact_path(value: Any, label: str, issues: list[str]) -> None:
    if not isinstance(value, str) or not _valid_artifact_path(value):
        issues.append(
            f"{label} must be a confined repo-relative path without aliases or control characters"
        )


def _valid_artifact_path(value: str) -> bool:
    if not value or Path(value).is_absolute() or "\\" in value:
        return False
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return False
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    return PurePosixPath(value).as_posix() == value


def _add_calendar_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def _legacy_non_empty(
    payload: Mapping[str, Any],
    field: str,
    issues: list[str],
    *,
    prefix: str | None = None,
) -> None:
    value = payload.get(field)
    label = f"{prefix}.{field}" if prefix else field
    if not isinstance(value, str) or not value.strip():
        issues.append(f"{label} must be a non-empty string")
