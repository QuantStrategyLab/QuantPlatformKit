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

## 策略选择器切换模式

这份公开 runbook 不绑定任何账户或服务当前应该跑哪条策略。先从受支持平台矩阵里选择目标 profile，再按下面的输入类型切换。

| 服务类型 | 策略选择器 | 直接运行输入 | Snapshot 驱动输入 |
| --- | --- | --- | --- |
| Schwab Cloud Run 服务 | `STRATEGY_PROFILE=<runtime_enabled us_equity profile>` | runtime 提供 market / benchmark history 和 portfolio snapshot | feature snapshot path、manifest path、可选 strategy config path |
| IBKR Cloud Run 服务 | `STRATEGY_PROFILE=<runtime_enabled us_equity profile>` | runtime 提供 market / benchmark history 和 portfolio snapshot | feature snapshot path、manifest path、可选 strategy config path，以及 reconciliation output path |
| LongBridge 区域服务 | `STRATEGY_PROFILE=<runtime_enabled us_equity profile>` | runtime 提供 market / benchmark history 和 portfolio snapshot | feature snapshot path、manifest path、可选 strategy config path |

## 切换时要改的 env

### 直接运行输入策略

设置：

- `STRATEGY_PROFILE=<direct-runtime profile>`

如果残留 snapshot env，要删掉：

- `*_FEATURE_SNAPSHOT_PATH`
- `*_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `*_STRATEGY_CONFIG_PATH`
- 平台拥有 reconciliation output 时，删掉 `*_RECONCILIATION_OUTPUT_PATH`

执行模式或 dry-run 相关变量保持不动，除非这次 rollout 明确要改变。

### Snapshot 驱动策略

设置：

- `STRATEGY_PROFILE=<snapshot-backed profile>`
- `<PLATFORM>_FEATURE_SNAPSHOT_PATH`
- `<PLATFORM>_FEATURE_SNAPSHOT_MANIFEST_PATH`
- profile 需要外部配置时设置 `<PLATFORM>_STRATEGY_CONFIG_PATH`

原因：

- snapshot 驱动策略消费 `UsEquitySnapshotPipelines` 发布的 artifact
- 直接运行输入策略不需要 feature snapshot artifact 链路

### LongBridge 区域服务

每个区域服务分别设置：

- `ACCOUNT_PREFIX=HK|SG`
- `ACCOUNT_REGION=HK|SG`
- `STRATEGY_PROFILE=<runtime_enabled us_equity profile>`
- `LONGPORT_SECRET_NAME=<region token secret>`

切换策略时不要改 service name。

## 验证清单

### 改 env 之前

每个平台仓库都要先做：

1. 确认 `requirements.txt` 已经 pin 到目标 QPK / UES tag
2. 跑最相关的 strategy runtime 测试
3. 部署
4. 确认 Cloud Run 上真的已经是新 commit

### 改 env 之后

用 `gcloud run services describe ...` 确认：

- `CLOUD_RUN_SERVICE` 指向对的服务
- `STRATEGY_PROFILE` 是目标策略
- 只有需要 snapshot 的服务保留 snapshot env
- 已经不再使用 snapshot 的服务，旧 env 已删掉

再看第一条心跳 / 执行通知：

- 策略显示名和选择的 profile 一致
- 输入类型 diagnostics 和选择的 profile 类型一致
- 直接运行输入策略没有残留 snapshot env
- snapshot 驱动策略能加载目标 artifact manifest

## 回滚原则

回滚顺序反过来：

1. 先回滚线上 env
2. 再回滚平台仓库 requirements
3. 真有必要时，再通过发布新的修复 tag 回滚共享包

不要再拿旧 service name 或旧的“服务名里带策略名”当回滚手段。
