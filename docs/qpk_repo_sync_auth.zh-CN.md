# QPK 下游 Pin 自动化 Token 配置

`open-downstream-qpk-pin-prs` workflow 需要 `QSL_REPO_SYNC_TOKEN` 才能跨仓 push 分支并开 PR。

## 当前发布链说明

QPK 发布采用 release-set 两阶段流程：先生成候选 QPK 版本并验证依赖闭包，再由下游仓库分别通过 CI 后更新正式 release-set。旧的 `auto/qpk-pin-sync-*` 和孤立的 `auto/qpk-pin-update` 分支不再作为发布输入；如果发现没有对应开放 PR 的孤立自动分支，应删除后再重新触发发布流程。

跨仓同步 token 只用于创建下游 PR，不用于部署、运行时交易或修改任何 broker 权限。优先使用仅限目标仓库的 fine-grained token；不要把个人长期 token 写入仓库文件、workflow 日志或 issue。

## 为什么用仓库级 Secret（不是 Org Secret）

`QuantPlatformKit` 是 **public** 仓库。在 GitHub Free org 上，org-level secret 对 public 仓的注入不可靠（workflow 里会静默变成空字符串）。**仓库级 secret** 是唯一已验证稳定的方案。

## 一次性配置（org admin）

### 方案 A：Classic PAT（推荐，可选 No expiration）

1. 打开：https://github.com/settings/tokens/new?scopes=repo&description=QSL-Repo-Sync
2. 勾选 **repo**，Expiration 选 **No expiration**（若 org 强制上限则选最长）。
3. 生成后执行：

   ```bash
   gh secret set QSL_REPO_SYNC_TOKEN --repo QuantStrategyLab/QuantPlatformKit
   ```

### 方案 B：Fine-grained PAT（org 通常最长 1 年）

1. 打开预填模板（需 Pigbibi 登录 GitHub）：

   https://github.com/settings/personal-access-tokens/new?name=QSL-Repo-Sync&description=QuantPlatformKit+downstream+QPK+pin+automation&target_name=QuantStrategyLab&expires_in=366&contents=write&pull_requests=write&metadata=read

2. Repository access 选 **All repositories**（或至少四个策略仓、六个执行平台和四个 P1 数据管道）。
3. 生成后执行：

   ```bash
   gh secret set QSL_REPO_SYNC_TOKEN --repo QuantStrategyLab/QuantPlatformKit
   ```

### 方案 C：临时 bootstrap（仅首次）

```bash
gh secret set QSL_REPO_SYNC_TOKEN --repo QuantStrategyLab/QuantPlatformKit --body "$(gh auth token)"
```

OAuth token 会随 `gh auth login` 刷新而失效；生产请用方案 A 或 B。

## 验真

```bash
gh workflow run open-downstream-qpk-pin-prs.yml -R QuantStrategyLab/QuantPlatformKit
# 日志应出现 QSL_REPO_SYNC_TOKEN: *** 且各仓 no changes needed
```

## 权限要求

PAT 需对以下仓库有 **Contents: Read and write** + **Pull requests: Read and write**：

- CnEquityStrategies, HkEquityStrategies, UsEquityStrategies, CryptoStrategies
- InteractiveBrokersPlatform, LongBridgePlatform, CharlesSchwabPlatform, FirstradePlatform, BinancePlatform, QmtPlatform
- CnEquitySnapshotPipelines, HkEquitySnapshotPipelines, UsEquitySnapshotPipelines, CryptoLivePoolPipelines
