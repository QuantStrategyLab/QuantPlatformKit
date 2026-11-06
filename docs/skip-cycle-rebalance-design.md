# Skip one rebalance cycle (design only)

Status: draft design, no runtime binding. This PR must remain draft and must not
be merged as part of this follow-up. It adds no executable trading code,
configuration, identity, credential, permission, endpoint, or deployment.

## Purpose and current source evidence

A verified severe reviewer consensus may request that one identified rebalance
cycle submit **zero new orders**, including buys, sells, options, hedges and cash
sweeps. It cannot authorize orders, liquidate a portfolio, cancel existing orders,
change targets, resume trading, or clear another block. Already outstanding orders
can still fill; skipping a cycle is not a claim that broker positions are frozen.

There is no verified cycle-pause interface today. The following existing code
locations define where a future implementation would consume the flag:

- QPK `common/feature_snapshot_runtime.py:evaluate_feature_snapshot_strategy`
  already returns a fail-closed strategy result before strategy evaluation when
  snapshot admission fails. Add the cycle-denial decision beside this existing
  pre-trade guard, before generating actionable rebalance targets.
- InteractiveBrokersPlatform `application/execution_service.py:execute_rebalance`
  already checks live risk authority and wraps every submission in
  `submit_claimed_order`, which requires an execution claim. The same denial must
  be enforced before any plan executes and again in that existing final submission
  guard, before calling its delegate. Broker adapters need equivalent enforcement
  before adoption; one IBKR example does not prove fleet coverage.
- QPK `execution_kernel/guards.py` contains pure deny/allow decisions. Current IBKR
  `consult_t1_live_submit` is **shadow-only** and explicitly ignores its result.
  Adding a shadow denial there alone would not pause anything. Do not change
  shadow behavior or present it as a functioning pause interface.

Source anchors: QPK main `ec26c1e94c8e06d758520711eba6b7d4603597ee`; IBKR main
`1bbf9ddbecddeef4f680f4bc5259bf5902e1b5dd`, read from GitHub during this review.
These are source observations, not production image or runtime acceptance.

## Flag and ownership

Use a caller-owned record `skip_cycle_rebalance.v1`, keyed by the **existing
durable cycle identity**. The runtime, not model text, constructs its scope:

```json
{
  "schema": "skip_cycle_rebalance.v1",
  "cycle_id": "<existing durable cycle identity>",
  "runtime_target": "<existing target identity>",
  "account_scope_sha256": "<hash of approved account scope>",
  "strategy_release": "<approved release identity>",
  "snapshot_sha256": "<frozen cycle input hash>",
  "skip": true,
  "reason": "missing_stale_inputs",
  "review_material_sha256": "<frozen material hash>",
  "review_receipt_ids": ["<validated primary>", "<validated independent>"],
  "recorded_at": "<UTC timestamp>"
}
```

The example is a contract, not a flag written to any runtime. Identifiers are
opaque metadata; secrets and raw account numbers never enter this record.
Allowed reasons are `data_integrity`, `risk_limit`, `missing_stale_inputs`.
Reject extra fields, duplicate JSON keys, incorrect types, missing scope, and any
`skip` value other than literal `true`. There is no `skip=false`, delete, reset,
resume, order or configuration operation exposed to the review writer.

The existing review consumer validates complete, distinct admitted reviewer roles,
current frozen material and receipts before setting a flag. All required roles
must flag the same severe category. Unverified Dot identity, a configured profile
name, missing secrets, or an advisory opinion alone cannot become authority to
write a runtime flag. If the admitted review channel is unavailable, the pre-trade
guard denies with `cycle_review_unavailable`; it does not invent a successful
consensus. No new IAM or secret access is proposed.

The future producer can only append an immutable skip record for the current
scope to an **already authorized durable store**. A repeated identical write is
idempotent; conflicting records deny and require investigation. Existing request
IDs with unknown outcomes are reconciled read-only, never replaced. If there is
no suitable existing store and producer identity, implementation/adoption stays
blocked. This design does not authorize creating either.

## Guard behavior

An admitted reader returns either a validated current-cycle skip, an authoritative
complete `absent` result for that exact key, or `unavailable`. File-not-found,
truncated listings, permission errors, timeouts and unknown writes must not be
silently interpreted as authoritative absence.

| Observed input | Guard result | Effect |
| --- | --- | --- |
| Valid skip matching every current scope field | deny `cycle_rebalance_skipped` | No new order of any side or instrument |
| Invalid, conflicting, unreadable or unresolved current lookup | deny `cycle_skip_state_unavailable` | No new order; operational alert |
| Admitted review channel unavailable | deny `cycle_review_unavailable` | No new order; operational alert |
| Authoritative absence for current key | keep original guard result | Adds no trading authority |
| Valid older-cycle record plus authoritative current absence | keep original guard result | Previous record cannot enable or disable another cycle |
| Existing guard already denies | preserve denial | Flag processing cannot change deny to allow |

Conceptually the existing guard computes:

```text
denied = original_guard_denied OR current_cycle_skip OR skip_read_unavailable
         OR admitted_cycle_review_unavailable
```

On denial, return the existing blocked/no-op execution result with
`orders_submitted=[]` and the explicit reason. Do not emulate holding by setting
targets to zero or cash: existing execution logic could turn that into sells.
Do not return a buy-only prohibition: it could still permit sells. Read-only
observation and original pending-order reconciliation may continue.

Keep the skip latched for all retries of the same durable cycle. A process restart,
new invocation UUID, changed timestamp or timeout must not produce a replacement
cycle that avoids it. A flag's age never clears it for that cycle. A genuinely new
cycle uses a new existing durable identity and must satisfy every original gate;
this is not automatic approval or an auto-resume command. `RECONCILE_ONLY`, unknown
submission, risk limits, live-enable, release admission and all existing claims
remain independently binding.

Before adoption, prove that flag publication and the final submission guard use
the existing cycle/claim serialization boundary: either the skip is committed
before cycle admission, or the final submission read observes it before delegate
execution. A separate best-effort read with a check-to-submit race is insufficient.
Late flags cannot undo earlier orders; report the actual submission state and
deny subsequent submissions. If existing storage/claims cannot provide this
ordering, keep adoption blocked instead of claiming a verified pause interface.

## Required offline and adoption evidence

Implementation tests must inject fake stores and broker delegates, and assert zero
delegate calls for valid skip, malformed state, read failure, stale current
receipt, disagreement, duplicate roles, unknown writer outcome and existing
denial. Cover sell, buy, cash sweep and option paths; retries/restarts must stay
denied. Prove a different cycle cannot inherit or bypass a skip, and unchanged
absence never changes the original decision. Cover a flag appearing between
planning and submission through the existing serialized claim boundary.

This documentation-only draft does not run those tests or claim implementation.
Future binding requires the approved store/identity, all broker path coverage,
the concurrency proof and a separately authorized adoption. Until then severe
consensus keeps reporting `pause_not_available` and notifying the owner honestly.
