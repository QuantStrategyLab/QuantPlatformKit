# Adaptive Allocation Control Plane (Shadow-Only Observation Slice)

[简体中文](adaptive-allocation-control-plane.zh-CN.md)

This module produces uniform, read-only shadow selection decisions without granting trading authority. It explains why an approved strategy and platform pair is suggested for shadow observation rather than letting a model mutate live runtime configuration.

This selector is not lifecycle stage `P0`. Canonical `P0` remains the authorized policy and control root, and this module never implies that `P4` Paper, `P5` Shadow, or `P6` Live is active or approved.

## Inputs and outputs

All inputs must be versioned and replayable:

- `qsl.market_context_snapshot.v1`: verifiable market factors, regime state, confidence, and data freshness.
- `qsl.platform_health_snapshot.v1`: platform health, reconciliation state, capacity, and cost estimates.
- Approved immutable `StrategyRelease` identities and plugin risk multipliers.

The output is `qsl.selection_decision.v1`, recording candidate status, rejection reasons, platform selection, strategy scores, canonical input digest, and an independent decision digest. Outputs always fix `authority=shadow_only`, `no_order=true`, and zero suggested weights.

## Common integration boundary

Any strategy or platform repository may submit a `qsl.selection_input.v1` JSON payload to `quant-adaptive-selection` to generate a replayable decision artifact:

```bash
quant-adaptive-selection --input selection-input.json --output selection-decision.json
```

Inputs use closed schemas and require timezone-aware platform health snapshots within policy TTL, versioned market context, immutable candidate releases, plugin risk multipliers, and frozen policy settings. The optional `ttl` field defaults to `3600` seconds for backward compatibility. The CLI accepts no broker credentials, runtime targets, or order parameters; its output file is a JSON artifact only and modifies no platform or scheduler state.

## Fixed boundaries

- Never trade directly from news narratives; factors must originate from versioned data pipelines.
- Fail closed on stale data, unknown state, insufficient confidence, unapproved plugins, or unreconciled/unhealthy platforms.
- Plugins may only provide `0..1` risk scaling and cannot raise risk or submit orders.
- Only candidates with shadow admission and a bound immutable release can be ranked; `shadow_candidate` may receive a zero-weight recommendation to enter shadow, never a runtime launch.
- This module cannot mutate platforms, strategies, plugin mounts, positions, or schedulers.

Downstream presentation layers (`M1`) display shadow conclusions to operators; progression to `M2`/`M3` still requires independent paper, canary, dual-AI review, and existing risk authorizations.

## Boundary with advisor research (`QuantAdvisorResearch`)

`QuantAdvisorResearch` acts as an **AssetIdeaAdvisor**: it identifies instruments or themes worth researching and provides non-personalized rationale, risk notes, and observation horizons. It is neither a portfolio allocator nor a strategy/platform selector.

This control plane answers a separate question: among lifecycle-admitted strategies bound to immutable releases, which candidates qualify for **zero-weight shadow recommendations** given verifiable market data and platform reconciliation health. It never treats advisor `recommend` tags, news text, theme narratives, or manual preferences as executable scores.

Only the following one-way, delayed research path is allowed between the two systems:

```text
Advisor research findings
  -> Operator / dual-AI research hypothesis
  -> P1-P3 data, backtests, and independent evidence
  -> Immutable strategy candidate
  -> Shadow-only selection record
  -> M1 operator review
```

Prohibited shortcuts:

- Feeding advisor artifacts directly into `qsl.selection_input.v1` as market factors, `base_score`, plugin risk multipliers, platform health, or strategy weights.
- Letting advisor reports invoke strategy switches, runtime targets, brokers, or order endpoints.
- Writing shadow selection outcomes back into advisor outputs as "market validation" to avoid self-confirming feedback loops.
- Overriding deterministic risk gates, reconciliation failures, or lifecycle rejections with advisor conclusions; advisor findings may trigger research only.

Console views (`M1`) must display research leads and shadow runtime recommendations in separate panels with clear labels. A text recommendation for an asset or theme is never position intent; nothing enters a runtime path without independent `P1`-`P6` evidence.
