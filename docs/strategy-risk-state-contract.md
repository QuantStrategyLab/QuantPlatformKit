# Strategy risk-state transition contract

`quant_platform_kit.common.strategy_risk_state` records immutable state
transitions for a strategy-owned risk rule. It is intended for rules that need
memory between sessions, such as a cooldown after a volatility deleveraging
event.

It is **not** an execution command, broker adapter, position store, scheduler,
or source of allocation authority. A strategy owns the deterministic transition
rule. A platform may later persist the records in a dedicated append-only store
and must not infer state from an execution report or a restarted container.

## Identity and transition

Every transition binds a logical `strategy_profile`, `account_scope`, frozen
`candidate_id`, and `config_sha256`. It also binds one frozen input digest,
one effective session, the prior transition digest (or `null` at chain root),
and the strategy-produced state object.

The complete payload is canonical JSON and content-addressed by
`transition_sha256`. A replay must use the same strategy/config identity and a
strictly later session. Missing, altered, duplicate-session, or cross-candidate
state is rejected.

`account_scope` is a logical label, never a broker account identifier. State
objects must contain only bounded, non-secret strategy diagnostics; never raw
broker responses, credentials, account numbers, or order IDs.

## Staged use

1. Add a pure, strategy-specific transition function and deterministic replay
   tests. It must be safe to run with no platform or broker.
2. Add a paper-only platform adapter with a dedicated `StrategyRiskStateStore`
   and audited transition receipts. The store puts the root at a deterministic
   chain location and each successor at its prior digest location. Atomic
   create-only semantics therefore allow exactly one successor to any head;
   crash, duplicate delivery, concurrent writers, missing predecessor, and
   input/config mismatch fail closed. It never shares an execution-command URI.
3. Collect immutable forward observations and compare them with the unchanged
   candidate before considering a new research candidate.

This contract does not change any current strategy parameter, plugin authority,
paper/shadow/live status, account, or order route.
