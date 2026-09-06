"""Capital risk envelope D1: pure equity → scale mapping (not live-wired).

Module boundary
---------------
- Pure function of injected equity / optional vol / drawdown / preference.
- No broker I/O, no network, no policy writes, no RiskEngine order path.
- Does **not** grant live authority.

Scale product
-------------
``combined_scale = capital_scale * vol_scale * dd_scale``, each factor ≤ 1,
then clamped to ``[0, 1]``.

Auto-downgrade only
-------------------
This evaluator is stateless and has no hysteresis. A more aggressive band
(higher ``capital_scale`` / looser leverage cap) after equity recovery must be
confirmed externally; this module never auto-upgrades posture.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import (
    RISK_PROFILE_IDS,
)

DEFAULT_TARGET_VOL_ANNUAL = 0.20

# Equity band rows (USD absolute; design draft frozen for D1 unit proof).
# Predicate order in ``_resolve_band``: <50k | <250k | ≤1M | >1M.
_BAND_UNDER_50K = (
    "under_50k",
    1.00,
    0.15,
    1.00,
    False,
    "allow_full_3x_etf; financing requires separate mandate",
)
_BAND_50K_250K = (
    "from_50k_to_250k",
    0.85,
    0.10,
    0.50,
    True,
    "cap_3x_etf_weight_or_partial_unlevered_sleeve",
)
_BAND_250K_1M = (
    "from_250k_to_1m",
    0.65,
    0.075,
    0.25,
    True,
    "reduce_3x_sleeve; new_leverage_requires_hitl",
)
_BAND_ABOVE_1M = (
    "above_1m",
    0.50,
    0.05,
    0.00,
    True,
    "default_prohibit_new_leverage_exposure",
)


@dataclass(frozen=True)
class LeverageProductCap:
    """Summary of product-level leverage posture for the equity band."""

    max_3x_etf_weight: float
    new_leverage_requires_hitl: bool
    summary: str


@dataclass(frozen=True)
class CapitalRiskEnvelope:
    """Computed capital-risk envelope; never grants live authority."""

    band_id: str
    capital_scale: float
    vol_scale: float
    dd_scale: float
    combined_scale: float
    leverage_product_cap: LeverageProductCap
    new_risk_allowed: bool
    reasons: tuple[str, ...]
    dd_brake: float
    risk_preference: str | None = None
    live_authority_granted: bool = False


def _clamp_unit(value: float) -> float:
    if not math.isfinite(value) or value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _resolve_band(equity_usd: float) -> tuple[str, float, float, float, bool, str]:
    """Resolve design bands: <50k, 50k–250k, 250k–1M (incl.), >1M."""
    if equity_usd < 50_000.0:
        return _BAND_UNDER_50K
    if equity_usd < 250_000.0:
        return _BAND_50K_250K
    if equity_usd <= 1_000_000.0:
        return _BAND_250K_1M
    return _BAND_ABOVE_1M


def _vol_scale(realized_vol: float | None, *, target_vol: float) -> tuple[float, list[str]]:
    reasons: list[str] = []
    if realized_vol is None:
        return 1.0, reasons
    if (
        isinstance(realized_vol, bool)
        or not isinstance(realized_vol, (int, float))
        or not math.isfinite(float(realized_vol))
        or float(realized_vol) < 0.0
    ):
        reasons.append("INVALID_REALIZED_VOL_FAIL_CLOSED")
        return 0.0, reasons
    rv = float(realized_vol)
    if rv <= 0.0:
        return 1.0, reasons
    scale = min(1.0, float(target_vol) / rv)
    if scale < 1.0:
        reasons.append("VOL_SCALE_REDUCED")
    return _clamp_unit(scale), reasons


def _dd_scale(drawdown_from_peak: float | None, *, dd_brake: float) -> tuple[float, bool, list[str]]:
    """Return (dd_scale, new_risk_allowed, reasons)."""
    reasons: list[str] = []
    if drawdown_from_peak is None:
        return 1.0, True, reasons
    if (
        isinstance(drawdown_from_peak, bool)
        or not isinstance(drawdown_from_peak, (int, float))
        or not math.isfinite(float(drawdown_from_peak))
        or float(drawdown_from_peak) < 0.0
    ):
        reasons.append("INVALID_DRAWDOWN_FAIL_CLOSED")
        return 0.0, False, reasons
    dd = float(drawdown_from_peak)
    half = 0.5 * dd_brake
    if dd >= dd_brake:
        reasons.append("DRAWDOWN_BRAKE_TRIPPED")
        return 0.0, False, reasons
    if dd >= half:
        reasons.append("DRAWDOWN_HALF_BRAKE")
        return 0.5, True, reasons
    return 1.0, True, reasons


def evaluate_capital_risk_envelope(
    equity_usd: float,
    *,
    realized_vol: float | None = None,
    drawdown_from_peak: float | None = None,
    risk_preference: str | None = None,
    target_vol: float = DEFAULT_TARGET_VOL_ANNUAL,
) -> CapitalRiskEnvelope:
    """Map injected equity (and optional vol/DD) to a capital-risk envelope.

    Auto-downgrade only: a higher capital band after equity recovery requires
    external confirmation; this function never raises posture from prior state
    (it is also intentionally stateful-hysteresis-free).
    """
    reasons: list[str] = []
    preference: str | None = None
    if risk_preference is not None:
        preference = str(risk_preference or "").strip().upper()
        if preference and preference not in RISK_PROFILE_IDS:
            reasons.append("UNKNOWN_RISK_PREFERENCE")
            preference = None
        elif preference:
            reasons.append(f"RISK_PREFERENCE_{preference}")

    if (
        isinstance(equity_usd, bool)
        or not isinstance(equity_usd, (int, float))
        or not math.isfinite(float(equity_usd))
        or float(equity_usd) < 0.0
    ):
        reasons.append("INVALID_EQUITY_FAIL_CLOSED")
        return CapitalRiskEnvelope(
            band_id="invalid",
            capital_scale=0.0,
            vol_scale=0.0,
            dd_scale=0.0,
            combined_scale=0.0,
            leverage_product_cap=LeverageProductCap(
                max_3x_etf_weight=0.0,
                new_leverage_requires_hitl=True,
                summary="invalid_equity",
            ),
            new_risk_allowed=False,
            reasons=tuple(reasons),
            dd_brake=0.0,
            risk_preference=preference,
        )

    if (
        isinstance(target_vol, bool)
        or not isinstance(target_vol, (int, float))
        or not math.isfinite(float(target_vol))
        or float(target_vol) <= 0.0
    ):
        reasons.append("INVALID_TARGET_VOL_FAIL_CLOSED")
        target = DEFAULT_TARGET_VOL_ANNUAL
    else:
        target = float(target_vol)

    equity = float(equity_usd)
    band_id, capital_scale, dd_brake, max_3x, hitl, lev_summary = _resolve_band(equity)
    reasons.append(f"BAND_{band_id.upper()}")

    vol_scale, vol_reasons = _vol_scale(realized_vol, target_vol=target)
    reasons.extend(vol_reasons)

    dd_scale, new_risk_allowed, dd_reasons = _dd_scale(
        drawdown_from_peak, dd_brake=dd_brake
    )
    reasons.extend(dd_reasons)

    combined = _clamp_unit(capital_scale * vol_scale * dd_scale)
    return CapitalRiskEnvelope(
        band_id=band_id,
        capital_scale=_clamp_unit(capital_scale),
        vol_scale=vol_scale,
        dd_scale=dd_scale,
        combined_scale=combined,
        leverage_product_cap=LeverageProductCap(
            max_3x_etf_weight=_clamp_unit(max_3x),
            new_leverage_requires_hitl=hitl,
            summary=lev_summary,
        ),
        new_risk_allowed=new_risk_allowed,
        reasons=tuple(reasons),
        dd_brake=dd_brake,
        risk_preference=preference,
    )


def apply_envelope_to_sized_weight(
    sized_weight: float,
    envelope: CapitalRiskEnvelope | Any,
) -> float:
    """Multiply a post-promotion/plugin sized weight by envelope; only shrinks.

    Result is in ``[0, 1]`` and never exceeds ``sized_weight`` when sized_weight
    is a finite non-negative float.
    """
    if (
        isinstance(sized_weight, bool)
        or not isinstance(sized_weight, (int, float))
        or not math.isfinite(float(sized_weight))
        or float(sized_weight) < 0.0
    ):
        return 0.0
    if not isinstance(envelope, CapitalRiskEnvelope):
        return 0.0
    scale = _clamp_unit(float(envelope.combined_scale))
    out = float(sized_weight) * scale
    if not math.isfinite(out) or out < 0.0:
        return 0.0
    # Never raise vs input sized weight; never exceed unit weight.
    return min(float(sized_weight), 1.0, out)


__all__ = [
    "DEFAULT_TARGET_VOL_ANNUAL",
    "CapitalRiskEnvelope",
    "LeverageProductCap",
    "apply_envelope_to_sized_weight",
    "evaluate_capital_risk_envelope",
]
