# 美股策略接入清单

_校验快照日期：2026-04-16_

这份清单说明一条新的 `us_equity` 策略，如何在不手写三个平台 allowlist 的情况下，进入 IBKR / Schwab / LongBridge 三个美股运行平台。

适用仓库：

- `InteractiveBrokersPlatform`
- `CharlesSchwabPlatform`
- `LongBridgePlatform`
- `UsEquityStrategies`
- `QuantPlatformKit`

## 目标模型

`UsEquityStrategies` 是 live 策略 profile 的事实来源。三个平台仓库从 `get_runtime_enabled_profiles()` 派生自己的运行时 allowlist。

新增策略只有满足下面条件后，才应该被某个平台选中：

1. 策略已经注册到 `UsEquityStrategies` 的 catalog。
2. 只有准备好实盘运行后，才标记 `status="runtime_enabled"`。
3. `supported_platforms` 明确写出支持的平台。
4. 策略暴露统一 entrypoint，并返回 `StrategyDecision`。
5. 策略提供一份平台无关的 runtime adapter spec。
6. 平台 runtime adapter 由这份 spec 加平台原生 target mode 自动派生。
7. 平台 capability matrix 能供应策略声明的 `required_inputs`。
8. 对应平台的状态脚本输出 `eligible=true` 且 `enabled=true`。

不要再给美股 live profile 维护第二套平台手写 allowlist。

## 策略仓库要求

在 `UsEquityStrategies` 里，一条新的 live profile 需要：

- 在 `catalog.py` 里有 canonical profile id
- 有 `domain="us_equity"` 的 `StrategyDefinition`
- 显式声明 `required_inputs`
- 显式声明 `target_mode`
- 只有平台覆盖完成后才设为 `status="runtime_enabled"`
- 在 `supported_platforms` 里声明目标平台
- 有 manifest 和统一 entrypoint
- 有聚焦的策略测试
- 一份平台无关的 runtime adapter spec
- 如果依赖 artifact，要声明 `StrategyArtifactContract`
- 如果有运行窗口、reconciliation 输出等运行策略，要声明 `StrategyRuntimePolicy`
- 如果有 live 默认配置，要把 canonical config 放在策略包或 artifact 发布链里

当前标准输入名：

- `market_history`
- `benchmark_history`
- `derived_indicators`
- `portfolio_snapshot`
- `feature_snapshot`

不要随手新增临时 input 名。如果确实需要新输入，要先更新跨平台契约文档。

## Runtime adapter 要求

每条策略只需要在 `UsEquityStrategies` 里有一份基础 `StrategyRuntimeAdapter` spec。

基础 adapter 只声明策略自己拥有的元数据：

- 使用 `feature_snapshot` 时需要的 snapshot columns
- artifact 对日期敏感时的日期列和 freshness 规则
- `StrategyArtifactContract`，包括是否需要 snapshot、manifest、strategy config，以及 config 来源策略
- `StrategyRuntimePolicy`，包括 reconciliation 输出是否必需和运行窗口等策略运行约束
- runtime config loader 只作为读取策略配置的适配入口，不能承担平台部署逻辑

平台 adapter 会根据下面这些信息自动生成：

- 策略的 `required_inputs`
- 策略的 `target_mode`
- 平台原生 target mode
- 平台声明的 capability

当 weight-mode 策略运行在 value-native 平台上时，生成器会自动加入 `portfolio_snapshot`，让平台能把权重翻译成金额订单。策略本身已经需要 `portfolio_snapshot` 时，生成器会自动把它映射为 portfolio input。

adapter 生成器是策略契约和平台运行时之间的桥。策略代码本身不要按券商平台分支。

新增或修改 adapter 时，平台脚本只能消费派生后的运行需求，例如：

- `requires_snapshot_artifacts`
- `requires_snapshot_manifest_path`
- `requires_strategy_config_path`
- `config_source_policy`
- `reconciliation_output_policy`
- `runtime_execution_window_trading_days`

平台代码不要再写 `if profile == "..."` 这类策略私有分支。

## 平台仓库要求

三个美股平台仓库应该保持薄运行层：

- 解析 `STRATEGY_PROFILE`
- 通过共享策略注册表确认 profile 是否支持
- 组装 `StrategyContext`
- 加载统一 entrypoint
- 把 `StrategyDecision` 映射成券商订单和通知

平台 registry 应该从 `UsEquityStrategies.get_runtime_enabled_profiles()` 派生 live profile。

平台仓库不要硬编码策略股票池、策略私有常量或手写 live profile allowlist。

平台仓库可以因为新增 broker 能力而改代码，例如补一个新的行情输入 builder；
但不能因为某条策略的私有参数而改平台执行主流程。

## Artifact 驱动策略

如果策略使用 `feature_snapshot`，平台 env sync workflow 必须在更新 Cloud Run 前校验 artifact env。workflow 应该从 `scripts/print_strategy_profile_status.py --json` 动态解析需求，不要维护硬编码 profile 名单。

当前 env 映射：

| 平台 | Snapshot 路径 env | Manifest 路径 env | Strategy config env |
| --- | --- | --- | --- |
| IBKR | `IBKR_FEATURE_SNAPSHOT_PATH` | `IBKR_FEATURE_SNAPSHOT_MANIFEST_PATH` | `IBKR_STRATEGY_CONFIG_PATH` |
| Schwab | `SCHWAB_FEATURE_SNAPSHOT_PATH` | `SCHWAB_FEATURE_SNAPSHOT_MANIFEST_PATH` | `SCHWAB_STRATEGY_CONFIG_PATH` |
| LongBridge | `LONGBRIDGE_FEATURE_SNAPSHOT_PATH` | `LONGBRIDGE_FEATURE_SNAPSHOT_MANIFEST_PATH` | `LONGBRIDGE_STRATEGY_CONFIG_PATH` |

只有 adapter 要求 manifest 的 profile，才强制 manifest path。
只有 `config_source_policy="env_only"` 的 profile，才强制 strategy config path。
`config_source_policy="bundled_or_env"` 的 profile 默认使用策略包内 canonical config，env path 只作为显式覆盖。

## 新策略最小接入步骤

1. 在 `UsEquityStrategies` 注册 profile、manifest、default config 和统一 entrypoint。
2. 明确 `required_inputs`、`target_mode`、`supported_platforms` 和 `status`。
3. 添加基础 `StrategyRuntimeAdapter`，同时声明 `StrategyArtifactContract` 和 `StrategyRuntimePolicy`。
4. 如果使用 `feature_snapshot`，补齐 schema、date columns、freshness、manifest contract version 和 managed symbols extractor。
5. 如果需要 live config，优先打包到策略包；只有不能打包时才使用 `env_only`。
6. 跑策略仓 contract governance 和 entrypoint 测试，确认 `describe_platform_runtime_requirements()` 输出正确。
7. 跑三个平台的 status/switch plan 脚本，确认 eligible/enabled 和 artifact env 需求来自 adapter。
8. 只有新增 broker 数据源或执行能力时，才修改平台仓主流程。

## 测试门槛

新增 profile 标记 `runtime_enabled` 前，要跑：

- `QuantPlatformKit` 策略契约测试
- `UsEquityStrategies` contract governance 和 entrypoint 测试
- IBKR runtime config、loader、runtime、workflow 测试
- LongBridge runtime config、loader、runtime、workflow 测试
- Schwab runtime config、loader、runtime、workflow 测试
- 三个平台的 `scripts/print_strategy_profile_status.py --json`

`UsEquityStrategies` 的治理测试应该在 `runtime_enabled` 策略缺少预期生成式平台 adapter 覆盖时直接失败。

## 发布顺序

线上发布按这个顺序走：

1. 如果共享契约变了，先合并并打 tag `QuantPlatformKit`。
2. 合并并打 tag `UsEquityStrategies`。
3. 更新平台仓库依赖到已发布 tag。
4. 合并平台仓库。
5. 让 Cloud Run source deployment 构建平台仓库。
6. 打开或更新 GitHub 管理的 env sync 变量。
7. 核对 Cloud Run env 和第一条运行心跳。

当前这批改动等待发布的 tag：

- `QuantPlatformKit` -> `v0.7.16`
- `UsEquityStrategies` -> `v0.7.23`

## 需要权限的步骤

本地代码、测试和文档不需要 GitHub 或 Google Cloud 登录。

下面这些需要凭据：

- push commits 和 tags
- 创建 PR 或 release
- 更新 GitHub repository variables、secrets、environments
- 创建或更新 Workload Identity Federation 绑定
- 创建或更新 Secret Manager secrets
- 部署或查看 Cloud Run 服务
- 创建或更新 Cloud Scheduler jobs
- 读取或写入 GCS 策略 artifact
