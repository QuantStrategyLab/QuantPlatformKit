# 美股线上切换与回滚运行手册

这份文档是当前美股策略在线上切换时的操作手册。

它默认前提是：

- 共享包和平台代码已经部署完成
- 平台状态矩阵已经放开目标策略

它**不是**用来替代策略接入改造的。

## 适用范围

当前美股 live profile：

- `dynamic_mega_leveraged_pullback`
- `global_etf_rotation`
- `mega_cap_leader_rotation_aggressive`
- `mega_cap_leader_rotation_dynamic_top20`
- `mega_cap_leader_rotation_top50_balanced`
- `russell_1000_multi_factor_defensive`
- `soxl_soxx_trend_income`
- `tqqq_growth_income`
- `tech_communication_pullback_enhancement`

说明：旧部署里 `qqq_tech_enhancement` 仍可能作为 `tech_communication_pullback_enhancement` 的 legacy alias 被接受，但运行手册统一使用 canonical profile 名。

当前运行平台：

- `ibkr`
- `schwab`
- `longbridge`

对当前这 9 条策略来说，三个平台现在都已经是 `eligible=true` 且 `enabled=true`。也就是说，接下来换线上策略主要是运维切换，不再是契约迁移。

## 运维分组

现在最好把 live 策略按两组理解：

- **直接运行输入策略**
  - `global_etf_rotation`
  - `tqqq_growth_income`
  - `soxl_soxx_trend_income`
- **snapshot 驱动策略**
  - `dynamic_mega_leveraged_pullback`
  - `mega_cap_leader_rotation_aggressive`
  - `mega_cap_leader_rotation_dynamic_top20`
  - `mega_cap_leader_rotation_top50_balanced`
  - `russell_1000_multi_factor_defensive`
  - `tech_communication_pullback_enhancement`

平台脚本现在会直接输出这些字段：

- `input_mode`
- `requires_snapshot_artifacts`
- `requires_snapshot_manifest_path`
- `requires_strategy_config_path`
- `config_source_policy`
- `reconciliation_output_policy`
- `runtime_execution_window_trading_days`

这样切换时不用再靠记忆判断“这条是不是 snapshot 策略”。

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
| `dynamic_mega_leveraged_pullback` | feature snapshot 路径 + manifest 路径 |
| `global_etf_rotation` | 无 |
| `mega_cap_leader_rotation_aggressive` | feature snapshot 路径 + manifest 路径 |
| `mega_cap_leader_rotation_dynamic_top20` | feature snapshot 路径 + manifest 路径 |
| `mega_cap_leader_rotation_top50_balanced` | feature snapshot 路径 + manifest 路径 |
| `russell_1000_multi_factor_defensive` | feature snapshot 路径 |
| `soxl_soxx_trend_income` | 无 |
| `tqqq_growth_income` | 无 |
| `tech_communication_pullback_enhancement` | feature snapshot 路径 + manifest 路径；strategy config 路径只在要覆盖包内配置时才需要 |

说明：

- `tech_communication_pullback_enhancement` 在 IBKR 上如果还要留对账产物，可以继续配 reconciliation output path。
- `tech_communication_pullback_enhancement` 现在是 `config_source_policy=bundled_or_env`，默认使用策略包里的 canonical config，只有显式覆盖时才配 env path。
- `dynamic_mega_leveraged_pullback` 还会用到 market history、benchmark history 和 portfolio snapshot，但这些由平台运行时从券商/行情侧供应，不是额外 artifact env。
- `russell_1000_multi_factor_defensive` 目前只强制 snapshot 路径，不强制 manifest 路径。
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
- `IBKR_FEATURE_SNAPSHOT_MANIFEST_PATH`（当目标 profile 要求 manifest 时）
- `IBKR_STRATEGY_CONFIG_PATH`（仅当 `config_source_policy=env_only`，或要显式覆盖 `bundled_or_env` 的包内配置时）

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
- `SCHWAB_FEATURE_SNAPSHOT_MANIFEST_PATH`（当目标 profile 要求 manifest 时）
- `SCHWAB_STRATEGY_CONFIG_PATH`（仅当 `config_source_policy=env_only`，或要显式覆盖 `bundled_or_env` 的包内配置时）

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
- `LONGBRIDGE_FEATURE_SNAPSHOT_MANIFEST_PATH`（当目标 profile 要求 manifest 时）
- `LONGBRIDGE_STRATEGY_CONFIG_PATH`（仅当 `config_source_policy=env_only`，或要显式覆盖 `bundled_or_env` 的包内配置时）

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

## 常用切换示例

下面这些不是唯一做法，但都是最常见、最容易照抄的切换模板。

### 示例 A：把 IBKR 切到 `tqqq_growth_income`

设置：

- `STRATEGY_PROFILE=<runtime_enabled us_equity profile>`
- 保留 `ACCOUNT_GROUP`
- 保留 `IB_ACCOUNT_GROUP_CONFIG_SECRET_NAME`

如果还留着，就删掉：

- `IBKR_FEATURE_SNAPSHOT_PATH`
- `IBKR_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `IBKR_STRATEGY_CONFIG_PATH`
- `IBKR_RECONCILIATION_OUTPUT_PATH`

原因：

- `tqqq_growth_income` 只需要 `benchmark_history + portfolio_snapshot`
- 不需要 feature-snapshot 这条 artifact 链

### 示例 B：把 Schwab 切到 `tech_communication_pullback_enhancement`

设置：

- `STRATEGY_PROFILE=<runtime_enabled us_equity profile>`
- `SCHWAB_FEATURE_SNAPSHOT_PATH`
- `SCHWAB_FEATURE_SNAPSHOT_MANIFEST_PATH`

可选覆盖：

- `SCHWAB_STRATEGY_CONFIG_PATH`

是否保留下面这个开关，单独按 rollout 决定：

- `SCHWAB_DRY_RUN_ONLY`

原因：

- `tech_communication_pullback_enhancement` 是 feature-snapshot 策略
- 策略包已经带 canonical config，只有要覆盖它时才设置 env path

### 示例 C：把 LongBridge HK 切到 `russell_1000_multi_factor_defensive`

保留：

- `ACCOUNT_PREFIX=HK`
- `ACCOUNT_REGION=HK`
- `LONGPORT_SECRET_NAME`
- `LONGPORT_APP_KEY_SECRET_NAME`
- `LONGPORT_APP_SECRET_SECRET_NAME`

设置：

- `STRATEGY_PROFILE=russell_1000_multi_factor_defensive`
- `LONGBRIDGE_FEATURE_SNAPSHOT_PATH`

如果还留着，就删掉：

- `LONGBRIDGE_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `LONGBRIDGE_STRATEGY_CONFIG_PATH`

原因：

- Russell 走的是 feature snapshot 合约
- 目前只强制 snapshot 路径，不需要 manifest 或 strategy config path

### 示例 D：把 LongBridge SG 切回非 snapshot 策略

保留：

- `ACCOUNT_PREFIX=SG`
- `ACCOUNT_REGION=SG`

下面三选一设置：

- `STRATEGY_PROFILE=<runtime_enabled us_equity profile>`
- `STRATEGY_PROFILE=<runtime_enabled us_equity profile>`
- `STRATEGY_PROFILE=global_etf_rotation`

如果还留着，就删掉：

- `LONGBRIDGE_FEATURE_SNAPSHOT_PATH`
- `LONGBRIDGE_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `LONGBRIDGE_STRATEGY_CONFIG_PATH`

下面这个单独决定：

- `LONGBRIDGE_DRY_RUN_ONLY` 是否保留

原因：

- 非 snapshot 策略不需要 feature-snapshot artifact 链
- SG 是否 dry-run 是运维选择，不是策略本身要求

### 示例 E：把 LongBridge SG dry-run 切到 `dynamic_mega_leveraged_pullback`

保留：

- `ACCOUNT_PREFIX=SG`
- `ACCOUNT_REGION=SG`
- `LONGPORT_SECRET_NAME`
- `LONGPORT_APP_KEY_SECRET_NAME`
- `LONGPORT_APP_SECRET_SECRET_NAME`

设置：

- `STRATEGY_PROFILE=dynamic_mega_leveraged_pullback`
- `LONGBRIDGE_FEATURE_SNAPSHOT_PATH`
- `LONGBRIDGE_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `LONGBRIDGE_DRY_RUN_ONLY=true`

如果还留着，就删掉：

- `LONGBRIDGE_STRATEGY_CONFIG_PATH`

原因：

- 这个策略用 feature snapshot 获取动态 mega-cap 池
- 每日 market、benchmark 和 portfolio 输入由平台运行时供应
- dry-run 是部署选择，不是策略契约的一部分

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
