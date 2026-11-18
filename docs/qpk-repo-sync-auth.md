# QPK Downstream Pin Automation Token Configuration

[简体中文](qpk-repo-sync-auth.zh-CN.md)

The `open-downstream-qpk-pin-prs.yml`, `update-qpk-pin.yml`, and `advance-staged-qpk-pin.yml` workflows run on short-lived GitHub App installation tokens minted for `QSL QPK Pin Sync` (`qsl-qpk-pin-sync`) via `QSL_GITHUB_APP_ID`, `QSL_GITHUB_APP_PRIVATE_KEY`, and `QSL_GITHUB_APP_PRIVATE_KEY_SECONDARY`. `update-qpk-pin.yml` and `advance-staged-qpk-pin.yml` also support `disable_legacy_pat_fallback` for fail-closed verification of the App token path. `QSL_REPO_SYNC_TOKEN` has been retired and removed from both `QuantPlatformKit` repository secrets and `QuantStrategyLab` organization secrets (historical reference only).

Read-only self-checks run via the `qpk-github-app-health` workflow (scheduled and manual): it mints a short-lived token using the primary private key first, falls back to the secondary key only if primary minting fails, and verifies repository access and `QPK_PIN` readback, failing closed without exposing secret, token, or private key material in summaries.

## Naming conventions

- GitHub fine-grained PAT display names follow `qsl-<purpose>-<rotation-cycle>` (the legacy `qsl-github-repo-sync-annual` PAT is retired).
- GitHub Actions secret names use uppercase snake case. `QSL_REPO_SYNC_TOKEN` remains in workflow expressions only as a historical fallback name and is no longer configured as an active secret.
- Future token migrations follow the same pattern (e.g., `qsl-binance-authority-maintenance-annual`) after verifying actual consumers and end-to-end checks.

**Strict boundary: Binance authority PATs (and any broker/trading secrets) are completely separate from this App and repo-sync credentials.** Never place Binance authority tokens into `QSL_GITHUB_APP_*` or `QSL_REPO_SYNC_TOKEN`, and never use this App's private key for Binance recovery or authority maintenance.

## Secret inventory (`QuantPlatformKit` repository secrets)

| Secret | Status | Purpose |
|---|---|---|
| `QSL_GITHUB_APP_ID` | Active | `QSL QPK Pin Sync` (`qsl-qpk-pin-sync`) GitHub App ID |
| `QSL_GITHUB_APP_PRIVATE_KEY` | Active | Primary private key (preferred mint path) |
| `QSL_GITHUB_APP_PRIVATE_KEY_SECONDARY` | Active | Secondary private key (used only when primary fails or is unset) |
| `QSL_REPO_SYNC_TOKEN` | Retired / Removed | Historical PAT fallback; removed from `QuantPlatformKit` repo secrets and `QuantStrategyLab` org secrets |

GitHub App installation tokens mint short-lived credentials per workflow run and avoid personal PAT expiration. Because `actions/create-github-app-token` accepts one `private-key` input per step, dual-key failover uses `continue-on-error` on the primary mint step plus conditional secondary minting only when primary fails—never concatenating keys or crafting custom JWTs. If the primary key mints a token lacking permissions, failover does not trigger (both keys share the same App installation permissions), and repository/`QPK_PIN` checks fail closed.

## Release chain notes

QPK releases use a two-stage release-set workflow: generate a candidate QPK revision and verify its dependency closure, then promote the official release-set after downstream CI passes. Legacy `auto/qpk-pin-sync-*` and orphaned `auto/qpk-pin-update` branches are retired; delete any orphaned auto-branches without open PRs before re-triggering the release flow.

Cross-repository sync tokens only open downstream PRs; they never deploy services, trade, or alter broker permissions. Never commit personal long-lived tokens to files, workflow logs, or issues.

## Why repository secrets (not organization secrets)

`QuantPlatformKit` is a **public** repository. On GitHub Free organizations, org-level secrets do not inject reliably into public repositories (appearing silently empty in workflows). **Repository-level secrets** are the verified reliable mechanism.

## One-time setup (org admin)

### Organization GitHub App (`QSL QPK Pin Sync` / `qsl-qpk-pin-sync`)

1. Install the organization GitHub App `QSL QPK Pin Sync` (`qsl-qpk-pin-sync`) on `QuantStrategyLab`.
2. Grant `Contents: Read and write` and `Pull requests: Read and write` (plus required metadata read access) solely to the 15 target repositories.
3. Save the App ID in `QSL_GITHUB_APP_ID` and the primary private key PEM in `QSL_GITHUB_APP_PRIVATE_KEY`.
4. Generate a second private key in App settings and store it in `QSL_GITHUB_APP_PRIVATE_KEY_SECONDARY` for rotation and failover.
5. Trigger `qpk-github-app-health` and confirm `token_source: primary` (or expected secondary) and `result: pass`, then trigger `open-downstream-qpk-pin-prs.yml`, `update-qpk-pin.yml`, and `advance-staged-qpk-pin.yml` (with `disable_legacy_pat_fallback: true` when verifying App-only execution).

Store App private keys exclusively in GitHub Actions Secrets—never in repositories, workflow logs, issues, or local files.

### Rotation and failover

1. Generate a new private key in GitHub App settings and write it to the inactive Secret slot (typically `QSL_GITHUB_APP_PRIVATE_KEY_SECONDARY`).
2. Run `qpk-github-app-health` manually to verify minting succeeds (temporarily clearing/invalidating primary if testing secondary directly, or observing `token_source: secondary`).
3. Promote the new key into `QSL_GITHUB_APP_PRIVATE_KEY`, keeping the prior key in secondary or revoking it.
4. Re-run `qpk-github-app-health` and verify `open-downstream-qpk-pin-prs.yml`, `update-qpk-pin.yml` (`disable_legacy_pat_fallback: true`), and `advance-staged-qpk-pin.yml` (`disable_legacy_pat_fallback: true`).
5. Delete retired keys in GitHub App settings and keep plaintext PEMs out of logs, PRs, and local files.

On failure, secondary is attempted automatically; the health workflow and `disable_legacy_pat_fallback: true` runs fail closed without masking App status behind a PAT.

### Legacy PAT retirement (`QSL_REPO_SYNC_TOKEN`)

`QSL_REPO_SYNC_TOKEN` (formerly `qsl-github-repo-sync-annual`) has been retired and removed from both `QuantPlatformKit` repository secrets and `QuantStrategyLab` organization secrets. Do not re-provision `QSL_REPO_SYNC_TOKEN` or store `gh auth token`, classic PATs, or plaintext tokens in repository or organization secrets; use `QSL_GITHUB_APP_PRIVATE_KEY_SECONDARY` for App key rotation and failover.

## Verification

```bash
gh workflow run qpk-github-app-health.yml -R QuantStrategyLab/QuantPlatformKit
# Summary should list token_source, repositories_checked, and result: pass with zero plaintext secrets

gh workflow run open-downstream-qpk-pin-prs.yml -R QuantStrategyLab/QuantPlatformKit
# Logs should show "Mint short-lived QSL GitHub App token", "Token revoked", and clean sync

gh workflow run update-qpk-pin.yml -R QuantStrategyLab/QuantPlatformKit -f disable_legacy_pat_fallback=true -f verify_app_token_only=true
gh workflow run advance-staged-qpk-pin.yml -R QuantStrategyLab/QuantPlatformKit -f disable_legacy_pat_fallback=true -f verify_app_token_only=true
```

## Required repository permissions

`QSL QPK Pin Sync` (`qsl-qpk-pin-sync`) requires **Contents: Read and write** + **Pull requests: Read and write** across these 15 repositories (health checks use read-only installation tokens):

- `QuantPlatformKit`, `CnEquityStrategies`, `HkEquityStrategies`, `UsEquityStrategies`, `CryptoStrategies`
- `InteractiveBrokersPlatform`, `LongBridgePlatform`, `CharlesSchwabPlatform`, `FirstradePlatform`, `BinancePlatform`, `QmtPlatform`
- `CnEquitySnapshotPipelines`, `HkEquitySnapshotPipelines`, `UsEquitySnapshotPipelines`, `CryptoLivePoolPipelines`
