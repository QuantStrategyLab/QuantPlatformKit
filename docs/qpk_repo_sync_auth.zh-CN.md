# QPK 下游 Pin 自动化 Token 配置

`open-downstream-qpk-pin-prs` workflow 需要 `QSL_REPO_SYNC_TOKEN` 才能跨仓 push 分支并开 PR。

## 命名约定

- GitHub fine-grained PAT 的显示名统一为 `qsl-<用途>-<轮换周期>`，例如
  `qsl-github-repo-sync-annual`。
- GitHub Actions Secret 的环境变量名统一使用大写下划线。`QSL_REPO_SYNC_TOKEN`
  是现有工作流契约名，保持不变，不要为了美化名称直接改名。
- 其他平台的 token 迁移时沿用同一格式，例如
  `qsl-binance-authority-maintenance-annual`；替换前必须先确认实际消费者和完整验证链路。

长期方案是 GitHub App installation token：每次工作流运行时临时签发短期 token，避免个人 PAT 到期。
App 的凭据使用 `QSL_GITHUB_APP_ID` 和 `QSL_GITHUB_APP_PRIVATE_KEY` 两个仓库 Secret；迁移期间
工作流优先使用 App token，未配置 App 时才回退到 `QSL_REPO_SYNC_TOKEN`。

## 当前发布链说明

QPK 发布采用 release-set 两阶段流程：先生成候选 QPK 版本并验证依赖闭包，再由下游仓库分别通过 CI 后更新正式 release-set。旧的 `auto/qpk-pin-sync-*` 和孤立的 `auto/qpk-pin-update` 分支不再作为发布输入；如果发现没有对应开放 PR 的孤立自动分支，应删除后再重新触发发布流程。

跨仓同步 token 只用于创建下游 PR，不用于部署、运行时交易或修改任何 broker 权限。优先使用仅限目标仓库的 fine-grained token；不要把个人长期 token 写入仓库文件、workflow 日志或 issue。

## 为什么用仓库级 Secret（不是 Org Secret）

`QuantPlatformKit` 是 **public** 仓库。在 GitHub Free org 上，org-level secret 对 public 仓的注入不可靠（workflow 里会静默变成空字符串）。**仓库级 secret** 是唯一已验证稳定的方案。

## 一次性配置（org admin）

### 长期方案：GitHub App

1. 创建一个仅服务于 QSL 下游 Pin 同步的 GitHub App，并安装到 QuantStrategyLab 组织。
2. 只授予目标 15 个仓库的 `Contents: Read and write`、`Pull requests: Read and write`，保留必要的 metadata 读取权限。
3. 将 App ID 写入 `QSL_GITHUB_APP_ID`，将下载的私钥完整写入 `QSL_GITHUB_APP_PRIVATE_KEY`。
4. 先手动触发 `open-downstream-qpk-pin-prs`，确认日志显示同步和 PR 操作成功；再撤销旧 PAT。

App 私钥只存储在 GitHub Actions Secret 中，不写入仓库、工作流日志、issue 或本机文件。

### Fine-grained PAT（当前生产方案）

1. 打开生成页（需 Pigbibi 登录 GitHub），token 显示名使用
   `qsl-github-repo-sync-annual`，有效期使用组织允许的最长期限：

   https://github.com/settings/personal-access-tokens/new

2. Resource owner 选 `QuantStrategyLab`，Repository access 只选择下列 15 个仓库：

   - `QuantPlatformKit` 及四个策略仓：`CnEquityStrategies`、`HkEquityStrategies`、`UsEquityStrategies`、`CryptoStrategies`
   - 六个执行仓：`InteractiveBrokersPlatform`、`LongBridgePlatform`、`CharlesSchwabPlatform`、`FirstradePlatform`、`BinancePlatform`、`QmtPlatform`
   - 四个数据/池管道：`CnEquitySnapshotPipelines`、`HkEquitySnapshotPipelines`、`UsEquitySnapshotPipelines`、`CryptoLivePoolPipelines`

3. 只授予 `Contents: Read and write`、`Pull requests: Read and write`，并保留 GitHub 要求的 `Metadata: Read-only`。
4. 生成后写入仓库级 Secret：

   ```bash
   gh secret set QSL_REPO_SYNC_TOKEN --repo QuantStrategyLab/QuantPlatformKit
   ```

不要把 `gh auth token`、classic PAT 或 token 明文写入生产 Secret；迁移完成并通过工作流验证后撤销旧 token。

## 验真

```bash
gh workflow run open-downstream-qpk-pin-prs.yml -R QuantStrategyLab/QuantPlatformKit
# 日志应出现 QSL_REPO_SYNC_TOKEN: *** 且各仓 no changes needed
```

## 权限要求

PAT 需对以下仓库有 **Contents: Read and write** + **Pull requests: Read and write**：

- QuantPlatformKit, CnEquityStrategies, HkEquityStrategies, UsEquityStrategies, CryptoStrategies
- InteractiveBrokersPlatform, LongBridgePlatform, CharlesSchwabPlatform, FirstradePlatform, BinancePlatform, QmtPlatform
- CnEquitySnapshotPipelines, HkEquitySnapshotPipelines, UsEquitySnapshotPipelines, CryptoLivePoolPipelines
