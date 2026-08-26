# Capital base contract for value targets

`target_value` is an amount, not a portfolio weight.  Any runtime that opts
into strict value-target risk enforcement must use one verified denominator
for both normalization and the risk decision.

## Migration interface

Pass both arguments to `apply_risk_gate`:

```python
from quant_platform_kit.common.capital_base import (
    CapitalBaseBinding,
    CapitalBaseSnapshot,
    CapitalScope,
    CapitalValuationBasis,
)

binding = CapitalBaseBinding(
    account_scope="stable-account-scope",
    runtime_scope="stable-runtime-scope",
    strategy_scope="soxl_soxx_trend_income",
    target_currency="USD",
    capital_scope=CapitalScope.ACCOUNT,
    valuation_basis=CapitalValuationBasis.BROKER_ACCOUNT_NET_LIQUIDATION,
    max_age_seconds=300,
)
capital_base = CapitalBaseSnapshot(
    reported_equity=100_000.0,
    reported_currency="USD",
    target_currency="USD",
    fx_rate_to_target=1.0,
    as_of=broker_observed_at,
    account_scope="stable-account-scope",
    runtime_scope="stable-runtime-scope",
    strategy_scope="soxl_soxx_trend_income",
    source_digest_sha256=broker_snapshot_digest,
    capital_scope=CapitalScope.ACCOUNT,
    valuation_basis=CapitalValuationBasis.BROKER_ACCOUNT_NET_LIQUIDATION,
)
```

When the platform has already built a canonical `PortfolioSnapshot`, it may
use the pure adapter instead of copying `total_equity` and `as_of` itself:

```python
from quant_platform_kit.common.capital_base import build_capital_base_snapshot

capital_base = build_capital_base_snapshot(
    portfolio_snapshot,
    account_scope="stable-account-scope",
    runtime_scope="stable-runtime-scope",
    strategy_scope="soxl_soxx_trend_income",
    reported_currency="USD",
    target_currency="USD",
    fx_rate_to_target=1.0,
    source_digest_sha256=broker_snapshot_digest,
    capital_scope=CapitalScope.ACCOUNT,
    valuation_basis=CapitalValuationBasis.BROKER_ACCOUNT_NET_LIQUIDATION,
)
```

This helper intentionally accepts only a canonical `PortfolioSnapshot`. It
does not read environment variables, inspect untrusted snapshot metadata, or
infer scope, currency, FX, or digests; platforms must supply those reviewed
facts explicitly.

## Denominator ownership and valuation coverage

Strict enforcement accepts only `qpk.capital_base.v2` evidence.  It binds the
denominator's ownership and valuation semantics, not just its numeric value:

- `ACCOUNT` + `BROKER_ACCOUNT_NET_LIQUIDATION`: an explicit broker account
  net-liquidation field.  It must cover the selected account and cannot carry
  a sleeve allocation scope.
- `ACCOUNT` + `FULL_ACCOUNT_MARK_TO_MARKET`: all account cash, positions and
  required FX must be covered by `component_coverage_digest_sha256`.  A
  strategy-symbol filter is never sufficient.
- `ALLOCATED_SLEEVE` + `ALLOCATED_SLEEVE_LEDGER`: the only sleeve form.  It
  requires a stable, approved `allocation_scope` and a coverage digest that
  binds the ledger, attributed cash flows, holdings and valuation inputs.

`CapitalBaseBinding` repeats the expected scope, valuation basis and, for a
sleeve, allocation scope.  The risk gate matches them exactly.  It rejects
the common but invalid hybrid of all available account cash plus only the
positions whose symbols happen to belong to a strategy.  A digest proves the
identity of supplied evidence; it does not make incomplete evidence complete.

For a shared broker account, use an `ACCOUNT` base only with an account-level
cross-strategy budget.  Use a sleeve base only after a human-approved ledger
defines ownership; do not infer it from symbols, account aliases or regions.

The earlier v1-shaped object remains readable only so diagnostics can identify
an incomplete migration. It always fails strict value-target admission.

When `reported_currency` and `target_currency` differ, set a positive
`fx_rate_to_target` and provide `fx_source_digest_sha256`.  The contract
rejects missing, zero, non-finite, future, stale, currency-mismatched, or
scope-mismatched bases.  Scope values are compared but only their SHA-256
digest is emitted in risk diagnostics.

Then enable the opt-in gate:

```python
apply_risk_gate(
    decision,
    portfolio_snapshot=portfolio_snapshot,
    enforce_value_target_exposure=True,
    capital_base=capital_base,
    capital_base_binding=binding,
)
```

The legacy default (`enforce_value_target_exposure=False`) remains diagnostic
only for compatibility.  It must not be interpreted as approval to execute an
unmigrated value-target strategy.

## Live-performance cash flows

Live execution telemetry may include signed `net_external_cash_flow` (or the
equivalent `external_cash_flow`) in account currency.  Deposits are positive;
withdrawals are negative.  Lifecycle daily returns use
`(ending_equity - external_cash_flow) / previous_equity - 1`, an
end-of-period, time-weighted-return-compatible convention.  Do not put cash
balances, internal sweeps, or PnL into this field.
