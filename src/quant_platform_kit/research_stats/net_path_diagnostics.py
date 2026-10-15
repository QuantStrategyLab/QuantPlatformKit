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


def _drawdown_counts(net: tuple[float, ...]) -> tuple[StatResult, ...]:
    # Only relative wealth to the latest window peak is needed. Exact rational
    # factors retain the supplied binary float returns, including 1 + tiny r,
    # and avoid float-NAV underflow/overflow or any recovery epsilon. Resetting
    # at every equal/new peak avoids retaining unneeded absolute wealth.
    relative_nav = Fraction(1)
    last_peak_index = 0
    current_underwater = longest_underwater = 0
    longest_recovered: int | None = None
    for index, return_value in enumerate(net, start=1):
        relative_nav *= 1 + Fraction(return_value)
        if relative_nav >= 1:
            if current_underwater:
                duration = index - last_peak_index
                longest_recovered = max(longest_recovered or 0, duration)
            relative_nav = Fraction(1)
            last_peak_index = index
            current_underwater = 0
        else:
            current_underwater += 1
            longest_underwater = max(longest_underwater, current_underwater)
    return (
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


def build_net_path_diagnostics(net_returns: Iterable[object]) -> NetPathDiagnostics:
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
    """
    net = simple_returns(net_returns, "net_returns")
    if not net:
        raise ResearchInputError("net_returns must be nonempty")
    current_negative = longest_negative = 0
    for return_value in net:
        current_negative = current_negative + 1 if return_value < 0 else 0
        longest_negative = max(longest_negative, current_negative)
    try:
        drawdowns = _drawdown_counts(net)
    except (ArithmeticError, ValueError):
        drawdowns = (
            _result(_UNDERWATER, None, "numerical_failure"),
            _result(_RECOVERED, None, "numerical_failure",
                    includes_recovery_observation=True),
            _result(_TERMINAL, None, "numerical_failure", right_censored=None),
        )
    return NetPathDiagnostics(
        len(net), drawdowns + (_result(_NEGATIVE, longest_negative,
            definition="consecutive_strictly_negative_net_return_observations"),),
    )
