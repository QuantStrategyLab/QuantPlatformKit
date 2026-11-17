# Account New-Risk Gate

[简体中文](account-new-risk-gate.zh-CN.md)

`quant_platform_kit.risk.account_new_risk_gate` provides an injected, read-only adapter that decides whether an account may add new risk. It complements order-level `RiskEngine` and `risk.gate` checks and does not replace them.

The library never grants live trading authority or enables accounts automatically. Platform adapters (`Schwab`, `LongBridge`, `IBKR`), capital-envelope evaluation (`evaluate_capital_risk_envelope`), W2 offline probes, and production drift checks (`production_drift_new_risk`) are source-level building blocks; deployed Cloud Run configuration, live metrics, and trading-cycle behavior still require separate operational verification.

## Module boundaries

| Does | Does not |
|---|---|
| Accepts caller-injected, redacted reconciliation snapshot projections (with optional equity summary) | Read live accounts, brokers, credentials, or network endpoints |
| Strictly binds equity summary dicts/dataclasses into `InjectedReconciliationSnapshot` via `reconciliation_snapshot_binding` | Automatically flatten positions or reset circuit breakers |
| Evaluates envelope and gate disposition offline via `capital_envelope_w2_probe` / `python -m quant_platform_kit.risk.capital_envelope_w2_probe` | Deploy services, toggle account enablement, or grant live authority |
| Returns `NEW_RISK_PROHIBITED` when snapshots are unhealthy, equity is missing/invalid, or the capital envelope forbids new risk | Weaken or bypass `RiskEngine` |
| Always keeps `live_authority_granted=false` | |

All of the following must hold for `ALLOW_NEW_RISK`:

- `observation_status == COMPLETE`
- `reconciliation_status == VERIFIED`
- `circuit_breaker_state == CLOSED`
- `equity_usd` is valid and the capital envelope sets `new_risk_allowed=True`
- Injected `production_drift_status` is neither `review`/`critical` nor an invalid value

### Cycle-health semantics (distinct from `RECONCILE_ONLY` recovery)

Platform execution cycles project the three health axes via `cycle_new_risk_health.project_cycle_new_risk_health_axes` and `apply_cycle_new_risk_health_axes`:

| Axis | Cycle-health meaning |
|---|---|
| `COMPLETE` | Read-only equity and position reads succeeded for this cycle (does not claim full GTC or fill-ledger completeness) |
| `VERIFIED` | No pending `UNKNOWN` items; passes when expected digests are unconfigured, or requires full match when configured |
| `CLOSED` | No durable `OPEN` state exists and the cycle did not open due to `UNKNOWN` or a trip; never clears an existing `OPEN` automatically |

The sidecar `/reconcile` path (`RECONCILE_ONLY` with expected digests) remains strictly for frozen baseline recovery and must not be conflated with cycle-health.

Optional inputs include `peak_equity_usd`, `drawdown_from_peak`, and `realized_vol`. Missing equity triggers `EQUITY_UNKNOWN_FAIL_CLOSED`. `ALLOW_NEW_RISK` is neither an order permit nor live trading authorization.

### Policy A: production drift blocks new risk only

`risk.production_drift_new_risk` reuses the same account gate:

- `review` / `critical` map to `PRODUCTION_DRIFT_REVIEW` / `PRODUCTION_DRIFT_CRITICAL` and `NEW_RISK_PROHIBITED`.
- `healthy` / `watch` add no drift block; any invalid injected status fails closed.
- `resolve_production_drift_status_from_store` reads an existing lifecycle store and returns an injectable status without creating duplicate scores, optimizing parameters, enabling accounts, or resetting breakers.
- Missing, parked, unavailable, or unreadable drift scores return `None`. The gate does not treat `None` as healthy, nor does it block new risk solely from `None`; verify store availability and consumer wiring independently.

Platform adapters use the active runtime target's `strategy_profile`; `PRODUCTION_DRIFT_STRATEGY_PROFILE` overrides in `observe` mode do not prove trading-path consumption. GitHub Variables and sync plans do not prove Cloud Run configuration or score availability. Lifecycle store writes must use approved GitHub Actions or Cloud Run WIF rather than local ADC credentials.

Bounded research optimization belongs to a separate authorized pipeline. Production Policy A never invokes `run_research_promotion_cycle` or `optimize`, never tunes active parameters, and never cancels orders, closes positions, or resumes trading automatically.

### Production drift axis (Policy A: block new risk, zero optimization)

| Injected `production_drift_status` | Gate effect |
|---|---|
| Missing / blank | No status invented; axis adds no block reason |
| `healthy` / `watch` | Allowed by this axis |
| `review` / `critical` | `NEW_RISK_PROHIBITED` (`PRODUCTION_DRIFT_REVIEW` / `PRODUCTION_DRIFT_CRITICAL`) |
| Invalid value | `PRODUCTION_DRIFT_STATUS_INVALID_FAIL_CLOSED` |

Helpers: `production_drift_new_risk_reasons` and `production_drift_status_from_result`. Platforms may call `resolve_production_drift_status_from_store` to read from `PerformanceStore`, omitting the axis when the store is absent, parked, or unreadable.

### W2 read-only probe usage

```bash
python -m quant_platform_kit.risk.capital_envelope_w2_probe --equity 40000
python -m quant_platform_kit.risk.capital_envelope_w2_probe --equity 85000 --peak 100000
python -m quant_platform_kit.risk.capital_envelope_w2_probe --equity 100000 --drawdown 0.10 --json
```

Programmatic helper: `probe_capital_envelope_w2(equity_usd, peak_equity_usd=..., realized_vol=...)`. Equity binding helper: `build_injected_snapshot_from_equity_summary({"equity_usd": 40000.0})`.

### D3 multi-account summary view

`evaluate_multi_account_envelope_view(accounts)` accepts injected `account_id`, `equity_usd`, and optional `peak_equity_usd`, `drawdown_from_peak`, or `realized_vol`:

- Total equity reuses the D1 capital tier table.
- Each account retains an independent envelope; aggregate tiers never raise any account's authority.
- If any account yields `new_risk_allowed=false`, the aggregate signal is false.
- Missing or invalid equity on any account fails closed and marks total equity unknown.
- Output is for console diagnostics only; it never allocates positions, places cross-account orders, or grants live authority.

## Relationship to the QRT deterministic kernel

The full limit and frequency kernel lives in `python/scripts/deterministic_risk_gate.py` in `QuantRuntimeSettings`. This module fixes the boundary "reconciliation health + capital envelope + injected drift -> block new risk" and its injection points. Deployed `OPEN` persistence, live broker readbacks, and final order enforcement must be verified per consumer rather than inferred from library presence or CI runs.

## Promotion sizing vs. composer MDD ceilings

- Composer MDD ceiling relative to unlevered benchmark: `CAPITAL_PRESERVATION` 1.00 / `BALANCED_COMPOUNDING` 1.25 / `GROWTH_COMPOUNDING` 1.50
- `promotion_sizing` scale: 0.50 / 0.75 / 1.00 for new promotions or material revisions; plugin scalar <= 1
- Never treat 1.50x as a 1.5x position multiplier, and never recompute legacy live allocations using promotion scaling.

## Risk input errors and action contract

`target_vol=None` falls back to the existing default; explicit non-positive, non-finite, boolean, or non-numeric values prohibit new risk. Invalid realized volatility, drawdown, or equity also prohibits new risk. Numeric envelope scales are diagnostic only; callers must inspect `new_risk_allowed` and reason codes.

`NewRiskAdmissionResult` exposes `risk_input_invalid` and `hard_brake_triggered` (default `False`). When data is invalid without a trusted drawdown hard brake, `combined_scale=None` does not mean zero target weight; when a trusted hard brake is also active, both flags are `True` and scale stays `0`. `apply_envelope_to_sized_weight` returns `None` for invalid data or `0` when a trusted hard brake applies. Consumers must handle optional return values before rollout.

## Persistent drawdown OPEN in account logs

`AccountSubmissionSession.record_circuit_breaker_open(snapshot=...)` records a confirmed drawdown hard brake as `CIRCUIT_BREAKER_OPEN` in the physical account's append-only `account_submission.v1` log using exclusive creation, sequential numbering, hash chaining, and full readback without creating separate state files. Events store only injected equity/peak/drawdown and caller identity, proving neither true cash-flow basis nor upstream origin.

If explicit drawdown is invalid while valid equity and peak confirm a breach, the log preserves equity and peak, writes `drawdown=null`, and recomputes drawdown on readback so the breach is never lost. Conversely, if explicit drawdown confirms a breach while peak is invalid, equity and drawdown are preserved with `peak=null`. Original invalid values are still reported by the risk gate.

`read_state()` adds `circuit_breaker_open` (bool). Legacy logs start `False`; once `OPEN` is recorded, it remains `True` across profiles and process restarts. Healthy observations, `CLOSED` snapshots, or reset-shaped events cannot clear it; no reset API exists. Invalid input, conflicts, corruption, or unconfirmed writes prohibit new risk.

Platforms use `reserve(order, new_risk=True)` to record new-risk classification in `PREPARED`. `OPEN` rejects `reserve` and re-checks before `dispatch`, blocking prepared but unsent new-risk orders (wired for IBKR buy orders; callers omitting the flag keep existing per-platform classification). `OPEN` creates no targets, generates no sell orders, does not replace risk-reduction proof, and leaves `UNKNOWN` semantics unchanged.

After order and account validation, `dispatch` acquires the account log's in-process and cross-process guard, re-reads `OPEN`, and holds the guard through `submit` and outcome persistence. Local logs use kernel exclusive file locks on the log file (processes sharing a lock domain only; not cross-host coordination). ObjectStore lacks lock-release or CAS primitives, so a create-only ownership record binds a single process and requires readback confirmation before writing `OPEN` or dispatching; forked children, restarts, or peer processes cannot steal it, and failed lock or ownership checks refuse dispatch.

Identity is re-verified after acquiring the guard, after final log read, and immediately before `submit`: local logs verify device/inode against the lock path and reject missing, replaced, or symlinked paths; ObjectStore re-reads and checks process ownership. Lost locks or records cannot be reconstructed to recover a session. Failed checks stop writes while leaving consumed attempts pending (never retried as unsent). Post-submit checks cannot undo a broker call already in flight, and in-flight orders precede a concurrent `OPEN` without claiming cancellation.

Because `CIRCUIT_BREAKER_OPEN` is a new append-only event type, older readers reject logs containing it. Never mix old and new writers: review library and platform patches, coordinate pin upgrades, stop legacy writers, and verify deployment separately. Offline synthetic logs do not prove initial production state, stopped legacy writers, consumer upgrades, or live behavior.
