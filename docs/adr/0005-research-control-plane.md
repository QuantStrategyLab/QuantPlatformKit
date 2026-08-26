# ADR 0005: Research Control Plane for Strategy, Plugin, and Runtime Change

**Status:** Accepted policy; implementation is staged  
**Date:** 2026-08-27

## Context

QuantStrategyLab already separates strategy code, shared risk controls, plugin
artifacts, broker platforms, and deployment authority. It also has
`ResearchSpec`, `OptimizationSpec`, evidence packages, lifecycle stages, and
forward-observation policies. The remaining gap is a common control plane for
detecting an anomaly, evaluating a parameter change/strategy rewrite/new
strategy/plugin revision, and performing network-assisted research without
giving a source, AI worker, or research artifact capital authority.

The SOXL incident makes the first point concrete. Its targets were monetary
`target_value` values while the legacy static gate evaluated only weights. The
cause was a mismatch of target semantics at the risk boundary, not a deposit or
withdrawal changing the strategy formula. Cash flows remain a separate control
concern: a stale or wrong-scope equity denominator can distort target exposure,
and raw net-value returns can misclassify external cash flows as P&L.

## Decision

### One lifecycle, with research substates

The canonical lifecycle remains unchanged:

`research_active -> shadow_active -> paper_active -> live_candidate -> live_enabled`.

The research control plane records these *substates* within the first two
stages; it does not introduce a competing lifecycle:

`DISCOVERED -> SPEC_FROZEN -> TRIALS_RUNNING -> CANDIDATE_FROZEN ->
VALIDATED_OOS -> FORWARD_OBSERVING -> AWAITING_HUMAN -> ACCEPTED | REJECTED |
PARKED`.

Each candidate has a versioned identity and a `candidate_kind` of
`parameter_change`, `strategy_revision`, `new_strategy`, or `plugin_revision`.
It binds strategy/profile, code revision, parent candidate when present,
benchmark policy, configuration, data/cost manifests, trial ledger, source
bundle, and evidence digests. A candidate is not a live authorization.

### Automation boundary

The control plane may detect anomalies, collect research, propose hypotheses,
freeze specifications, run permitted research, create a reviewable pull request
and evidence bundle, start non-live shadow/paper work, and pause a
non-conforming target.

It must not automatically merge executable changes into a live deployment,
enable or resume live trading, change live parameters, enlarge capital or
leverage, expand broker/IAM permissions, or replace a data source. Those
actions require a human decision bound to candidate ID, evidence-core digest,
platform/account scope, and expiry.

### Monetary targets and capital basis

Every `target_value` must be normalized before exposure controls are evaluated.
The target producer and Risk Gate must use the same immutable
`CapitalBaseSnapshot`: scope ID; account/runtime/strategy scope; gross account
equity; strategy-allocated equity; net external flow; currency/FX basis;
observation time/freshness; and source digest. Missing, stale, zero, or
mismatched scope/basis fails closed for enforced value targets.

Compatibility exceptions are temporary, explicitly owned, and expire. They
emit value-free exposure telemetry during migration; they are not a permanent
opt-out from risk normalization. Performance/drift must use cash-flow-aware
time-weighted return, with money-weighted return reported separately where DCA
cash-flow experience is useful. A deposit or withdrawal is not investment
return.

### Validation and forward observation

Candidate evaluation uses a frozen specification and complete trial ledger,
including rejected and failed trials. It requires point-in-time and
survivorship controls, nested/purged walk-forward evaluation, an independently
locked OOS interval, cost/turnover/liquidity stress, and comparison with the
current production profile, passive benchmark, simple rule, risk-matched
benchmark, and relevant unlevered underlying. Leveraged strategies must report
drawdown and recovery relative to their unlevered reference.

A genuine shadow records candidate and baseline against the same timestamped
inputs: signals, hypothetical orders, positions, costs, and returns. A recent
production performance snapshot is monitoring, not candidate shadow evidence.

### Network-assisted research

Network content is untrusted data, never an instruction. The implementation is
split into least-privilege domains:

1. **Fetcher** has public-network access only and no repository, cloud,
   broker, or secret access.
2. **Quarantine corpus** stores source receipts: URL, publisher/author,
   retrieval time, content digest, declared licence/SPDX expression, permitted
   use, and `untrusted=true`.
3. **Planner/Builder** has no network or secrets. It consumes the bounded,
   sanitized corpus and emits structured hypotheses, specifications, and
   candidate code only.
4. **Publisher** has the minimum repository permission needed to create a
   research pull request. It cannot edit deployment settings, access secrets,
   or submit orders.

Unknown or incompatible licences permit citation/summary only, not copying
code or data into a candidate. Prompt-injection detection is advisory; the
security boundary is capability isolation, schema validation, bounded inputs
and outputs, no secrets, and human review of consequential actions.

Plugins remain observer-only artifacts. A plugin may emit a versioned signal,
provenance, and notification, but may not mutate positions or obtain broker
authority. Only the owning approved strategy candidate may deterministically
consume a signal, and the central Risk Gate remains final authority.

### Ownership

| Layer | Owns |
| --- | --- |
| QuantPlatformKit | contracts, lifecycle/state validation, digests, risk normalization, evidence and forward-observation ports |
| Strategy repositories | hypotheses, benchmarks, candidate formula/configuration, backtest runner, evidence production |
| Plugin repositories | signal schema, lineage, notification/shadow artifacts |
| Platform repositories | fresh capital-base snapshot, paper/shadow telemetry, broker execution receipt, independent live authorization |
| Research orchestrator | isolated research workers and research-only pull requests |

## Rollout

1. **P0 — safety and inventory.** Keep SOXL protected, merge generic
   value-target audit, inventory all `target_value` consumers, and record
   compatibility owners/expiry. Add cash-flow-aware capital-base contracts.
2. **P1 — shared contracts.** Add candidate, trigger, source-receipt,
   forward-receipt, and promotion-decision schemas; remove obsolete
   auto-approval semantics; align plugin observer-only language.
3. **P2 — real closed loop.** Run candidate and baseline in paired shadow,
   persist receipts, and connect strategy backtest runners to evidence flow.
4. **P3 — network research factory.** Introduce the isolated
   Fetcher/Corpus/Planner/Publisher pipeline, initially limited to research
   pull requests and evidence bundles.
5. **P4 — staged adoption.** Exercise the loop with SOXL as a research-only
   candidate, then migrate TQQQ, TECL, DCA, other domains, and plugins by
   target semantics and risk profile.

## Consequences and verification

This evolves the control plane without rewriting strategy formulas or platform
runtimes. Required tests cover target weight/value normalization; stale or
scope-mismatched capital bases; cash-flow metamorphic cases; multi-currency and
multi-target exposure; immutable trial/OOS evidence; paired-shadow replay;
source receipt tampering/licence/injection; plugin no-order invariants; and
authority-digest mismatch. Research, shadow, and paper receipts must never be
interpretable as live authorization.

