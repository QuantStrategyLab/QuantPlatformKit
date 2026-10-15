"""Contract tests for qsl.backtest_report.v1. Synthetic placeholders only."""

from __future__ import annotations

import copy
import dataclasses
import json
import random

import pytest
from jsonschema import Draft202012Validator

from quant_platform_kit.research_stats import (
    BacktestReportV1,
    BenchmarkSpec,
    CostModelSpec,
    DataSpec,
    MetricEntry,
    ReportGates,
    TimingSpec,
    TrialSummary,
    UncertaintySpec,
    VetoItem,
    WalkForwardFold,
    WalkForwardSpec,
    load_backtest_report_schema,
    probabilistic_sharpe_ratio,
)
from quant_platform_kit.research_stats.backtest_report import BacktestReportError

SYNTHETIC_SHA = "a" * 64


def _validator() -> Draft202012Validator:
    schema = load_backtest_report_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _report(**overrides) -> BacktestReportV1:
    rng = random.Random(5)
    synthetic = [rng.gauss(0.0, 0.01) for _ in range(60)]
    psr = probabilistic_sharpe_ratio(synthetic)
    fields = dict(
        report_id="synthetic-report",
        candidate_id="synthetic-candidate",
        source_revision="0" * 40,
        created_at="2026-10-10T00:00:00Z",
        data=DataSpec(SYNTHETIC_SHA, "synthetic-fixture", "n/a-synthetic", "XNYS", "2020-01-02", "2020-03-31", 60, "development"),
        timing=TimingSpec("as_of close", "next_open", "monthly"),
        cost_model=CostModelSpec("synthetic-cost", 1.0, 2.0, 0.0, (1.0, 2.0, 3.0), "T+2 sale settlement", True),
        benchmark=BenchmarkSpec("synthetic-benchmark", "unleveraged underlying"),
        trials=TrialSummary(3, 1, 1, "pre-declared: max log growth", SYNTHETIC_SHA),
        walk_forward=WalkForwardSpec(
            "purged_walk_forward.v1",
            (WalkForwardFold("2020-01-02", "2020-01-31", "2020-02-10", "2020-02-28"),),
            None,
        ),
        status="DEVELOPMENT_ONLY",
        metrics=(
            MetricEntry("psr", 1.0, psr.status, psr.value, psr.reason_code),
            MetricEntry("dsr", 1.0, "NOT_COMPUTED", None, "trial_sharpes_not_supplied"),
        ),
        uncertainty=UncertaintySpec(5.0, 1000, 42, 0.95),
        gates=ReportGates(("log_growth",), ("log_growth",), (VetoItem("log_growth", ">", 0.0, "2026-10-10", "human"),)),
        limitations=("synthetic fixture; not a backtest result",),
    )
    fields.update(overrides)
    return BacktestReportV1(**fields)


def test_valid_report_matches_schema_and_round_trips() -> None:
    report = _report()
    payload = report.to_dict()
    _validator().validate(payload)
    assert json.loads(report.to_json()) == payload
    assert payload["live_ready"] is False and payload["no_order"] is True
    assert payload["schema_version"] == "qsl.backtest_report.v1"


def test_live_flags_cannot_be_flipped() -> None:
    with pytest.raises(BacktestReportError):
        _report(live_ready=True)
    with pytest.raises(BacktestReportError):
        _report(no_order=False)
    payload = _report().to_dict()
    for key, value in (("live_ready", True), ("no_order", False)):
        bad = copy.deepcopy(payload)
        bad[key] = value
        assert list(_validator().iter_errors(bad))


def test_missing_metric_is_never_a_number() -> None:
    with pytest.raises(BacktestReportError):
        MetricEntry("dsr", 1.0, "UNCOMPUTABLE", 0.0, "insufficient_trials")
    with pytest.raises(BacktestReportError):
        MetricEntry("dsr", 1.0, "COMPUTED", None)
    with pytest.raises(BacktestReportError):
        MetricEntry("dsr", 1.0, "NOT_COMPUTED", None, None)
    bad = _report().to_dict()
    bad["metrics"][1]["value"] = 0.0
    assert list(_validator().iter_errors(bad))
    bad = _report().to_dict()
    bad["metrics"][0]["value"] = None
    assert list(_validator().iter_errors(bad))


def test_development_data_cannot_be_labelled_oos() -> None:
    with pytest.raises(BacktestReportError):
        _report(status="OOS_EVALUATED")
    bad = _report().to_dict()
    bad["status"] = "OOS_EVALUATED"
    assert list(_validator().iter_errors(bad))
    ok = _report().to_dict()
    ok["status"] = "OOS_EVALUATED"
    ok["data"]["data_identity"] = "locked_oos"
    _validator().validate(ok)


def test_other_python_invariants() -> None:
    with pytest.raises(BacktestReportError):
        TrialSummary(2, 2, 1, "rule", SYNTHETIC_SHA)
    with pytest.raises(BacktestReportError):
        BenchmarkSpec("b", "r", same_dates=False)
    with pytest.raises(BacktestReportError):
        TimingSpec("as_of close", "same_close", "monthly")
    with pytest.raises(BacktestReportError):
        _report(metrics=(MetricEntry("psr", 4.0, "NOT_COMPUTED", None, "x"),))
    with pytest.raises(BacktestReportError):
        _report(source_revision="abc")
    with pytest.raises(BacktestReportError):
        WalkForwardFold("2020-01-02", "2020-02-15", "2020-02-10", "2020-02-28")


def test_schema_rejects_unknown_fields() -> None:
    bad = _report().to_dict()
    bad["sharpe_pass"] = True
    assert list(_validator().iter_errors(bad))


def test_dataclass_is_frozen() -> None:
    report = _report()
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.live_ready = True  # type: ignore[misc]
