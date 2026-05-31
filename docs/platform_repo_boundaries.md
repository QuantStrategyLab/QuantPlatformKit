# Platform Repository Boundaries


## 中文摘要

- 完整中文版见 [`platform_repo_boundaries.zh-CN.md`](platform_repo_boundaries.zh-CN.md)；本节保留在英文文件顶部，方便从当前文件直接找到中文入口。
- 用途：本文档围绕 `Platform Repository Boundaries`，用于理解 `QuantPlatformKit` 的配置、运行、部署、研究或验收边界。
- 主要覆盖：`QuantPlatformKit`、`Strategy Repositories`、`Platform Repositories`、`Practical Rule`。
- 阅读顺序：先确认边界、输入输出和权限要求，再执行文档里的命令、CI、dry-run、发布或切换步骤。
- 风险提示：涉及实盘、密钥、权限、Cloud Run、交易所或券商 API 的变更，必须先在测试环境或 dry-run 验证；不要只凭示例直接修改生产。
- 英文正文保留更完整的命令、字段名和配置键；如果摘要和正文不一致，以正文中的实际命令和配置为准。
This document describes how `QuantPlatformKit` fits with strategy repositories
and broker platform repositories.

## QuantPlatformKit

`QuantPlatformKit` is the shared package. It owns contracts and helpers that are
useful across repositories:

- shared domain models
- ports and interfaces for market data, portfolio snapshots, execution,
  notifications, and state
- broker adapter utilities
- strategy manifest, context, decision, loader, and validation contracts
- strategy-plugin parsing, compatibility, and alert-message helpers

It should stay platform-neutral. It should not contain broker sessions,
platform-specific runtime wiring, generated artifacts, or strategy formulas.

## Strategy Repositories

Strategy repositories own reusable strategy behavior:

- profile metadata and manifests
- pure `evaluate(ctx)` entrypoints
- strategy parameters and diagnostics
- artifact schema expectations when a strategy needs upstream generated data

They should not import broker SDKs or branch on a broker platform.

## Platform Repositories

Platform repositories connect brokers and runtime inputs to the shared
contracts:

- create broker sessions
- load runtime configuration
- assemble `StrategyContext`
- call a strategy entrypoint
- map `StrategyDecision` into broker-native execution
- render and send platform-specific notifications
- persist platform-owned run state and reports

They may keep broker-specific adapters, request handlers, and decision mappers
locally. If a helper becomes useful across more than one platform, move the
shared part into `QuantPlatformKit` and keep only the platform edge local.

## Practical Rule

Use this split when deciding where code belongs:

- shared contract or reusable adapter: `QuantPlatformKit`
- strategy formula or profile semantics: strategy repository
- broker session, runtime assembly, execution, notification routing, or state:
  platform repository
