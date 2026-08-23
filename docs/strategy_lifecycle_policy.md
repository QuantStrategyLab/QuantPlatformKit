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

## Canonical Lifecycle Stages

| Stage | Meaning | Capital impact | Typical owner |
| --- | --- | --- | --- |
| `research_active` | Backtests, optimization, evidence collection, and candidate generation | none | strategy repo |
| `shadow_active` | Forward/shadow observation and drift tracking | none | strategy lifecycle |
| `paper_active` | Simulated-account execution when a platform supports it | simulated only | platform |
| `live_candidate` | Passed validation and is awaiting platform enablement | gated | platform + strategy |
| `live_enabled` | Runs only inside an independently approved deployment envelope | approved envelope only | deployment control plane |

### Practical interpretation

- `research_active` is the default for anything new and remains actively researched.
- AI monitoring is a capability of every applicable stage, not a promotion stage.
- `shadow_active` should require repeatable shadow consistency, not just one
  good backtest.
- `live_candidate` should only be used when the strategy has enough evidence to
  justify platform enablement.
- `live_enabled` records an existing deployment authorization; it does not
  create or enlarge that authorization.

### Legacy catalog compatibility

Read-only consumers normalize legacy values conservatively:

| Legacy value | Canonical catalog interpretation |
| --- | --- |
| `research_backtest_only` | `research_active` |
| `ai_monitored_candidate` | `research_active` |
| `shadow_candidate` | `shadow_active` |
| `runtime_enabled` | `live_candidate` |

The last mapping is intentional. Historically, `runtime_enabled` often meant
"selectable by the runtime package", not "approved to submit broker orders".
An existing live deployment may report `live_enabled` only from its independent
deployment authorization record. Catalog, inventory, and evidence records have
no permission effect by themselves.

## Three-Gate Rule

A strategy should clear all three gates before live use:

1. **Strategy gate**
   - Does the strategy have enough history, risk characterization, and drift
     tolerance to move beyond research?
2. **Plugin gate**
   - If the strategy depends on plugins, are those plugins at least
     `automation_approved` or explicitly `notification_only`?
3. **Platform gate**
   - Does the target platform accept the profile and required runtime inputs,
     and does the deployment control plane hold a current explicit authorization?

Any one of these gates failing should keep the profile out of live settings.

## Recommended Promotion Policy

- Keep the monitoring threshold relatively low so candidates are visible early.
- If AI monitoring already exists, use it to move promising profiles into
  `research_active` quickly; monitoring is for visibility, not capital.
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

`get_runtime_enabled_profiles()` remains a legacy compatibility API and means
runtime-selectable only. A profile absent from it must stay out of the runtime;
a profile present in it still needs explicit deployment authorization, a
current risk gate, and broker/account permission before orders are possible.
