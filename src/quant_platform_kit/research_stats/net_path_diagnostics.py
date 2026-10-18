"""Window-local net-return path counts; research-only and stdlib-only.

The normalized initial NAV participates in the peak without becoming a return
observation. This module neither reconstructs trades nor attests earlier history.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

from quant_platform_kit.research_stats._validation import (
    ResearchInputError, positive_int, simple_returns,
)
from quant_platform_kit.research_stats.sharpe_inference import StatResult

_UNDERWATER = "longest_underwater_run_observations"
_RECOVERED = "longest_recovered_drawdown_duration_observations"
_TERMINAL = "terminal_underwater_run_observations"
_NEGATIVE = "longest_negative_net_return_run_observations"
_MDD_PEAK_RECOVERY = "max_drawdown_peak_to_recovery_observations"
_MDD_TROUGH_RECOVERY = "max_drawdown_trough_to_recovery_observations"


@dataclass(frozen=True)
class NetPathDiagnostics:
    observations: int
    metrics: tuple[StatResult, ...]
    schema_version: str = "qsl.net_path_diagnostics.v1"
    status: str = "DEVELOPMENT_ONLY"
    purpose: str = "REPORT_ONLY"
    no_order: bool = True
    live_ready: bool = False
    unit: str = "return_observations"
    scope: str = "window_only"
    prior_history: str = "unknown"
    initial_nav: float = 1.0

    def __post_init__(self) -> None:
        positive_int(self.observations, "observations")
        if (self.schema_version != "qsl.net_path_diagnostics.v1"
                or self.status != "DEVELOPMENT_ONLY" or self.purpose != "REPORT_ONLY"
                or self.no_order is not True or self.live_ready is not False
                or self.unit != "return_observations" or self.scope != "window_only"
                or self.prior_history != "unknown" or isinstance(self.initial_nav, bool)
                or self.initial_nav != 1.0):
            raise ResearchInputError("net path diagnostics are window-local research reports only")

    def metric(self, name: str) -> StatResult:
        return next(result for result in self.metrics if result.name == name)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version, "status": self.status,
            "purpose": self.purpose, "no_order": self.no_order,
            "live_ready": self.live_ready, "observations": self.observations,
            "unit": self.unit, "scope": self.scope,
            "prior_history": self.prior_history, "initial_nav": self.initial_nav,
            "metrics": [result.to_dict() for result in self.metrics],
        }


def _result(name: str, value: int | None, reason: str | None = None,
            **details: object) -> StatResult:
    return StatResult(
        name, "COMPUTED" if value is not None else "UNCOMPUTABLE", value, reason,
        {"unit": "return_observations", "input_basis": "same_period_net_returns",
         "scope": "window_only", "prior_history": "unknown",
         "descriptive_only": True, **details},
    )


def _mdd_recovery_results(peak: int | None, trough: int | None, recovery: int | None,
                          end: int, *, numerical_failure: bool = False) -> tuple[StatResult, ...]:
    censored = None if numerical_failure else trough is not None and recovery is None
    reason = ("numerical_failure" if numerical_failure else "no_drawdown" if trough is None
              else "right_censored" if censored else None)
    details = dict(
        definition_version="qpk.max_drawdown_recovery.v1",
        event_selection="first_trough_at_deepest_percentage_drawdown",
        peak_tie_rule="latest_equal_high_water_mark", trough_tie_rule="first_deepest_trough",
        recovery_rule="first_observation_after_trough_at_or_above_event_peak",
        comparison_basis="exact_supplied_binary_return_wealth_factors",
        initial_nav_index=0, peak_index=peak, trough_index=trough,
        recovery_index=recovery, window_end_index=end, right_censored=censored,
        observed_peak_to_end_lower_bound=end - peak if censored else None,
        observed_trough_to_end_lower_bound=end - trough if censored else None,
        duration_basis="index_difference_not_below_peak_count", calendar_duration_computed=False,
    )
    return (
        _result(_MDD_PEAK_RECOVERY, recovery - peak if reason is None else None, reason,
                definition="recovery_index_minus_peak_index", **details),
        _result(_MDD_TROUGH_RECOVERY, recovery - trough if reason is None else None, reason,
                definition="recovery_index_minus_trough_index", **details),
    )


def _drawdown_counts(net: tuple[float, ...], *,
                     include_max_drawdown_recovery: bool = False) -> tuple[StatResult, ...]:
    # Only relative wealth to the latest window peak is needed. Exact rational
    # factors retain the supplied binary float returns, including 1 + tiny r,
    # and avoid float-NAV underflow/overflow or any recovery epsilon. Resetting
    # at every equal/new peak avoids retaining unneeded absolute wealth.
    relative_nav = Fraction(1)
    last_peak_index = 0
    current_underwater = longest_underwater = 0
    longest_recovered: int | None = None
    worst_relative = Fraction(1) if include_max_drawdown_recovery else None
    worst_peak = worst_trough = worst_recovery = None
    for index, return_value in enumerate(net, start=1):
        relative_nav *= 1 + Fraction(return_value)
        if relative_nav >= 1:
            if current_underwater:
                duration = index - last_peak_index
                longest_recovered = max(longest_recovered or 0, duration)
            if include_max_drawdown_recovery and worst_trough is not None and worst_recovery is None:
                worst_recovery = index
            relative_nav = Fraction(1)
            last_peak_index = index
            current_underwater = 0
        else:
            current_underwater += 1
            longest_underwater = max(longest_underwater, current_underwater)
            if include_max_drawdown_recovery and relative_nav < worst_relative:
                # Strictly deeper only: equal depths retain the first trough
                # and its event, even if a later separate episode is censored.
                worst_relative = relative_nav
                worst_peak, worst_trough, worst_recovery = last_peak_index, index, None
    results = (
        _result(_UNDERWATER, longest_underwater,
                definition="consecutive_observations_strictly_below_window_peak"),
        _result(_RECOVERED, longest_recovered,
                "no_recovered_drawdown" if longest_recovered is None else None,
                definition="recovery_index_minus_latest_peak_index",
                includes_recovery_observation=True),
        _result(_TERMINAL, current_underwater,
                right_censored=current_underwater > 0,
                definition="below_peak_observations_at_window_end"),
    )
    if include_max_drawdown_recovery:
        results += _mdd_recovery_results(worst_peak, worst_trough, worst_recovery, len(net))
    return results


def build_net_path_diagnostics(net_returns: Iterable[object], *,
                               include_max_drawdown_recovery: bool = False) -> NetPathDiagnostics:
    """Count same-frequency net-return observations without filling or dropping.

    Invalid/empty input raises ResearchInputError. A zero return continues an
    underwater episode but breaks a strictly-negative return streak. Recovery
    reaches or exceeds the latest tied/new window peak; its duration includes
    the recovering return observation. No completed recovery has value None,
    not zero. Earlier history is always unknown, and terminal underwater runs
    are right-censored; counts cannot be called calendar days or closed trades.
    Arithmetic failure makes all three drawdown metrics UNCOMPUTABLE without
    inventing recovery, while the directly observable negative streak remains.
    No files, accounts, strategy, policy, budget or orders are read or written.

    Explicit opt-in appends two metrics for the deepest percentage drawdown,
    not the longest completed episode. Equal depths retain the first trough;
    the event peak is its latest prior equal high-water mark. Initial NAV is
    index0, and recovery is the first later observation at/above that peak.
    Durations are index differences only, never annualized or calendar days.
    No drawdown has no event (None/no_drawdown). Unrecovered events retain
    None/right_censored and separate observed peak/trough-to-end lower bounds;
    a lower bound0 is not a completed recovery duration. Default output stays
    byte-compatible; earlier history remains unknown in either mode.
    """
    if type(include_max_drawdown_recovery) is not bool:
        raise ResearchInputError("include_max_drawdown_recovery must be boolean")
    net = simple_returns(net_returns, "net_returns")
    if not net:
        raise ResearchInputError("net_returns must be nonempty")
    current_negative = longest_negative = 0
    for return_value in net:
        current_negative = current_negative + 1 if return_value < 0 else 0
        longest_negative = max(longest_negative, current_negative)
    try:
        drawdowns = _drawdown_counts(net, include_max_drawdown_recovery=include_max_drawdown_recovery)
    except (ArithmeticError, ValueError):
        drawdowns = (
            _result(_UNDERWATER, None, "numerical_failure"),
            _result(_RECOVERED, None, "numerical_failure",
                    includes_recovery_observation=True),
            _result(_TERMINAL, None, "numerical_failure", right_censored=None),
        )
        if include_max_drawdown_recovery:
            drawdowns += _mdd_recovery_results(None, None, None, len(net), numerical_failure=True)
    return NetPathDiagnostics(
        len(net), drawdowns[:3] + (_result(_NEGATIVE, longest_negative,
            definition="consecutive_strictly_negative_net_return_observations"),) + drawdowns[3:],
    )
