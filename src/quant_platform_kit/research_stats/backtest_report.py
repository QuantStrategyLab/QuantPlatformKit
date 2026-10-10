"""``qsl.backtest_report.v1`` dataclasses (research-only).

The dataclasses mirror ``schemas/backtest-report.v1.schema.json``. Python
validation enforces the invariants that matter most for honesty; the JSON
Schema is the full structural contract and is validated in tests.

Hard invariants: ``live_ready`` is always ``False`` and ``no_order`` always
``True``. A report is never an order, allocation, promotion or live permit.
A ``COMPUTED`` metric must carry a finite value; anything else carries
``value=None`` plus a ``reason_code`` (missing is never zero).
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import date
from importlib import resources
from typing import Any, Mapping

BACKTEST_REPORT_SCHEMA_VERSION = "qsl.backtest_report.v1"
SCHEMA_RESOURCE = "backtest-report.v1.schema.json"

DATA_IDENTITIES = ("development", "locked_oos", "forward")
EXECUTION_TIMINGS = ("next_open", "next_close", "same_close_research_only")
METRIC_STATUSES = ("COMPUTED", "UNCOMPUTABLE", "NOT_COMPUTED")
REPORT_STATUSES = ("UNCOMPUTABLE", "PARKED", "DEVELOPMENT_ONLY", "OOS_EVALUATED")
VETO_OPERATORS = ("<", "<=", ">", ">=", "==")

_SHA256 = re.compile(r"[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40}")


class BacktestReportError(ValueError):
    """Raised when a report would violate the v1 contract."""


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BacktestReportError(f"{label} must be a non-empty string")
    return value


def _iso(value: object, label: str) -> date:
    if not isinstance(value, str):
        raise BacktestReportError(f"{label} must be an ISO date string")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise BacktestReportError(f"{label} must be an ISO date string") from exc


def _number(value: object, label: str, *, minimum: float | None = None, exclusive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise BacktestReportError(f"{label} must be a finite number")
    number = float(value)
    if minimum is not None and (number <= minimum if exclusive else number < minimum):
        raise BacktestReportError(f"{label} out of range")
    return number


def _count(value: object, label: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise BacktestReportError(f"{label} must be an integer >= {minimum}")
    return value


def _choice(value: object, label: str, options: tuple[str, ...]) -> str:
    if value not in options:
        raise BacktestReportError(f"{label} must be one of {options}")
    return str(value)


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise BacktestReportError(f"{label} must be a lowercase SHA-256 hex digest")
    return value


@dataclass(frozen=True)
class DataSpec:
    manifest_sha256: str
    source: str
    license: str
    calendar: str
    start_date: str
    end_date: str
    observations: int
    data_identity: str

    def __post_init__(self) -> None:
        _sha(self.manifest_sha256, "data.manifest_sha256")
        for name in ("source", "license", "calendar"):
            _text(getattr(self, name), f"data.{name}")
        if _iso(self.start_date, "data.start_date") > _iso(self.end_date, "data.end_date"):
            raise BacktestReportError("data window is reversed")
        _count(self.observations, "data.observations", 1)
        _choice(self.data_identity, "data.data_identity", DATA_IDENTITIES)


@dataclass(frozen=True)
class TimingSpec:
    signal_cutoff: str
    execution: str
    rebalance_rule: str

    def __post_init__(self) -> None:
        _text(self.signal_cutoff, "timing.signal_cutoff")
        _choice(self.execution, "timing.execution", EXECUTION_TIMINGS)
        _text(self.rebalance_rule, "timing.rebalance_rule")


@dataclass(frozen=True)
class CostModelSpec:
    model_id: str
    commission_bps: float
    half_spread_bps: float
    impact_bps: float
    scenario_multipliers: tuple[float, ...]
    settlement_rule: str
    whole_shares: bool

    def __post_init__(self) -> None:
        _text(self.model_id, "cost_model.model_id")
        for name in ("commission_bps", "half_spread_bps", "impact_bps"):
            _number(getattr(self, name), f"cost_model.{name}", minimum=0.0)
        multipliers = tuple(self.scenario_multipliers)
        if not multipliers or len(set(multipliers)) != len(multipliers):
            raise BacktestReportError("cost_model.scenario_multipliers must be unique and non-empty")
        for value in multipliers:
            _number(value, "cost_model.scenario_multipliers[]", minimum=0.0, exclusive=True)
        object.__setattr__(self, "scenario_multipliers", multipliers)
        _text(self.settlement_rule, "cost_model.settlement_rule")
        if not isinstance(self.whole_shares, bool):
            raise BacktestReportError("cost_model.whole_shares must be a bool")


@dataclass(frozen=True)
class BenchmarkSpec:
    name: str
    rationale: str
    same_dates: bool = True

    def __post_init__(self) -> None:
        _text(self.name, "benchmark.name")
        _text(self.rationale, "benchmark.rationale")
        if self.same_dates is not True:
            raise BacktestReportError("benchmark comparisons must use the same dates (no silent intersection)")


@dataclass(frozen=True)
class TrialSummary:
    total: int
    failed: int
    rejected: int
    selection_rule: str
    trial_log_sha256: str

    def __post_init__(self) -> None:
        _count(self.total, "trials.total", 1)
        _count(self.failed, "trials.failed", 0)
        _count(self.rejected, "trials.rejected", 0)
        if self.failed + self.rejected > self.total:
            raise BacktestReportError("failed + rejected trials cannot exceed total trials")
        _text(self.selection_rule, "trials.selection_rule")
        _sha(self.trial_log_sha256, "trials.trial_log_sha256")


@dataclass(frozen=True)
class MetricEntry:
    name: str
    scenario_multiplier: float
    status: str
    value: float | None = None
    reason_code: str | None = None

    def __post_init__(self) -> None:
        _text(self.name, "metrics[].name")
        _number(self.scenario_multiplier, "metrics[].scenario_multiplier", minimum=0.0, exclusive=True)
        _choice(self.status, "metrics[].status", METRIC_STATUSES)
        if self.status == "COMPUTED":
            _number(self.value, f"metrics[{self.name}].value")
            if self.reason_code is not None:
                raise BacktestReportError("computed metrics must not carry a reason_code")
        else:
            if self.value is not None:
                raise BacktestReportError("non-computed metrics must have value=None (never a placeholder)")
            _text(self.reason_code, f"metrics[{self.name}].reason_code")


@dataclass(frozen=True)
class UncertaintySpec:
    mean_block_length: float
    n_resamples: int
    seed: int
    confidence: float
    method: str = "stationary_bootstrap"

    def __post_init__(self) -> None:
        if self.method != "stationary_bootstrap":
            raise BacktestReportError("uncertainty.method must be stationary_bootstrap")
        _number(self.mean_block_length, "uncertainty.mean_block_length", minimum=1.0)
        _count(self.n_resamples, "uncertainty.n_resamples", 100)
        _count(self.seed, "uncertainty.seed", 0)
        level = _number(self.confidence, "uncertainty.confidence")
        if not 0.0 < level < 1.0:
            raise BacktestReportError("uncertainty.confidence must be in (0, 1)")


@dataclass(frozen=True)
class WalkForwardFold:
    train_start: str
    train_end: str
    test_start: str
    test_end: str

    def __post_init__(self) -> None:
        ts, te = _iso(self.train_start, "train_start"), _iso(self.train_end, "train_end")
        vs, ve = _iso(self.test_start, "test_start"), _iso(self.test_end, "test_end")
        if ts > te or vs > ve or te >= vs:
            raise BacktestReportError("walk-forward fold must be ordered train < test")


@dataclass(frozen=True)
class WalkForwardSpec:
    protocol: str
    folds: tuple[WalkForwardFold, ...] = ()
    locked_oos: tuple[str, str] | None = None

    def __post_init__(self) -> None:
        _text(self.protocol, "walk_forward.protocol")
        object.__setattr__(self, "folds", tuple(self.folds))
        if self.locked_oos is not None:
            start, end = self.locked_oos
            if _iso(start, "locked_oos.start") > _iso(end, "locked_oos.end"):
                raise BacktestReportError("locked OOS window is reversed")
            object.__setattr__(self, "locked_oos", (start, end))


@dataclass(frozen=True)
class VetoItem:
    metric: str
    op: str
    threshold: float
    frozen_at: str
    frozen_by: str

    def __post_init__(self) -> None:
        _text(self.metric, "veto.metric")
        _choice(self.op, "veto.op", VETO_OPERATORS)
        _number(self.threshold, "veto.threshold")
        _text(self.frozen_at, "veto.frozen_at")
        _text(self.frozen_by, "veto.frozen_by")


@dataclass(frozen=True)
class ReportGates:
    report_items: tuple[str, ...] = ()
    ranking_items: tuple[str, ...] = ()
    veto_items: tuple[VetoItem, ...] = ()

    def __post_init__(self) -> None:
        for name in ("report_items", "ranking_items", "veto_items"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        for item in self.report_items + self.ranking_items:
            _text(item, "gates item")


@dataclass(frozen=True)
class BacktestReportV1:
    report_id: str
    candidate_id: str
    source_revision: str
    created_at: str
    data: DataSpec
    timing: TimingSpec
    cost_model: CostModelSpec
    benchmark: BenchmarkSpec
    trials: TrialSummary
    walk_forward: WalkForwardSpec
    status: str
    metrics: tuple[MetricEntry, ...] = ()
    uncertainty: UncertaintySpec | None = None
    gates: ReportGates = field(default_factory=ReportGates)
    limitations: tuple[str, ...] = ()
    live_ready: bool = False
    no_order: bool = True
    schema_version: str = BACKTEST_REPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != BACKTEST_REPORT_SCHEMA_VERSION:
            raise BacktestReportError("unsupported schema_version")
        if self.live_ready is not False or self.no_order is not True:
            raise BacktestReportError("research reports are always live_ready=False and no_order=True")
        _text(self.report_id, "report_id")
        _text(self.candidate_id, "candidate_id")
        if not isinstance(self.source_revision, str) or not _REVISION.fullmatch(self.source_revision):
            raise BacktestReportError("source_revision must be a lowercase 40-character Git revision")
        _text(self.created_at, "created_at")
        _choice(self.status, "status", REPORT_STATUSES)
        if self.status == "OOS_EVALUATED" and self.data.data_identity == "development":
            raise BacktestReportError("development data cannot be reported as OOS_EVALUATED")
        object.__setattr__(self, "metrics", tuple(self.metrics))
        object.__setattr__(self, "limitations", tuple(self.limitations))
        for item in self.limitations:
            _text(item, "limitations[]")
        declared = set(self.cost_model.scenario_multipliers)
        for metric in self.metrics:
            if metric.scenario_multiplier not in declared:
                raise BacktestReportError("metric scenario_multiplier is not declared in cost_model")

    def to_dict(self) -> dict[str, Any]:
        d, t, c, b, tr, wf, g = (
            self.data, self.timing, self.cost_model, self.benchmark, self.trials, self.walk_forward, self.gates
        )
        return {
            "schema_version": self.schema_version,
            "report_id": self.report_id,
            "candidate_id": self.candidate_id,
            "source_revision": self.source_revision,
            "created_at": self.created_at,
            "data": {
                "manifest_sha256": d.manifest_sha256,
                "source": d.source,
                "license": d.license,
                "calendar": d.calendar,
                "start_date": d.start_date,
                "end_date": d.end_date,
                "observations": d.observations,
                "data_identity": d.data_identity,
            },
            "timing": {"signal_cutoff": t.signal_cutoff, "execution": t.execution, "rebalance_rule": t.rebalance_rule},
            "cost_model": {
                "model_id": c.model_id,
                "commission_bps": c.commission_bps,
                "half_spread_bps": c.half_spread_bps,
                "impact_bps": c.impact_bps,
                "scenario_multipliers": list(c.scenario_multipliers),
                "settlement_rule": c.settlement_rule,
                "whole_shares": c.whole_shares,
            },
            "benchmark": {"name": b.name, "rationale": b.rationale, "same_dates": b.same_dates},
            "trials": {
                "total": tr.total,
                "failed": tr.failed,
                "rejected": tr.rejected,
                "selection_rule": tr.selection_rule,
                "trial_log_sha256": tr.trial_log_sha256,
            },
            "metrics": [
                {
                    "name": m.name,
                    "scenario_multiplier": m.scenario_multiplier,
                    "status": m.status,
                    "value": m.value,
                    "reason_code": m.reason_code,
                }
                for m in self.metrics
            ],
            "uncertainty": None
            if self.uncertainty is None
            else {
                "method": self.uncertainty.method,
                "mean_block_length": self.uncertainty.mean_block_length,
                "n_resamples": self.uncertainty.n_resamples,
                "seed": self.uncertainty.seed,
                "confidence": self.uncertainty.confidence,
            },
            "walk_forward": {
                "protocol": wf.protocol,
                "folds": [
                    {"train_start": f.train_start, "train_end": f.train_end, "test_start": f.test_start, "test_end": f.test_end}
                    for f in wf.folds
                ],
                "locked_oos": None if wf.locked_oos is None else {"start": wf.locked_oos[0], "end": wf.locked_oos[1]},
            },
            "gates": {
                "report_items": list(g.report_items),
                "ranking_items": list(g.ranking_items),
                "veto_items": [
                    {"metric": v.metric, "op": v.op, "threshold": v.threshold, "frozen_at": v.frozen_at, "frozen_by": v.frozen_by}
                    for v in g.veto_items
                ],
            },
            "status": self.status,
            "live_ready": self.live_ready,
            "no_order": self.no_order,
            "limitations": list(self.limitations),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, indent=2)


def load_backtest_report_schema() -> Mapping[str, Any]:
    """Load the packaged JSON Schema (no network)."""
    text = (resources.files("quant_platform_kit") / "schemas" / SCHEMA_RESOURCE).read_text(encoding="utf-8")
    return json.loads(text)
