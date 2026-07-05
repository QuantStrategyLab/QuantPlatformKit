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
