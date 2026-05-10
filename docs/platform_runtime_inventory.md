# Platform Runtime Inventory

_Verified snapshot: 2026-04-18_

This document records the public runtime wiring inventory across platform repositories and deployment projects. It is meant to answer one question quickly:

> which repository, project, service, scheduler, runtime identity, selector, and secret set is wired for each platform?

This is a wiring runbook, not a record of any account's deployed strategy. It intentionally does **not** record mutable deployment state or account-specific allocation choices.

For the platform / strategy-domain / configurable-profile matrix, see [`platform_strategy_matrix.md`](./platform_strategy_matrix.md).

## Shared rules

- `QuantPlatformKit` remains a shared dependency and is **not deployed** by itself.
- GitHub Variables remain the control plane for:
  - service names
  - regions
  - structured runtime selectors such as `RUNTIME_TARGET_JSON`
  - compatibility strategy selectors such as `STRATEGY_PROFILE`
  - secret selector variables such as `*_SECRET_NAME`
- Secret Manager is the runtime source of truth for sensitive values that Cloud Run services actually consume.
- The US equity Cloud Run env-sync workflows use GitHub OIDC + Workload Identity Federation. `GCP_SA_KEY` is not required for those workflows.
- GitHub Secrets can remain as temporary runtime fallbacks where migration is not fully finished.

## Runtime inventory

| Platform | Repo | Strategy domain | Runtime identity | Strategy selector | Runtime model | Project / backend | Runtime unit |
|---|---|---:|---|---|---|---|---|
| IBKR | `QuantStrategyLab/InteractiveBrokersPlatform` | `us_equity` | `RUNTIME_TARGET_JSON` + `ACCOUNT_GROUP` | `STRATEGY_PROFILE=<runtime_enabled us_equity profile>` | Cloud Run | configurable |
| Schwab | `QuantStrategyLab/CharlesSchwabPlatform` | `us_equity` | `RUNTIME_TARGET_JSON` | `STRATEGY_PROFILE=<runtime_enabled us_equity profile>` | Cloud Run | `charlesschwabquant` | `charles-schwab-quant-service` |
| LongBridge | `QuantStrategyLab/LongBridgePlatform` | `us_equity` | `RUNTIME_TARGET_JSON` + `ACCOUNT_REGION` | `STRATEGY_PROFILE=<runtime_enabled us_equity profile>` | Cloud Run | configurable |
| Binance | `QuantStrategyLab/BinancePlatform` | `crypto` | `RUNTIME_TARGET_JSON` (workflow-local) | `STRATEGY_PROFILE=crypto_leader_rotation` | Oracle Cloud + self-hosted runner | `binancequant` only for Firestore / GCP credentials | GitHub Actions `workflow_dispatch` + self-hosted runner |

## Platform details

### IBKR

- **Repository**
  - `QuantStrategyLab/InteractiveBrokersPlatform`
- **Cloud Run project**
  - `interactivebrokersquant`
- **Service**
  - `interactive-brokers-quant-service`
- **Runtime service account**
  - `ibkr-platform-runtime@interactivebrokersquant.iam.gserviceaccount.com`
- **Scheduler**
  - `interactive-brokers-quant-service-scheduler`
  - region: `us-central1`
- **Core runtime selectors**
  - `STRATEGY_PROFILE=<runtime_enabled us_equity profile>`
  - `ACCOUNT_GROUP=<account group selector>`
  - `IB_ACCOUNT_GROUP_CONFIG_SECRET_NAME=<Secret Manager secret name>`
- **Runtime secrets**
  - account-group payload secret selected by `IB_ACCOUNT_GROUP_CONFIG_SECRET_NAME`
  - runtime Telegram token secret
- **Runtime notes**
  - `ACCOUNT_GROUP` decides which broker/account payload the runtime loads.
  - Gateway zone and IP-mode settings should live in the selected account-group payload when the migration is complete.

### Charles Schwab

- **Repository**
  - `QuantStrategyLab/CharlesSchwabPlatform`
- **Cloud Run project**
  - `charlesschwabquant`
- **Service**
  - `charles-schwab-quant-service`
- **Runtime service account**
  - `schwab-platform-runtime@charlesschwabquant.iam.gserviceaccount.com`
- **Scheduler**
  - `charles-schwab-quant-service-scheduler`
  - region: `us-central1`
- **Core runtime selectors**
  - `STRATEGY_PROFILE=<runtime_enabled us_equity profile>`
  - optional strategy-specific envs such as `DUAL_DRIVE_UNLEVERED_SYMBOL`
- **Runtime secrets**
  - Schwab token payload secret
  - Schwab API key / app secret refs
  - runtime Telegram token secret
- **Runtime notes**
  - Runtime-sensitive envs should use Secret Manager refs, not plain Cloud Run env values.
  - Strategy plugins are sidecars: `shadow` logs and notifies only; `paper`, `advisory`, and `live` semantics are governed by the plugin execution mode contract.
  - The token refresher lives outside this repo:
    - `QuantStrategyLab/SchwabTokenAutoRefresher`

### LongBridge

- **Repository**
  - `QuantStrategyLab/LongBridgePlatform`
- **Cloud Run project**
  - `longbridgequant`
- **Services**
  - PAPER: `longbridge-quant-paper-service`
  - HK: reserved / not yet wired
  - SG: `longbridge-quant-sg-service`
- **Runtime service account**
  - `longbridge-platform-runtime@longbridgequant.iam.gserviceaccount.com`
- **Schedulers**
  - `longbridge-quant-paper-service-scheduler` in `asia-east2`
  - HK: reserved / not yet wired
  - `longbridge-quant-sg-service-scheduler` in `asia-southeast1`
- **Core runtime selectors**
  - `STRATEGY_PROFILE=<runtime_enabled us_equity profile>` per account service
  - `ACCOUNT_REGION=PAPER|HK|SG`
  - `LONGPORT_SECRET_NAME=<account token secret>`
- **Runtime secrets**
  - Secret Manager refs for LongPort app key / app secret
  - account token secrets selected by `LONGPORT_SECRET_NAME`
  - runtime Telegram token secret
- **Runtime notes**
  - PAPER and SG are live today; HK keeps the same deployment pattern when it is added. Each account identity gets its own Cloud Run service, trigger, and GitHub Environment.
  - Snapshot-backed profiles require feature snapshot path / manifest envs; direct-runtime profiles do not.
  - App key / secret are account-specific Secret Manager refs; Telegram token is shared inside the LongBridge project.
  - `SERVICE_NAME` should use the full runtime-facing service names above, not older short prefixes.

### Binance

- **Repository**
  - `QuantStrategyLab/BinancePlatform`
- **Primary runtime model**
  - Oracle Cloud
  - self-hosted GitHub Actions runner
  - `workflow_dispatch`
- **GCP project**
  - `binancequant`
- **What GCP is used for**
  - Firestore
  - GCP service-account credentials consumed by the workflow / runtime
- **Runtime selector**
  - `STRATEGY_PROFILE=crypto_leader_rotation`
- **Known Firestore backend**
  - database: `(default)`
  - mode: `FIRESTORE_NATIVE`
  - location: `nam5`
- **Runtime notes**
  - Binance is intentionally **not** modeled like the Cloud Run platforms.
  - Any future cleanup here should keep Oracle runtime concerns separate from GCP backend concerns.

## GitHub responsibility split

### Keep in GitHub Variables

- `CLOUD_RUN_REGION`
- `CLOUD_RUN_SERVICE`
- `STRATEGY_PROFILE`
- `ACCOUNT_GROUP`
- `ACCOUNT_REGION`
- `LONGPORT_SECRET_NAME`
- `*_SECRET_NAME`
- shared low-risk settings such as:
  - `GLOBAL_TELEGRAM_CHAT_ID`
  - `NOTIFY_LANG`

### Keep in GitHub Secrets

- temporary fallback values if a runtime migration is still in progress

### Keep in Secret Manager

- broker API keys / app secrets
- runtime Telegram tokens
- token refresh payloads
- account-group payloads

## What is still intentionally not finished

- Scheduler OIDC identity is still tied to the default compute service account in the Cloud Run projects.
- Real cross-platform strategy implementation sharing has **not** started yet. Only the shared strategy contract and platform-compatibility skeleton are in place.
