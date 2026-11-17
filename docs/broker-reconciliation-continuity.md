# Broker Reconciliation Continuity Contract for Legacy Live Baselines

[简体中文](broker-reconciliation-continuity.zh-CN.md)

`RECONCILE_ONLY` is the protective state entered by a legacy live baseline
after migration, configuration drift, or runtime anomalies. It permits
read-only verification while blocking normal strategy order placement. Service
health, API authentication, or isolated position reads never restore
`ACTIVE_LKG`.

The shared library's `broker_reconciliation_evidence.v1` defines a
cross-platform recovery receipt. A platform adapter must verify all of the
following within one read-only session and write only digests and boolean
outcomes into the receipt:

- Connected to the expected broker account.
- Current positions match the state derived from the local execution ledger.
- Cash balances match trusted expected cash facts.
- Open orders match.
- Recent fills and order history match.
- The local idempotent execution ledger is intact and consistent.
- The active runtime target digest still equals the frozen baseline digest.

Positions, cash balances, orders, fills, and account scopes must never enter
public repositories, logs, or notifications. Adapters compute SHA-256 digests
locally over canonicalized read-only snapshots; receipts store only those
digests, `observed_at`, and stable failure codes. Private control planes may
retain access-controlled verification inputs for independent recomputation
while public artifacts carry receipts only.

Cash reconciliation must compare platform-defined stable cash facts across
identical currency, account, and observation scope. Because `buying_power`,
total equity, and market value fluctuate with broker rules or market prices,
preserve them for real-time risk checks rather than treating their movement as
a cash discrepancy. Digest field coverage must match the comparison algorithm;
legacy digests cannot backfill new fields, and current observations cannot
automatically become the approved baseline.

## Platform facts and comparison states

Platforms are responsible for proving data came from the target account,
observation time, and query scope, and for reporting coverage boundaries across
positions, cash, open orders, fills, and the execution ledger. Truncation,
insufficient lookback windows, undetermined identity, or read failures cannot
pass as complete empty sets; an empty set is valid only when reads succeed
with full coverage. Completeness of `broker_connected`, digests, or match
outcomes cannot be inferred from HTTP 200 status or matching digests alone.

For diagnostics and operator display, distinguish per-item outcomes and retain
read-failure or source-unavailability reasons:

| Status | Meaning |
|---|---|
| `not_configured` | Expected digest for comparison is missing |
| `not_compared` | Comparison could not complete, e.g., incomplete coverage |
| `matched` | Coverage was full and digests matched under the same contract |
| `mismatched` | Compared under the same contract and digests differed; inspect facts and digest version |
| `read_failed` | Required read failed; no successful comparison can be produced |

These are display semantics rather than new shared schema fields. Existing
`broker_reconciliation_evidence.v1` `*_match` booleans can be `False` due to
missing configuration, skipped comparison, or mismatch; interpret them
alongside coverage, configuration, and errors rather than claiming an
accounting break from `False` alone. Whole-receipt summaries must not mask
uncompared items, and independent connectivity, identity, freshness, and
target-binding blocks remain enforced.

## Three recovery scenarios

The flows below apply to recovery from `RECONCILE_ONLY`. Normal process restarts
where an approved baseline and healthy state remain intact do not require
re-enrollment or re-confirmation, though ordinary execution remains gated by
real-time risk checks.

1. **Frozen baseline available**: compare against the approved baseline and
   independent sources following the recovery sequence below; never overwrite
   expected digests with a live snapshot.
2. **First enrollment of a legacy instance**: establish provenance and
   integrity via the v2 candidate and human confirmation flow below; fresh
   observations alone do not authorize recovery or backfill unknown history.
3. **Unresolved history or unknown accounting baseline**: retain legacy claims
   and `UNKNOWN` state without replaying old intents or altering ledger
   namespaces to bypass deduplication. Verify current account facts, open
   orders, fills, and cash flows, quantify unverified historical risk, and let
   the account owner decide whether to accept a new baseline. Existing v2 and
   activation interfaces neither isolate unknown history nor approve new
   baselines automatically.

## Recovery sequence

1. The platform generates a candidate receipt in a read-only broker session;
   connection or read failures fail immediately.
2. The trusted control plane re-verifies receipt digests, account scope,
   baseline target, and freshness (default 30 minutes).
3. The control plane verifies private snapshots and local ledgers against
   independent sources rather than trusting adapter `*_match=true` flags alone.
4. Only after every check passes may a privilege-protected control plane
   transition the frozen baseline from `RECONCILE_ONLY` to `ACTIVE_LKG`. This
   is neither strategy promotion nor a capital increase.

If any step is missing, stale, or inconsistent, remain in `RECONCILE_ONLY` and
emit redacted failure codes for the console. New strategies follow the separate
`P0`-`P6` lifecycle; this contract governs continuity only for previously
authorized legacy live baselines.

## First enrollment into a trusted baseline (legacy instances)

Legacy instances may lack local execution ledgers or historical digests and
must never record the first observed broker state directly as expected state.
The shared library generates **human-confirmation candidates** only and holds
no recovery authority:

1. New enrollments explicitly use `broker_reconciliation_baseline_candidate.v2`
   with `source_receipts_sha256`; at least one fresh receipt is required (no
   second sample or minimum separation interval is mandatory; default max
   observation window remains 15 minutes and max receipt age 30 minutes).
2. Each receipt must show successful broker connection, consistent account
   identity, matching baseline runtime target, and completed reconciliation
   across positions, cash, open orders, recent fills, and local ledger by a
   trusted producer.
3. Multiple receipts must bind identical identity and five-part state digests,
   keeping the five-digest check in activation unchanged.
4. Candidates store digests, source roots, and timestamps only—never raw
   account data or execution authority.

**A source root proves content binding only, not truth, completeness, or
authorization.** Platform producers must verify account binding, query
boundaries, open orders, accounting baseline, and discrepancy explanations
before emitting receipts. The shared library does not read raw source records
and cannot prove account safety from digests, duplicate samples, or unverified
`*_match=True` values.

Model reviews remain advisory rather than a voting gate for human confirmation.
Omitted reviews stay `unavailable` with `reviewer_count=0`, and
`rejected`/`unavailable` reviews are never rewritten to `approved`. Provided
reviews stay bound to the candidate so opinions cannot cross-apply. Explicit
human confirmation remains mandatory, and this contract grants no account
takeover, live trading, order, or capital authority.

Legacy `v1` parsing and round-trips remain intact without automatic migration,
though source-root-less `v1` candidates cannot enter new human confirmation or
activation. New callers use enrollment's optional `source_receipts_sha256`
parameter to emit `v2`; `min_separation` remains accepted for compatibility
without imposing a separation gate.

## Shared publish and recovery-plan ports

`reconciliation_recovery.py` defines three **side-effect-free** cross-platform
contracts:

1. `ReconciliationRecoverySourceSnapshot` exports redacted candidates, optional
   advisory reviews, observation windows, and stable blocker codes as
   `qsl_reconciliation_recovery_source_snapshot.v1` for a dedicated publisher
   port, omitting accounts, positions, cash, orders, fills, and five-part state
   digests.
2. `ReconciliationRecoveryConfirmation` reads console-stored
   `qsl_reconciliation_recovery_confirmation.v1` receipts with fixed
   `no_order=true` and `execution_authority_granted=false`, never implying order
   or state-write authority.
3. `evaluate_reconciliation_recovery_activation` requires a source-bound v2
   candidate, matching human confirmation, a **post-confirmation** read-only
   broker receipt, current state still `RECONCILE_ONLY`, and matching five-part
   digests before returning a `RECONCILE_ONLY -> ACTIVE_LKG` compare-and-set
   plan.

The shared library implements no publisher HTTP transport, confirmation storage
reads, source verification, or state writes. `dual_review_binding_reverified`
is deprecated and kept for compatibility only. Private platform controllers must
implement these ports with least-privilege IAM, verifying current state, frozen
target digest, and five-part digests within one atomic compare-and-set
transaction. Read failures, expired confirmations, non-post-confirmation
receipts, failed source verification, or CAS conflicts must never retry as
normal execution and must remain `RECONCILE_ONLY`.
