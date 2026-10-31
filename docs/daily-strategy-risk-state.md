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
