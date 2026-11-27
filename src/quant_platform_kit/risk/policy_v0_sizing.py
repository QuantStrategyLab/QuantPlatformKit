"""Pure canonical Phase 9 PAPER ``policy v0`` whole-share IBKR sizing engine.

Implements the deterministic sizing rules documented in
``QuantRuntimeSettings/docs/quant/pilot-results.md`` (§7 Option A),
``cost-model.md`` (§5.1 ``OI-COST-3``), and ``paper-readiness.md``:
- Tier parameters (``D``, ``M_full``, ``P-C`` no-trade band) across all three
  mandates with Option A proportional cushion scaling ``x_ML(c)`` only
  (``vol_scale=OFF``, ``dd_scale=OFF``, ``kelly=OFF``, ``stop_loss=OFF``, ``H=0``).
- ``SOXL`` beta scaling (``beta_SOXL = 1.50``) and ``P-D`` diversification
  credit ``0.0`` (``w_TQQQ + 1.50 * w_SOXL == x_target``).
- Mandatory IBKR whole-share API sizing (errors ``10242``/``10243`` guard),
  FUSE fail-closed buy suppression, IBKR Pro Tiered/Fixed commission estimation,
  and strict settled-cash-only enforcement (never spending unsettled sell
  proceeds).
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

BETA_SOXL = 1.50
# Option A baseline sets diversification credit to 0.0 (used as an exported schema invariant).
DIVERSIFICATION_CREDIT = 0.0
DEFAULT_SLEEVE_BETA_SHARES = (0.5, 0.5)
PILOT_SYMBOLS = ("TQQQ", "SOXL")

_IBKR_PRICING_PLANS: dict[str, tuple[float, float, float]] = {
    # (per_share_usd, min_order_usd, max_trade_pct)
    "PRO_TIERED": (0.0035, 0.35, 0.01),
    "PRO_FIXED": (0.005, 1.00, 0.01),
}


@dataclass(frozen=True)
class PolicyV0TierSpec:
    """Locked Option A tier constants from PREREG-R5."""

    tier: str
    drawdown_budget_d: float
    m_full: float
    no_trade_band: float


POLICY_V0_TIERS: dict[str, PolicyV0TierSpec] = {
    "CAPITAL_PRESERVATION": PolicyV0TierSpec(
        tier="CAPITAL_PRESERVATION",
        drawdown_budget_d=0.15,
        m_full=0.16,
        no_trade_band=0.10,
    ),
    "BALANCED_COMPOUNDING": PolicyV0TierSpec(
        tier="BALANCED_COMPOUNDING",
        drawdown_budget_d=0.30,
        m_full=0.27,
        no_trade_band=0.10,
    ),
    "GROWTH_COMPOUNDING": PolicyV0TierSpec(
        tier="GROWTH_COMPOUNDING",
        drawdown_budget_d=0.50,
        m_full=0.46,
        no_trade_band=0.20,
    ),
}


@dataclass(frozen=True)
class PolicyV0SafetyInvariants:
    """Explicit safety lock posture embedded on every sizing result."""

    live: bool = False
    kelly_applied: bool = False
    stop_loss_return_rule: bool = False
    vol_scale_enabled: bool = False
    dd_scale_enabled: bool = False
    cash_only: bool = True
    external_reserve_h_usd: float = 0.0
    whole_shares_only: bool = True


@dataclass(frozen=True)
class PolicyV0OrderProposal:
    """Whole-share rebalance output and audit flags for one ETF sleeve."""

    symbol: str
    current_shares: int
    raw_target_shares: int
    final_target_shares: int
    delta_shares: int
    price_usd: float
    target_weight: float
    current_weight: float
    estimated_notional_usd: float
    estimated_commission_usd: float
    suppressed_by_no_trade_band: bool
    suppressed_by_fuse: bool
    trimmed_for_settled_cash: bool


@dataclass(frozen=True)
class PolicyV0SizingResult:
    """Complete deterministic rebalance proposal across pilot ETF sleeves."""

    tier: str
    pricing_plan: str
    cushion: float
    target_effective_exposure: float
    cash_target_weight: float
    projected_settled_cash_usd: float
    proposals: dict[str, PolicyV0OrderProposal]
    safety_invariants: PolicyV0SafetyInvariants
    fail_closed_reasons: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.fail_closed_reasons


def _is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def get_policy_v0_tier(tier: str) -> PolicyV0TierSpec:
    """Return the locked PREREG-R5 specification for one mandate tier."""
    if not isinstance(tier, str) or tier not in POLICY_V0_TIERS:
        raise ValueError("UNKNOWN_POLICY_V0_TIER")
    return POLICY_V0_TIERS[tier]


def estimate_ibkr_commission_usd(
    shares: int,
    price_usd: float,
    *,
    pricing_plan: str = "PRO_TIERED",
) -> float:
    """Estimate IBKR Pro base US ETF commission in USD for whole-share orders.

    Applies the IBKR 1% trade-value cap after the per-order minimum, so tiny
    notional trades can be capped below ``min_order``.
    """
    if isinstance(shares, bool) or not isinstance(shares, int) or shares < 0:
        raise ValueError("INVALID_ORDER_SHARES")
    if not _is_finite_number(price_usd) or float(price_usd) <= 0.0:
        raise ValueError("INVALID_ORDER_PRICE")
    if not isinstance(pricing_plan, str) or pricing_plan not in _IBKR_PRICING_PLANS:
        raise ValueError("UNKNOWN_IBKR_PRICING_PLAN")
    if shares == 0:
        return 0.0
    per_share, min_order, max_pct = _IBKR_PRICING_PLANS[pricing_plan]
    trade_value = float(shares) * float(price_usd)
    raw = max(min_order, per_share * float(shares))
    return min(raw, max_pct * trade_value)


def _buy_cash_required(
    current_shares: int,
    target_shares: int,
    price_usd: float,
    pricing_plan: str,
) -> float:
    if target_shares <= current_shares:
        return 0.0
    delta = target_shares - current_shares
    return delta * price_usd + estimate_ibkr_commission_usd(
        delta,
        price_usd,
        pricing_plan=pricing_plan,
    )


def _fail_closed_result(
    *,
    tier: str,
    pricing_plan: str,
    cushion: float,
    reasons: list[str],
    whole_shares_only: bool,
) -> PolicyV0SizingResult:
    return PolicyV0SizingResult(
        tier=tier if isinstance(tier, str) else "",
        pricing_plan=pricing_plan if isinstance(pricing_plan, str) else "",
        cushion=cushion,
        target_effective_exposure=0.0,
        cash_target_weight=1.0,
        projected_settled_cash_usd=0.0,
        proposals={},
        safety_invariants=PolicyV0SafetyInvariants(whole_shares_only=bool(whole_shares_only)),
        fail_closed_reasons=tuple(reasons),
    )


def _validate_sleeve_beta_shares(
    sleeve_beta_shares: object,
) -> tuple[float, float] | None:
    if not isinstance(sleeve_beta_shares, tuple) or len(sleeve_beta_shares) != 2:
        return None
    a, b = sleeve_beta_shares
    if not (_is_finite_number(a) and _is_finite_number(b)):
        return None
    fa, fb = float(a), float(b)
    if fa < 0.0 or fb < 0.0 or not math.isclose(fa + fb, 1.0, abs_tol=1e-9):
        return None
    return (fa, fb)


def _validate_rebalance_inputs(
    *,
    tier: str,
    equity_usd: float,
    settled_cash_usd: float,
    cushion: float,
    prices_usd: Mapping[str, float],
    current_shares: Mapping[str, int],
    fuse_new_risk_allowed: bool,
    sleeve_beta_shares: tuple[float, float],
    pricing_plan: str,
    whole_shares_only: bool,
) -> tuple[list[str], tuple[float, float] | None, dict[str, float], dict[str, int]]:
    reasons: list[str] = []
    if not isinstance(whole_shares_only, bool) or not whole_shares_only:
        reasons.append("IBKR_FRACTIONAL_EQUITY_API_UNSUPPORTED")
    if not isinstance(fuse_new_risk_allowed, bool):
        reasons.append("INVALID_FUSE_GATE_FLAG")
    if not isinstance(tier, str) or tier not in POLICY_V0_TIERS:
        reasons.append("UNKNOWN_POLICY_V0_TIER")
    if not isinstance(pricing_plan, str) or pricing_plan not in _IBKR_PRICING_PLANS:
        reasons.append("UNKNOWN_IBKR_PRICING_PLAN")
    if not _is_finite_number(equity_usd) or float(equity_usd) <= 0.0:
        reasons.append("INVALID_EQUITY_USD")
    if not _is_finite_number(settled_cash_usd) or float(settled_cash_usd) < 0.0:
        reasons.append("INVALID_SETTLED_CASH_USD")
    if not _is_finite_number(cushion) or float(cushion) < 0.0:
        reasons.append("INVALID_CUSHION")

    parsed_split = _validate_sleeve_beta_shares(sleeve_beta_shares)
    if parsed_split is None:
        reasons.append("INVALID_SLEEVE_BETA_SHARES")

    parsed_prices: dict[str, float] = {}
    parsed_holdings: dict[str, int] = {}
    for sym in PILOT_SYMBOLS:
        raw_price = prices_usd.get(sym) if isinstance(prices_usd, Mapping) else None
        if raw_price is None or not _is_finite_number(raw_price) or float(raw_price) <= 0.0:
            reasons.append(f"INVALID_PRICE_{sym}")
        else:
            parsed_prices[sym] = float(raw_price)

        raw_qty = current_shares.get(sym, 0) if isinstance(current_shares, Mapping) else None
        if isinstance(raw_qty, bool) or not isinstance(raw_qty, int) or raw_qty < 0:
            reasons.append(f"INVALID_HOLDINGS_{sym}")
        else:
            parsed_holdings[sym] = raw_qty

    return reasons, parsed_split, parsed_prices, parsed_holdings


def _apply_settled_cash_cap(
    *,
    gated_target: dict[str, int],
    parsed_holdings: dict[str, int],
    parsed_prices: dict[str, float],
    target_weights: dict[str, float],
    equity_usd: float,
    settled_cash_usd: float,
    pricing_plan: str,
) -> tuple[dict[str, int], dict[str, bool], float]:
    """Scale down positive buy deltas in O(log N) fixed steps to fit settled cash."""
    final_target = dict(gated_target)

    def _total_buy_cash(targets: dict[str, int]) -> float:
        return sum(
            _buy_cash_required(parsed_holdings[s], targets[s], parsed_prices[s], pricing_plan)
            for s in PILOT_SYMBOLS
        )

    initial_cash = _total_buy_cash(final_target)
    if initial_cash <= settled_cash_usd + 1e-12:
        trimmed = {sym: False for sym in PILOT_SYMBOLS}
        return final_target, trimmed, settled_cash_usd - initial_cash

    buy_deltas = {s: max(0, gated_target[s] - parsed_holdings[s]) for s in PILOT_SYMBOLS}
    lo, hi = 0.0, 1.0
    for _ in range(48):
        mid = 0.5 * (lo + hi)
        cand = {
            s: parsed_holdings[s] + math.floor(mid * buy_deltas[s])
            if buy_deltas[s] > 0
            else gated_target[s]
            for s in PILOT_SYMBOLS
        }
        if _total_buy_cash(cand) <= settled_cash_usd + 1e-12:
            lo = mid
        else:
            hi = mid

    final_target = {
        s: parsed_holdings[s] + math.floor(lo * buy_deltas[s])
        if buy_deltas[s] > 0
        else gated_target[s]
        for s in PILOT_SYMBOLS
    }

    # Add up to one residual rounded share per buying sleeve when cash allows.
    for _ in range(len(PILOT_SYMBOLS)):
        candidates = [
            s
            for s in PILOT_SYMBOLS
            if final_target[s] < gated_target[s]
            and target_weights[s] > 0.0
            and _total_buy_cash({**final_target, s: final_target[s] + 1}) <= settled_cash_usd + 1e-12
        ]
        if not candidates:
            break
        top_up_sym = min(
            candidates,
            key=lambda s: (
                ((final_target[s] * parsed_prices[s]) / equity_usd) / target_weights[s],
                s,
            ),
        )
        final_target[top_up_sym] += 1

    trimmed = {sym: final_target[sym] < gated_target[sym] for sym in PILOT_SYMBOLS}
    return final_target, trimmed, settled_cash_usd - _total_buy_cash(final_target)


def compute_policy_v0_rebalance(
    *,
    tier: str,
    equity_usd: float,
    settled_cash_usd: float,
    cushion: float,
    prices_usd: Mapping[str, float],
    current_shares: Mapping[str, int],
    fuse_new_risk_allowed: bool = True,
    sleeve_beta_shares: tuple[float, float] = DEFAULT_SLEEVE_BETA_SHARES,
    pricing_plan: str = "PRO_TIERED",
    whole_shares_only: bool = True,
) -> PolicyV0SizingResult:
    """Compute fail-closed Option A ``policy v0`` whole-share rebalance orders.

    When ``target_weight > 0``, the no-trade band suppresses small drifts on both
    buys and sells; when ``target_weight == 0`` (e.g. ``cushion == 0``), the
    no-trade band is bypassed for full liquidation. FUSE gating only blocks buys
    and never blocks sells outside the no-trade band.
    """
    reasons, parsed_split, parsed_prices, parsed_holdings = _validate_rebalance_inputs(
        tier=tier,
        equity_usd=equity_usd,
        settled_cash_usd=settled_cash_usd,
        cushion=cushion,
        prices_usd=prices_usd,
        current_shares=current_shares,
        fuse_new_risk_allowed=fuse_new_risk_allowed,
        sleeve_beta_shares=sleeve_beta_shares,
        pricing_plan=pricing_plan,
        whole_shares_only=whole_shares_only,
    )
    safe_cushion = float(cushion) if _is_finite_number(cushion) else 0.0
    if reasons or parsed_split is None:
        return _fail_closed_result(
            tier=tier,
            pricing_plan=pricing_plan,
            cushion=safe_cushion,
            reasons=reasons,
            whole_shares_only=whole_shares_only if isinstance(whole_shares_only, bool) else False,
        )

    spec = POLICY_V0_TIERS[tier]
    eff_equity = float(equity_usd)
    eff_settled_cash = float(settled_cash_usd)
    p_tqqq, p_soxl = parsed_split

    cushion_ratio = min(1.0, max(0.0, safe_cushion / spec.drawdown_budget_d))
    x_target = spec.m_full * cushion_ratio
    target_weights = {
        "TQQQ": p_tqqq * x_target,
        "SOXL": (p_soxl * x_target) / BETA_SOXL,
    }
    cash_target_weight = 1.0 - (target_weights["TQQQ"] + target_weights["SOXL"])

    raw_target: dict[str, int] = {}
    gated_target: dict[str, int] = {}
    band_suppressed: dict[str, bool] = {}
    fuse_suppressed: dict[str, bool] = {}
    current_weights: dict[str, float] = {}

    for sym in PILOT_SYMBOLS:
        price = parsed_prices[sym]
        cur_qty = parsed_holdings[sym]
        w_target = target_weights[sym]
        w_cur = (cur_qty * price) / eff_equity
        current_weights[sym] = w_cur
        raw_qty = math.floor((w_target * eff_equity) / price)
        raw_target[sym] = raw_qty

        in_band = w_target > 0.0 and abs(w_cur - w_target) <= spec.no_trade_band * w_target
        band_suppressed[sym] = in_band
        desired_qty = cur_qty if in_band else raw_qty

        blocked_by_fuse = (not fuse_new_risk_allowed) and desired_qty > cur_qty
        fuse_suppressed[sym] = blocked_by_fuse
        gated_target[sym] = cur_qty if blocked_by_fuse else desired_qty

    final_target, trimmed, projected_settled_cash = _apply_settled_cash_cap(
        gated_target=gated_target,
        parsed_holdings=parsed_holdings,
        parsed_prices=parsed_prices,
        target_weights=target_weights,
        equity_usd=eff_equity,
        settled_cash_usd=eff_settled_cash,
        pricing_plan=pricing_plan,
    )

    proposals: dict[str, PolicyV0OrderProposal] = {}
    for sym in PILOT_SYMBOLS:
        cur_qty = parsed_holdings[sym]
        fin_qty = final_target[sym]
        delta = fin_qty - cur_qty
        price = parsed_prices[sym]
        proposals[sym] = PolicyV0OrderProposal(
            symbol=sym,
            current_shares=cur_qty,
            raw_target_shares=raw_target[sym],
            final_target_shares=fin_qty,
            delta_shares=delta,
            price_usd=price,
            target_weight=target_weights[sym],
            current_weight=current_weights[sym],
            estimated_notional_usd=abs(delta) * price,
            estimated_commission_usd=estimate_ibkr_commission_usd(
                abs(delta),
                price,
                pricing_plan=pricing_plan,
            ),
            suppressed_by_no_trade_band=band_suppressed[sym],
            suppressed_by_fuse=fuse_suppressed[sym],
            trimmed_for_settled_cash=trimmed[sym],
        )

    return PolicyV0SizingResult(
        tier=tier,
        pricing_plan=pricing_plan,
        cushion=safe_cushion,
        target_effective_exposure=x_target,
        cash_target_weight=cash_target_weight,
        projected_settled_cash_usd=projected_settled_cash,
        proposals=proposals,
        safety_invariants=PolicyV0SafetyInvariants(),
    )


__all__ = (
    "BETA_SOXL",
    "DEFAULT_SLEEVE_BETA_SHARES",
    "DIVERSIFICATION_CREDIT",
    "PILOT_SYMBOLS",
    "POLICY_V0_TIERS",
    "PolicyV0OrderProposal",
    "PolicyV0SafetyInvariants",
    "PolicyV0SizingResult",
    "PolicyV0TierSpec",
    "compute_policy_v0_rebalance",
    "estimate_ibkr_commission_usd",
    "get_policy_v0_tier",
)
