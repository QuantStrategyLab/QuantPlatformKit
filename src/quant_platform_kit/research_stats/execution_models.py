"""Pure daily-bar execution conventions for opt-in research (stdlib only).

Signals are available after the completed close at ``signal_index``. Indices
refer to the caller's validated, strictly ordered trading-session calendar.
``same_close`` is an explicitly hypothetical close-on-close convention: these
helpers do not claim a completed-close signal could be placed before that close.
No quotes are carried forward. Missing terminal fills return ``None``.

Costs use total traded *security* notional / pre-fill NAV; buys and sells each
count once and the cash leg is free. Commission and slippage are additive bps
per side. ``start`` reproduces cost_stress_recompute's multiplicative ordering;
``end`` deducts the same cost fraction after the session return. Neither helper
estimates market impact, models spreads separately, or touches broker state.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

EXECUTION_MODEL_VERSION = "daily_bar_execution_v1"
FILL_TIMINGS = ("same_close", "next_close", "next_open")


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}_INVALID")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name}_INVALID")
    return result


@dataclass(frozen=True)
class FillPoint:
    index: int
    price_field: str
    timing: str
    model_version: str = EXECUTION_MODEL_VERSION


@dataclass(frozen=True)
class FillModel:
    timing: str

    def __post_init__(self) -> None:
        if self.timing not in FILL_TIMINGS:
            raise ValueError("FILL_TIMING_INVALID")

    def resolve(self, *, signal_index: int, available_index: int,
                bar_count: int) -> FillPoint | None:
        for value in (signal_index, available_index, bar_count):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("SESSION_INDEX_INVALID")
        if signal_index >= bar_count or available_index >= bar_count:
            raise ValueError("SESSION_INDEX_INVALID")
        if available_index > signal_index:
            raise ValueError("SIGNAL_NOT_AVAILABLE")
        index = signal_index + (self.timing != "same_close")
        if index >= bar_count:
            return None
        return FillPoint(index, "open" if self.timing == "next_open" else "close", self.timing)


@dataclass(frozen=True)
class CostModel:
    commission_bps: float = 0.0
    slippage_bps: float = 0.0
    multiplier: float = 1.0

    def __post_init__(self) -> None:
        for name in ("commission_bps", "slippage_bps", "multiplier"):
            value = _number(getattr(self, name), name.upper())
            if value < 0 or (name == "multiplier" and value == 0):
                raise ValueError("COST_MODEL_INVALID")
        if not math.isfinite(self.total_bps_per_side):
            raise ValueError("COST_MODEL_INVALID")

    @property
    def total_bps_per_side(self) -> float:
        return (self.commission_bps + self.slippage_bps) * self.multiplier

    def fraction(self, security_turnover: float) -> float:
        turnover = _number(security_turnover, "TURNOVER")
        if turnover < 0:
            raise ValueError("TURNOVER_INVALID")
        fraction = turnover * self.total_bps_per_side / 10_000.0
        if not math.isfinite(fraction):
            raise ValueError("COST_INVALID")
        return fraction

    def net_return(self, gross_return: float, security_turnover: float,
                   *, charge_at: str = "start") -> float:
        gross = _number(gross_return, "RETURN")
        cost = self.fraction(security_turnover)
        if gross <= -1:
            raise ValueError("RUINED")
        if charge_at == "start":
            if cost >= 1:
                raise ValueError("RUINED")
            net = (1.0 - cost) * (1.0 + gross) - 1.0
        elif charge_at == "end":
            # End-of-session cost is expressed relative to starting NAV. It
            # can exceed that NAV after a gain without exhausting ending NAV.
            net = gross - cost
        else:
            raise ValueError("COST_CHARGE_TIMING_INVALID")
        if not math.isfinite(net) or net <= -1:
            raise ValueError("RUINED")
        return net
