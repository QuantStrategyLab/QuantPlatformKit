[English](qpk-repo-sync-auth.md) | 简体中文

# QPK 下游 Pin 自动化 Token 配置

`open-downstream-qpk-pin-prs.yml`、`update-qpk-pin.yml` 与 `advance-staged-qpk-pin.yml` 均使用组织级 GitHub App（`<github-app-name>`，`<github-app-slug>`）的短期 installation token（通过 `QSL_GITHUB_APP_ID`、`QSL_GITHUB_APP_PRIVATE_KEY` 与 `QSL_GITHUB_APP_PRIVATE_KEY_SECONDARY` 签发），其中 `update-qpk-pin.yml` 与 `advance-staged-qpk-pin.yml` 支持 `disable_legacy_pat_fallback` 以对 App token 路径做 fail-closed 验真。`QSL_REPO_SYNC_TOKEN` 已退役并从 `QuantPlatformKit` 仓库级 secret 与 `QuantStrategyLab` 组织级 secret 中移除（仅保留历史引用说明，不再作为现役回退配置）。

只读自检由 `qpk-github-app-health` workflow（定时 + 手动）完成：优先用主私钥签发短期
token，仅在主钥签发未成功时使用备用私钥，再校验目标仓库访问与 `QPK_PIN` 读回，失败则
fail-closed，摘要不含任何 secret / token / 私钥内容。

## 命名约定

- GitHub fine-grained PAT 的显示名统一为 `qsl-<用途>-<轮换周期>`（原
  `qsl-github-repo-sync-annual` 已退役）。
- GitHub Actions Secret 的环境变量名统一使用大写下划线。`QSL_REPO_SYNC_TOKEN`
  仅作为历史工作流引用名保留在说明中，不再配置为现役仓库级或组织级 Secret。
- 其他平台的 token 迁移时沿用同一格式，例如
  `qsl-binance-authority-maintenance-annual`；替换前必须先确认实际消费者和完整验证链路。

**明确边界：Binance authority PAT（以及任何券商/交易相关 Secret）与本 App / repo-sync
凭据完全分离。** 不得把 Binance authority token 写入
`QSL_GITHUB_APP_*` 或 `QSL_REPO_SYNC_TOKEN`，也不要用本 App 私钥去代替 Binance 恢复或
authority 维护。

## Secret 清单（QuantPlatformKit 仓库级）

| Secret | 状态 | 用途 |
|---|---|---|
| `QSL_GITHUB_APP_ID` | 现役 | 组织级 GitHub App ID（`<github-app-id>`） |
| `QSL_GITHUB_APP_PRIVATE_KEY` | 现役 | 主私钥（优先签发） |
| `QSL_GITHUB_APP_PRIVATE_KEY_SECONDARY` | 现役 | 备用私钥（仅主钥签发失败/未配置时使用） |
| `QSL_REPO_SYNC_TOKEN` | 已退役 / 已移除 | 历史 PAT 回退名；已从 `QuantPlatformKit` 仓库级与 `QuantStrategyLab` 组织级 Secret 移除 |

长期方案是 GitHub App installation token：每次工作流运行时临时签发短期 token，避免个人
PAT 到期。`actions/create-github-app-token` 每次只接受一个 `private-key` 输入，因此双钥
failover 通过「主钥步骤 `continue-on-error` + 仅在主钥未成功时条件签发备用钥」实现，
不拼接私钥、不自写 JWT。主钥能签发但权限不足时不会改走备用钥（同一 App 安装权限相同），
由后续仓库/`QPK_PIN` 校验 fail-closed。

## 当前发布链说明

QPK 发布采用 release-set 两阶段流程：先生成候选 QPK 版本并验证依赖闭包，再由下游仓库分别通过 CI 后更新正式 release-set。旧的 `auto/qpk-pin-sync-*` 和孤立的 `auto/qpk-pin-update` 分支不再作为发布输入；如果发现没有对应开放 PR 的孤立自动分支，应删除后再重新触发发布流程。

跨仓同步 token 只用于创建下游 PR，不用于部署、运行时交易或修改任何 broker 权限。不要把个人长期 token 写入仓库文件、workflow 日志或 issue。

## 为什么用仓库级 Secret（不是 Org Secret）

`QuantPlatformKit` 是 **public** 仓库。在 GitHub Free org 上，org-level secret 对 public 仓的注入不可靠（workflow 里会静默变成空字符串）。**仓库级 secret** 是唯一已验证稳定的方案。

## 一次性配置（org admin）

### 当前方案：组织级 GitHub App

1. 已创建并安装组织级 App（`<github-app-name>`，App ID `<github-app-id>`）到 `QuantStrategyLab`。
2. 只授予目标 15 个仓库的 `Contents: Read and write`、`Pull requests: Read and write`，保留必要的 metadata 读取权限。
3. 将 App ID 写入 `QSL_GITHUB_APP_ID`，将主私钥写入 `QSL_GITHUB_APP_PRIVATE_KEY`。
4. 在 App 设置中生成第二把私钥写入 `QSL_GITHUB_APP_PRIVATE_KEY_SECONDARY`，供轮换与故障切换。
5. 手动触发 `qpk-github-app-health`，确认摘要显示 `token_source: primary`（或预期的
   secondary）且结果为 pass；再验证 `open-downstream-qpk-pin-prs.yml`、`update-qpk-pin.yml` 与 `advance-staged-qpk-pin.yml`（可通过 `disable_legacy_pat_fallback: true` 验证纯 App 路径）。旧的 `qsl-github-repo-sync-annual` PAT 已撤销，Binance 专用 PAT 保持不变。

App 私钥只存储在 GitHub Actions Secret 中，不写入仓库、工作流日志、issue 或本机文件。

### 轮换与故障切换

1. 在 GitHub App 设置中生成新私钥，写入尚未承载生产主钥的 Secret 槽位（通常是
   `QSL_GITHUB_APP_PRIVATE_KEY_SECONDARY`）。
2. 手动运行 `qpk-github-app-health`：确认新钥可签发（必要时临时清空/失效主钥槽位做受控验证，
   或在主钥失败时观察 `token_source: secondary`）。
3. 将新钥提升为主钥：把新材料写入 `QSL_GITHUB_APP_PRIVATE_KEY`，旧主钥保留在 secondary
   或撤销。
4. 再次运行 `qpk-github-app-health` 并验证 `open-downstream-qpk-pin-prs.yml`、`update-qpk-pin.yml`（`disable_legacy_pat_fallback: true`）与 `advance-staged-qpk-pin.yml`（`disable_legacy_pat_fallback: true`）。
5. 在 App 设置中删除已退役的私钥。不要在日志、PR 或本机文件中保留 PEM 明文。

故障时：主钥签发失败会自动尝试 secondary；health workflow 与 `disable_legacy_pat_fallback: true` 运行均采用 fail-closed（不使用 PAT 伪装 App 健康）。

### 历史 PAT 退役说明（`QSL_REPO_SYNC_TOKEN`）

`QSL_REPO_SYNC_TOKEN`（原 `qsl-github-repo-sync-annual`）已退役，并已从 `QuantPlatformKit` 仓库级 Secret 与 `QuantStrategyLab` 组织级 Secret 中移除。不要重新配置 `QSL_REPO_SYNC_TOKEN`，也不要把 `gh auth token`、classic PAT 或 token 明文写入仓库或组织 Secret；密钥轮换与故障切换统一使用 `QSL_GITHUB_APP_PRIVATE_KEY_SECONDARY`。

## 验真

```bash
gh workflow run qpk-github-app-health.yml -R QuantStrategyLab/QuantPlatformKit
# 摘要应出现 token_source / repositories_checked / result: pass，且无 secret 明文

gh workflow run open-downstream-qpk-pin-prs.yml -R QuantStrategyLab/QuantPlatformKit
# 日志应出现 Mint short-lived QSL GitHub App token、Token revoked，且同步步骤成功

gh workflow run update-qpk-pin.yml -R QuantStrategyLab/QuantPlatformKit -f disable_legacy_pat_fallback=true -f verify_app_token_only=true
gh workflow run advance-staged-qpk-pin.yml -R QuantStrategyLab/QuantPlatformKit -f disable_legacy_pat_fallback=true -f verify_app_token_only=true
```

## 权限要求

组织级 GitHub App（`<github-app-name>`）需对以下 14 个仓库具有 **Contents: Read and write** + **Pull requests: Read and write**
（health 校验只用只读 installation token）：

- QuantPlatformKit, CnEquityStrategies, HkEquityStrategies, UsEquityStrategies, CryptoStrategies
- InteractiveBrokersPlatform, LongBridgePlatform, CharlesSchwabPlatform, FirstradePlatform, BinancePlatform
- CnEquitySnapshotPipelines, HkEquitySnapshotPipelines, UsEquitySnapshotPipelines, CryptoLivePoolPipelines
