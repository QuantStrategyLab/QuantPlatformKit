# 美股发布与切换计划

> 这份文档主要记录最初那次共享包发布和首轮切换顺序。
> 现在日常做线上策略切换或回滚时，请优先看 `docs/us_equity_live_switch_runbook.zh-CN.md`。

这份文档是下面两份规范的执行版补充：

- `docs/us_equity_cross_platform_strategy_spec.md`
- `docs/us_equity_execution_translation_spec.md`

它只解决两件事：

- 共享包怎么安全发布
- 线上平台服务怎么切到目标策略

它**不**重新定义策略公式。

## 为什么要单独写这份计划

这轮本地重构已经跨了：

- `QuantPlatformKit`
- `UsEquityStrategies`
- `InteractiveBrokersPlatform`
- `CharlesSchwabPlatform`
- `LongBridgePlatform`

而平台服务并不是直接装本地 sibling repo，它们装的是固定 Git tag：

- `quant-platform-kit`
- `us-equity-strategies`

所以线上切换不能反着来，必须按这个顺序：

1. 先发共享包
2. 再改平台仓库依赖 pin
3. 再部署平台仓库
4. 最后再改线上策略 env

## 当前基线

### 共享包版本

- `QuantPlatformKit`: `0.7.8`
- `UsEquityStrategies`: `0.7.11`

### 当前平台仓库依赖 pin

| 仓库 | `quant-platform-kit` | `us-equity-strategies` |
| --- | --- | --- |
| `InteractiveBrokersPlatform` | `v0.7.7` | `v0.7.7` |
| `CharlesSchwabPlatform` | `v0.7.8` | `v0.7.10` |
| `LongBridgePlatform` | `v0.7.8` | `v0.7.11` |

这就是当前发布风险最大的地方：本地 runtime 改动已经超过线上 tag 版本了。

## 建议的下一组发布版本

建议这次统一成：

- `QuantPlatformKit` -> `v0.7.10`
- `UsEquityStrategies` -> `v0.7.13`

原因：

- `UsEquityStrategies` 依赖 `QuantPlatformKit`
- 这轮新的 runtime / execution helper 主要都在 `QuantPlatformKit`
- 所以必须先发 QPK，再发 UES

## 发布顺序

### 第一步：发布 `QuantPlatformKit`

这次应该包含：

- execution translation helper
- feature snapshot 共享加载逻辑
- 跨平台 runtime input helper
- IBKR runtime input helper

产出：

- tag `v0.7.10`

### 第二步：更新并发布 `UsEquityStrategies`

改动：

- 把它对 QPK 的依赖升级到 `quant-platform-kit @ ...@v0.7.10`

产出：

- tag `v0.7.13`

### 第三步：更新平台仓库 requirements

等两个 tag 都存在后，再统一把三个平台仓库改成：

| 仓库 | `quant-platform-kit` | `us-equity-strategies` |
| --- | --- | --- |
| `InteractiveBrokersPlatform` | `v0.7.10` | `v0.7.13` |
| `CharlesSchwabPlatform` | `v0.7.10` | `v0.7.13` |
| `LongBridgePlatform` | `v0.7.10` | `v0.7.13` |

注意：

- tag 还没发出来之前，**不要**先改 requirements 指向不存在的 tag
- 也不要先切线上 env，再赌部署会补上

### 第四步：部署平台仓库

每个平台仓库都应该在 requirements 更新并合并后再部署。

最低要求：

- 镜像里必须已经带上新的 QPK / UES tag
- Cloud Run 上必须先确认部署 commit 正确，再改线上策略 env

## 实际命令清单

下面这套顺序可以直接用，前提是每一步先看清楚待提交内容再打 tag。

### 1）发布 `QuantPlatformKit` -> `v0.7.10`

```bash
cd /Users/lisiyi/Projects/QuantPlatformKit
git diff --check
./.venv/bin/python -m unittest tests.test_strategy_contracts
PYTHONPATH=src /Users/lisiyi/Projects/LongBridgePlatform/.venv/bin/python -m unittest \
  tests.test_strategy_contracts \
  tests.test_ibkr_runtime_inputs \
  tests.test_longbridge_portfolio

git add README.md README.zh-CN.md pyproject.toml src tests docs
git commit -m "Prepare v0.7.10 release"
git tag v0.7.10
git push origin HEAD
git push origin v0.7.10
```

### 2）发布 `UsEquityStrategies` -> `v0.7.13`

```bash
cd /Users/lisiyi/Projects/UsEquityStrategies
git diff --check
PYTHONPATH=/Users/lisiyi/Projects/QuantPlatformKit/src:src \
  /Users/lisiyi/Projects/LongBridgePlatform/.venv/bin/python -m unittest \
  tests.test_catalog \
  tests.test_entrypoints \
  tests.test_platform_registry_support

git add README.md pyproject.toml src tests docs
git commit -m "Prepare v0.7.13 release"
git tag v0.7.13
git push origin HEAD
git push origin v0.7.13
```

### 3）等两个 tag 都存在后，再更新三个平台仓库

```bash
cd /Users/lisiyi/Projects/InteractiveBrokersPlatform
git diff --check
git add requirements.txt
git commit -m "Bump shared strategy package pins"
git push origin HEAD

cd /Users/lisiyi/Projects/CharlesSchwabPlatform
git diff --check
git add requirements.txt
git commit -m "Bump shared strategy package pins"
git push origin HEAD

cd /Users/lisiyi/Projects/LongBridgePlatform
git diff --check
git add requirements.txt
git commit -m "Bump shared strategy package pins"
git push origin HEAD
```

如果某个仓库还有无关本地改动，先拆提交或先 stash，再做这次发版提交。

## 目标线上策略矩阵

| 平台服务 | 目标策略 profile | 说明 |
| --- | --- | --- |
| `charles-schwab-quant-service` | `tqqq_growth_income` | Schwab 继续跑 TQQQ 增长收益 |
| `longbridge-quant-hk-service` | `qqq_tech_enhancement` | HK 切到 QQQ 科技增强 |
| `longbridge-quant-sg-service` | `tqqq_growth_income` | SG 继续跑 TQQQ 增长收益 |
| `interactive-brokers-quant-service` | `soxl_soxx_trend_income` | IBKR 切到 SOXL/SOXX 半导体趋势收益 |

## 切换时要改的 env

### CharlesSchwabPlatform

服务：

- `charles-schwab-quant-service`

设置：

- `STRATEGY_PROFILE=tqqq_growth_income`

删除：

- `SCHWAB_DRY_RUN_ONLY`，除非明确要临时回到 dry-run

### LongBridgePlatform HK

服务：

- `longbridge-quant-hk-service`

设置：

- `ACCOUNT_PREFIX=HK`
- `ACCOUNT_REGION=HK`
- `STRATEGY_PROFILE=qqq_tech_enhancement`
- `LONGBRIDGE_FEATURE_SNAPSHOT_PATH`
- `LONGBRIDGE_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `LONGBRIDGE_STRATEGY_CONFIG_PATH`

默认保持不设：

- `LONGBRIDGE_DRY_RUN_ONLY`

原因：

- `qqq_tech_enhancement` 是 feature snapshot 策略
- HK 这次不只是改 profile，还需要把 snapshot/config 输入一起接上

### LongBridgePlatform SG

服务：

- `longbridge-quant-sg-service`

设置：

- `ACCOUNT_PREFIX=SG`
- `ACCOUNT_REGION=SG`
- `STRATEGY_PROFILE=tqqq_growth_income`

是否继续 dry-run，保持当前决定：

- `LONGBRIDGE_DRY_RUN_ONLY`

如果还有这些变量，要删掉：

- `LONGBRIDGE_FEATURE_SNAPSHOT_PATH`
- `LONGBRIDGE_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `LONGBRIDGE_STRATEGY_CONFIG_PATH`

### InteractiveBrokersPlatform

服务：

- `interactive-brokers-quant-service`

设置：

- `STRATEGY_PROFILE=soxl_soxx_trend_income`

下面这些先保持现状，除非另行决定是否真跑：

- `IBKR_DRY_RUN_ONLY`
- `ACCOUNT_GROUP`

从 `qqq_tech_enhancement` 切走后，要把 tech 专用的 feature snapshot env 删掉：

- `IBKR_FEATURE_SNAPSHOT_PATH`
- `IBKR_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `IBKR_STRATEGY_CONFIG_PATH`
- `IBKR_RECONCILIATION_OUTPUT_PATH`

原因：

- `soxl_soxx_trend_income` 现在走的是 canonical `derived_indicators + portfolio_snapshot`
- 不再需要科技增强那套 feature snapshot artifact 链路

## 验证清单

### 改线上 env 之前

每个平台仓库都要先做：

1. 确认 `requirements.txt` 已经 pin 到目标 QPK / UES tag
2. 跑最相关的 strategy runtime 测试
3. 部署
4. 确认 Cloud Run 上真的已经是新 commit

### 改线上 env 之后

用 `gcloud run services describe ...` 确认：

- `CLOUD_RUN_SERVICE` 指向对的服务
- `STRATEGY_PROFILE` 是目标策略
- 只有需要 snapshot 的服务保留 snapshot env
- 已经不再使用 snapshot 的服务，旧 env 已删掉

再看第一条心跳 / 执行通知：

- Schwab -> `TQQQ Growth Income`
- LongBridge HK -> `QQQ Tech Enhancement`
- LongBridge SG -> `TQQQ Growth Income`
- IBKR -> `SOXL/SOXX Semiconductor Trend Income`

## 回滚原则

回滚顺序反过来：

1. 先回滚线上 env
2. 再回滚平台仓库 requirements
3. 真有必要时，再通过发布新的修复 tag 回滚共享包

不要再拿旧 service name 或旧的“服务名里带策略名”当回滚手段。
