"""Single source for risk-mandate identifiers and exposure caps.

The bootstrap and TQQQ ETF-only mandates are enforced by both the risk gate
and position sizing.  Keeping their identifiers, factors, and caps here
prevents the two enforcement points from drifting apart.

This module lives under ``common`` rather than ``risk`` so importing it does
not execute the ``risk`` package initializer, which imports the gate while the
gate is still importing position sizing.
"""

from __future__ import annotations

_APPROVED_BOOTSTRAP_MANDATE = "bootstrap_small_account_v2"
_TQQQ_ETF_ONLY_RESEARCH_MANDATE = "tqqq_etf_only_research_v1"
_TQQQ_ETF_ONLY_STRATEGY_PROFILE = "tqqq_etf_only_single_strategy_research_v1"
_TQQQ_ETF_ONLY_FACTORS = {"TQQQ": 3, "BOXX": 1}
_TQQQ_ETF_ONLY_NOMINAL_CAPS = {"TQQQ": 0.15, "BOXX": 0.50}
_TQQQ_ETF_ONLY_EFFECTIVE_CAPS = {"TQQQ": 0.45, "BOXX": 0.50}
_BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP = 0.50
_BOOTSTRAP_NOMINAL_CAPS = {1: 0.50, 2: 0.25, 3: 0.15}
