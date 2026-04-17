# 平台运行接线清单

_校验快照日期：2026-04-18_

这份文档记录公开仓库里可以保留的 runtime 接线信息，用来快速回答一个问题：

> 每个平台对应哪个仓库、项目、服务、scheduler、runtime 身份、selector 和 secret 入口？

这是一份接线手册，不是任何账户的部署策略记录。它刻意不记录可变部署状态或账户级仓位选择。

如果要看平台 / 策略大类 / 可配置 profile 对照表，请看 [`platform_strategy_matrix.zh-CN.md`](./platform_strategy_matrix.zh-CN.md)。

## 共同规则

- `QuantPlatformKit` 继续只是共享依赖，**不单独部署**。
- GitHub Variables 继续负责配置入口：
  - service 名
  - region
  - `STRATEGY_PROFILE` 这类策略选择器
  - `*_SECRET_NAME` 这类 secret 选择器
- Secret Manager 负责 Cloud Run 运行时真正要吃的敏感值。
- 美股 Cloud Run env-sync workflow 使用 GitHub OIDC + Workload Identity Federation，不再需要 `GCP_SA_KEY`。
- GitHub Secrets 可以继续保留给运行时迁移还没完成时的临时 fallback。

## 运行接线清单

| 平台 | 仓库 | 策略大类 | 策略选择器 | 运行模型 | 项目 / 后端 | 运行单元 |
|---|---|---:|---|---|---|---|
| IBKR | `QuantStrategyLab/InteractiveBrokersPlatform` | `us_equity` | `STRATEGY_PROFILE=<runtime_enabled us_equity profile>` | Cloud Run | configurable |
| Schwab | `QuantStrategyLab/CharlesSchwabPlatform` | `us_equity` | `STRATEGY_PROFILE=<runtime_enabled us_equity profile>` | Cloud Run | `charlesschwabquant` | `charles-schwab-quant-service` |
| LongBridge | `QuantStrategyLab/LongBridgePlatform` | `us_equity` | `STRATEGY_PROFILE=<runtime_enabled us_equity profile>` | Cloud Run | configurable |
| Binance | `QuantStrategyLab/BinancePlatform` | `crypto` | `STRATEGY_PROFILE=crypto_leader_rotation` | Oracle Cloud + self-hosted runner | `binancequant` 只承担 Firestore / GCP 凭据 | GitHub Actions `workflow_dispatch` + self-hosted runner |

## 各平台明细

### IBKR

- **仓库**
  - `QuantStrategyLab/InteractiveBrokersPlatform`
- **Cloud Run 项目**
  - `interactivebrokersquant`
- **服务**
  - `interactive-brokers-quant-service`
- **runtime service account**
  - `ibkr-platform-runtime@interactivebrokersquant.iam.gserviceaccount.com`
- **Scheduler**
  - `interactive-brokers-quant-service-scheduler`
  - region：`us-central1`
- **核心运行选择器**
  - `STRATEGY_PROFILE=<runtime_enabled us_equity profile>`
  - `ACCOUNT_GROUP=<account group selector>`
  - `IB_ACCOUNT_GROUP_CONFIG_SECRET_NAME=<Secret Manager secret name>`
- **运行时 secret**
  - 由 `IB_ACCOUNT_GROUP_CONFIG_SECRET_NAME` 选择的账户组 payload secret
  - runtime Telegram token secret
- **运行说明**
  - `ACCOUNT_GROUP` 决定 runtime 加载哪组券商 / 账户 payload。
  - Gateway zone 和 IP-mode 设置在迁移完成后应放进选中的 account-group payload。

### Charles Schwab

- **仓库**
  - `QuantStrategyLab/CharlesSchwabPlatform`
- **Cloud Run 项目**
  - `charlesschwabquant`
- **服务**
  - `charles-schwab-quant-service`
- **runtime service account**
  - `schwab-platform-runtime@charlesschwabquant.iam.gserviceaccount.com`
- **Scheduler**
  - `charles-schwab-quant-service-scheduler`
  - region：`us-central1`
- **核心运行选择器**
  - `STRATEGY_PROFILE=<runtime_enabled us_equity profile>`
  - 策略专属可选 env，例如 `DUAL_DRIVE_UNLEVERED_SYMBOL`
- **运行时 secret**
  - Schwab token payload secret
  - Schwab API key / app secret 引用
  - runtime Telegram token secret
- **运行说明**
  - 运行时敏感配置应使用 Secret Manager 引用，不应放在 Cloud Run 明文 env。
  - 策略插件是 sidecar：`shadow` 只写日志和通知；`paper`、`advisory`、`live` 的语义由插件执行模式契约统一约束。
  - token refresher 不在这个仓库里，而是在：
    - `QuantStrategyLab/SchwabTokenAutoRefresher`

### LongBridge

- **仓库**
  - `QuantStrategyLab/LongBridgePlatform`
- **Cloud Run 项目**
  - `longbridgequant`
- **服务**
  - HK：`longbridge-quant-hk-service`
  - SG：`longbridge-quant-sg-service`
- **runtime service account**
  - `longbridge-platform-runtime@longbridgequant.iam.gserviceaccount.com`
- **Scheduler**
  - `longbridge-quant-hk-service-scheduler`（`asia-east2`）
  - `longbridge-quant-sg-service-scheduler`（`asia-southeast1`）
- **核心运行选择器**
  - 每个区域服务设置 `STRATEGY_PROFILE=<runtime_enabled us_equity profile>`
  - `ACCOUNT_REGION=HK|SG`
  - `LONGPORT_SECRET_NAME=<region token secret>`
- **运行时 secret**
  - LongPort app key / app secret 的 Secret Manager 引用
  - 由 `LONGPORT_SECRET_NAME` 选择的区域 token secret
  - runtime Telegram token secret
- **运行说明**
  - HK / SG 继续保持两个 Cloud Run 服务、两个 trigger、两个 GitHub Environment。
  - snapshot 驱动策略需要 feature snapshot path / manifest env；直接运行输入策略不需要。
  - App key / secret 使用分区域的 Secret Manager 引用；Telegram token 在 LongBridge 项目内共享。
  - `SERVICE_NAME` 应使用上面的完整运行时服务名，不再使用旧短前缀。

### Binance

- **仓库**
  - `QuantStrategyLab/BinancePlatform`
- **主运行模型**
  - Oracle Cloud
  - self-hosted GitHub Actions runner
  - `workflow_dispatch`
- **GCP 项目**
  - `binancequant`
- **GCP 承担的职责**
  - Firestore
  - workflow / runtime 使用的 GCP service-account 凭据
- **运行选择器**
  - `STRATEGY_PROFILE=crypto_leader_rotation`
- **Firestore 后端**
  - database：`(default)`
  - mode：`FIRESTORE_NATIVE`
  - location：`nam5`
- **运行说明**
  - Binance 是刻意**不按 Cloud Run 平台**建模的。
  - 后续如果继续清理，要把 Oracle 运行面和 GCP 后端职责分开看。

## GitHub / Secret Manager 分工

### 继续放在 GitHub Variables

- `CLOUD_RUN_REGION`
- `CLOUD_RUN_SERVICE`
- `STRATEGY_PROFILE`
- `ACCOUNT_GROUP`
- `ACCOUNT_REGION`
- `LONGPORT_SECRET_NAME`
- `*_SECRET_NAME`
- 共享但低风险的设置，例如：
  - `GLOBAL_TELEGRAM_CHAT_ID`
  - `NOTIFY_LANG`

### 继续放在 GitHub Secrets

- 迁移还没结束时的临时 fallback

### 应该放在 Secret Manager

- broker API key / app secret
- 运行时 Telegram token
- token refresh payload
- account-group payload

## 当前刻意还没做完的事

- Cloud Run 项目里的 scheduler OIDC 身份还在用默认 compute service account。
- 真正的跨平台策略实现共享还没开始；现在只有共享策略契约和平台兼容骨架。
