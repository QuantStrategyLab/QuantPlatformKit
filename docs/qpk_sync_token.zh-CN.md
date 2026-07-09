# QPK 下游 Pin 自动化 Token 配置

`open-downstream-qpk-pin-prs` workflow 需要 `QSL_REPO_SYNC_TOKEN` 才能跨仓 push 分支并开 PR。

## 为什么用仓库级 Secret（不是 Org Secret）

`QuantPlatformKit` 是 **public** 仓库。在 GitHub Free org 上，org-level secret 对 public 仓的注入不可靠（workflow 里会静默变成空字符串）。**仓库级 secret** 是唯一已验证稳定的方案。

## 一次性配置（org admin）

### 方案 A：专用 Fine-grained PAT（推荐，可设 1 年过期）

1. 打开预填模板（需 Pigbibi 登录 GitHub）：

   https://github.com/settings/personal-access-tokens/new?name=QSL-Repo-Sync&description=QuantPlatformKit+downstream+QPK+pin+automation&target_name=QuantStrategyLab&expires_in=365&contents=write&pull_requests=write&metadata=read

2. Repository access 选 **All repositories**（或至少九仓策略 + 四平台 + Binance）。
3. 生成后执行：

   ```bash
   gh secret set QSL_REPO_SYNC_TOKEN --repo QuantStrategyLab/QuantPlatformKit
   # 粘贴 PAT，回车
   ```

### 方案 B：临时用 gh 登录 token（已用于首次 bootstrap）

```bash
gh secret set QSL_REPO_SYNC_TOKEN --repo QuantStrategyLab/QuantPlatformKit --body "$(gh auth token)"
```

OAuth token 会随 `gh auth login` 刷新而失效，仅适合 bootstrap；生产请用方案 A。

## 验真

```bash
gh workflow run open-downstream-qpk-pin-prs.yml -R QuantStrategyLab/QuantPlatformKit
# 日志应出现 QSL_REPO_SYNC_TOKEN: *** 且各仓 no changes needed
```

## 权限要求

PAT 需对以下仓库有 **Contents: Read and write** + **Pull requests: Read and write**：

- CnEquityStrategies, HkEquityStrategies, UsEquityStrategies, CryptoStrategies
- InteractiveBrokersPlatform, LongBridgePlatform, CharlesSchwabPlatform, FirstradePlatform, BinancePlatform
