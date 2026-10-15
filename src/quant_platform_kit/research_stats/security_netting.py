"""Opt-in security-level netting with explicit cash roles (research only, stdlib).

Default off: nothing in QPK calls this module and existing helpers
(``CostModel``, ``FillModel``, ``cost_stress_recompute``,
``build_unified_net_report``) are unchanged. A research consumer must call it
explicitly.

One session, one composed book. The strategy sleeve (inner) holds securities
plus a zero-return residual; the outer Kelly layer holds ``f`` of the sleeve
and ``1 - f`` in an outer cash leg. Roles are never merged implicitly:

* ``inner_residual_cash`` - unallocated inner weight, zero return, never charged.
* ``a2_zero_return_cash`` - A2 single-security residual, zero return, never
  charged. Alternative label for the inner residual; never BOXX.
* ``inner_cash_like_security`` - e.g. BOXX inside the inner sleeve; a normal
  traded security, charged at its caller-supplied bps.
* ``outer_cash_leg`` - the ``1 - f`` leg. ``outer_cash_mode="separate"`` keeps
  it as a free virtual asset (never netted with inner securities).
  ``"merge_into_security"`` places it into a caller-named security, which is
  then netted and charged like any other trade (ledger-design option).

Three turnover columns are reported side by side and never summed:
``inner_unnetted_turnover`` (inner rebalance at the pre-trade ``f``),
``outer_unnetted_turnover`` (the ``f`` change applied to the inner target plus
any merged cash-leg change) and ``net_security_turnover`` (per-security net
trades). ``net <= inner + outer`` holds by construction; the sum is not a
reported or charged quantity. Fee rates are caller inputs; none are defaulted.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

SECURITY_NETTING_VERSION = "security_level_netting_v1"
ROLE_INNER_RESIDUAL_CASH = "inner_residual_cash"
ROLE_A2_ZERO_RETURN_CASH = "a2_zero_return_cash"
ROLE_INNER_CASH_LIKE_SECURITY = "inner_cash_like_security"
ROLE_OUTER_CASH_LEG = "outer_cash_leg"
CASH_ROLES = (ROLE_INNER_RESIDUAL_CASH, ROLE_A2_ZERO_RETURN_CASH,
              ROLE_INNER_CASH_LIKE_SECURITY, ROLE_OUTER_CASH_LEG)
INNER_RESIDUAL_ROLES = (ROLE_INNER_RESIDUAL_CASH, ROLE_A2_ZERO_RETURN_CASH)
OUTER_CASH_MODES = ("separate", "merge_into_security")
_TOL = 1e-12


def _num(value: object, code: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(code)
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(code)
    return out


def _weights(raw: Mapping[str, float], code: str) -> dict[str, float]:
    if not isinstance(raw, Mapping):
        raise ValueError(code)
    out: dict[str, float] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key:
            raise ValueError(code)
        weight = _num(value, code)
        if weight < 0:
            raise ValueError(code)
        out[key] = weight
    if sum(out.values()) > 1 + _TOL:
        raise ValueError(code)
    return out


def _fraction(value: object, code: str) -> float:
    out = _num(value, code)
    if out < 0 or out > 1:
        raise ValueError(code)
    return out


@dataclass(frozen=True)
class SecurityNettingSpec:
    """Caller-frozen roles and rates. ``bps_per_side`` must list every traded symbol."""

    bps_per_side: Mapping[str, float]
    outer_cash_mode: str = "separate"
    outer_cash_symbol: str | None = None
    inner_residual_role: str = ROLE_INNER_RESIDUAL_CASH
    cash_like_symbols: tuple[str, ...] = ()
    multiplier: float = 1.0

    def __post_init__(self) -> None:
        if self.outer_cash_mode not in OUTER_CASH_MODES:
            raise ValueError("OUTER_CASH_MODE_INVALID")
        if self.outer_cash_mode == "merge_into_security":
            if not isinstance(self.outer_cash_symbol, str) or not self.outer_cash_symbol:
                raise ValueError("OUTER_CASH_SYMBOL_REQUIRED")
        elif self.outer_cash_symbol is not None:
            raise ValueError("OUTER_CASH_SYMBOL_UNEXPECTED")
        if self.inner_residual_role not in INNER_RESIDUAL_ROLES:
            raise ValueError("INNER_RESIDUAL_ROLE_INVALID")
        if not isinstance(self.cash_like_symbols, tuple):
            raise ValueError("CASH_LIKE_SYMBOLS_INVALID")
        if not isinstance(self.bps_per_side, Mapping):
            raise ValueError("BPS_INVALID")
        for symbol, bps in self.bps_per_side.items():
            if not isinstance(symbol, str) or not symbol or _num(bps, "BPS_INVALID") < 0:
                raise ValueError("BPS_INVALID")
        mult = _num(self.multiplier, "MULTIPLIER_INVALID")
        if mult <= 0:
            raise ValueError("MULTIPLIER_INVALID")

    def role_of(self, symbol: str) -> str | None:
        if symbol in self.cash_like_symbols:
            return ROLE_INNER_CASH_LIKE_SECURITY
        return None


@dataclass(frozen=True)
class SecurityNettingResult:
    target_weights: dict[str, float]
    net_trades: dict[str, float]
    role_weights: dict[str, float]
    inner_unnetted_turnover: float
    outer_unnetted_turnover: float
    net_security_turnover: float
    cost_fraction: float
    turnover_columns_summable: bool = False
    version: str = SECURITY_NETTING_VERSION


def compose_security_targets(*, f: float, inner_weights: Mapping[str, float],
                             spec: SecurityNettingSpec) -> tuple[dict[str, float], dict[str, float]]:
    """Return (security weights, role weights) for outer fraction ``f``."""
    frac = _fraction(f, "OUTER_FRACTION_INVALID")
    inner = _weights(inner_weights, "INNER_WEIGHTS_INVALID")
    securities = {s: frac * w for s, w in inner.items()}
    residual = frac * max(0.0, 1.0 - sum(inner.values()))
    roles = {spec.inner_residual_role: residual,
             ROLE_INNER_CASH_LIKE_SECURITY: sum(securities.get(s, 0.0) for s in spec.cash_like_symbols),
             ROLE_OUTER_CASH_LEG: 1.0 - frac}
    if spec.outer_cash_mode == "merge_into_security":
        sym = spec.outer_cash_symbol
        securities[sym] = securities.get(sym, 0.0) + (1.0 - frac)
    return securities, roles


def net_security_session(*, f_pre: float, inner_pre: Mapping[str, float],
                         f_target: float, inner_target: Mapping[str, float],
                         spec: SecurityNettingSpec) -> SecurityNettingResult:
    """Net the outer ``f`` change against inner weights per security for one session.

    ``f_pre``/``inner_pre`` are the drifted pre-trade book; targets are the
    caller's frozen decisions. Cost is ``sum_s |net trade_s| * bps_s * multiplier``
    as a fraction of pre-trade NAV; the outer cash leg is free only in
    ``separate`` mode.
    """
    pre, _ = compose_security_targets(f=f_pre, inner_weights=inner_pre, spec=spec)
    tgt, roles = compose_security_targets(f=f_target, inner_weights=inner_target, spec=spec)
    fp = float(f_pre)
    ft = float(f_target)
    inner_p = _weights(inner_pre, "INNER_WEIGHTS_INVALID")
    inner_t = _weights(inner_target, "INNER_WEIGHTS_INVALID")
    symbols = sorted(set(pre) | set(tgt))
    missing = [s for s in symbols if s not in spec.bps_per_side]
    if missing:
        raise ValueError("BPS_MISSING:" + ",".join(missing))
    trades = {s: tgt.get(s, 0.0) - pre.get(s, 0.0) for s in symbols}
    inner_syms = sorted(set(inner_p) | set(inner_t))
    inner_un = sum(abs(fp * (inner_t.get(s, 0.0) - inner_p.get(s, 0.0))) for s in inner_syms)
    outer_un = sum(abs((ft - fp) * inner_t.get(s, 0.0)) for s in inner_syms)
    if spec.outer_cash_mode == "merge_into_security":
        outer_un += abs(ft - fp)
    net = sum(abs(v) for v in trades.values())
    cost = sum(abs(trades[s]) * float(spec.bps_per_side[s]) for s in symbols)
    cost = cost * float(spec.multiplier) / 10_000.0
    if not math.isfinite(cost):
        raise ValueError("COST_INVALID")
    return SecurityNettingResult(
        target_weights=dict(sorted(tgt.items())), net_trades=trades,
        role_weights=roles, inner_unnetted_turnover=inner_un,
        outer_unnetted_turnover=outer_un, net_security_turnover=net,
        cost_fraction=cost)


def drift_inner_weights(inner_weights: Mapping[str, float],
                        returns: Mapping[str, float]) -> tuple[dict[str, float], float]:
    """Drift an inner book one session; residual cash earns zero. Returns (weights, gross return)."""
    inner = _weights(inner_weights, "INNER_WEIGHTS_INVALID")
    grown = {}
    for s, w in inner.items():
        if s not in returns:
            raise ValueError("RETURN_MISSING:" + s)
        r = _num(returns[s], "RETURN_INVALID")
        if r <= -1:
            raise ValueError("RUINED")
        grown[s] = w * (1.0 + r)
    residual = max(0.0, 1.0 - sum(inner.values()))
    total = sum(grown.values()) + residual
    return {s: v / total for s, v in sorted(grown.items())}, total - 1.0
