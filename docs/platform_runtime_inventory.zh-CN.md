# 平台运行清单

_校验快照日期：2026-03-30_

这份文档记录的是**公开 runtime 接线清单**，用来快速回答一个问题：

> 现在到底是哪一个仓库、哪一个项目、哪一个服务、哪一个 scheduler、哪一个 runtime 身份、哪一组 secret 在跑？

这是一份**现状运行手册**，不是目标架构设计稿。目标模型和迁移规则请看 [`deployment_model.zh-CN.md`](./deployment_model.zh-CN.md)。

如果要看当前的平台 / 策略大类 / 可配置 profile 对照表，请看 [`platform_strategy_matrix.zh-CN.md`](./platform_strategy_matrix.zh-CN.md)。

## 共同规则

- `QuantPlatformKit` 继续只是共享依赖，**不单独部署**。
- GitHub Variables 继续负责配置入口：
  - service 名
  - region
  - `STRATEGY_PROFILE` 这类策略选择器
  - `*_SECRET_NAME` 这类 secret 选择器
- Secret Manager 负责 Cloud Run 运行时真正要吃的敏感值。
- GitHub Secrets 依然保留给 CI/CD 启动凭据用，比如：
  - `GCP_SA_KEY`
  - 以及运行时迁移还没完成时的临时 fallback

## 当前清单

| 平台 | 仓库 | 策略大类 | 策略选择器 | 运行模型 | 项目 / 后端 | 运行单元 |
|---|---|---:|---|---|---|---|
| IBKR | `QuantStrategyLab/InteractiveBrokersPlatform` | `us_equity` | `STRATEGY_PROFILE=<runtime_enabled us_equity profile>` | Cloud Run | configurable |
| Schwab | `QuantStrategyLab/CharlesSchwabPlatform` | `us_equity` | `hybrid_growth_income` | Cloud Run | `charlesschwabquant` | `charles-schwab-quant-hybrid-growth-income-service` |
| LongBridge | `QuantStrategyLab/LongBridgePlatform` | `us_equity` | `STRATEGY_PROFILE=<runtime_enabled us_equity profile>` | Cloud Run | configurable |
| Binance | `QuantStrategyLab/BinanceQuant` | `crypto` | `crypto_leader_rotation` | Oracle Cloud + self-hosted runner | `binancequant` 只承担 Firestore / GCP 凭据 | GitHub Actions `workflow_dispatch` + self-hosted runner |

## 各平台明细

### IBKR

- **仓库**
  - `QuantStrategyLab/InteractiveBrokersPlatform`
- **Cloud Run 项目**
  - `interactivebrokersquant`
- **服务**
  - `interactive-brokers-quant-global-etf-rotation-service`
- **runtime service account**
  - `ibkr-platform-runtime@interactivebrokersquant.iam.gserviceaccount.com`
- **runtime revision**
  - `interactive-brokers-quant-global-etf-rotation-service-00001-wg8`
- **Scheduler**
  - `interactive-brokers-quant-global-etf-rotation-service-scheduler`
  - region：`us-central1`
- **核心运行选择器**
  - `STRATEGY_PROFILE=global_etf_rotation`
  - `ACCOUNT_GROUP=<account group selector>`
  - `IB_ACCOUNT_GROUP_CONFIG_SECRET_NAME=<Secret Manager secret name>`
- **运行时 secret**
  - `ibkr-account-groups`
  - `interactive-brokers-telegram-token`
- **运行说明**
  - 过渡 env `IB_GATEWAY_ZONE`、`IB_GATEWAY_IP_MODE` 已经从服务上删掉，因为当前选中的 account-group payload 已经带了这两个值。

### Charles Schwab

- **仓库**
  - `QuantStrategyLab/CharlesSchwabPlatform`
- **Cloud Run 项目**
  - `charlesschwabquant`
- **服务**
  - `charles-schwab-quant-hybrid-growth-income-service`
- **runtime service account**
  - `schwab-platform-runtime@charlesschwabquant.iam.gserviceaccount.com`
- **runtime revision**
  - `charles-schwab-quant-hybrid-growth-income-service-00002-nhn`
- **Scheduler**
  - `charles-schwab-quant-hybrid-growth-income-service-scheduler`
  - region：`us-central1`
- **核心运行选择器**
  - `STRATEGY_PROFILE=hybrid_growth_income`
- **运行时 secret**
  - `schwab_token`
  - `charles-schwab-api-key`
  - `charles-schwab-app-secret`
  - `charles-schwab-telegram-token`
- **运行说明**
  - 运行时敏感配置已经不再走 Cloud Run 明文 env，而是走 Secret Manager 引用。
  - token refresher 不在这个仓库里，而是在：
    - `QuantStrategyLab/SchwabTokenAutoRefresher`

### LongBridge

- **仓库**
  - `QuantStrategyLab/LongBridgePlatform`
- **Cloud Run 项目**
  - `longbridgequant`
- **服务**
  - HK：`longbridge-quant-semiconductor-rotation-income-hk-service`
  - SG：`longbridge-quant-semiconductor-rotation-income-sg-service`
- **runtime service account**
  - `longbridge-platform-runtime@longbridgequant.iam.gserviceaccount.com`
- **runtime revision**
  - HK：`longbridge-quant-semiconductor-rotation-income-hk-ser-00002-w62`
  - SG：`longbridge-quant-semiconductor-rotation-income-sg-ser-00002-694`
- **Scheduler**
  - `longbridge-quant-semiconductor-rotation-income-hk-service-scheduler`（`asia-east2`）
  - `longbridge-quant-semiconductor-rotation-income-sg-service-scheduler`（`asia-southeast1`）
- **核心运行选择器**
  - `STRATEGY_PROFILE=semiconductor_rotation_income`
  - `ACCOUNT_REGION=HK|SG`
  - `LONGPORT_SECRET_NAME=<region token secret>`
- **运行时 secret**
  - 共享 app secret：
    - `longbridge-telegram-token`
    - `longport-app-key`
    - `longport-app-secret`
  - 区域 token secret：
    - `longport_token_hk`
    - `longport_token_sg`
- **运行说明**
  - HK / SG 继续保持两个 Cloud Run 服务、两个 trigger、两个 GitHub Environment。
  - App key / secret 和 Telegram token 现在都已经改成 LongBridge 项目内部共享的 Secret Manager 引用。
  - `SERVICE_NAME` 现在也已经对齐到上面的完整运行时名字，不再使用旧的 `longbridge-quant-hk` / `longbridge-quant-sg` 这种短前缀。

### Binance

- **仓库**
  - `QuantStrategyLab/BinanceQuant`
- **主运行模型**
  - Oracle Cloud
  - self-hosted GitHub Actions runner
  - `workflow_dispatch`
- **GCP 项目**
  - `binancequant`
- **GCP 现在承担的职责**
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

- `GCP_SA_KEY`
- 迁移还没结束时的临时 fallback

### 应该放在 Secret Manager

- broker API key / app secret
- 运行时 Telegram token
- token refresh payload
- account-group payload

## 当前刻意还没做完的事

- Cloud Run 项目里的 scheduler OIDC 身份还在用默认 compute service account。
- 真正的跨平台策略实现共享还没开始；现在只有共享策略契约和平台兼容骨架。

## 这份清单之后的建议

1. 以后只要 runtime 服务名、secret 名、runtime service account 变了，就同步更新这份文档
2. 以后只要 repo 名、service 名、scheduler 名任意一边变了，就把文档一起同步
3. 等命名和运行配置稳定后，再开始真正按策略大类拆实现
