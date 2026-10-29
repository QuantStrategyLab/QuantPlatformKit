"""Account-currency risk budget calculations for explicitly supplied snapshots."""
from __future__ import annotations

import math
import re

from .account_domain import _time
from typing import Any, Mapping


def available_new_risk_budget(snapshot: Mapping[str, Any], *, currency: str, floor: float,
                              reserved: float, cost_buffer: float, risk_fraction: float) -> float:
    """Return the available budget, excluding losses already reflected in equity.

    The caller supplies a complete, trusted snapshot; this function does not
    read an account or grant authority. All amounts use one account currency.
    """
    if snapshot.get("complete") is not True or snapshot.get("currency") != currency:
        raise ValueError("complete matching-currency snapshot required")
    _time(snapshot.get("valuation_at"))
    if not isinstance(snapshot.get("source_digest"), str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", snapshot["source_digest"]):
        raise ValueError("snapshot provenance required")
    values = (snapshot.get("balance"), snapshot.get("equity"), snapshot.get("cash"), floor, reserved, cost_buffer, risk_fraction)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) for v in values):
        raise ValueError("finite risk facts required")
    balance, equity, _cash, floor_value, reserved_value, costs, fraction = map(float, values)
    if min(balance, floor_value, reserved_value, costs) < 0 or not 0 < fraction <= 1:
        raise ValueError("nonnegative risk inputs required")
    return max(0.0, min(fraction * balance, equity - floor_value - reserved_value - costs))


def maximum_risk_quantity(*, budget: float, loss_per_unit: float, estimated_fee: float,
                          quantity_step: float) -> float:
    """Floor a proposed risk budget to units after a nonnegative estimated fee."""
    values = (budget, loss_per_unit, estimated_fee, quantity_step)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) for v in values):
        raise ValueError("finite quantity inputs required")
    budget, loss, fee, step = map(float, values)
    if budget < 0 or fee < 0 or loss <= 0 or step <= 0:
        raise ValueError("invalid quantity inputs")
    if budget <= fee:
        return 0.0
    return math.floor((budget - fee) / (loss * step)) * step
