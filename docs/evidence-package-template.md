# Strategy Promotion Evidence Package

This template defines the minimum package to request `live_candidate` review.

## Required contents

- strategy profile name
- target platform(s)
- backtest summary
- drift / regime notes
- platform compatibility evidence
- plugin gate status, if applicable
- operator notes and rollout constraints

## Suggested structure

```text
profile: cn_chinext_growth_momentum_quality
market: cn_equity
requested_stage: live_candidate

1. Backtest summary
2. Drift and regime observations
3. Risk review
4. Platform compatibility evidence
5. Plugin gate status
6. Rollout notes
```

## Acceptance rule

If any of the following are missing, keep the profile out of live settings:

- the profile is not runtime-compatible with the target platform
- the plugin gate is not clearly approved or notification-only
- the evidence does not cover both performance and regime sensitivity
- the request is based on a single good window only

## Ownership

- strategy repo: produces the evidence package
- platform repo: verifies runtime compatibility and gate status
- operator review: makes the final live decision

## Canonical promotion package (v2)

Promotion reruns must produce a new `strategy_evidence_package.v2` that validates against the packaged `strategy-evidence-package.v2.schema.json` and the dependency-free Python validator. Do not relabel or implicitly migrate a v1/alias package.

The closed v2 object binds strategy and input provenance, the exact `BacktestOrchestrator` `purged_walk_forward.v1` output, at least three ordered folds, positive purge/embargo, an independent locked OOS window of at least 12 calendar months, timing/cost/risk/metric identities, verified repo-relative artifact bytes and SHA-256 digests, and a human acceptance bound to the evidence-core digest.

Required lifecycle claims are fail-closed:

- learning: `learning_only=true`, `promotion_eligible=false`, `live_ready=false`, `size_zero_required=true`, `no_order=true`;
- accepted promotion evidence may set `promotion_eligible=true`, but must still keep `live_ready=false`, `size_zero_required=true`, and `no_order=true`.

Structural validation does not invent performance thresholds. Metric quality remains a bound human promotion decision. A requested stage, CI/PR/review/health result, or notification never grants paper, shadow, live, order, or capital authority; live/runtime requests remain `HOLD`.
