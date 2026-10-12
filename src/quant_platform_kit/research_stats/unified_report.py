"""B3 unified net-return evidence, stdlib only and never a live permit.

All returns and trial Sharpes use the same caller-declared period and net-cost
basis. MinTRL inverts the existing IID/non-Normal PSR approximation; it is not
a correction for serial dependence or nonstationarity. CVaR is a descriptive
fractional-mass empirical tail mean, not a population-risk guarantee.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from statistics import NormalDist, stdev
from typing import Iterable

from quant_platform_kit.research_stats._validation import (
    ResearchInputError, finite_float, positive_int, simple_returns,
)
from quant_platform_kit.research_stats.backtest_report import MetricEntry
from quant_platform_kit.research_stats.sharpe_inference import (
    DEFAULT_MIN_OBSERVATIONS, StatResult, expected_max_sharpe, probabilistic_sharpe_ratio,
)

NEGATIVE_COST_TOLERANCE_ULPS = 4


def _cost_roundoff_bound(gross: float) -> float:
    # A no-cost (1 + gross) - 1 path rounds at the wealth-factor scale,
    # including tiny returns near zero. Return-scale ULPs alone miss that.
    return NEGATIVE_COST_TOLERANCE_ULPS * math.ulp(1 + gross)


@dataclass(frozen=True)
class TrialEvidence:
    """Caller-supplied cumulative ledger summary, including failed/rejected trials.

    The digest identifies the caller's source; this module does not read or
    attest that ledger. Variance is ddof=1 across all same-period net Sharpes.
    No smaller effective-trial count can be supplied to this interface.
    """

    cumulative_total: int
    sharpe_variance: float
    ledger_sha256: str

    def __post_init__(self) -> None:
        positive_int(self.cumulative_total, "cumulative_total")
        if finite_float(self.sharpe_variance, "sharpe_variance") < 0:
            raise ResearchInputError("sharpe_variance must be nonnegative")
        if not isinstance(self.ledger_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.ledger_sha256):
            raise ResearchInputError("ledger_sha256 must be lowercase SHA-256 hex")


@dataclass(frozen=True)
class UnifiedNetReport:
    observations: int
    metrics: tuple[StatResult, ...]
    cumulative_trials: int | None
    trial_ledger_sha256: str | None
    volatility_ddof: int = 1
    schema_version: str = "qsl.unified_net_report.v1"
    status: str = "DEVELOPMENT_ONLY"
    live_ready: bool = False
    no_order: bool = True

    def __post_init__(self) -> None:
        positive_int(self.observations, "observations")
        if (self.live_ready is not False or self.no_order is not True
                or self.status != "DEVELOPMENT_ONLY"
                or self.schema_version != "qsl.unified_net_report.v1"
                or type(self.volatility_ddof) is not int or self.volatility_ddof != 1):
            raise ResearchInputError("unified net reports are research-only with ddof=1")

    def metric(self, name: str) -> StatResult:
        return next(result for result in self.metrics if result.name == name)

    def metric_entries(self, *, scenario_multiplier: float) -> tuple[MetricEntry, ...]:
        """Reuse the existing backtest v1 entries; the report envelope is separate."""
        return tuple(MetricEntry(m.name, scenario_multiplier, m.status, m.value, m.reason_code)
                     for m in self.metrics)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version, "status": self.status,
            "observations": self.observations, "volatility_ddof": self.volatility_ddof,
            "cumulative_trials": self.cumulative_trials,
            "trial_ledger_sha256": self.trial_ledger_sha256,
            "live_ready": self.live_ready, "no_order": self.no_order,
            "metrics": [m.to_dict() for m in self.metrics],
        }


def _missing(name: str, reason: str, **details: object) -> StatResult:
    return StatResult(name, "UNCOMPUTABLE", None, reason, details)


def _computed(name: str, value: float, **details: object) -> StatResult:
    if not math.isfinite(value):
        return _missing(name, "numerical_failure", **details)
    return StatResult(name, "COMPUTED", value, details=details)


def _psr(returns: tuple[float, ...], benchmark: float, floor: int) -> StatResult:
    try:
        return probabilistic_sharpe_ratio(returns, sr_benchmark=benchmark, min_observations=floor)
    except (ArithmeticError, ValueError):
        return _missing("probabilistic_sharpe_ratio", "numerical_failure")


def _dsr(returns: tuple[float, ...], trials: TrialEvidence | None, floor: int) -> StatResult:
    name = "deflated_sharpe_ratio"
    if trials is None:
        return _missing(name, "missing_trial_evidence")
    details = {"cumulative_trials": trials.cumulative_total,
               "trial_sharpe_variance": trials.sharpe_variance,
               "trial_ledger_sha256": trials.ledger_sha256,
               "trial_provenance": "caller_supplied_not_attested"}
    try:
        threshold = expected_max_sharpe(trials.sharpe_variance, trials.cumulative_total)
        if not threshold.computed:
            return _missing(name, threshold.reason_code or "uncomputable", **details)
        result = _psr(returns, threshold.value, floor)
        details.update(result.details)
        details["expected_max_sharpe"] = threshold.value
        return StatResult(name, result.status, result.value, result.reason_code, details)
    except (ArithmeticError, ValueError):
        return _missing(name, "numerical_failure", **details)


def _mintrl(psr: StatResult, benchmark: float, confidence: float, floor: int) -> StatResult:
    name = "minimum_track_record_periods"
    assumptions = ("independent_stationary_observations", "finite_first_four_moments",
                   "asymptotic_psr_approximation_no_serial_correlation_correction")
    details = {"confidence": confidence, "sr_benchmark": benchmark,
               "structural_min_observations": floor, "assumptions": assumptions}
    if not psr.computed:
        return _missing(name, psr.reason_code or "uncomputable", **details)
    sr = psr.details["sharpe_per_period"]
    if sr <= benchmark:
        return _missing(name, "sharpe_not_above_benchmark", **details)
    skew, kurt = psr.details["skewness"], psr.details["kurtosis"]
    try:
        variance = 1 - skew * sr + (kurt - 1) * sr * sr / 4
        required = 1 + variance * (NormalDist().inv_cdf(confidence) / (sr - benchmark)) ** 2
        if not math.isfinite(required) or variance <= 0:
            return _missing(name, "numerical_failure", **details)
        details.update(sharpe_variance_term=variance, asymptotic_minimum_periods=required)
        return _computed(name, float(max(floor, math.ceil(required))), **details)
    except (ArithmeticError, ValueError):
        return _missing(name, "numerical_failure", **details)


def build_unified_net_report(
    net_returns: Iterable[object], *, gross_returns: Iterable[object] | None = None,
    trials: TrialEvidence | None = None, sr_benchmark: float = 0.0,
    confidence: float = .95, min_observations: int = DEFAULT_MIN_OBSERVATIONS,
) -> UnifiedNetReport:
    """Summarize validated same-period net returns; never fill/drop observations.

    Gross returns, if supplied, must represent the identical observation window
    with nonnegative cost deductions apart from a recorded 4-ULP roundoff bound.
    Invalid inputs raise ResearchInputError;
    missing/undefined inference is UNCOMPUTABLE with no numeric placeholder.
    No files, accounts, ledgers, policy, orders or budgets are read or written.
    """
    net = simple_returns(net_returns, "net_returns")
    if not net:
        raise ResearchInputError("net_returns must be nonempty")
    gross = None if gross_returns is None else simple_returns(gross_returns, "gross_returns")
    if gross is not None and (len(gross) != len(net) or any(
            b > a and b - a > _cost_roundoff_bound(a) for a, b in zip(gross, net))):
        raise ResearchInputError("gross/net returns must align with nonnegative cost deductions")
    if trials is not None and not isinstance(trials, TrialEvidence):
        raise ResearchInputError("trials must be TrialEvidence or None")
    floor = positive_int(min_observations, "min_observations", minimum=3)
    benchmark = finite_float(sr_benchmark, "sr_benchmark")
    level = finite_float(confidence, "confidence")
    if not .5 < level < 1:
        raise ResearchInputError("confidence must be in (.5, 1)")
    logs = tuple(math.log1p(r) for r in net)
    growth = _computed("net_log_growth_per_period", math.fsum(logs) / len(net))
    if len(net) < floor:
        sharpe = _missing("sharpe_per_period", "insufficient_observations")
    else:
        try:
            std = stdev(net)
            sharpe = (_missing("sharpe_per_period", "zero_variance") if std == 0 else
                      _computed("sharpe_per_period", (math.fsum(net) / len(net)) / std, ddof=1))
        except (ArithmeticError, ValueError):
            sharpe = _missing("sharpe_per_period", "numerical_failure")
    psr = _psr(net, benchmark, floor)
    dsr = _dsr(net, trials, floor)
    mintrl = _mintrl(psr, benchmark, level, floor)
    # Each observation has mass 1/n. Integrate exactly the worst 5% mass,
    # splitting the boundary observation rather than rounding up its count.
    mass = len(net) * .05
    full = math.floor(mass)
    fraction = mass - full
    ordered = sorted(net)
    try:
        tail_sum = math.fsum(ordered[:full]) + (fraction * ordered[full] if fraction else 0)
        cvar = _computed("cvar95_return_per_period", tail_sum / mass,
                         tail_probability=.05, tail_observation_mass=mass,
                         fully_weighted_observations=full, boundary_weight=fraction,
                         sign="signed_return_negative_is_loss", descriptive_only=True)
    except (ArithmeticError, ValueError):
        cvar = _missing("cvar95_return_per_period", "numerical_failure")
    cumulative, peak, worst = 0.0, 0.0, 0.0
    for log_return in logs:
        cumulative += log_return
        peak = max(peak, cumulative)
        worst = min(worst, math.expm1(cumulative - peak))
    drawdown = _computed("max_drawdown", worst, includes_initial_nav=True)
    if gross is None:
        drag = _missing("cost_log_drag_per_period", "missing_gross_returns")
    else:
        roundoff_pairs = [(a, b) for a, b in zip(gross, net) if b > a]
        # Preserve net inputs everywhere. Only a permitted micro-negative cost
        # component is zeroed; substantive negative costs were rejected above.
        drag = _computed("cost_log_drag_per_period",
                         math.fsum(0.0 if b > a else math.log1p(a) - log_net
                                   for a, b, log_net in zip(gross, net, logs)) / len(net),
                         negative_cost_tolerance_ulps=NEGATIVE_COST_TOLERANCE_ULPS,
                         negative_cost_tolerance_scale="ulp(1+gross)",
                         roundoff_negative_cost_pairs_zeroed=len(roundoff_pairs),
                         max_roundoff_negative_return_delta=max((b - a for a, b in roundoff_pairs), default=0.0))
    return UnifiedNetReport(len(net), (growth, sharpe, psr, dsr, mintrl, cvar, drawdown, drag),
                            trials.cumulative_total if trials else None,
                            trials.ledger_sha256 if trials else None)
