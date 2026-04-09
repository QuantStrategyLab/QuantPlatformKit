# 美股线上切换与回滚运行手册

这份文档是当前美股策略在线上切换时的操作手册。

它默认前提是：

- 共享包和平台代码已经部署完成
- 平台状态矩阵已经放开目标策略

它**不是**用来替代策略接入改造的。

## 适用范围

当前美股 live profile：

- `global_etf_rotation`
- `tqqq_growth_income`
- `soxl_soxx_trend_income`
- `russell_1000_multi_factor_defensive`
- `qqq_tech_enhancement`

当前运行平台：

- `ibkr`
- `schwab`
- `longbridge`

对当前这 5 条策略来说，三个平台现在都已经是 `eligible=true` 且 `enabled=true`。也就是说，接下来换线上策略主要是运维切换，不再是契约迁移。

## 标准切换路径

每次都按同一套顺序走：

1. 先确认目标策略在状态矩阵里是 `eligible=true`、`enabled=true`
2. 再改 GitHub 管理的运行时变量
3. 重跑或等待 `Sync Cloud Run Env`
4. 再检查 Cloud Run 上的 env
5. 最后看第一条心跳或执行通知

切换策略时不要顺手改 service name。

## 服务清单

| 平台 | 服务名 | 运行身份拆分方式 |
| --- | --- | --- |
| IBKR | `interactive-brokers-quant-service` | `ACCOUNT_GROUP` |
| Schwab | `charles-schwab-quant-service` | 单服务 |
| LongBridge HK | `longbridge-quant-hk-service` | `ACCOUNT_REGION=HK` |
| LongBridge SG | `longbridge-quant-sg-service` | `ACCOUNT_REGION=SG` |

## 第一步：改 env 之前先看状态矩阵

在各自平台仓库里跑状态脚本。

### IBKR

```bash
cd /Users/lisiyi/Projects/InteractiveBrokersPlatform
PYTHONPATH=/Users/lisiyi/Projects/QuantPlatformKit/src:/Users/lisiyi/Projects/UsEquityStrategies/src:. \
  .venv/bin/python scripts/print_strategy_profile_status.py --json
```

### Schwab

```bash
cd /Users/lisiyi/Projects/CharlesSchwabPlatform
PYTHONPATH=/Users/lisiyi/Projects/QuantPlatformKit/src:/Users/lisiyi/Projects/UsEquityStrategies/src:. \
  /Users/lisiyi/Projects/LongBridgePlatform/.venv/bin/python scripts/print_strategy_profile_status.py --json
```

### LongBridge

```bash
cd /Users/lisiyi/Projects/LongBridgePlatform
PYTHONPATH=/Users/lisiyi/Projects/QuantPlatformKit/src:/Users/lisiyi/Projects/UsEquityStrategies/src:. \
  .venv/bin/python scripts/print_strategy_profile_status.py --json
```

必须看到：

- 目标 `canonical_profile` 存在
- `eligible` 是 `true`
- `enabled` 是 `true`

只要有一项不满足，就先停下。这不是线上切换问题，而是代码或 rollout 没放开。

## 第二步：先搞清楚目标策略还需要哪些额外 env

| 策略 | 除了 `STRATEGY_PROFILE` 之外还需要的输入 |
| --- | --- |
| `global_etf_rotation` | 无 |
| `tqqq_growth_income` | 无 |
| `soxl_soxx_trend_income` | 无 |
| `russell_1000_multi_factor_defensive` | feature snapshot 路径 + manifest 路径 |
| `qqq_tech_enhancement` | feature snapshot 路径 + manifest 路径 + strategy config 路径 |

说明：

- `qqq_tech_enhancement` 在 IBKR 上如果还要留对账产物，可以继续配 reconciliation output path。
- 如果从 feature-snapshot 策略切回普通策略，要把旧的 snapshot/config env 一起删掉，不要留脏状态。

## 第三步：改 GitHub 管理的运行时变量

推荐路径：

- 改 GitHub repository variables 或 environment variables
- 让 `.github/workflows/sync-cloud-run-env.yml` 负责把变更同步到 Cloud Run

### IBKR

必填：

- `STRATEGY_PROFILE`
- `ACCOUNT_GROUP`
- `IB_ACCOUNT_GROUP_CONFIG_SECRET_NAME`

可选：

- `IBKR_DRY_RUN_ONLY`

如果是 feature-snapshot 策略，还需要：

- `IBKR_FEATURE_SNAPSHOT_PATH`
- `IBKR_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `IBKR_STRATEGY_CONFIG_PATH`（`qqq_tech_enhancement` 需要）

不再需要时要删掉：

- `IBKR_FEATURE_SNAPSHOT_PATH`
- `IBKR_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `IBKR_STRATEGY_CONFIG_PATH`
- `IBKR_RECONCILIATION_OUTPUT_PATH`

### Schwab

必填：

- `STRATEGY_PROFILE`

可选：

- `SCHWAB_DRY_RUN_ONLY`

如果是 feature-snapshot 策略，还需要：

- `SCHWAB_FEATURE_SNAPSHOT_PATH`
- `SCHWAB_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `SCHWAB_STRATEGY_CONFIG_PATH`（当该策略走外部配置文件时）

不再需要时要删掉：

- `SCHWAB_FEATURE_SNAPSHOT_PATH`
- `SCHWAB_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `SCHWAB_STRATEGY_CONFIG_PATH`

### LongBridge

必填：

- `STRATEGY_PROFILE`
- `ACCOUNT_PREFIX`
- `ACCOUNT_REGION`
- `LONGPORT_SECRET_NAME`
- `LONGPORT_APP_KEY_SECRET_NAME`
- `LONGPORT_APP_SECRET_SECRET_NAME`

可选：

- `LONGBRIDGE_DRY_RUN_ONLY`

如果是 feature-snapshot 策略，还需要：

- `LONGBRIDGE_FEATURE_SNAPSHOT_PATH`
- `LONGBRIDGE_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `LONGBRIDGE_STRATEGY_CONFIG_PATH`

不再需要时要删掉：

- `LONGBRIDGE_FEATURE_SNAPSHOT_PATH`
- `LONGBRIDGE_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `LONGBRIDGE_STRATEGY_CONFIG_PATH`

## 第四步：重跑 env sync，再直接看 Cloud Run

先等平台 workflow：

- `Sync Cloud Run Env`

然后直接查服务上的 env。

### 示例命令

```bash
gcloud run services describe interactive-brokers-quant-service \
  --project interactivebrokersquant \
  --region us-central1 \
  --format='flattened(spec.template.spec.containers[0].env[])'
```

```bash
gcloud run services describe charles-schwab-quant-service \
  --project charlesschwabquant \
  --region us-central1 \
  --format='flattened(spec.template.spec.containers[0].env[])'
```

```bash
gcloud run services describe longbridge-quant-hk-service \
  --project longbridgequant \
  --region asia-east2 \
  --format='flattened(spec.template.spec.containers[0].env[])'
```

```bash
gcloud run services describe longbridge-quant-sg-service \
  --project longbridgequant \
  --region asia-southeast1 \
  --format='flattened(spec.template.spec.containers[0].env[])'
```

要核对：

- `STRATEGY_PROFILE` 是目标策略
- 只有 feature-snapshot 策略才保留 snapshot env
- 不需要的 dry-run 或 artifact env 已经删掉

## 第五步：别只看 env，还要看第一条运行输出

至少确认第一条心跳或执行通知里：

- 策略显示名是对的
- LongBridge 只有 `[HK]` / `[SG]` 这样的账号前缀
- 没有旧的策略名后缀残留在 LongBridge 通知前缀里

如果切的是 feature-snapshot 策略，还要再确认：

- snapshot 文件确实存在
- manifest 和当前 contract version 对得上
- 第一条通知里的 managed symbols 符合预期

## 回滚原则

回滚时保持简单：

1. 把 `STRATEGY_PROFILE` 改回上一个稳定值
2. 把这个策略对应的 snapshot/config env 一起恢复或删掉
3. 重跑 `Sync Cloud Run Env`
4. 再查一遍 Cloud Run env
5. 再看下一条心跳或执行通知

不要把下面这些东西当回滚手段：

- 旧 service name
- 直接在 Cloud Run 上手工乱改一半 env
- 只改 `STRATEGY_PROFILE`，不处理配套的 snapshot/config env

如果服务切完后起不来：

1. 先把 env 回回去
2. 再去查代码或依赖问题

## 建议的操作记录

每次线上切换，最好都记录这 5 项：

1. 服务名
2. 旧策略
3. 新策略
4. 新增或删除了哪些配套 env
5. 第一条成功心跳或执行通知的时间
