# Strategy Release and Runtime Receipt Contract (v1)

[简体中文](strategy-release-runtime-contract.zh-CN.md)

`StrategyReleaseManifest` is an immutable release record binding strategy,
configuration, risk rules, evidence, and plugin bundles. It is neither a
backtest result nor standalone trading authorization.

Each runtime instance receives only the compact `StrategyReleaseIdentity`.
Every runtime report includes `runtime_release_receipt`:

- `self_attested`: this process loaded a complete release identity (does not
  prove cross-platform consistency).
- `legacy_unattested`: a legacy runtime instance has no release identity;
  monitoring must surface this as a migration gap rather than treating empty
  versions as healthy.

Before command gates go live, legacy instances keep existing execution
semantics, though any risk-increasing release must never enter `ACTIVE` in
`legacy_unattested` state.

Plugin V2 may provide shadow signals to strategies for display, diagnostics, and
research. Shared-library snapshot injection forces all order, position, and
allocation authority flags to `false` while preserving raw artifacts in
`StrategyPluginSignal.payload` for auditability; plugins cannot authorize
strategy position changes via metadata.

Cross-platform releases must satisfy in order: every target pre-loads the same
release, every runtime reports the identical identity, activation uses a
unified effective trading date, and the observation period completes. Any
missing receipt or digest mismatch blocks `ACTIVE` promotion.

## One-time setup intent

`common.automation_setup.SetupIntent` and
`schemas/automation-setup-intent.v1.schema.json` define an independent,
non-executing setup intent contract without changing existing `RuntimeTarget`,
`RuntimeControl`, candidate promotion, or research mandate interfaces.
Downstream consumers must pin a reviewed QPK revision before adopting it.

`SetupIntent.create(subject, decision=None)` validates and freezes the
contract; `to_dict()` and `from_dict()` support protected transport and
round-trip checks without exposing payloads in public listings. Schema
validation checks structure while Python checks verify digests, decimal amount
bounds, target/control alignment, and expiry ordering; deserialization cannot
renew or restore revoked intents.

`subject` records opaque account reference lists, currency, decimal string
amount and cap, `one_time` or `standing_plan` (with immutable `plan_ref`), fee
and reserve handling, instrument/action scope, `policy_ref`, and explicit
environment. Downstream protected storage maps real accounts; account selectors,
aliases, hosts, credentials, and free text are forbidden. Targets and releases
reuse existing public builders, and controls reuse `RuntimeControl` (and must
remain disabled). Control reserves are not confirmed budgets, and `LIVE`
indicates requested intent only without enabling execution. `release_id`
allows 3-128 chars (alphanumeric start plus `.`, `_`, `-`), and
`strategy_revision` allows 1-64 chars; both reject whitespace, path separators,
control chars, and sensitive patterns. Initial revision is `1`; subsequent
revisions must cite the prior `subject` digest (binding content only, never
authenticating owners or anonymizing resources).

`decision` records the matching `subject` digest and revision, `actor_ref`,
`decision_ref`, `confirmed`/`rejected`, `reviewed`/`effective`/`expires`
timestamps, and `state_version`/`epoch`. Finite timezone-aware expiry is
required with no open-ended default. It never embeds `PromotionDecision`,
masquerades as a candidate, or consumes a research nonce.

`classify_setup_intent(intent, now=..., current=..., proposed_subject=...)` is
a pure descriptive classifier. `current` must come fresh from an authenticated
source carrying setup/revision/digest, `decision_ref`, `state_version`/`epoch`,
`source_ref`, `checked_at`/`valid_until`, `current`/`revoked`/`superseded`,
independent prerequisites, and `activation_readback`. Missing, invalid,
mismatched, or out-of-window `current` blocks progression, and stale confirmed
decisions cannot override current revocations or superseding revisions. The
classifier never authenticates sources, saves state, or acquires cross-process
locks.

Outputs expose only `intent_status`, `requires_owner_setup`, `blocker_codes`,
`changed_fields`, `resume_condition`, `activation_readback`, and two
permanently `false` authority fields. Public listings and notification summaries
project only these allowed fields without exposing account references, raw
`subject`, or actors. Re-classifying an identical valid current confirmed
revision yields `requires_owner_setup=false` rather than demanding per-trade or
per-cycle confirmation. Changes to account, amount, environment, release,
policy, instrument, or plan appear in `changed_fields` and require confirming a
successor revision rather than expanding existing scope; rejections, expiries,
and revocations never trigger retries automatically.

Paper minimum must be integer `3`, `4`, or `5` as a requirement target rather
than completion proof. Because this module cannot verify full exchange trading
days, candidate forward windows, risk, reconciliation, or alert evidence, those
blockers stay active regardless of self-reported passes, simulated sessions, or
successful notifications. `activation_readback` always projects `unknown`,
separate from owner intent, and `LIVE` adds `LIVE_ACTIVATION_OWNER_NEEDED`.
Both authority flags stay `false` on every path, with no `may_submit`, executor,
budget math, or production switch writes.

When `QuantRuntimeSettings` adapts `automation_setup` subjects into
Decisions/list/store, authenticated sessions provide `actor`, writes compare
`subject` digest, revision, and `state_version`/`epoch` atomically, `request_id`
enforces idempotency and rejects mismatched reuse, and restarts or stale
processes cannot overwrite revocations. Readbacks bind backend apply evidence
with explicit acknowledgement; notifications and console clicks never imply live
execution, and actual confirmation or protected apply remains gated by owner
authorization.
