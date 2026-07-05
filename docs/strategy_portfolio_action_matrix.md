# Strategy Portfolio Action Matrix

[简体中文](./strategy_portfolio_action_matrix.zh-CN.md)

This document turns the current cross-repository review into an execution plan.
It uses the present repo state as the source of truth and separates:

- keep tuning
- rebuild / redesign
- deprecate / downgrade
- new strategy ideas

## Decision rules

- If a profile is still `runtime_enabled` and has clear evidence, keep tuning it.
- If a profile is useful but its shape is wrong, keep the idea and rebuild the
  wrapper / orchestrator.
- If a profile is clearly weaker than the main live line, downgrade it to
  `shadow_candidate`, `research_backtest_only`, or archive it.
- If a market lacks a good live candidate, prefer a new architecture instead of
  adding more variants.

## Cross-market matrix

| Market | Keep tuning | Rebuild / redesign | Downgrade / retire | New ideas worth testing |
| --- | --- | --- | --- | --- |
| US equity | `global_etf_rotation`, `tqqq_growth_income`, `soxl_soxx_trend_income`, `russell_top50_leader_rotation`, DCA lines | `us_equity_combo`, `us_equity_combo_leveraged` should stay as shadow/orchestrator layers rather than live profiles | `tecl_xlk_trend_income` stays research-only | Optional LEAPS overlay, but only as a separately gated research track |
| HK equity | `hk_global_etf_tactical_rotation`, `hk_low_vol_dividend_quality_snapshot` | `hk_equity_combo` should be a research/orchestration wrapper, not a live profile | any combo-style live promotion should be blocked until evidence improves | A dedicated factor-enhanced rotation wrapper only after the core lines are stable |
| CN equity | `cn_industry_etf_rotation`, `cn_industry_etf_rotation_aggressive` | `cn_equity_combo` should be rebuilt as an orchestrator / dual-track composition, not a direct live profile | `cn_index_etf_tactical_rotation` stays legacy/research; `cn_chinext_tactical_rotation` and `cn_chinext_growth_momentum_quality_snapshot` should be redesigned, not discarded | `cn_dual_track_combo`, a first-class ChiNext growth sleeve, and a separate STAR growth sleeve |
| Crypto | `crypto_live_pool_rotation`, `crypto_btc_dca` | `crypto_trend_rotation`, `crypto_equity_combo` need redesign before any live promotion | all non-live crypto profiles stay research/shadow until proven otherwise | A volatility-regime filter or stablecoin cash-deploy layer before adding more rotation variants |

## What this means by market

### US

US already has a strong main live set. The right move is not more live variants;
it is better separation:

- keep the live trend and rotation lines as the core
- keep combo logic as a shadow/orchestrator layer
- retire weak legacy templates like TECL

### HK

HK should stay narrow:

- keep the ETF rotation and snapshot-backed dividend-quality line
- treat combo as a research wrapper
- do not broaden live exposure until the evidence gap is closed

### CN

CN still has room for improvement, but the current strongest path is:

- one direct ETF rotation main line
- one aggressive variant under controlled rollout
- one future orchestrator / dual-track line

ChiNext and STAR should not be treated as disposable research branches; they
are board-specific growth sleeves whose design needs to match the market
regime.

The combo profile should not compete with the main live line until it is
rebuilt as a composition engine.

### Crypto

Crypto is the most regime-sensitive domain, so the live gate should stay strict:

- keep the live pool rotation line as the main runtime strategy
- keep BTC DCA as a simple tuneable accumulation line
- redesign trend and combo variants before any live promotion

## Plugin and gate implications

- `notification_only` is fine for monitoring and research visibility.
- `automation_candidate` is fine for shadow and pre-live validation.
- `automation_approved + position_control_allowed` remains the hard gate for
  any automatic position impact.
- A strategy being AI-monitored is not the same as being live-enabled.

## Recommended next implementation steps

1. Keep the current live lines stable.
2. Rebuild combo/orchestrator profiles around composition, not duplication.
3. Add any new strategies only if they solve a real gap in the matrix above.
4. Use evidence packages to promote, not ad hoc exceptions.

## Reference strategy families

The external research that best matches this matrix is still:

- time-series momentum / trend following
- factor investing: quality, momentum, low volatility, dividend yield
- multi-asset value + momentum overlays

Official references:

- AQR Trends Everywhere
- AQR Value and Momentum Everywhere
- Kenneth French Data Library
- MSCI Factor Indexes
- EDHEC trend-following research
