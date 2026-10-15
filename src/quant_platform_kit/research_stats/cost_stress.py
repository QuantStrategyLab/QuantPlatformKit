"""Cost-stress recomputation of net returns (research-only, stdlib only).

Convention (declared, not inferred):

- ``turnover[t]`` is the **total traded notional** (buys + sells, each side
  counted) at the start of period ``t``, as a fraction of pre-trade NAV.
- Every unit of traded notional pays ``cost_bps_per_side × multiplier``.
- The cost is deducted before the period return is earned:
  ``net[t] = (1 − turnover[t]·c)·(1 + gross[t]) − 1``.

Conventions that charge half of L1 turnover (e.g. a cash leg left unpriced)
must be converted by the caller before calling. Gross returns must already be
free of the costs being stressed; this function never deducts the same cost
twice and never fills missing values.

Invalid or mismatched inputs return ``status="PARKED"`` with no numbers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

from quant_platform_kit.research_stats._validation import (
    ResearchInputError,
    finite_float,
    simple_returns,
)
from quant_platform_kit.research_stats.sharpe_inference import STATUS_COMPUTED

STATUS_PARKED = "PARKED"
DEFAULT_MULTIPLIERS = (1.0, 2.0, 3.0)


@dataclass(frozen=True)
class CostStressScenario:
    multiplier: float
    cost_bps_per_side: float
    net_returns: tuple[float, ...]
    log_growth_per_period: float | None
    gross_log_growth_per_period: float
    total_cost_log_drag: float | None
    ruined: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "multiplier": self.multiplier,
            "cost_bps_per_side": self.cost_bps_per_side,
            "log_growth_per_period": self.log_growth_per_period,
            "gross_log_growth_per_period": self.gross_log_growth_per_period,
            "total_cost_log_drag": self.total_cost_log_drag,
            "ruined": self.ruined,
            "observations": len(self.net_returns),
        }


@dataclass(frozen=True)
class CostStressResult:
    status: str
    base_cost_bps_per_side: float | None
    scenarios: tuple[CostStressScenario, ...] = field(default_factory=tuple)
    reason_code: str | None = None

    def scenario(self, multiplier: float) -> CostStressScenario:
        for item in self.scenarios:
            if item.multiplier == multiplier:
                return item
        raise KeyError(multiplier)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "base_cost_bps_per_side": self.base_cost_bps_per_side,
            "scenarios": [s.to_dict() for s in self.scenarios],
            "reason_code": self.reason_code,
        }


def _parked(reason: str) -> CostStressResult:
    return CostStressResult(status=STATUS_PARKED, base_cost_bps_per_side=None, reason_code=reason)


def cost_stress_recompute(
    gross_returns: Iterable[object],
    turnover: Iterable[object],
    *,
    cost_bps_per_side: object,
    multipliers: Iterable[object] = DEFAULT_MULTIPLIERS,
) -> CostStressResult:
    try:
        gross = simple_returns(gross_returns, "gross_returns")
        if isinstance(turnover, (str, bytes)):
            raise ResearchInputError("turnover must be a sequence of numbers")
        traded = tuple(finite_float(v, f"turnover[{i}]") for i, v in enumerate(list(turnover)))
        if any(v < 0.0 for v in traded):
            raise ResearchInputError("turnover must be non-negative")
        base = finite_float(cost_bps_per_side, "cost_bps_per_side")
        if base < 0.0:
            raise ResearchInputError("cost_bps_per_side must be non-negative")
        if isinstance(multipliers, (str, bytes)):
            raise ResearchInputError("multipliers must be a sequence of numbers")
        factors = tuple(finite_float(v, f"multipliers[{i}]") for i, v in enumerate(list(multipliers)))
        if not factors or any(f <= 0.0 for f in factors) or len(set(factors)) != len(factors):
            raise ResearchInputError("multipliers must be unique positive numbers")
    except (ResearchInputError, TypeError):
        return _parked("invalid_input")
    if not gross:
        return _parked("empty_returns")
    if len(traded) != len(gross):
        return _parked("length_mismatch")

    gross_log = [math.log1p(g) for g in gross]
    gross_g = math.fsum(gross_log) / len(gross)
    scenarios: list[CostStressScenario] = []
    for factor in factors:
        cost_rate = base * factor / 10_000.0
        net: list[float] = []
        ruined = False
        for g, tau in zip(gross, traded):
            retained = 1.0 - tau * cost_rate
            if retained <= 0.0:
                ruined = True
                net.append(-1.0)
                continue
            net.append(retained * (1.0 + g) - 1.0)
        if ruined:
            scenarios.append(
                CostStressScenario(factor, base * factor, tuple(net), None, gross_g, None, ruined=True)
            )
            continue
        net_log = [math.log1p(r) for r in net]
        scenarios.append(
            CostStressScenario(
                multiplier=factor,
                cost_bps_per_side=base * factor,
                net_returns=tuple(net),
                log_growth_per_period=math.fsum(net_log) / len(net),
                gross_log_growth_per_period=gross_g,
                total_cost_log_drag=math.fsum(gross_log) - math.fsum(net_log),
            )
        )
    return CostStressResult(status=STATUS_COMPUTED, base_cost_bps_per_side=base, scenarios=tuple(scenarios))
