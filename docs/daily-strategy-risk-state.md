# Daily strategy risk state

`read_daily_strategy_risk_state` reads the existing create-only strategy risk
state chain. It returns `available` with the validated head, `missing` when no
root exists, and `unavailable` on read or integrity failure. Missing or
unavailable state does not establish an inactive risk control.

`coordinate_daily_strategy_risk_state` accepts a fully constructed transition.
It returns `confirmed` with that transition only after finding the identical
head or appending and reading back the identical head. A changed same-session
transition, stale predecessor, or changed head at readback returns `conflict`.
Read and write failures return `unavailable`; a write failure can leave an
uncertain durable outcome, so the caller must re-read before retrying. The
underlying chain permits one transition per session. The caller must validate
expected session continuity and frozen inputs before constructing a transition.

For an absent chain, the coordinator returns `missing` unless the caller passes
`DailyRiskStateBootstrapAuthorization` matching the exact identity, session,
input digest and root transition digest. This object records the caller's
explicit authorization decision; it is not a signature or proof of external
approval. The caller must independently verify that authorization. The generic
store remains available to existing research users and does not enforce this
guard itself.

The coordinator grants no execution authority. Persisting a state does not
fence a later submission against concurrent state changes: a platform must
bind the actual decision and intent to the durable state at the appropriate
execution boundary. This daily contract does not define an intraday event
ordering or prove that no trading sessions were omitted.

## Joint state and submission journal

An explicitly enrolled account may use the account submission journal as its
single authoritative sequence for TQQQ daily state and order reservations.
Enrollment loads and validates the exact legacy state head and binds the
physical account, account domain, owner, release, strategy identity, and a
migration authorization receipt digest. The caller must independently verify
the authorization and arrange a quiescent cutover; the receipt digest is not
proof of authorization. After cutover, the legacy state chain is evidence, not
the authoritative head. Every enrolled state writer and submission path must
use the same account journal. Unenrolled accounts retain their existing path.

An ordinary reservation requires the exact current state digest, session and
pending-intent digest. The account journal also binds the post-risk submission
intent and order. The caller is responsible for establishing the market
session, validating decision inputs and applying the production risk gate.
A state advance cannot pass an unresolved prepared, unknown or pending
submission. Concurrent state changes and reservations compete for the same
create-only sequence. Existing independently verified account-brake reductions retain their separate
admission. An enrolled strategy reduction also requires a complete, fresh account
snapshot with no open orders, a position in the opposite direction at least as
large as the order, and no unresolved journal submissions. The journal checks
prior fill and fee coverage; an order side alone proves nothing. A process-local
planning handle permits only conditional candidate calculation. The final
post-risk intent and order require a separate journal reservation.

The journal reservation and state change are atomic with respect to each
other, but an external broker call is not part of that transaction. An unknown
or pending broker outcome requires actual reconciliation; elapsed time or a
summary count does not establish cancellation or a fill. Enrollment does not
activate an account, authorize an order, authenticate input provenance, or
replace broker and account controls.
