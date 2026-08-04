from __future__ import annotations

import copy
import hashlib
import importlib
import json
import math
from dataclasses import fields
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_VERSION = "strategy_evidence_package.v2"
SOURCE_REVISION = "a" * 40
CORE_FIELDS = (
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
ARTIFACT_NAMES = (
    "config",
    "data_manifest",
    "backtest",
    "risk",
    "information_coefficient",
    "cost_model",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _artifact_records(tmp_path: Path) -> dict[str, dict[str, str]]:
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    records: dict[str, dict[str, str]] = {}
    for name in ARTIFACT_NAMES:
        path = artifact_dir / f"{name}.json"
        path.write_bytes(_canonical({"artifact": name}))
        records[name] = {
            "path": path.relative_to(tmp_path).as_posix(),
            "sha256": _sha256(path.read_bytes()),
        }
    return records


def _folds() -> list[dict[str, str]]:
    return [
        {
            "train_start": "2015-01-01",
            "train_end": "2015-12-31",
            "test_start": "2016-01-03",
            "test_end": "2016-06-30",
        },
        {
            "train_start": "2016-07-03",
            "train_end": "2017-06-30",
            "test_start": "2017-07-03",
            "test_end": "2017-12-31",
        },
        {
            "train_start": "2018-01-03",
            "train_end": "2018-12-31",
            "test_start": "2019-01-03",
            "test_end": "2019-06-30",
        },
    ]


def _result(
    *,
    fold_id: str,
    fold_role: str,
    test_start: str,
    test_end: str,
    train_start: str | None,
    train_end: str | None,
) -> dict[str, Any]:
    return {
        "strategy_profile": "alpha_momentum",
        "domain": "us_equity",
        "sharpe_ratio": 1.2,
        "max_drawdown": -0.1,
        "cagr": 0.15,
        "observation_count": 126,
        "run_duration_seconds": 1.0,
        "start_date": test_start,
        "end_date": test_end,
        "source_revision": SOURCE_REVISION,
        "cost_model": "retail_us_equity_v1",
        "cost_inputs": {
            "commission_bps": 1.0,
            "slippage_bps": 2.0,
            "market_impact_bps": 0.5,
        },
        "validation_identity": {
            "protocol": "purged_walk_forward.v1",
            "fold_id": fold_id,
            "fold_role": fold_role,
            "train_start": train_start,
            "train_end": train_end,
            "test_start": test_start,
            "test_end": test_end,
            "locked_oos_start": "2019-07-03",
            "locked_oos_end": "2020-07-03",
            "purge_days": 1,
            "embargo_days": 1,
        },
    }


def _promotion_run() -> dict[str, Any]:
    folds = _folds()
    fold_results = [
        _result(
            fold_id=f"promotion_wf{index}",
            fold_role="test",
            test_start=fold["test_start"],
            test_end=fold["test_end"],
            train_start=fold["train_start"],
            train_end=fold["train_end"],
        )
        for index, fold in enumerate(folds)
    ]
    return {
        "strategy_profile": "alpha_momentum",
        "domain": "us_equity",
        "folds": folds,
        "fold_results": fold_results,
        "locked_oos_result": _result(
            fold_id="promotion_locked_oos",
            fold_role="locked_oos",
            test_start="2019-07-03",
            test_end="2020-07-03",
            train_start=None,
            train_end=None,
        ),
        "locked_oos_start": "2019-07-03",
        "locked_oos_end": "2020-07-03",
        "purge_days": 1,
        "embargo_days": 1,
        "source_revision": SOURCE_REVISION,
        "cost_model": {
            "model_id": "retail_us_equity_v1",
            "commission_bps": 1.0,
            "slippage_bps": 2.0,
            "market_impact_bps": 0.5,
        },
    }


def _refresh_digests(payload: dict[str, Any], *, bind_acceptance: bool = True) -> None:
    core = {key: payload[key] for key in CORE_FIELDS}
    core_sha256 = _sha256(_canonical(core))
    payload["digests"]["evidence_core_sha256"] = core_sha256
    acceptance = payload.get("human_acceptance")
    if bind_acceptance and isinstance(acceptance, dict):
        acceptance["evidence_core_sha256"] = core_sha256
    package_projection = copy.deepcopy(payload)
    package_projection["digests"].pop("package_sha256", None)
    payload["digests"]["package_sha256"] = _sha256(_canonical(package_projection))


def _payload(
    tmp_path: Path,
    *,
    learning_only: bool = False,
    accepted: bool = True,
    promotion_eligible: bool | None = None,
    requested_stage: str = "ai_monitored_candidate",
) -> dict[str, Any]:
    artifacts = _artifact_records(tmp_path)
    if promotion_eligible is None:
        promotion_eligible = accepted and not learning_only
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "evidence_package_id": "pkg_20260805_001",
        "generated_at": "2026-08-05T00:00:00Z",
        "requested_stage": requested_stage,
        "strategy": {
            "profile": "alpha_momentum",
            "domain": "us_equity",
            "source_revision": SOURCE_REVISION,
        },
        "input_provenance": {
            "source": "licensed_fixture_provider",
            "source_revision": "dataset-2026-08-01",
            "license": "personal_internal_research",
            "usage_scope": "non-commercial internal research",
            "range": {"start": "2015-01-01", "end": "2020-07-03"},
            "timestamp": "2026-08-04T23:00:00Z",
            "manifest_sha256": artifacts["data_manifest"]["sha256"],
        },
        "backtest": {
            "orchestrator": "BacktestOrchestrator",
            "protocol": "purged_walk_forward.v1",
            "calendar": "XNYS",
            "timezone": "America/New_York",
            "signal_timing": "close_t",
            "execution_timing": "open_t_plus_1",
            "locked_independent_oos": {
                "locked": True,
                "independent": True,
                "reused_for_selection": False,
            },
            "promotion_run": _promotion_run(),
        },
        "artifacts": artifacts,
        "metrics": {
            "sharpe_ratio": 1.42,
            "sortino_ratio": 2.15,
            "max_drawdown": -0.12,
            "annualized_return": 0.18,
            "annualized_volatility": 0.22,
            "calmar_ratio": 1.5,
            "information_ratio": 0.83,
            "information_coefficient": 0.07,
            "var_95": -0.03,
            "cvar_95": -0.05,
            "turnover": 1.8,
            "trade_count": 128,
            "win_rate": 0.57,
            "profit_factor": 1.34,
        },
        "cost_stress": {
            "scenarios": [
                {"multiplier": 1, "total_cost_bps": 3.5},
                {"multiplier": 2, "total_cost_bps": 7.0},
                {"multiplier": 3, "total_cost_bps": 10.5},
            ],
            "status": "PASS",
        },
        "risk_assessment": {
            "status": "PASS",
            "standard_id": "docs/strategy_promotion_risk_standard.zh-CN.md",
            "standard_sha256": "f" * 64,
        },
        "digests": {
            "config_sha256": artifacts["config"]["sha256"],
            "data_manifest_sha256": artifacts["data_manifest"]["sha256"],
            "backtest_sha256": artifacts["backtest"]["sha256"],
            "risk_sha256": artifacts["risk"]["sha256"],
            "information_coefficient_sha256": artifacts["information_coefficient"][
                "sha256"
            ],
            "cost_model_sha256": artifacts["cost_model"]["sha256"],
            "evidence_core_sha256": "0" * 64,
            "package_sha256": "0" * 64,
        },
        "human_acceptance": None,
        "lifecycle_claims": {
            "learning_only": learning_only,
            "promotion_eligible": promotion_eligible,
            "live_ready": False,
            "size_zero_required": True,
            "no_order": True,
        },
    }
    if accepted and not learning_only:
        payload["human_acceptance"] = {
            "decision": "ACCEPTED",
            "acceptance_id": "promotion_acceptance_20260805",
            "actor": "human:operator",
            "accepted_at": "2026-08-05T00:05:00Z",
            "authority_receipt_sha256": "e" * 64,
            "evidence_core_sha256": "0" * 64,
        }
    _refresh_digests(payload)
    return payload


def _module():
    return importlib.import_module(
        "quant_platform_kit.strategy_lifecycle.evidence_package_v2"
    )


def _issues(
    payload: dict[str, Any], *, base_dir: Path | None = None
) -> tuple[str, ...]:
    return tuple(_module().validate_evidence_package_v2(payload, base_dir=base_dir))


def _set_path(payload: dict[str, Any], dotted_path: str, value: Any) -> None:
    target: Any = payload
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        target = target[int(part)] if part.isdigit() else target[part]
    if parts[-1].isdigit():
        target[int(parts[-1])] = value
    else:
        target[parts[-1]] = value


def test_v2_public_api_and_packaged_schema_exist() -> None:
    module = _module()

    assert module.STRATEGY_EVIDENCE_PACKAGE_SCHEMA_VERSION == SCHEMA_VERSION
    assert callable(module.read_evidence_package_v2_json)
    assert callable(module.validate_evidence_package_v2)
    assert callable(module.canonical_evidence_package_v2_bytes)
    schema = resources.files("quant_platform_kit.schemas").joinpath(
        "strategy-evidence-package.v2.schema.json"
    )
    assert schema.is_file()


def test_valid_learning_package_enforces_non_live_truth_vector(tmp_path: Path) -> None:
    payload = _payload(tmp_path, learning_only=True, accepted=False)

    assert _issues(payload, base_dir=tmp_path) == ()
    assert payload["lifecycle_claims"] == {
        "learning_only": True,
        "promotion_eligible": False,
        "live_ready": False,
        "size_zero_required": True,
        "no_order": True,
    }


def test_complete_package_without_acceptance_is_human_required(tmp_path: Path) -> None:
    from quant_platform_kit.strategy_lifecycle.evidence_gate import (
        validate_evidence_package,
    )

    payload = _payload(tmp_path, accepted=False, promotion_eligible=False)
    result = validate_evidence_package(payload, base_dir=tmp_path)

    assert result.valid
    assert result.promotion_status == "HUMAN_REQUIRED"
    assert result.promotion_eligible is False
    assert result.live_ready is False
    assert result.size_zero_required is True
    assert result.no_order is True


def test_bound_acceptance_can_promote_but_never_authorizes_live(tmp_path: Path) -> None:
    from quant_platform_kit.strategy_lifecycle.evidence_gate import (
        validate_evidence_package,
    )

    result = validate_evidence_package(_payload(tmp_path), base_dir=tmp_path)

    assert result.valid
    assert result.promotion_status == "PROMOTION_ELIGIBLE"
    assert result.promotion_eligible is True
    assert result.live_ready is False
    assert result.size_zero_required is True
    assert result.no_order is True


def test_accepts_exact_backtest_orchestrator_promotion_output(tmp_path: Path) -> None:
    from quant_platform_kit.strategy_lifecycle.backtest_orchestrator import (
        BacktestOrchestrator,
    )
    from quant_platform_kit.strategy_lifecycle.contracts import (
        BacktestResult,
        PromotionCostModel,
        PurgedWalkForwardFold,
    )
    from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore

    class Runner:
        @staticmethod
        def _result(start_date: date, end_date: date) -> BacktestResult:
            return BacktestResult(
                strategy_profile="alpha_momentum",
                domain="us_equity",
                param_set_id="candidate",
                params={},
                sharpe_ratio=1.2,
                max_drawdown=-0.1,
                cagr=0.15,
                start_date=start_date,
                end_date=end_date,
                observation_count=126,
                run_duration_seconds=1.0,
            )

        def run_purged_fold(
            self,
            strategy_profile: str,
            params: dict[str, Any],
            *,
            fold: PurgedWalkForwardFold,
            purge_days: int,
            embargo_days: int,
            cost_model: PromotionCostModel,
        ) -> BacktestResult:
            return self._result(fold.test_start, fold.test_end)

        def run_locked_oos(
            self,
            strategy_profile: str,
            params: dict[str, Any],
            *,
            start_date: date,
            end_date: date,
            cost_model: PromotionCostModel,
        ) -> BacktestResult:
            return self._result(start_date, end_date)

    orchestrator = BacktestOrchestrator(
        store=PerformanceStore(local_root=tmp_path / "store")
    )
    orchestrator.register_runner("us_equity", Runner())
    folds = [
        PurgedWalkForwardFold(
            date.fromisoformat(fold["train_start"]),
            date.fromisoformat(fold["train_end"]),
            date.fromisoformat(fold["test_start"]),
            date.fromisoformat(fold["test_end"]),
        )
        for fold in _folds()
    ]
    run = orchestrator.run_promotion(
        "alpha_momentum",
        domain="us_equity",
        params={},
        folds=folds,
        locked_oos_start=date(2019, 7, 3),
        locked_oos_end=date(2020, 7, 3),
        purge_days=1,
        embargo_days=1,
        source_revision=SOURCE_REVISION,
        cost_model=PromotionCostModel(
            model_id="retail_us_equity_v1",
            commission_bps=1.0,
            slippage_bps=2.0,
            market_impact_bps=0.5,
        ),
    )
    payload = _payload(tmp_path)
    payload["backtest"]["promotion_run"] = run.to_dict()
    _refresh_digests(payload)

    assert _issues(payload, base_dir=tmp_path) == ()


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("metrics.sharpe_ratio", None),
        ("metrics.max_drawdown", True),
        ("metrics.var_95", math.nan),
        ("metrics.information_coefficient", math.inf),
        ("cost_stress.scenarios.0.total_cost_bps", False),
        ("backtest.promotion_run.cost_model.slippage_bps", math.nan),
        ("backtest.promotion_run.fold_results.0.cost_inputs.commission_bps", math.inf),
    ],
)
def test_metrics_and_costs_are_present_non_bool_and_finite(
    tmp_path: Path, path: str, value: Any
) -> None:
    payload = _payload(tmp_path)
    if value is None:
        target: Any = payload
        parts = path.split(".")
        for part in parts[:-1]:
            target = target[int(part)] if part.isdigit() else target[part]
        target.pop(parts[-1])
    else:
        _set_path(payload, path, value)
    if not (isinstance(value, float) and not math.isfinite(value)):
        _refresh_digests(payload)

    assert _issues(payload, base_dir=tmp_path)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"schema_version":"strategy_evidence_package.v2","schema_version":"duplicate"}',
        b'{"value":NaN}',
        b'{"value":Infinity}',
        b'{"value":-Infinity}',
        b'{"value":1} trailing',
        b'{"value":"\xff"}',
    ],
)
def test_strict_json_reader_rejects_ambiguous_or_invalid_json(
    tmp_path: Path, raw: bytes
) -> None:
    path = tmp_path / "invalid.json"
    path.write_bytes(raw)

    with pytest.raises(ValueError):
        _module().read_evidence_package_v2_json(path)


def test_schema_and_python_parity_for_expressible_constraints(tmp_path: Path) -> None:
    module = _module()
    payload = _payload(tmp_path)
    schema = json.loads(
        resources.files("quant_platform_kit.schemas")
        .joinpath("strategy-evidence-package.v2.schema.json")
        .read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    assert list(validator.iter_errors(payload)) == []
    assert tuple(module.validate_evidence_package_v2(payload, base_dir=tmp_path)) == ()

    for dotted_path, value in (
        ("artifacts.config.path", "artifacts/config\u0000.json"),
        ("metrics.sharpe_ratio", True),
        ("backtest.promotion_run.purge_days", 0),
        ("input_provenance.timestamp", "2026-08-04T23:00:00"),
    ):
        candidate = copy.deepcopy(payload)
        _set_path(candidate, dotted_path, value)
        _refresh_digests(candidate)
        assert list(validator.iter_errors(candidate)), dotted_path
        assert tuple(
            module.validate_evidence_package_v2(candidate, base_dir=tmp_path)
        ), dotted_path


@pytest.mark.parametrize(
    "bad_path",
    [
        "../outside.json",
        "/tmp/absolute.json",
        "artifacts/../outside.json",
        "artifacts/config\n.json",
    ],
)
def test_artifact_paths_are_repo_relative_confined_and_unaliased(
    tmp_path: Path, bad_path: str
) -> None:
    payload = _payload(tmp_path)
    payload["artifacts"]["config"]["path"] = bad_path
    _refresh_digests(payload)

    assert _issues(payload, base_dir=tmp_path)


def test_artifact_symlink_escape_is_rejected(tmp_path: Path) -> None:
    payload = _payload(tmp_path)
    outside = tmp_path.parent / "qpk-evidence-outside.json"
    outside.write_text("outside", encoding="utf-8")
    link = tmp_path / "artifacts" / "escape.json"
    link.symlink_to(outside)
    payload["artifacts"]["config"] = {
        "path": link.relative_to(tmp_path).as_posix(),
        "sha256": _sha256(outside.read_bytes()),
    }
    payload["digests"]["config_sha256"] = payload["artifacts"]["config"]["sha256"]
    _refresh_digests(payload)

    assert _issues(payload, base_dir=tmp_path)


def test_artifact_bytes_and_all_digest_bindings_are_verified(tmp_path: Path) -> None:
    payload = _payload(tmp_path)
    config_path = tmp_path / payload["artifacts"]["config"]["path"]
    config_path.write_text("changed", encoding="utf-8")

    assert any(
        "config" in issue and "sha256" in issue
        for issue in _issues(payload, base_dir=tmp_path)
    )

    payload = _payload(tmp_path)
    payload["digests"]["risk_sha256"] = "1" * 64
    _refresh_digests(payload)
    assert any("risk_sha256" in issue for issue in _issues(payload, base_dir=tmp_path))

    payload = _payload(tmp_path)
    payload["human_acceptance"]["evidence_core_sha256"] = "2" * 64
    _refresh_digests(payload, bind_acceptance=False)
    assert any(
        "evidence_core_sha256" in issue for issue in _issues(payload, base_dir=tmp_path)
    )

    payload = _payload(tmp_path)
    payload["digests"]["package_sha256"] = "3" * 64
    assert any(
        "package_sha256" in issue for issue in _issues(payload, base_dir=tmp_path)
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "few_folds",
        "misordered",
        "zero_purge",
        "zero_embargo",
        "unlocked",
        "reused",
        "short_oos",
    ],
)
def test_backtest_orchestrator_identity_fails_closed(
    tmp_path: Path, mutation: str
) -> None:
    payload = _payload(tmp_path)
    run = payload["backtest"]["promotion_run"]
    if mutation == "few_folds":
        run["folds"] = run["folds"][:2]
        run["fold_results"] = run["fold_results"][:2]
    elif mutation == "misordered":
        run["folds"][0], run["folds"][1] = run["folds"][1], run["folds"][0]
    elif mutation == "zero_purge":
        run["purge_days"] = 0
    elif mutation == "zero_embargo":
        run["embargo_days"] = 0
    elif mutation == "unlocked":
        payload["backtest"]["locked_independent_oos"]["locked"] = False
    elif mutation == "reused":
        payload["backtest"]["locked_independent_oos"]["reused_for_selection"] = True
    else:
        run["locked_oos_end"] = "2020-07-02"
        run["locked_oos_result"]["end_date"] = "2020-07-02"
        run["locked_oos_result"]["validation_identity"]["test_end"] = "2020-07-02"
        run["locked_oos_result"]["validation_identity"]["locked_oos_end"] = "2020-07-02"
        for result in run["fold_results"]:
            result["validation_identity"]["locked_oos_end"] = "2020-07-02"
    _refresh_digests(payload)

    assert _issues(payload, base_dir=tmp_path)


def test_locked_oos_uses_calendar_months_across_leap_day(tmp_path: Path) -> None:
    payload = _payload(tmp_path)
    run = payload["backtest"]["promotion_run"]
    run["locked_oos_start"] = "2020-02-29"
    run["locked_oos_end"] = "2021-02-28"
    payload["input_provenance"]["range"]["end"] = "2021-02-28"
    run["locked_oos_result"]["start_date"] = "2020-02-29"
    run["locked_oos_result"]["end_date"] = "2021-02-28"
    run["locked_oos_result"]["validation_identity"]["test_start"] = "2020-02-29"
    run["locked_oos_result"]["validation_identity"]["test_end"] = "2021-02-28"
    for result in [*run["fold_results"], run["locked_oos_result"]]:
        identity = result["validation_identity"]
        identity["locked_oos_start"] = "2020-02-29"
        identity["locked_oos_end"] = "2021-02-28"
    _refresh_digests(payload)

    assert _issues(payload, base_dir=tmp_path) == ()


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("strategy.source_revision", "b" * 40),
        ("input_provenance.source_revision", ""),
        ("input_provenance.license", ""),
        ("input_provenance.range.start", "2016-01-01"),
        ("input_provenance.timestamp", "2026-08-04T23:00:00"),
        ("input_provenance.manifest_sha256", "b" * 64),
        ("backtest.orchestrator", "CallerLoop"),
        ("backtest.protocol", "walk_forward.v0"),
        ("backtest.calendar", ""),
        ("backtest.timezone", ""),
        ("backtest.signal_timing", ""),
        ("backtest.execution_timing", ""),
        ("backtest.promotion_run.strategy_profile", "other"),
        ("backtest.promotion_run.cost_model.model_id", "other_costs"),
        ("cost_stress.scenarios.1.total_cost_bps", 8.0),
        ("digests.config_sha256", "b" * 64),
        ("risk_assessment.status", "WARN"),
        ("cost_stress.status", "WARN"),
    ],
)
def test_strategy_input_backtest_cost_and_risk_identities_are_bound(
    tmp_path: Path, path: str, value: Any
) -> None:
    payload = _payload(tmp_path)
    _set_path(payload, path, value)
    _refresh_digests(payload)

    assert _issues(payload, base_dir=tmp_path)


@pytest.mark.parametrize(
    "condition", ["missing", "rejected", "stale", "digest_mismatch"]
)
def test_human_acceptance_must_be_current_accepted_and_bound(
    tmp_path: Path, condition: str
) -> None:
    payload = _payload(tmp_path)
    if condition == "missing":
        payload["human_acceptance"] = None
    elif condition == "rejected":
        payload["human_acceptance"]["decision"] = "REJECTED"
    elif condition == "stale":
        payload["human_acceptance"]["accepted_at"] = "2026-08-04T23:59:59Z"
    else:
        payload["human_acceptance"]["evidence_core_sha256"] = "d" * 64
    _refresh_digests(payload, bind_acceptance=False)

    issues = _issues(payload, base_dir=tmp_path)
    assert issues
    assert any(
        "promotion_eligible" in issue or "human_acceptance" in issue for issue in issues
    )


def test_requested_stage_and_caller_flags_cannot_create_live_truth(
    tmp_path: Path,
) -> None:
    payload = _payload(tmp_path, requested_stage="runtime_enabled")
    payload["lifecycle_claims"]["live_ready"] = True
    payload["ci_passed"] = True
    _refresh_digests(payload)

    issues = _issues(payload, base_dir=tmp_path)
    assert issues
    assert any("live_ready" in issue for issue in issues)
    assert any("unexpected" in issue or "additional" in issue for issue in issues)


def test_no_unfrozen_performance_threshold_is_invented(tmp_path: Path) -> None:
    payload = _payload(tmp_path)
    payload["metrics"]["sharpe_ratio"] = -7.0
    payload["metrics"]["annualized_return"] = -0.9
    payload["metrics"]["information_coefficient"] = -0.8
    _refresh_digests(payload)

    assert _issues(payload, base_dir=tmp_path) == ()


def test_backtest_result_identity_is_cross_checked(tmp_path: Path) -> None:
    payload = _payload(tmp_path)
    result = payload["backtest"]["promotion_run"]["fold_results"][0]
    result["source_revision"] = "b" * 40
    result["validation_identity"]["protocol"] = "caller_label.v1"
    _refresh_digests(payload)

    assert _issues(payload, base_dir=tmp_path)


def test_canonical_bytes_are_stable_and_reject_non_finite_values(
    tmp_path: Path,
) -> None:
    module = _module()
    payload = _payload(tmp_path)
    reordered = dict(reversed(list(payload.items())))

    assert module.canonical_evidence_package_v2_bytes(
        payload
    ) == module.canonical_evidence_package_v2_bytes(reordered)
    payload["metrics"]["sharpe_ratio"] = math.nan
    with pytest.raises((TypeError, ValueError)):
        module.canonical_evidence_package_v2_bytes(payload)


def test_legacy_dataclass_positional_order_is_unchanged() -> None:
    from quant_platform_kit.strategy_lifecycle.evidence_gate import (
        EvidenceGateResult,
        EvidencePackage,
    )

    assert [field.name for field in fields(EvidencePackage)][:12] == [
        "strategy_profile",
        "domain",
        "requested_stage",
        "target_platforms",
        "backtest_summary",
        "drift_notes",
        "platform_compatibility",
        "plugin_gate",
        "rollout_notes",
        "operator_notes",
        "evidence_version",
        "submitted_at",
    ]
    assert [field.name for field in fields(EvidenceGateResult)][:4] == [
        "valid",
        "package",
        "issues",
        "warnings",
    ]
    legacy = EvidenceGateResult(
        True, EvidencePackage("legacy_profile", "us_equity", "research_backtest_only")
    )
    assert set(legacy.to_dict()) == {"valid", "issues", "warnings", "package"}
