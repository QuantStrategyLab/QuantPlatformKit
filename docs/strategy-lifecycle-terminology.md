# Strategy Lifecycle Terminology

[简体中文](strategy-lifecycle-terminology.zh-CN.md)

The current system no longer treats `research-only` as "halted development". It indicates that automated research may process the strategy continuously while trading authority remains disabled.

| State | Permitted | Forbidden |
|---|---|---|
| `research_active` | Historical backtests, parameter optimization, portfolio analysis, AI research, candidate revisions | Live order submission |
| `shadow_active` | Forward/shadow runs on live market data, drift monitoring | Real funds and broker orders |
| `paper_active` | Paper-account execution (when supported by platform) | Real funds |
| `live_candidate` | Live package preparation, risk checks, notifications | Automatic live enablement |
| `live_enabled` | Execution within approved authority | Bypassing the Risk Gate or expanding authority automatically |

Lifecycle states describe progression stages only and never grant execution authority. Even if a catalog or inventory lists `live_enabled`, execution layers must still verify unexpired deployment authority, account and broker permissions, the central Risk Gate, and current risk limits independently. No catalog or inventory may derive order permission automatically.

## Legacy state compatibility mapping

| Legacy catalog state | Mapped canonical state | Notes |
|---|---|---|
| `research_backtest_only` | `research_active` | Research continues; not halted |
| `ai_monitored_candidate` | `research_active` | AI monitoring is a capability, not a separate stage |
| `shadow_candidate` | `shadow_active` | Keeps `no_order=true` |
| `runtime_enabled` | `live_candidate` | Indicates legacy runtime selectability only, not live authorization |

Legacy deployments that already have live authority may report `live_enabled` only while independent deployment authority remains valid; that status must come from deployment and account control planes, never from the compatibility mapping above.

Legacy references to `research-only` map to:

```text
research_active + automated progression to shadow/forward + no_order=true
```

Platforms lacking paper accounts may run shadow directly without blocking the research pipeline.

## Existing live legacy strategies

Legacy strategies that already hold live authority continue operating as production baselines without halting or rewriting during migration. Automated tooling handles:

- Daily performance, risk, data quality, and drift recording.
- Generating parameter, plugin, and candidate revision proposals.
- Running historical validation and shadow/forward evaluation first on proposed changes.
- Automated pausing, de-risking, or rollback to the last stable revision on hard risk triggers.

Automated optimization cannot expand live capital, leverage, instrument scope, or broker permissions; those changes always require an independent human live decision.
