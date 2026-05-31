# US equity cross-platform strategy spec


## 中文摘要

- 完整中文版见 [`us_equity_cross_platform_strategy_spec.zh-CN.md`](us_equity_cross_platform_strategy_spec.zh-CN.md)；本节保留在英文文件顶部，方便从当前文件直接找到中文入口。
- 用途：本文档围绕 `US equity cross-platform strategy spec`，用于理解 `QuantPlatformKit` 的配置、运行、部署、研究或验收边界。
- 主要覆盖：`Goal`、`Scope`、`Design rule`、`Responsibility boundaries`、`Mandatory layers`。
- 阅读顺序：先确认边界、输入输出和权限要求，再执行文档里的命令、CI、dry-run、发布或切换步骤。
- 风险提示：涉及实盘、密钥、权限、Cloud Run、交易所或券商 API 的变更，必须先在测试环境或 dry-run 验证；不要只凭示例直接修改生产。
- 英文正文保留更完整的命令、字段名和配置键；如果摘要和正文不一致，以正文中的实际命令和配置为准。

## Goal

All US equity strategies should be written once and be portable across the
current broker runtimes:

- `ibkr`
- `schwab`
- `longbridge`
- `firstrade`

This document defines the contract new strategies must follow, and the migration
target existing strategies should converge to.

## Scope

This spec applies to:

- `QuantPlatformKit`
- `UsEquityStrategies`
- the US equity runtime repositories that consume them

It does **not** define broker authentication, platform runtime wiring, schedule
behavior, or notification wording beyond the shared runtime contract.

## Design rule

Strategy code must stay platform-agnostic.

In practice that means:

1. strategy repos declare required inputs and strategy metadata
2. platform repos build those inputs from broker/runtime data
3. strategy repos return a standard `StrategyDecision`
4. platform repos translate the resulting `AllocationIntent` into broker-native
   execution

Strategy code must not branch on broker platform.

## Responsibility boundaries

`QuantPlatformKit` owns shared contracts and common runtime helpers:

- `StrategyManifest`, `StrategyDecision`, and `StrategyRuntimeAdapter`
- `StrategyArtifactContract` and `StrategyRuntimePolicy`
- artifact path resolution, runtime config resolution, and feature snapshot guards
- standard `StrategyContext` builders and input validation

`UsEquityStrategies` owns strategy semantics:

- profile catalog, manifest, and default config
- pure `evaluate(ctx)` implementations
- platform-neutral base runtime adapter specs
- feature snapshot schema, manifest contract version, and managed symbol extractors
- packaged or published canonical strategy config

Platform repositories own runtime and broker integration:

- runtime configuration and broker sessions
- market data, account data, holdings, and portfolio snapshots
- `StrategyContext` assembly from declared contracts
- mapping `StrategyDecision` to broker orders, notifications, and runtime reports
- retries, idempotency, and reconciliation output

The snapshot pipeline owns artifact publication:

- snapshot files, manifests, checksums, and contract versions
- config checksum alignment with profile and config name
- artifact publication location and retention

Do not introduce reverse coupling:

- strategy code must not import broker SDKs or read platform env vars
- platform code must not hard-code private strategy symbol pools, snapshot schemas, or config paths by profile name
- platform repositories must read derived adapter requirements instead of keeping a second hard-coded list of snapshot profiles
- live strategy config must not depend on platform `research/` directories

## Mandatory layers

### 1. Strategy definition layer

Each US equity profile must declare:

- canonical profile name
- display metadata
- `target_mode`
- `required_inputs`
- supported platforms
- entrypoint definition

### 2. Runtime adapter layer

Each supported platform must expose a `StrategyRuntimeAdapter` for that profile.

The adapter may define:

- available inputs
- available capabilities
- portfolio input name
- artifact validation expectations
- temporary migration metadata

The adapter must **not** leak broker order sequencing back into strategy logic.

### 3. Platform input builder layer

Platforms are responsible for assembling normalized inputs. Strategy code only
consumes the normalized inputs it asked for.

### 4. Execution translation layer

Platforms must translate the unified allocation intent into their own native
execution style:

- `ibkr`: native `weight`
- `schwab`: native `value`
- `longbridge`: native `value`
- `firstrade`: native `value`

Strategies must not implement broker-specific execution transforms themselves.

## Canonical required inputs

New US equity strategies must choose from this canonical input vocabulary:

- `market_history`
- `benchmark_history`
- `portfolio_snapshot`
- `derived_indicators`
- `feature_snapshot`

Current legacy input names may still exist during migration, but new profiles
should use the canonical names from day one. Platform repos may keep temporary
mapping shims until all live profiles are migrated.

### Input intent

- `market_history`: broad instrument history used for ranking, rotation, or risk
  checks
- `benchmark_history`: dedicated benchmark history such as `QQQ` or `SPY`
- `portfolio_snapshot`: current holdings, cash, market value, and account state
- `derived_indicators`: precomputed regime or indicator bundle owned by the
  platform runtime
- `feature_snapshot`: validated artifact-backed cross-sectional feature dataset

## Strategy outputs

US equity strategies must return:

- `StrategyDecision`
- `AllocationIntent` derived from that decision

Broker-specific order payloads, notification rows, UI layout fields, and service
state writes must stay in the platform repository.

### Target mode

Each strategy must declare exactly one `target_mode`:

- `weight`
- `value`

Mixed output modes inside one profile are not allowed.

The strategy picks the semantic target mode. Platform repos are responsible for
translating that mode when their native execution model differs.

## Artifact contract

If a strategy depends on artifacts such as feature snapshots, it must declare a
stable contract:

- artifact type
- schema version
- freshness rule
- optional manifest/checksum rule

The platform runtime owns:

- artifact transport
- artifact storage path or URI
- freshness validation
- runtime injection into `StrategyContext`

The strategy layer must not assume broker-local files or service-specific paths.

## Broker-platform support rule

For new US equity strategy profiles, the default expectation is:

- `ibkr` adapter present
- `schwab` adapter present
- `longbridge` adapter present
- `firstrade` adapter present

If one platform is intentionally unsupported, the PR must include an explicit
reason and the profile must remain `eligible=false` there until the gap is
closed.

## Eligible vs enabled

These two states must stay separate:

- `eligible`: the platform can run the profile in theory
- `enabled`: the current rollout actually turns it on

Eligibility should be derived from the contract:

- domain match
- target mode support or translation support
- required inputs available
- runtime adapter present
- capability requirements met

Rollout allowlists should only control `enabled`.

## Definition of done for a new strategy

A new US equity strategy is not ready until it has:

1. metadata and canonical profile registration
2. manifest and entrypoint
3. explicit `target_mode`
4. canonical `required_inputs`
5. runtime adapters for the intended platforms
6. allocation-contract tests
7. platform adapter tests
8. at least one dry-run smoke path per enabled platform

## Review checklist

Reviewers should reject a new strategy PR if any of these are true:

- strategy code branches on platform id
- strategy code reads broker env vars directly
- strategy output includes broker-specific order fields
- a new ad-hoc required input name is introduced without updating this spec
- `target_mode` is missing or mixed
- artifact-dependent logic skips schema or freshness checks

## Migration notes for runtime profiles

Current runtime-enabled profiles can migrate incrementally, but the end state should be:

- `global_etf_rotation`: portable through normalized history inputs plus
  weight/value translation
- `tqqq_growth_income`: portable through benchmark/portfolio inputs plus
  value/weight translation
- `soxl_soxx_trend_income`: portable through indicator/account-state
  inputs plus value/weight translation
- `russell_1000_multi_factor_defensive`: portable through standardized
  `feature_snapshot` artifact delivery
- `tech_communication_pullback_enhancement`: portable through standardized `feature_snapshot`
  artifact delivery
- `mega_cap_leader_rotation_top50_balanced`: portable through standardized
  `feature_snapshot` artifact delivery

New profiles should target the end state immediately instead of adding more
one-off runtime contracts.
