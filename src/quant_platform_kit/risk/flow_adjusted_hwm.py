"""Pure canonical net-inflow HWM, cushion, and split/reverse-split state advance.

Implements ``QuantRuntimeSettings/docs/quant/definitions-contract.md`` §2.1–2.5
and §3.1–3.4 without broker, cloud, or I/O dependencies:
- Exact ``daily_linked_twr`` across ending-boundary and intraday cash flows.
- Fail-closed rejection when an intraday flow lacks a pre-flow valuation
  (never falling back to Modified Dietz).
- Separation between governed high-water sizing equity ``E*`` (monotonic upward
  ratchet except explicit owner governance reset) and flow-adjusted performance
  peak reference ``W_ref`` preserving ``W_ref - L == W`` and flow-invariant
  drawdown ``dd_B`` and cushion ``c``.
- Forward and reverse split reconciliation fail-closed checks (``V2``).
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


def _is_finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


@dataclass(frozen=True)
class ExternalCashFlow:
    """One external deposit (``> 0``) or withdrawal (``< 0``) in USD."""

    amount_usd: float
    pre_flow_equity_usd: float | None = None
    is_end_of_session: bool = True


@dataclass(frozen=True)
class CorporateActionSplit:
    """Forward or reverse split event for exact position/notional reconciliation."""

    symbol: str
    split_ratio: float
    pre_shares: float
    post_shares: float
    pre_price: float
    post_price: float
    cash_in_lieu_usd: float = 0.0


@dataclass(frozen=True)
class FlowAdjustedHwmState:
    """Carry-forward session-close state for flow-adjusted drawdown & HWM."""

    equity_usd: float
    governed_hwm_usd: float
    external_reserve_h_usd: float = 0.0
    twr_index: float = 1.0
    twr_peak_index: float = 1.0
    bankroll_twr_index: float = 1.0
    bankroll_twr_peak_index: float = 1.0
    underwater_sessions: int = 0


@dataclass(frozen=True)
class FlowAdjustedHwmUpdate:
    """Result of advancing one session across flows, splits, and resets."""

    next_state: FlowAdjustedHwmState
    session_return: float
    bankroll_return: float
    bankroll_drawdown: float
    reference_peak_bankroll_usd: float
    accumulated_loss_usd: float
    cushion: float
    one_session_bankroll_loss: float
    mid_drawdown_deposit_audit: bool
    fail_closed_reasons: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.fail_closed_reasons


def adjust_position_for_split(
    shares: float,
    price: float,
    split_ratio: float,
) -> tuple[float, float]:
    """Scale share count and per-share price across a forward or reverse split."""
    if not _is_finite(shares) or float(shares) < 0.0:
        raise ValueError("INVALID_SHARES")
    if not _is_finite(price) or float(price) < 0.0:
        raise ValueError("INVALID_PRICE")
    if not _is_finite(split_ratio) or float(split_ratio) <= 0.0:
        raise ValueError("INVALID_SPLIT_RATIO")
    ratio = float(split_ratio)
    return float(shares) * ratio, float(price) / ratio


def validate_split_reconciliation(
    split: CorporateActionSplit,
    *,
    notional_tolerance_usd: float = 0.01,
    price_rel_tolerance: float = 0.02,
) -> tuple[str, ...]:
    """Validate that a split or reverse split preserves position notional value."""
    if not isinstance(split.symbol, str) or not split.symbol.strip():
        return ("V2_SPLIT_RECONCILIATION_FAIL_CLOSED",)
    nums = (
        split.split_ratio,
        split.pre_shares,
        split.post_shares,
        split.pre_price,
        split.post_price,
        split.cash_in_lieu_usd,
    )
    if not all(_is_finite(v) for v in nums):
        return ("V2_SPLIT_RECONCILIATION_FAIL_CLOSED",)
    ratio = float(split.split_ratio)
    pre_shares = float(split.pre_shares)
    post_shares = float(split.post_shares)
    pre_price = float(split.pre_price)
    post_price = float(split.post_price)
    cash_in_lieu = float(split.cash_in_lieu_usd)
    if ratio <= 0.0 or pre_shares < 0.0 or post_shares < 0.0 or pre_price < 0.0 or post_price < 0.0 or cash_in_lieu < 0.0:
        return ("V2_SPLIT_RECONCILIATION_FAIL_CLOSED",)
    if pre_price > 0.0:
        if abs((post_price * ratio) - pre_price) / pre_price > price_rel_tolerance:
            return ("V2_SPLIT_RECONCILIATION_FAIL_CLOSED",)
    pre_notional = pre_shares * pre_price
    post_notional = post_shares * post_price + cash_in_lieu
    if abs(post_notional - pre_notional) > notional_tolerance_usd:
        return ("V2_SPLIT_RECONCILIATION_FAIL_CLOSED",)
    return ()


def _validate_state_and_inputs(
    prior_state: FlowAdjustedHwmState,
    ending_equity_usd: float,
    tier_loss_budget_d: float,
    splits: Iterable[CorporateActionSplit],
    flows: list[ExternalCashFlow],
    split_tolerance_usd: float,
) -> tuple[str, ...]:
    valid_prior = (
        _is_finite(prior_state.equity_usd)
        and prior_state.equity_usd > 0.0
        and _is_finite(prior_state.governed_hwm_usd)
        and prior_state.governed_hwm_usd > 0.0
        and _is_finite(prior_state.external_reserve_h_usd)
        and prior_state.external_reserve_h_usd >= 0.0
        and _is_finite(prior_state.twr_index)
        and prior_state.twr_index > 0.0
        and _is_finite(prior_state.twr_peak_index)
        and prior_state.twr_peak_index >= prior_state.twr_index
        and _is_finite(prior_state.bankroll_twr_index)
        and prior_state.bankroll_twr_index > 0.0
        and _is_finite(prior_state.bankroll_twr_peak_index)
        and prior_state.bankroll_twr_peak_index >= prior_state.bankroll_twr_index
        and _is_finite(ending_equity_usd)
        and float(ending_equity_usd) >= 0.0
        and _is_finite(tier_loss_budget_d)
        and 0.0 < float(tier_loss_budget_d) <= 1.0
    )
    if not valid_prior:
        return ("INVALID_INPUT_FAIL_CLOSED",)

    reasons: list[str] = []
    for split in splits:
        reasons.extend(validate_split_reconciliation(split, notional_tolerance_usd=split_tolerance_usd))
    if reasons:
        return tuple(dict.fromkeys(reasons))

    if any(not _is_finite(flow.amount_usd) for flow in flows):
        return ("INVALID_CASH_FLOW_FAIL_CLOSED",)
    return ()


def _chain_session_flows(
    prior_equity_usd: float,
    ending_equity_usd: float,
    h_reserve: float,
    flows: list[ExternalCashFlow],
) -> tuple[float, float, list[float], tuple[str, ...]]:
    prev_post_eq = float(prior_equity_usd)
    eq_factor = 1.0
    bankroll_factor = 1.0
    observations: list[float] = []

    for flow in flows:
        if flow.is_end_of_session:
            continue
        if flow.pre_flow_equity_usd is None or not _is_finite(flow.pre_flow_equity_usd):
            return 1.0, 1.0, [], ("O1_MISSING_PRE_FLOW_VALUATION_FAIL_CLOSED",)
        pre_eq = float(flow.pre_flow_equity_usd)
        post_eq = pre_eq + float(flow.amount_usd)
        if pre_eq < 0.0 or post_eq <= 0.0 or prev_post_eq <= 0.0:
            return 1.0, 1.0, [], ("INVALID_FLOW_EQUITY_FAIL_CLOSED",)
        eq_factor *= pre_eq / prev_post_eq
        bankroll_factor *= (pre_eq + h_reserve) / (prev_post_eq + h_reserve)
        observations.extend((pre_eq, post_eq))
        prev_post_eq = post_eq

    end_flow_total = sum(float(flow.amount_usd) for flow in flows if flow.is_end_of_session)
    end_pre_eq = float(ending_equity_usd) - end_flow_total
    if end_pre_eq < 0.0 or prev_post_eq <= 0.0:
        return 1.0, 1.0, [], ("INVALID_FLOW_EQUITY_FAIL_CLOSED",)

    eq_factor *= end_pre_eq / prev_post_eq
    bankroll_factor *= (end_pre_eq + h_reserve) / (prev_post_eq + h_reserve)
    observations.extend((end_pre_eq, float(ending_equity_usd)))
    return eq_factor, bankroll_factor, observations, ()


def _resolve_governed_hwm(
    prior_hwm_usd: float,
    observations: list[float],
    ending_equity_usd: float,
    dd_bankroll: float,
    tier_loss_budget_d: float,
    has_positive_deposit: bool,
    owner_hwm_reset_usd: float | None,
    days_since_last_reset: int | None,
) -> tuple[float, bool, tuple[str, ...]]:
    next_governed_hwm = max(prior_hwm_usd, max(observations))
    mid_dd_deposit_audit = bool(
        has_positive_deposit and dd_bankroll > 0.0 and next_governed_hwm > prior_hwm_usd
    )
    if owner_hwm_reset_usd is None:
        return next_governed_hwm, mid_dd_deposit_audit, ()
    if not _is_finite(owner_hwm_reset_usd) or float(owner_hwm_reset_usd) < ending_equity_usd:
        return prior_hwm_usd, False, ("INVALID_OWNER_RESET_FAIL_CLOSED",)
    if dd_bankroll >= tier_loss_budget_d / 3.0:
        return prior_hwm_usd, False, ("L1_AMBER_RESET_LOCKED",)
    if days_since_last_reset is None or days_since_last_reset < 30:
        return prior_hwm_usd, False, ("OWNER_RESET_COOLDOWN_ACTIVE",)
    return max(float(owner_hwm_reset_usd), ending_equity_usd), mid_dd_deposit_audit, ()


def _fail_closed_update(
    prior_state: FlowAdjustedHwmState,
    reasons: tuple[str, ...],
) -> FlowAdjustedHwmUpdate:
    dd = 1.0
    if prior_state.bankroll_twr_peak_index > 0.0:
        dd = max(0.0, min(1.0, 1.0 - prior_state.bankroll_twr_index / prior_state.bankroll_twr_peak_index))
    bankroll = prior_state.equity_usd + prior_state.external_reserve_h_usd
    w_ref = bankroll / (1.0 - dd) if dd < 1.0 else bankroll
    return FlowAdjustedHwmUpdate(
        next_state=prior_state,
        session_return=0.0,
        bankroll_return=0.0,
        bankroll_drawdown=dd,
        reference_peak_bankroll_usd=w_ref,
        accumulated_loss_usd=max(0.0, w_ref - bankroll),
        cushion=0.0,
        one_session_bankroll_loss=0.0,
        mid_drawdown_deposit_audit=False,
        fail_closed_reasons=reasons,
    )


def advance_flow_adjusted_hwm(
    prior_state: FlowAdjustedHwmState,
    *,
    ending_equity_usd: float,
    flows: Iterable[ExternalCashFlow] = (),
    splits: Iterable[CorporateActionSplit] = (),
    owner_hwm_reset_usd: float | None = None,
    days_since_last_reset: int | None = None,
    tier_loss_budget_d: float = 0.30,
    split_tolerance_usd: float = 0.01,
) -> FlowAdjustedHwmUpdate:
    """Advance governed HWM, exact daily-linked TWR, drawdown, and cushion."""
    flow_list = list(flows)
    pre_reasons = _validate_state_and_inputs(
        prior_state, ending_equity_usd, tier_loss_budget_d, splits, flow_list, split_tolerance_usd
    )
    if pre_reasons:
        return _fail_closed_update(prior_state, pre_reasons)

    h_reserve = float(prior_state.external_reserve_h_usd)
    end_eq = float(ending_equity_usd)
    eq_factor, bankroll_factor, observations, flow_reasons = _chain_session_flows(
        prior_state.equity_usd, end_eq, h_reserve, flow_list
    )
    if flow_reasons:
        return _fail_closed_update(prior_state, flow_reasons)

    next_twr = prior_state.twr_index * eq_factor
    next_twr_peak = max(prior_state.twr_peak_index, next_twr)
    next_b_twr = prior_state.bankroll_twr_index * bankroll_factor
    next_b_twr_peak = max(prior_state.bankroll_twr_peak_index, next_b_twr)
    dd_bankroll = 1.0 if next_b_twr <= 0.0 else max(0.0, min(1.0, 1.0 - (next_b_twr / next_b_twr_peak)))

    w_current = end_eq + h_reserve
    w_ref = w_current / (1.0 - dd_bankroll) if dd_bankroll < 1.0 else max(prior_state.governed_hwm_usd + h_reserve, w_current)
    acc_loss = max(0.0, w_ref - w_current)
    d_budget = float(tier_loss_budget_d)
    cushion = max(0.0, (d_budget - dd_bankroll) / (1.0 - dd_bankroll)) if dd_bankroll < d_budget else 0.0

    has_positive_deposit = any(float(f.amount_usd) > 0.0 for f in flow_list)
    next_governed_hwm, mid_dd_deposit_audit, reset_reasons = _resolve_governed_hwm(
        prior_state.governed_hwm_usd,
        observations,
        end_eq,
        dd_bankroll,
        d_budget,
        has_positive_deposit,
        owner_hwm_reset_usd,
        days_since_last_reset,
    )
    if reset_reasons:
        return _fail_closed_update(prior_state, reset_reasons)

    next_underwater = 0 if next_twr >= prior_state.twr_peak_index else prior_state.underwater_sessions + 1
    next_state = FlowAdjustedHwmState(
        equity_usd=end_eq,
        governed_hwm_usd=next_governed_hwm,
        external_reserve_h_usd=h_reserve,
        twr_index=next_twr,
        twr_peak_index=next_twr_peak,
        bankroll_twr_index=next_b_twr,
        bankroll_twr_peak_index=next_b_twr_peak,
        underwater_sessions=next_underwater,
    )
    return FlowAdjustedHwmUpdate(
        next_state=next_state,
        session_return=eq_factor - 1.0,
        bankroll_return=bankroll_factor - 1.0,
        bankroll_drawdown=dd_bankroll,
        reference_peak_bankroll_usd=w_ref,
        accumulated_loss_usd=acc_loss,
        cushion=cushion,
        one_session_bankroll_loss=max(0.0, -(bankroll_factor - 1.0)),
        mid_drawdown_deposit_audit=mid_dd_deposit_audit,
        fail_closed_reasons=(),
    )


__all__ = [
    "CorporateActionSplit",
    "ExternalCashFlow",
    "FlowAdjustedHwmState",
    "FlowAdjustedHwmUpdate",
    "adjust_position_for_split",
    "advance_flow_adjusted_hwm",
    "validate_split_reconciliation",
]
