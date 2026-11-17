# Kelly Contract v2 (Research-Only)

[简体中文](kelly-contract-v2.zh-CN.md)

This document specifies QPK Kelly helper units and compatibility boundaries. It grants no paper or live trading authority and leaves trading consumers unchanged.

## Units

| Unit | Meaning | Primary API |
|---|---|---|
| `bet_loss_risk_share` | Risk share assuming full loss on a binary bet losing leg | `estimate_kelly`, `constrained_kelly_recommendation` |
| `capital_exposure` | Asset capital exposure converted via explicit `loss_fraction_per_unit` | `research_capital_exposure_kelly` |

Contract version identifiers:

- `kelly.bet_loss_risk_share.v1`
- `kelly.capital_exposure.v1`

## Compatibility rules

- Legacy fields `KellyResult.kelly_fraction`, `half_kelly`, and `max_position_pct` remain populated with `bet_loss_risk_share` semantics.
- `max_position_pct` is a historical name equal to `min(half_kelly, 0.10)` as a risk-share cap and must **never** be treated as asset capital exposure.
- New `contract_version` and `unit` fields carry defaults to keep construction and equality checks backward-compatible.
- `constrained_kelly_recommendation` also labels risk-share units; `recommended_position_pct` is not capital exposure.

## Binary Kelly rules

- Zero returns are excluded from win/loss probabilities and conditional means; mixing zero returns must not alter optimal risk share.
- Non-finite, `bool`, or mistyped inputs fail closed: `estimate_kelly` returns zero; constrained/exposure APIs return `PARKED`.
- Invalid or non-finite drawdown returns `PARKED` without raising exceptions.
- Full Kelly (`fractional_kelly >= 1`) is forbidden.

## Capital exposure research API

`research_capital_exposure_kelly`:

1. Computes `bet_loss_risk_share`.
2. Converts using explicit trusted `loss_fraction_per_unit`: `theoretical = risk_share / loss_fraction_per_unit`.
3. Applies the fractional multiplier once to that theoretical value.
4. Caps by `min(..., risk_budget_cap, position_cap)`.
5. Treats the unscaled remainder as cash; never renormalize risk weights to 100% invested and call the result half-Kelly.

This API retains fail-closed gates requiring at least 30 samples, both positive and negative returns, and an observed max drawdown not exceeding 25%; callers cannot relax sample or drawdown gates here. Missing trusted loss fractions must return `PARKED` rather than substituting average loss to fabricate hard risk guarantees. Capital exposure caps must lie in `(0, 1]`, parking leverage suggestions above 100%. This API is research-only and stays outside order execution chains.

Reference example: returns `(+20%, +20%, -10%)` yield risk share `0.5`; with `10%` loss per unit, unconstrained theoretical capital exposure is `5`, which independent capital caps may still clamp to `<= 0.1`.

## Portfolio diagnostics and shadow ranking

- Short-position unrealized PnL uses signed cost: `market_value - quantity * average_cost`.
- Partial cost coverage must not pass as complete PnL; diagnostics return `unrealized_pnl_coverage` and mark missing/non-finite costs unknown.
- Metadata `unrealized_pnl_pct` overrides remain highest priority, tagged `unrealized_pnl_source=metadata`.
- In adaptive shadow ranking, valid `score=0` outranks negative scores; smaller `risk_multiplier` values must not make negative scores appear less negative. `shadow_only`, `no_order`, and zero weights remain unchanged.

## Strategy-scope projections and diagnostic inputs

Round-tripping snapshots through `account_state` preserves per-symbol average cost, currency, and account identifier via optional `position_details`. Short quantities and market values are preserved; positions with zero quantity and zero market value are omitted. Missing costs remain `None` rather than reporting full coverage.

Symbol-only indexing cannot disambiguate duplicate tickers across accounts. The projection flags such ambiguity and rejects reconstructing affected symbols rather than pairing one account's cost with another account's quantity. Legacy `account_state` inputs without sidecar fields keep existing behavior.

Offline tests cover IBKR projection entry points and UES cash normalization with the candidate helper without updating consumer dependency pins; downstream adoption and production acceptance remain separate.

## Non-goals

- No distributionally robust optimization solvers and no new runtime dependencies.
- No changes to trading consumers, active strategies, risk-budget authorization, or the no-full-Kelly policy.
