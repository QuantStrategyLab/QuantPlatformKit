# 平台运行清单

_校验快照日期：2026-04-18_

这份文档记录的是**当前线上真实运行清单**，用来快速回答一个问题：

> 现在到底是哪一个仓库、哪一个项目、哪一个服务、哪一个 scheduler、哪一个 runtime 身份、哪一组 secret 在跑？

这是一份**现状运行手册**，不是目标架构设计稿。目标模型和迁移规则请看 [`deployment_model.zh-CN.md`](./deployment_model.zh-CN.md)。

如果要看当前的平台 / 策略大类 / live profile 对照表，请看 [`platform_strategy_matrix.zh-CN.md`](./platform_strategy_matrix.zh-CN.md)。

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

## 当前清单

| 平台 | 仓库 | 策略大类 | 当前策略值 | 运行模型 | 项目 / 后端 | 当前运行单元 |
|---|---|---:|---|---|---|---|
| IBKR | `QuantStrategyLab/InteractiveBrokersPlatform` | `us_equity` | `soxl_soxx_trend_income` | Cloud Run | `interactivebrokersquant` | `interactive-brokers-quant-service` |
| Schwab | `QuantStrategyLab/CharlesSchwabPlatform` | `us_equity` | `tqqq_growth_income` | Cloud Run | `charlesschwabquant` | `charles-schwab-quant-service` |
| LongBridge | `QuantStrategyLab/LongBridgePlatform` | `us_equity` | `HK: tech_communication_pullback_enhancement` / `SG: soxl_soxx_trend_income` | Cloud Run | `longbridgequant` | `longbridge-quant-hk-service`、`longbridge-quant-sg-service` |
| Binance | `QuantStrategyLab/BinancePlatform` | `crypto` | `crypto_leader_rotation` | Oracle Cloud + self-hosted runner | `binancequant` 只承担 Firestore / GCP 凭据 | GitHub Actions `workflow_dispatch` + self-hosted runner |

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
- **当前 ready revision**
  - `interactive-brokers-quant-service-00111-wr5`
- **Scheduler**
  - `interactive-brokers-quant-service-scheduler`
  - region：`us-central1`
- **核心运行选择器**
  - `STRATEGY_PROFILE=soxl_soxx_trend_income`
  - `ACCOUNT_GROUP=default`
  - `IB_ACCOUNT_GROUP_CONFIG_SECRET_NAME=ibkr-account-groups`
- **运行时 secret**
  - `ibkr-account-groups`
  - `interactive-brokers-telegram-token`
- **当前说明**
  - 过渡 env `IB_GATEWAY_ZONE=us-central1-c`、`IB_GATEWAY_IP_MODE=internal` 目前仍作为服务级 fallback 保留；目标状态仍然是放进选中的 account-group payload。

### Charles Schwab

- **仓库**
  - `QuantStrategyLab/CharlesSchwabPlatform`
- **Cloud Run 项目**
  - `charlesschwabquant`
- **服务**
  - `charles-schwab-quant-service`
- **runtime service account**
  - `schwab-platform-runtime@charlesschwabquant.iam.gserviceaccount.com`
- **当前 ready revision**
  - `charles-schwab-quant-service-00092-8hz`
- **Scheduler**
  - `charles-schwab-quant-service-scheduler`
  - region：`us-central1`
- **核心运行选择器**
  - `STRATEGY_PROFILE=tqqq_growth_income`
  - `DUAL_DRIVE_UNLEVERED_SYMBOL=QQQM`
- **运行时 secret**
  - `schwab_token`
  - `charles-schwab-api-key`
  - `charles-schwab-app-secret`
  - `charles-schwab-telegram-token`
- **当前说明**
  - 运行时敏感配置已经不再走 Cloud Run 明文 env，而是走 Secret Manager 引用。
  - `crisis_response_shadow` 以 `shadow` 模式挂载到 `tqqq_growth_income`；它只进入日志/通知上下文，不改变 allocation。
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
- **当前 ready revision**
  - HK：`longbridge-quant-hk-service-00086-slh`
  - SG：`longbridge-quant-sg-service-00089-526`
- **Scheduler**
  - `longbridge-quant-hk-service-scheduler`（`asia-east2`）
  - `longbridge-quant-sg-service-scheduler`（`asia-southeast1`）
- **核心运行选择器**
  - `STRATEGY_PROFILE=HK 使用 tech_communication_pullback_enhancement；SG 使用 soxl_soxx_trend_income`
  - `ACCOUNT_REGION=HK|SG`
  - `LONGPORT_SECRET_NAME=longport_token_hk|longport_token_sg`
- **运行时 secret**
  - Secret Manager 引用：
    - `longbridge-telegram-token`
    - `longport-app-key-hk`
    - `longport-app-key-sg`
    - `longport-app-secret-hk`
    - `longport-app-secret-sg`
  - 区域 token secret：
    - `longport_token_hk`
    - `longport_token_sg`
- **当前说明**
  - HK / SG 继续保持两个 Cloud Run 服务、两个 trigger、两个 GitHub Environment。
  - HK 使用 `tech_communication_pullback_enhancement` 的 feature-snapshot env；SG 当前是直接运行输入的 `soxl_soxx_trend_income`。
  - App key / secret 现在使用分区域的 Secret Manager 引用；Telegram token 在 LongBridge 项目内共享。
  - `SERVICE_NAME` 现在也已经对齐到上面的完整运行时名字，不再使用旧的 `longbridge-quant-hk` / `longbridge-quant-sg` 这种短前缀。

### Binance

- **仓库**
  - `QuantStrategyLab/BinancePlatform`
- **主运行模型**
  - Oracle Cloud
  - self-hosted GitHub Actions runner
  - `workflow_dispatch`
- **GCP 项目**
  - `binancequant`
- **GCP 现在承担的职责**
  - Firestore
  - workflow / runtime 使用的 GCP service-account 凭据
- **当前运行选择器**
  - `STRATEGY_PROFILE=crypto_leader_rotation`
- **当前 Firestore 后端**
  - database：`(default)`
  - mode：`FIRESTORE_NATIVE`
  - location：`nam5`
- **当前说明**
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

## 这份清单之后的建议

1. 以后只要 runtime 服务名、secret 名、runtime service account 变了，就同步更新这份文档
2. 以后只要 repo 名、service 名、scheduler 名任意一边变了，就把文档一起同步
3. 等命名和运行配置稳定后，再开始真正按策略大类拆实现
