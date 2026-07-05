# Strategy Lifecycle Policy

[简体中文](./strategy_lifecycle_policy.zh-CN.md)

This document defines the lifecycle gates for strategy profiles across the
quant repositories.

## Design Goal

The lifecycle should be permissive for research and monitoring, but strict for
capital impact.

- AI monitoring may accelerate review and highlight drift.
- AI monitoring must not bypass the live-enable gate.
- A strategy can be observed earlier than it can trade.
- Live enablement remains a platform decision, not just a backtest decision.

## Recommended Lifecycle Stages

| Stage | Meaning | Capital impact | Typical owner |
| --- | --- | --- | --- |
| `research_backtest_only` | Backtests, feature work, or evidence collection only | none | strategy repo |
| `ai_monitored_candidate` | Eligible for AI review, drift scoring, and shadow tracking | none | strategy lifecycle |
| `shadow_candidate` | Shadow runs are stable enough for repeatable comparisons | none | strategy lifecycle |
| `live_candidate` | Passed validation and is awaiting platform enablement | gated | platform + strategy |
| `runtime_enabled` | Exposed by `get_runtime_enabled_profiles()` and allowed in runtime settings | yes | platform repo |

### Practical interpretation

- `research_backtest_only` is the default for anything new.
- `ai_monitored_candidate` is the lowest-friction review stage when the
  organization already has automated monitoring.
- `shadow_candidate` should require repeatable shadow consistency, not just one
  good backtest.
- `live_candidate` should only be used when the strategy has enough evidence to
  justify platform enablement.
- `runtime_enabled` is the only stage that should influence live deployment
  defaults.

## Three-Gate Rule

A strategy should clear all three gates before live use:

1. **Strategy gate**
   - Does the strategy have enough history, risk characterization, and drift
     tolerance to move beyond research?
2. **Plugin gate**
   - If the strategy depends on plugins, are those plugins at least
     `automation_approved` or explicitly `notification_only`?
3. **Platform gate**
   - Does the target platform expose the profile via
     `get_runtime_enabled_profiles()` and accept the required runtime inputs?

Any one of these gates failing should keep the profile out of live settings.

## Recommended Promotion Policy

- Keep the monitoring threshold relatively low so candidates are visible early.
- If AI monitoring already exists, use it to move promising profiles into
  `ai_monitored_candidate` quickly; this stage is for visibility, not capital.
- Keep the live-enable threshold high so runtime exposure remains deliberate.
- Prefer promotion by evidence package, not by ad hoc overrides. A promotion
  package should include backtest summary, drift notes, risk review, and
  platform compatibility evidence.
- See [`evidence_package_template.md`](./evidence_package_template.md) for the
  recommended package shape.
- When a strategy is a wrapper or orchestrator, promote it only after the
  wrapped components are stable and the wrapper itself has been validated.

## Repo-Level Guidance

- **US equity**: long-history trend / rotation profiles can move through the
  lifecycle earlier; wrapper combos should stay candidate-first.
- **HK equity**: keep live exposure narrow and promote only stable runtime
  profiles.
- **CN equity**: treat QMT-specific optional runtime profiles separately from
  the main live catalog.
- **Crypto**: keep the monitoring stage permissive, but use a stricter live
  gate because regime shifts are faster.

## Operational Rule

If a profile is not returned by `get_runtime_enabled_profiles()`, it should
stay out of live runtime settings regardless of monitoring status.
