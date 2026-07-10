# reusable drift workflow rollout / 联调清单

适用范围：

- `QuantStrategyLab/QuantPlatformKit`
- `QuantStrategyLab/UsEquityStrategies`
- `QuantStrategyLab/HkEquityStrategies`
- `QuantStrategyLab/CnEquityStrategies`
- `QuantStrategyLab/CryptoStrategies`

## 1. 合并顺序

必须按下面顺序执行，否则下游仓库会引用到不存在的 reusable workflow：

1. 先合并 `QuantPlatformKit`
   - 新增 `.github/workflows/reusable-drift-check.yml`
   - 新增 `quant-lifecycle doctor`
   - `doctor` 已要求 `--require-snapshot --require-backtest --max-freshness-days 7`
2. 再合并 4 个策略仓库
   - `UsEquityStrategies`
   - `HkEquityStrategies`
   - `CnEquityStrategies`
   - `CryptoStrategies`

## 2. 合并前本地校验

### QuantPlatformKit

```bash
cd /Users/lisiyi/Projects/_worktrees/quant_p0/QuantPlatformKit
PYTHONPATH=src python3 -m pytest -q \
  tests/test_reusable_drift_workflow.py \
  tests/test_lifecycle_cli.py \
  tests/test_lifecycle_doctor.py \
  tests/test_strategy_performance_export.py
```

### 4 个策略仓库

```bash
QPK=/Users/lisiyi/Projects/_worktrees/quant_p0/QuantPlatformKit/src
for repo in UsEquityStrategies HkEquityStrategies CnEquityStrategies CryptoStrategies; do
  cd "/Users/lisiyi/Projects/_worktrees/quant_p0/$repo"
  PYTHONPATH="$QPK" python3 -m pytest -q tests/test_drift_workflow_config.py
done
```

## 3. 合并后线上联调步骤

以下步骤必须在 `QuantPlatformKit` 和对应策略仓库都进入 `main` 后执行。

### 3.1 手动触发 workflow

```bash
gh workflow run drift-check.yml -R QuantStrategyLab/UsEquityStrategies
gh workflow run drift-check.yml -R QuantStrategyLab/HkEquityStrategies
gh workflow run drift-check.yml -R QuantStrategyLab/CnEquityStrategies
gh workflow run drift-check.yml -R QuantStrategyLab/CryptoStrategies
```

### 3.2 观察最近一次运行

```bash
for repo in UsEquityStrategies HkEquityStrategies CnEquityStrategies CryptoStrategies; do
  echo "==== $repo ===="
  gh run list -R QuantStrategyLab/$repo -w drift-check.yml -L 3 \
    --json databaseId,status,conclusion,createdAt,updatedAt,headBranch,event,url
done
```

### 3.3 失败时重点看 doctor step

如果 workflow 变红，先看 `Validate lifecycle prerequisites`：

- `No strategy return series discovered`
  - snapshot/pipeline 仓库没有生成可读 returns
  - `QUANT_PROJECTS_ROOT` 下路径不匹配
- `missing lifecycle snapshot`
  - `quant-lifecycle monitor` 没有落到 `LIFECYCLE_LOCAL_ROOT` / bucket
- `missing lifecycle backtest`
  - 当前域还没有持久化 baseline / walk-forward backtest
  - 这是本次收口最可能暴露出来的新红灯
- `snapshot freshness ... exceeds max 7d`
  - 数据链路断更或产物过旧

## 4. 当前 main 基线（2026-07-10）

下面是切换到 reusable workflow 之前，`main` 上最近一次 `drift-check.yml` 运行：

- `UsEquityStrategies`
  - run: `29081276798`
  - created: `2026-07-10T08:54:29Z`
  - conclusion: `success`
  - link: <https://github.com/QuantStrategyLab/UsEquityStrategies/actions/runs/29081276798>
- `HkEquityStrategies`
  - run: `29081274915`
  - created: `2026-07-10T08:54:27Z`
  - conclusion: `success`
  - link: <https://github.com/QuantStrategyLab/HkEquityStrategies/actions/runs/29081274915>
- `CnEquityStrategies`
  - run: `29083727180`
  - created: `2026-07-10T09:38:36Z`
  - conclusion: `success`
  - link: <https://github.com/QuantStrategyLab/CnEquityStrategies/actions/runs/29083727180>
- `CryptoStrategies`
  - run: `29083379166`
  - created: `2026-07-10T09:32:18Z`
  - conclusion: `success`
  - link: <https://github.com/QuantStrategyLab/CryptoStrategies/actions/runs/29083379166>

注意：这些都是旧 workflow 的结果，不能证明新的 `doctor --require-backtest` 已通过。

## 5. 通过标准

4 个仓库全部满足以下条件，才算这一批 rollout 完成：

1. `drift-check.yml` 在 `main` 上成功运行；
2. workflow summary 不再是“0 strategies checked”假绿灯；
3. `doctor` 没有报 `missing lifecycle backtest`；
4. `drift` step 至少验证到真实策略样本；
5. GitHub Issues / AIAuditBridge dual-review 链路未回归。
