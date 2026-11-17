# QPK Downstream Pin Automation Token Configuration

[简体中文](qpk-repo-sync-auth.zh-CN.md)

The `open-downstream-qpk-pin-prs` workflow uses a GitHub App installation token by default to push cross-repository branches and open PRs; `QSL_REPO_SYNC_TOKEN` serves only as a migration and failover fallback.

Read-only self-checks run via the `qpk-github-app-health` workflow (scheduled and manual): it mints a short-lived token using the primary private key first, falls back to the secondary key only if primary minting fails, and verifies repository access and `QPK_PIN` readback, failing closed without exposing secret, token, or private key material in summaries.

## Naming conventions

- GitHub fine-grained PAT display names follow `qsl-<purpose>-<rotation-cycle>`, e.g., `qsl-github-repo-sync-annual`.
- GitHub Actions secret names use uppercase snake case. Keep `QSL_REPO_SYNC_TOKEN` unchanged as the existing workflow contract name.
- Future token migrations follow the same pattern (e.g., `qsl-binance-authority-maintenance-annual`) after verifying actual consumers and end-to-end checks.

**Strict boundary: Binance authority PATs (and any broker/trading secrets) are completely separate from this App and repo-sync credentials.** Never place Binance authority tokens into `QSL_GITHUB_APP_*` or `QSL_REPO_SYNC_TOKEN`, and never use this App's private key for Binance recovery or authority maintenance.

## Secret inventory (`QuantPlatformKit` repository secrets)

| Secret | Purpose |
|---|---|
| `QSL_GITHUB_APP_ID` | GitHub App ID |
| `QSL_GITHUB_APP_PRIVATE_KEY` | Primary private key (preferred mint path) |
| `QSL_GITHUB_APP_PRIVATE_KEY_SECONDARY` | Secondary private key (used only when primary fails or is unset) |
| `QSL_REPO_SYNC_TOKEN` | Migration PAT fallback; revoke once the App path is stable |

GitHub App installation tokens mint short-lived credentials per workflow run and avoid personal PAT expiration. Because `actions/create-github-app-token` accepts one `private-key` input per step, dual-key failover uses `continue-on-error` on the primary mint step plus conditional secondary minting only when primary fails—never concatenating keys or crafting custom JWTs. If the primary key mints a token lacking permissions, failover does not trigger (both keys share the same App installation permissions), and repository/`QPK_PIN` checks fail closed.

## Release chain notes

QPK releases use a two-stage release-set workflow: generate a candidate QPK revision and verify its dependency closure, then promote the official release-set after downstream CI passes. Legacy `auto/qpk-pin-sync-*` and orphaned `auto/qpk-pin-update` branches are retired; delete any orphaned auto-branches without open PRs before re-triggering the release flow.

Cross-repository sync tokens only open downstream PRs; they never deploy services, trade, or alter broker permissions. Scope fallback PATs strictly to target repositories and never commit personal long-lived tokens to files, workflow logs, or issues.

## Why repository secrets (not organization secrets)

`QuantPlatformKit` is a **public** repository. On GitHub Free organizations, org-level secrets do not inject reliably into public repositories (appearing silently empty in workflows). **Repository-level secrets** are the verified reliable mechanism.

## One-time setup (org admin)

### Organization GitHub App

1. Install the organization App `QSL QPK Pin Sync 20260920` (App ID `5004823`) on `QuantStrategyLab`.
2. Grant `Contents: Read and write` and `Pull requests: Read and write` (plus required metadata read access) solely to the 15 target repositories.
3. Save the App ID in `QSL_GITHUB_APP_ID` and the primary private key PEM in `QSL_GITHUB_APP_PRIVATE_KEY`.
4. Generate a second private key in App settings and store it in `QSL_GITHUB_APP_PRIVATE_KEY_SECONDARY` for rotation and failover.
5. Trigger `qpk-github-app-health` and confirm `token_source: primary` (or expected secondary) and `result: pass`, then trigger `open-downstream-qpk-pin-prs` and confirm App token sync before revoking any legacy `qsl-github-repo-sync-annual` PAT (verified in workflow run `<verified-health-run-id>`; Binance PATs remain untouched).

Store App private keys exclusively in GitHub Actions Secrets—never in repositories, workflow logs, issues, or local files.

### Rotation and failover

1. Generate a new private key in GitHub App settings and write it to the inactive Secret slot (typically `QSL_GITHUB_APP_PRIVATE_KEY_SECONDARY`).
2. Run `qpk-github-app-health` manually to verify minting succeeds (temporarily clearing/invalidating primary if testing secondary directly, or observing `token_source: secondary`).
3. Promote the new key into `QSL_GITHUB_APP_PRIVATE_KEY`, keeping the prior key in secondary or revoking it.
4. Re-run health and an `open-downstream-qpk-pin-prs` smoke check to confirm no dependency on `QSL_REPO_SYNC_TOKEN`.
5. Delete retired keys in GitHub App settings and keep plaintext PEMs out of logs, PRs, and local files.

On failure, secondary is attempted automatically; if both fail, pin sync falls back to `QSL_REPO_SYNC_TOKEN` during migration while the health workflow fails closed without masking App status behind a PAT.

### Fine-grained PAT (migration fallback)

1. Open the token creation page as an org admin with naming `qsl-github-repo-sync-annual` and the maximum org-allowed expiration:

   https://github.com/settings/personal-access-tokens/new

2. Set resource owner to `QuantStrategyLab` and restrict Repository access strictly to these 15 repositories:

   - `QuantPlatformKit` and 4 strategy repos: `CnEquityStrategies`, `HkEquityStrategies`, `UsEquityStrategies`, `CryptoStrategies`
   - 6 execution repos: `InteractiveBrokersPlatform`, `LongBridgePlatform`, `CharlesSchwabPlatform`, `FirstradePlatform`, `BinancePlatform`, `QmtPlatform`
   - 4 data/pool pipelines: `CnEquitySnapshotPipelines`, `HkEquitySnapshotPipelines`, `UsEquitySnapshotPipelines`, `CryptoLivePoolPipelines`

3. Grant only `Contents: Read and write`, `Pull requests: Read and write`, and mandatory `Metadata: Read-only`.
4. Store in repository secret:

   ```bash
   gh secret set QSL_REPO_SYNC_TOKEN --repo QuantStrategyLab/QuantPlatformKit
   ```

Never store `gh auth token`, classic PATs, or plaintext tokens in production secrets. Restore `QSL_REPO_SYNC_TOKEN` only if App secrets or installation fail, and revoke it once the App recovers.

## Verification

```bash
gh workflow run qpk-github-app-health.yml -R QuantStrategyLab/QuantPlatformKit
# Summary should list token_source, repositories_checked, and result: pass with zero plaintext secrets

gh workflow run open-downstream-qpk-pin-prs.yml -R QuantStrategyLab/QuantPlatformKit
# Logs should show "Mint short-lived QSL GitHub App token", "Token revoked", and clean sync
# When App path succeeds, repos show no changes needed; QSL_REPO_SYNC_TOKEN applies only during fallback
```

## Required repository permissions

Both App and fallback PAT require **Contents: Read and write** + **Pull requests: Read and write** across these 15 repositories (health checks use read-only installation tokens):

- `QuantPlatformKit`, `CnEquityStrategies`, `HkEquityStrategies`, `UsEquityStrategies`, `CryptoStrategies`
- `InteractiveBrokersPlatform`, `LongBridgePlatform`, `CharlesSchwabPlatform`, `FirstradePlatform`, `BinancePlatform`, `QmtPlatform`
- `CnEquitySnapshotPipelines`, `HkEquitySnapshotPipelines`, `UsEquitySnapshotPipelines`, `CryptoLivePoolPipelines`
