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
)

binding = CapitalBaseBinding(
    account_scope="stable-account-scope",
    runtime_scope="stable-runtime-scope",
    strategy_scope="soxl_soxx_trend_income",
    target_currency="USD",
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
)
```

This helper intentionally accepts only a canonical `PortfolioSnapshot`. It
does not read environment variables, inspect untrusted snapshot metadata, or
infer scope, currency, FX, or digests; platforms must supply those reviewed
facts explicitly.

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
