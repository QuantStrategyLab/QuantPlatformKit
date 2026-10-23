"""Risk-package re-exports for the shared risk-mandate constants.

The values live in :mod:`quant_platform_kit.common.risk_mandates`; this module
keeps the ``quant_platform_kit.risk.mandates`` import path available.
"""

from __future__ import annotations

from quant_platform_kit.common.risk_mandates import (
    _APPROVED_BOOTSTRAP_MANDATE,
    _BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP,
    _BOOTSTRAP_NOMINAL_CAPS,
    _TQQQ_ETF_ONLY_EFFECTIVE_CAPS,
    _TQQQ_ETF_ONLY_FACTORS,
    _TQQQ_ETF_ONLY_NOMINAL_CAPS,
    _TQQQ_ETF_ONLY_RESEARCH_MANDATE,
    _TQQQ_ETF_ONLY_STRATEGY_PROFILE,
)
