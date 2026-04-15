# Platform Runtime Inventory

_Verified snapshot: 2026-04-14_

This document records the **public runtime wiring inventory** across platform repositories and deployment projects. It is meant to answer one question quickly:

> which repository, project, service, scheduler, runtime identity, and secret set is wired for each platform?

This is a **wiring runbook**, not a target-state design doc. For target architecture and migration rules, see [`deployment_model.md`](./deployment_model.md).

For the platform / strategy-domain / configurable-profile matrix, see [`platform_strategy_matrix.md`](./platform_strategy_matrix.md).

## Shared rules

- `QuantPlatformKit` remains a shared dependency and is **not deployed** by itself.
- GitHub Variables remain the control plane for:
  - service names
  - regions
  - strategy selectors such as `STRATEGY_PROFILE`
  - secret selector variables such as `*_SECRET_NAME`
- Secret Manager is the runtime source of truth for sensitive values that Cloud Run services actually consume.
- The US equity Cloud Run env-sync workflows use GitHub OIDC + Workload Identity Federation. `GCP_SA_KEY` is not required for those workflows.
- GitHub Secrets can remain as temporary runtime fallbacks where migration is not fully finished.

## Runtime inventory

| Platform | Repo | Strategy domain | Strategy selector | Runtime model | Project / backend | Runtime unit |
|---|---|---:|---|---|---|---|
***REMOVED***
***REMOVED***
***REMOVED***
| Binance | `QuantStrategyLab/BinancePlatform` | `crypto` | `crypto_leader_rotation` | Oracle Cloud + self-hosted runner | `binancequant` only for Firestore / GCP credentials | GitHub Actions `workflow_dispatch` + self-hosted runner |

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
- **Runtime revision**
  - `interactive-brokers-quant-service-00072-2hn`
- **Scheduler**
  - `interactive-brokers-quant-service-scheduler`
  - region: `us-central1`
- **Core runtime selectors**
  - `STRATEGY_PROFILE=<runtime_enabled us_equity profile>`
  - `ACCOUNT_GROUP=<account group selector>`
  - `IB_ACCOUNT_GROUP_CONFIG_SECRET_NAME=<Secret Manager secret name>`
- **Runtime secrets**
  - `ibkr-account-groups`
  - `interactive-brokers-telegram-token`
- **Runtime notes**
  - Transitional envs `IB_GATEWAY_ZONE` and `IB_GATEWAY_IP_MODE` have already been removed from the service because the selected account-group payload now carries those values.

### Charles Schwab

- **Repository**
  - `QuantStrategyLab/CharlesSchwabPlatform`
- **Cloud Run project**
  - `charlesschwabquant`
- **Service**
  - `charles-schwab-quant-service`
- **Runtime service account**
  - `schwab-platform-runtime@charlesschwabquant.iam.gserviceaccount.com`
- **Runtime revision**
  - `charles-schwab-quant-service-00043-jvd`
- **Scheduler**
  - `charles-schwab-quant-service-scheduler`
  - region: `us-central1`
- **Core runtime selectors**
  - `STRATEGY_PROFILE=<runtime_enabled us_equity profile>`
- **Runtime secrets**
  - `schwab_token`
  - `charles-schwab-api-key`
  - `charles-schwab-app-secret`
  - `charles-schwab-telegram-token`
- **Runtime notes**
  - Runtime-sensitive envs have already been moved off plain Cloud Run env vars and into Secret Manager refs.
  - The token refresher lives outside this repo:
    - `QuantStrategyLab/SchwabTokenAutoRefresher`

### LongBridge

- **Repository**
  - `QuantStrategyLab/LongBridgePlatform`
- **Cloud Run project**
  - `longbridgequant`
- **Services**
  - HK: `longbridge-quant-hk-service`
  - SG: `longbridge-quant-sg-service`
- **Runtime service account**
  - `longbridge-platform-runtime@longbridgequant.iam.gserviceaccount.com`
- **Runtime revisions**
  - HK: `longbridge-quant-hk-service-00060-xgm`
  - SG: `longbridge-quant-sg-service-00055-pch`
- **Schedulers**
  - `longbridge-quant-hk-service-scheduler` in `asia-east2`
  - `longbridge-quant-sg-service-scheduler` in `asia-southeast1`
- **Core runtime selectors**
  - `STRATEGY_PROFILE=<runtime_enabled us_equity profile> on HK; STRATEGY_PROFILE=<runtime_enabled us_equity profile> on SG`
  - `ACCOUNT_REGION=HK|SG`
  - `LONGPORT_SECRET_NAME=<region token secret>`
- **Runtime secrets**
  - Secret Manager refs:
    - `longbridge-telegram-token`
    - `longport-app-key-hk`
    - `longport-app-key-sg`
    - `longport-app-secret-hk`
    - `longport-app-secret-sg`
  - region token secrets:
    - `longport_token_hk`
    - `longport_token_sg`
- **Runtime notes**
  - HK and SG keep two independent Cloud Run services, two triggers, and two GitHub Environments.
  - App key / secret are region-specific Secret Manager refs; Telegram token is shared inside the LongBridge project.
  - `SERVICE_NAME` is now aligned to the full runtime-facing names above, instead of using the older short `longbridge-quant-hk` / `longbridge-quant-sg` prefixes.

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

## Recommended next steps after this inventory

1. keep this file current whenever a runtime service, secret name, or runtime service account changes
2. keep repository names, service names, scheduler names, and docs aligned whenever one side changes
3. only after naming and runtime config are stable, start the real strategy-implementation split by domain
