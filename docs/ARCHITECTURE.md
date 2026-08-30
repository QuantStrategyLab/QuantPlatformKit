# QuantStrategyLab Architecture

> Comprehensive architecture document for the QuantStrategyLab ecosystem.
> Covers layer responsibilities, data flow, design patterns, and naming conventions across all repositories.
> Maintained in QuantPlatformKit as the shared reference for all platform and strategy repos.

## 1. System Overview

QuantStrategyLab is a multi-broker, multi-market quantitative trading system. It separates concerns into four strict layers: **Infrastructure**, **Strategy**, **Snapshot**, and **Execution**. Each layer is a set of Python packages with well-defined boundaries, and dependencies flow downward only (Execution depends on Strategy depends on Infrastructure; Snapshot is cross-cutting).

```
┌───────────────────────────────────────────────────────────────────┐
│                      EXECUTION LAYER                              │
│                                                                   │
│  ┌────────────────────┐  ┌────────────────────┐                  │
│  │ CharlesSchwab      │  │ InteractiveBrokers  │  Cloud Run       │
│  │ Platform           │  │ Platform            │  (Flask +        │
│  │                   │  │                    │   Gunicorn)       │
│  │ Schwab API (REST) │  │ ib_insync (TWS/GW) │                  │
│  └────────┬───────────┘  └────────┬───────────┘                  │
│           │                       │                              │
│  ┌────────▼───────────┐  ┌────────▼───────────┐                  │
│  │ LongBridge         │  │ BinancePlatform    │  VPS / GH        │
│  │ Platform           │  │                    │  Actions Runner  │
│  │                    │  │ Binance WebSocket   │                  │
│  │ LongPort OpenAPI   │  │ + REST             │  ┌──────────┐   │
│  └────────┬───────────┘  └────────┬───────────┘  │Firstrade│   │
│           │                       │              │Platform │   │
│           │                       │              └──────────┘   │
├───────────┼───────────────────────┼──────────────────────────────┤
│           │                       │                              │
│  ┌────────▼───────────────────────▼───────────┐                  │
│  │         STRATEGY LAYER                     │                  │
│  │                                            │                  │
│  │  UsEquityStrategies     HkEquityStrategies │  pip wheel       │
│  │  CnEquityStrategies     CryptoStrategies   │  packages        │
│  │  QuantUsComboStrategies                    │  (pure logic)    │
│  │                                            │                  │
│  │  ┌─ Catalog & Manifest ──┐                 │                  │
│  │  │ StrategyContracts     │                 │                  │
│  │  │ RuntimeAdapters       │                 │                  │
│  │  └───────────────────────┘                 │                  │
│  └────────────────────────────────────────────┤                  │
│                                               │                  │
│  ┌────────────────────────────────────────────┐                  │
│  │         SNAPSHOT LAYER                     │                  │
│  │                                            │  GCS artifacts   │
│  │  UsEquitySnapshotPipelines                 │  (CSV/JSON)      │
│  │  HkEquitySnapshotPipelines                 │                  │
│  │  CryptoLivePoolPipelines                   │                  │
│  │                                            │                  │
│  │  feature_snapshots → rankings → manifests  │                  │
│  └────────────────────────────────────────────┘                  │
├───────────────────────────────────────────────────────────────────┤
│                    INFRASTRUCTURE LAYER                           │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  QuantPlatformKit                                         │    │
│  │                                                          │    │
│  │  ┌─────────────┐ ┌──────────────┐ ┌──────────────────┐  │    │
│  │  │ Broker      │ │ Cloud        │ │ Strategy         │  │    │
│  │  │ Adapters    │ │ Abstraction  │ │ Lifecycle        │  │    │
│  │  │ (Schwab/    │ │ (GCP/AWS/    │ │ (BT orchestration│  │    │
│  │  │  IBKR/LB/   │ │  Azure/Local │ │  drift detection │  │    │
│  │  │  Binance)   │ │  /Env)       │ │  performance mon │  │    │
│  │  └─────────────┘ └──────────────┘ │  AI review /      │  │    │
│  │  ┌─────────────┐ ┌──────────────┐ │  rollback mgmt)  │  │    │
│  │  │ Notifications│ │ Runtime      │ └──────────────────┘  │    │
│  │  │ (Email/SMS/ │ │ Contracts    │                        │    │
│  │  │  Push/TG/   │ │ & Strategy   │                        │    │
│  │  │  Webhook)   │ │ Loader       │                        │    │
│  │  └─────────────┘ └──────────────┘                        │    │
│  └──────────────────────────────────────────────────────────┘    │
│  ┌──────────────┐  ┌──────────────────┐                          │
│  │QuantRuntime  │  │QuantStrategy     │                          │
│  │Settings      │  │Plugins           │                          │
│  │(runtime      │  │(plugin defs      │                          │
│  │ targets)     │  │ & pipelines)     │                          │
│  └──────────────┘  └──────────────────┘                          │
└───────────────────────────────────────────────────────────────────┘
```

## 2. Layer Descriptions

### 2.1 Infrastructure Layer

**Owner:** QuantPlatformKit

**Purpose:** Shared runtime infrastructure that all other layers depend on. No broker credentials, no platform-specific runtime wiring, no strategy formulas.

**QuantPlatformKit** (`quant-platform-kit` pip package) provides:

| Subsystem | Module | Responsibility |
|---|---|---|
| Broker Adapters | `schwab/`, `ibkr/`, `longbridge/`, `binance/` | Broker-specific API wrappers: auth, execution, market data, portfolio snapshots |
| Cloud Abstraction | `cloud/` | Provider-agnostic interfaces for secrets, storage, document DB. Implementations: GCP, AWS, Azure, Local, Env. Switch via `QSL_CLOUD_PROVIDER` |
| Notifications | `notifications/` | Multi-channel notification pipeline: Email, SMS, Push, Telegram, Webhook. Shared envelope (`RenderedNotification`, `NotificationPublisher`) for consistent delivery |
| Strategy Lifecycle | `strategy_lifecycle/` | Backtest orchestration, drift detection, performance monitoring, AI review, rollback management, health scoring, return collection, audit logging |
| Runtime Contracts | `common/` | Strategy contracts, execution outcomes, runtime assembly, runtime reports, execution state, cash sweep, plugin artifact parsing |
| Strategy Plugins | `common/strategy_plugins.py` | Plugin signal parsing, compatibility checks, alert generation |
| Portfolio Ports | `common/ports.py` | Port interfaces for market data, portfolio snapshots, execution, notifications |

**QuantRuntimeSettings** provides the runtime target configuration consumed by all execution platforms. It is the source of truth for which strategy runs on which platform.

**QuantStrategyPlugins** defines plugin signal definitions and pipeline orchestration shared across platforms.

Cloud provider selection is done through environment variables:

```
QSL_CLOUD_PROVIDER=gcp       # Default: Google Cloud
QSL_CLOUD_PROVIDER=aws       # Amazon Web Services
QSL_CLOUD_PROVIDER=azure     # Microsoft Azure
QSL_CLOUD_PROVIDER=local     # Local filesystem (dev without cloud creds)
QSL_CLOUD_PROVIDER=env       # Environment variables only
```

### 2.2 Strategy Layer

**Owner:** UsEquityStrategies, HkEquityStrategies, CnEquityStrategies, CryptoStrategies, QuantUsComboStrategies, (QuantHkComboStrategies)

**Purpose:** Pure strategy logic and metadata. Each package is a reusable wheel published to PyPI (or installed via pip from GitHub SHA pins). They do NOT import broker SDKs, do NOT branch on platform identity, and do NOT hold credentials.

Each strategy package follows a common structure:

```
repo_root/
├── catalog.py              # StrategyCatalog: lists all profiles with metadata
├── strategies/             # Strategy implementations (evaluate(ctx) entrypoints)
│   ├── __init__.py
│   ├── strategy_a.py
│   └── strategy_b.py
├── manifests/              # Generated manifest JSON files
├── entrypoints/            # CLI entrypoints for local execution
├── runtime_adapters.py     # StrategyRuntimeAdapter implementations
├── research/               # Backtest scripts, research notebooks
├── __init__.py
├── pyproject.toml          # Package metadata, dependencies
└── README.md
```

Strategy profiles expose a common contract:

| Field | Type | Description |
|---|---|---|
| `name` | str | Profile name (snake_case) |
| `domain` | str | Market domain (`us_equity`, `hk_equity`, `crypto`, `quant_combo`) |
| `compatible_platforms` | list[str] | Allowed platform IDs |
| `status` | str | lifecycle stage, for example `research_backtest_only`, `shadow_candidate`, `live_candidate`, or `runtime_enabled` |
| `evaluate()` | function | The pure decision function: `(ctx: StrategyContext) -> StrategyDecision` |

Strategy packages and their coverage:

| Package | Domain | Profiles | Downstream Platforms |
|---|---|---|---|
| `us-equity-strategies` | US Equity | ETF rotation, growth/income, smart DCA, trend income (SOXL/SOXX, TECL/XLK, TQQQ) | Schwab, IBKR, LongBridge, Firstrade |
| `hk-equity-strategies` | HK Equity | Global ETF tactical rotation, low-vol dividend quality | IBKR, LongBridge |
| `cn-equity-strategies` | A-Share | ETF rotation, dividend-quality composite | QmtPlatform (planned) |
| `crypto-strategies` | Crypto | Live pool rotation, BTC DCA, trend rotation, equity combo | BinancePlatform |
| `quant-us-combo-strategies` | US Combo | Russell Top50 + IBIT (50/50), leveraged combo (TQQQ/SOXL/BOXX + SPY MA200) | Schwab, IBKR, LongBridge, Firstrade |

Catalog metadata is published through lifecycle-aware profile helpers which platforms call to discover available strategies. Status promotion gates (`research_backtest_only` -> `shadow_candidate` -> `live_candidate` -> `runtime_enabled`) require passing evidence checks (backtest performance, drawdown limits, slippage tolerance).

### 2.3 Snapshot Layer

**Owner:** UsEquitySnapshotPipelines, HkEquitySnapshotPipelines, CryptoLivePoolPipelines, (CnEquitySnapshotPipelines)

**Purpose:** Artifact-producing repositories that build feature snapshots, backtest summaries, rankings, and promotion evidence. They do NOT place trades and are NOT execution platforms.

Data flow:

```
Strategy specs (from strategy layer metadata)
  → Data ingestion (yfinance, market data APIs)
    → Feature computation (momentum, volatility, correlation)
      → Snapshot CSV/JSON artifacts
        → Written to GCS buckets
          → Consumed by execution platform runtimes
```

Pipeline outputs include:
- **Feature snapshots:** Per-security feature vectors used by strategy signal computation
- **Backtest summaries:** Historical performance metrics (CAGR, Sharpe, max drawdown, win rate)
- **Rankings:** Cross-sectional ranking for rotation strategies
- **Promotion evidence:** Gate validation artifacts for promoting strategies from research to live

### 2.4 Execution Layer

**Owner:** CharlesSchwabPlatform, InteractiveBrokersPlatform, LongBridgePlatform, BinancePlatform, FirstradePlatform

**Purpose:** Broker-facing execution services. Each platform repository connects a specific broker API to the shared strategy contracts. They are deployed as stateless HTTP services on Google Cloud Run (Flask + Gunicorn) or on VPS (BinancePlatform via GitHub Actions self-hosted runner).

#### Common Platform Structure

```
platform_repo/
├── main.py                    # Flask app, HTTP routes
├── strategy_registry.py       # PLATFORM_CAPABILITY_MATRIX, derived profile lists
├── runtime_config_support.py  # PlatformRuntimeSettings dataclass, env var loading
├── strategy_runtime.py        # Runtime orchestration (fetch data → evaluate → execute)
├── decision_mapper.py         # StrategyDecision → broker-native order payloads
├── runtime_config.json        # RUNTIME_TARGET_JSON or equivalent
├── scripts/                   # CI, validation, migration scripts
├── tests/
├── Dockerfile
├── requirements.txt           # Pinned SHAs for strategy packages
├── pyproject.toml
└── README.md
```

#### Route Contract

Every platform exposes these HTTP endpoints:

| Route | Purpose | Scheduling |
|---|---|---|
| `/run` | Live execution | 45 min before market close |
| `/dry-run` | Pre-check without orders | Morning pre-market |
| `/health` | Module import + config self-check | Continuous (Cloud Run health check) |
| `/probe` | Extended health check with account snapshot | Periodic (Schwab) |
| `/monitor-dispatch` | Cross-platform monitoring dispatch | Periodic (IBKR) |

#### Platform Capabilities

| Platform | Markets | Broker SDK | Deploy Target | Execution Modes |
|---|---|---|---|---|
| CharlesSchwabPlatform | US Equity | schwab-py (REST) | GCP Cloud Run | live, dry-run |
| InteractiveBrokersPlatform | US Equity, HK Equity | ib_insync (TWS/IBGW) | GCP Cloud Run | live, dry-run, paper |
| LongBridgePlatform | US Equity, HK Equity | longport (LongPort OpenAPI) | GCP Cloud Run (3 services) | live, dry-run, paper |
| BinancePlatform | Crypto | python-binance | GH Actions VPS | live, dry-run |
| FirstradePlatform | US Equity | firstrade (SDK) | GCP Cloud Run | live, dry-run |

## 3. Data Flow

### 3.1 Strategy Signal Flow (End-to-End)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Strategy Definition                                                     │
│                                                                          │
│  us_equity_strategies/catalog.py:                                         │
│    StrategyCatalog.profiles = {                                          │
│      "soxl_soxx_trend_income": {                                        │
│        "domain": "us_equity",                                            │
│        "compatible_platforms": ["schwab", "interactive_brokers", ...],   │
│        "status": "runtime_enabled"                                       │
│      }                                                                  │
│    }                                                                    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ pip install us-equity-strategies@<sha>
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Platform Registry (per platform repo)                                   │
│                                                                          │
│  strategy_registry.py:                                                   │
│    PLATFORM_CAPABILITY_MATRIX = {                                       │
│      "domains": ["us_equity"],                                          │
│      "inputs": ["market_data", "portfolio"],                            │
│      "broker_capabilities": ["limit_orders", "fractional_shares"]      │
│    }                                                                    │
│    ELIGIBLE_PROFILES = derive_enabled_profiles_for_platform(            │
│        PLATFORM_CAPABILITY_MATRIX, runtime_enabled_profiles             │
│    )                                                                    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ Config: RUNTIME_TARGET_JSON
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Snapshot Pipeline (if strategy requires upstream artifacts)            │
│                                                                          │
│  UsEquitySnapshotPipelines:                                              │
│    1. Fetch price data (yfinance / direct feed)                         │
│    2. Compute features (momentum, vol, correlation)                     │
│    3. Generate rankings & manifests                                     │
│    4. Publish to GCS: gs://<bucket>/snapshots/<date>/                   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ GCS artifact read at runtime
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Runtime Assembly (per execution cycle)                                  │
│                                                                          │
│  1. Cloud Scheduler fires: {cron} → POST /run                          │
│  2. Flask handler receives request                                       │
│  3. runtime_config_support loads env vars → PlatformRuntimeSettings     │
│  4. strategy_registry resolves profile from RUNTIME_TARGET_JSON         │
│  5. StrategyRuntime assembles StrategyContext:                          │
│     - MarketDataPort (broker SDK or cached)                             │
│     - PortfolioSnapshot (current positions, cash)                       │
│     - Plugin signals (if configured)                                    │
│     - Artifact snapshots (if strategy requires GCS data)               │
│  6. strategy.evaluate(ctx) → StrategyDecision                           │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ StrategyDecision
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Decision Mapping → Execution                                            │
│                                                                          │
│  decision_mapper.py:                                                     │
│    StrategyDecision {                                                    │
│      orders: [Order(symbol, side, qty, order_type)],                    │
│      blockers: [ExecutionBlocker(reason)],                              │
│      metadata: {...}                                                     │
│    }                                                                    │
│      → Broker-native order payload                                      │
│      → Submit via broker SDK                                             │
│      → Record execution outcome                                          │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Post-Execution                                                          │
│                                                                          │
│  1. Execution report persisted to GCS                                    │
│  2. Notification sent (Telegram primary)                                │
│  3. Execution state updated (dedup prevention)                          │
│  4. Plugin alerts dispatched (if signal thresholds breached)            │
│  5. Cloud Logging: structured logs                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Config Auto-Sync Flow

```
Deploy: RUNTIME_TARGET_JSON.strategy_profile = "soxl_soxx_trend_income"
                          │
                    [startup]
                          ▼
              config-sync layer runs:
              1. Read RUNTIME_TARGET_JSON.strategy_profile
              2. Sync to STRATEGY_PLUGIN_MOUNTS_JSON.*.strategy
              3. Sync to MONITOR_DISPATCH_TARGETS_JSON.*.strategy_profile
              4. Log: "[config-sync] auto-corrected plugin mount strategy
                 from 'old_value' to 'soxl_soxx_trend_income'"
                          │
                    [verified]
                          ▼
              Cloud Logging confirms sync
              → /dry-run confirms expected behavior
              → execution report contains correct strategy name
```

### 3.3 Notification Flow

```
Execution Stage (ORDERS_PLANNED, NO_ACTION, SUBMITTED, etc.)
  → RenderedNotification(detailed_text, compact_text) [shared envelope]
    → NotificationPublisher.log_message() [structured log]
    → NotificationPublisher.send_message() [channel dispatch]
      ┌─ Telegram (default primary channel) ────────────┐
      ├─ SMS (strategy_plugin_sms for urgent alerts)    │
      ├─ Email (strategy_plugin_email for daily reports) │
      ├─ Push (strategy_plugin_push for mobile)          │
      └─ Webhook (strategy_plugin_webhook for external)  ┘
```

## 4. Design Patterns

### 4.1 Strategy Registry & Capability Matrix

Each platform maintains a `PLATFORM_CAPABILITY_MATRIX` that declares its supported domains, input sources, and broker capabilities. Strategy packages declare `compatible_platforms` on each profile. The derivation logic (`derive_enabled_profiles_for_platform()`) computes the intersection at import time — no platform hardcodes strategy names.

```python
# platform/strategy_registry.py
PLATFORM_CAPABILITY_MATRIX = {
    "domains": ["us_equity", "quant_combo"],
    "inputs": ["market_data", "portfolio_snapshot"],
    "broker_capabilities": ["limit_orders", "fractional_shares"],
}

# Intersection: catalog.compatible_platforms ∩ capability_matrix
ELIGIBLE_STRATEGY_PROFILES = derive_enabled_profiles_for_platform(
    PLATFORM_ID, PLATFORM_CAPABILITY_MATRIX, ALL_RUNTIME_ENABLED_PROFILES
)
```

Exclusion lists handle strategies that are technically compatible but not yet approved for live trading:

```python
SCHWAB_EXCLUDED_LIVE_PROFILES = [
    "tecl_xlk_trend_income",          # research_backtest_only, not cleared for live
    "soxl_soxx_trend_income",         # awaiting promo gate signoff
]
```

### 4.2 Runtime Adapter Pattern

Strategy packages expose `evaluate(ctx)` as pure functions. Platform runtimes build the `StrategyContext` with platform-specific data sources. The adapter pattern decouples strategy logic from runtime concerns:

```
StrategyPackage                          PlatformRuntime
┌─────────────────┐                     ┌──────────────────────┐
│ evaluate(ctx)   │ ◄── calls ──────────│ StrategyRuntime      │
│   → Decision    │                     │                      │
│                 │                     │ build_ctx()          │
│ Manifest        │                     │   → MarketDataPort   │
│ Catalog         │                     │   → PortfolioSnapshot│
│ RuntimeAdapter  │                     │   → PluginSignals    │
└─────────────────┘                     │   → ArtifactSnapshots│
                                        │ evaluate(ctx)        │
                                        │ map_decision()       │
                                        │ execute()            │
                                        │ notify()             │
                                        └──────────────────────┘
```

### 4.3 Single Source of Truth (RUNTIME_TARGET_JSON)

Every platform service has exactly one canonical config entry point:

```json
{
  "platform_id": "schwab",
  "strategy_profile": "soxl_soxx_trend_income",
  "domain": "us_equity",
  "mode": "live",
  "market": "us_equity"
}
```

**Rules:**
- No duplicate `STRATEGY_PROFILE` env var (deprecated, removed)
- All downstream config values (plugin mounts, monitor targets) derive from `RUNTIME_TARGET_JSON.strategy_profile`
- Config auto-sync layer corrects misaligned references on startup
- Validation scripts (`check_required_env.py`, `validate_platform_consistency.py`) verify consistency before deploy

### 4.4 Config Auto-Sync

On startup, each platform runtime runs a config synchronization pass:

| Source | Target(s) | Auto-Correct |
|---|---|---|
| `RUNTIME_TARGET_JSON.strategy_profile` | Plugin mount strategy names | Yes |
| `RUNTIME_TARGET_JSON.strategy_profile` | Monitor dispatch target profiles | Yes |

The sync is idempotent and logs corrections. If the value was already correct, no action is taken.

### 4.5 Plugin System

Strategy plugins overlay external signals onto a strategy execution cycle. Each plugin has:

| Field | Description |
|---|---|
| `strategy` | Associated strategy profile (auto-synced) |
| `plugin` | Plugin name (e.g., `ai_sentiment`, `market_regime`) |
| `signal_path` | GCS path to the signal artifact |
| `enabled` | Boolean toggle |
| `expected_mode` | `shadow` (log-only) or `active` (affects decisions) |

Plugins are mounted via JSON env vars (`STRATEGY_PLUGIN_MOUNTS_JSON`) and parsed by shared helpers in `quant_platform_kit.common.strategy_plugins`. Alert messages are generated when plugin signals exceed thresholds and dispatched through the notification pipeline.

### 4.6 Cloud Provider Abstraction

`QuantPlatformKit.cloud` defines protocol interfaces for three cloud primitives:

| Interface | GCP | AWS | Azure | Local | Env |
|---|---|---|---|---|---|
| Secrets | Secret Manager | Secrets Manager | Key Vault | `.env` file | Env vars |
| Object Storage | GCS | S3 | Blob Storage | Local filesystem | Env override |
| Document DB | Firestore | DynamoDB | Cosmos DB | JSON file | Env override |

Selection is driven by `QSL_CLOUD_PROVIDER` env var. No platform code imports cloud SDKs directly — always through the abstraction layer. Lazy imports ensure SDKs are only loaded when the corresponding provider is active.

### 4.7 Execution Outcomes & Notification Envelope

Execution stages are shared constants from `quant_platform_kit.common.execution_outcomes`:

| Stage | Terminal | Meaning |
|---|---|---|
| `ORDERS_PLANNED` | No | A plan was built before execution |
| `DRY_RUN_COMPLETED` | No | Dry-run finished without live orders |
| `NO_ACTION` | No | Live cycle completed with no order needed |
| `SUBMITTED` | Yes | One or more orders were submitted |
| `EXECUTION_BLOCKED` | No | Retryable blocker prevented execution |
| `PARTIAL_SUBMITTED` | No | Some orders submitted, blocker remains |
| `FUNDING_BLOCKED` | No | Insufficient cash; retry only while the execution window remains open and no broker submission was made |
| `RECONCILED` | Yes | Submitted run reconciled |
| `COMPLETED` | Yes | Run marked complete |

Terminal stages prevent duplicate submission for the same account/profile/period.

Notifications are dispatched through a shared `NotificationPublisher` that wraps a consistent `RenderedNotification(detailed_text, compact_text)` envelope. Platform renderers handle broker-specific formatting; the delivery contract is shared.

### 4.8 Strategy Lifecycle Management

`QuantPlatformKit.strategy_lifecycle` provides production-grade tooling:

| Module | Purpose |
|---|---|
| `backtest_orchestrator` | Schedule and run backtests across parameter grids |
| `drift_detector` | Detect strategy performance drift vs. backtest expectations |
| `performance_monitor` | Real-time performance tracking (CAGR, Sharpe, drawdown) |
| `ai_reviewer` | LLM-based strategy code review and performance commentary |
| `rollback_manager` | Detect degradation and record no-order rollback proposals with an audit trail; platform-specific, owner-authorized rollback remains separate |
| `shadow_validator` | Validate shadow-mode execution outcomes against live results |
| `health_dashboard` | Aggregate health metrics across platforms |
| `audit_log` | Immutable audit log for strategy changes |

## 5. Naming Conventions

### 5.1 Repository Names

| Type | Convention | Examples |
|---|---|---|
| **Infrastructure** | PascalCase + no suffix | `QuantPlatformKit`, `QuantRuntimeSettings`, `QuantStrategyPlugins` |
| **Execution Platform** | `<BrokerName>Platform` | `CharlesSchwabPlatform`, `InteractiveBrokersPlatform`, `LongBridgePlatform`, `BinancePlatform`, `FirstradePlatform` |
| **Strategy Package** | `<Market>Strategies` | `UsEquityStrategies`, `HkEquityStrategies`, `CnEquityStrategies`, `CryptoStrategies` |
| **Combo Strategy** | `Quant<Market>ComboStrategies` | `QuantUsComboStrategies`, `QuantHkComboStrategies` |
| **Snapshot Pipeline** | `<Market>SnapshotPipelines` | `UsEquitySnapshotPipelines`, `HkEquitySnapshotPipelines` |
| **Crypto Pipeline** | `<Domain>LivePoolPipelines` | `CryptoLivePoolPipelines` |
| **Strategy Signals** | PascalCase | `MarketSignalSources` |
| **Market Data Pipeline** | `<Market>SnapshotPipelines` | `HkEquitySnapshotPipelines` |

### 5.2 Package Names (`pip install ...`)

| Type | Convention | Example |
|---|---|---|
| Shared infra | `quant-platform-kit` | `quant-platform-kit` |
| Strategy | `<domain>-strategies` | `us-equity-strategies`, `hk-equity-strategies` |
| Combo | `quant-<domain>-combo-strategies` | `quant-us-combo-strategies` |

### 5.3 Python Import Names

| Convention | Example |
|---|---|
| Lowercase + underscore | `import quant_platform_kit` |
| Strategy package same as pip name, underscore | `from us_equity_strategies import catalog` |

### 5.4 Platform Identifiers

Used in `RUNTIME_TARGET_JSON.platform_id`, capability matrices, and logs:

| Platform | Platform ID |
|---|---|
| CharlesSchwabPlatform | `schwab` |
| InteractiveBrokersPlatform | `interactive_brokers` |
| LongBridgePlatform | `longbridge` |
| BinancePlatform | `binance` |
| FirstradePlatform | `firstrade` |

### 5.5 Strategy Profile Names

| Convention | Example |
|---|---|
| Smallcase + underscore, from asset/strategy semantics | `soxl_soxx_trend_income`, `hk_global_etf_tactical_rotation`, `us_equity_combo_leveraged`, `crypto_btc_dca` |

### 5.6 Domain Names

| Domain | Usage |
|---|---|
| `us_equity` | US equity strategies & platforms |
| `hk_equity` | Hong Kong equity strategies & platforms |
| `cn_equity` | China A-share strategies (QMT) |
| `crypto` | Cryptocurrency strategies (Binance) |
| `quant_combo` | Cross-market combo strategies |

### 5.7 GCP Resource Names

| Resource | Convention | Example |
|---|---|---|
| Cloud Run service | `{platform}-{market}-{mode}` | `charles-schwab-quant-service` |
| Scheduler job | `{platform}-{strategy}-{type}` | `schwab-soxl-main` |
| Secret name | `{PLATFORM_ID}-{env}` | `schwab-prod` |

### 5.8 Environment Variables

| Variable | Purpose |
|---|---|
| `QSL_CLOUD_PROVIDER` | Cloud provider selector |
| `RUNTIME_TARGET_JSON` | Single source of truth for runtime config |
| `{PLATFORM}_STRATEGY_PLUGIN_MOUNTS_JSON` | Plugin mount config |
| `MONITOR_DISPATCH_TARGETS_JSON` | Cross-platform monitor targets |
| `PLATFORM_ID` | Platform identifier (deprecated, use `RUNTIME_TARGET_JSON.platform_id`) |
| `STRATEGY_PROFILE` | Deprecated; replaced by `RUNTIME_TARGET_JSON.strategy_profile` |

## 6. Dependency Graph

```
QuantStrategyPlugins ────┐
                         ├──► QuantPlatformKit ◄────────────────────────┐
MarketSignalSources ─────┘                                              │
                                                                        │
                         ┌──────────────────────────────────────────────┤
                         │                                              │
                    ┌────▼────┐   ┌──────────────┐   ┌───────────────┐ │
                    │UsEquity │   │HkEquity      │   │CnEquity       │ │
                    │Strategies│  │Strategies    │   │Strategies     │ │
                    └────┬────┘   └──────┬───────┘   └───────┬───────┘ │
                         │               │                    │         │
                    ┌────▼───────────────▼────────────────────▼───────┐ │
                    │              QuantUsComboStrategies              │ │
                    └────┬────────────────────────────────────────────┘ │
                         │                                              │
              ┌──────────┼──────────┬─────────────┬──────────┐          │
              ▼          ▼          ▼             ▼          ▼          │
     CharlesSchwab  Interactive  LongBridge   Binance    Firstrade     │
     Platform       Brokers       Platform    Platform   Platform      │
                     Platform                                          │
              │          │          │             │          │          │
              └──────────┴──────────┴─────────────┴──────────┘          │
                                │                                       │
                         ┌──────▼───────┐                               │
                         │ QuantRuntime │───────────────────────────────┘
                         │ Settings     │  (defines which strategy
                         └──────────────┘   runs on which platform)
```

Arrows point from consumer to dependency. Each platform depends on QuantPlatformKit for shared contracts, and on one or more strategy packages for profile definitions.

## 7. Cross-Cutting Concerns

### 7.1 Dependency Pinning Strategy

Strategy packages and QuantPlatformKit are pinned via commit SHA in platform `requirements.txt` files:

```
# CharlesSchwabPlatform/requirements.txt
git+https://github.com/QuantStrategyLab/QuantPlatformKit@dfdbef6
git+https://github.com/QuantStrategyLab/UsEquityStrategies@0463457a
git+https://github.com/QuantStrategyLab/QuantUsComboStrategies@c9e290c
```

**Important:** All downstream platforms must pin to the same SHA for consistency. When upgrading a shared package, update all platform repos in sequence (shared libs first, platform repos after).

### 7.2 CI/CD Gates

Every change follows the mandated PR workflow:

1. Create feature branch from `main`
2. Commit with format `type(scope): description`
3. Push and open PR
4. CI must pass (lint, type check, tests)
5. Merge PR, then delete remote + local branches

### 7.3 Scheduler Timezone Rules

| Market | Calendar | Timezone | Example Cron |
|---|---|---|---|
| US Equity | NASDAQ | `America/New_York` | `45 15 * * *` (3:45 PM ET) |
| HK Equity | XHKG | `Asia/Hong_Kong` | `45 15 * * *` (3:45 PM HKT) |

**Rule:** Scheduler timezone must match the market timezone, not the Cloud Run deployment region.

Execution frequency:

| Type | Cron | Notes |
|---|---|---|
| Daily | `45 15 * * *` | Every trading day, 15 min before close |
| Monthly DCA/Snapshot | `45 15 1-7 * *` | 7-day retry window for data readiness |
| Month-end | `45 15 28-31 * *` | Last days of month |

### 7.4 Cloud Run Service Architecture

Each platform service is a single-process Flask app behind Gunicorn WSGI:

- Cloud Scheduler fires HTTP POST to the service endpoint at market close
- Service is stateless — all state persisted to GCS / Firestore
- Secrets resolved at startup from Secret Manager (or local `.env`)
- Config auto-sync runs at process start
- `/health` endpoint enables Cloud Run's built-in health checking
- No long-running background threads (no daemon mode)

### 7.5 Repo Boundary Rules (Who Owns What)

| Concern | Owner |
|---|---|
| Broker API wrappers, auth, connection mgmt | QuantPlatformKit (shared) OR platform repo (if unique) |
| Cloud secrets, storage, DB abstraction | QuantPlatformKit.cloud |
| Strategy contracts (StrategyContext, StrategyDecision) | QuantPlatformKit.common |
| Execution outcomes, notification envelope | QuantPlatformKit.common |
| Strategy profile metadata, evaluate() logic | Strategy package |
| Runtime assembly, config loading | Platform repo |
| Decision → broker-native mappers | Platform repo |
| Notification rendering (broker-specific layout) | Platform repo |
| Execution reports, run state persistence | Platform repo |
| Plugin signal parsing | QuantPlatformKit.common |
| Backtest orchestration, drift detection | QuantPlatformKit.strategy_lifecycle |

**Practical test:** If code references more than one broker SDK, it belongs in QuantPlatformKit. If it references a specific broker, it belongs in that platform repo. If it contains no broker imports and no platform-specific wiring, it belongs in a strategy package.

## 8. Repository Summary

| Repository | Layer | Description | Status |
|---|---|---|---|
| **QuantPlatformKit** | Infrastructure | Shared runtime infrastructure, broker adapters, cloud abstraction, notifications, strategy lifecycle | Active |
| **QuantRuntimeSettings** | Infrastructure | Runtime target configuration (single source of truth for which strategy runs where) | Active |
| **QuantStrategyPlugins** | Infrastructure | Plugin signal definitions and pipeline orchestration | Active |
| **UsEquityStrategies** | Strategy | US equity strategy catalog, implementations, runtime adapters | Active |
| **HkEquityStrategies** | Strategy | HK equity strategy catalog and runtime adapters | Active |
| **CnEquityStrategies** | Strategy | A-share strategy catalog, adapters (targeting QMT) | Active |
| **CryptoStrategies** | Strategy | Crypto strategy catalog (rotation, DCA, trend) | Active |
| **QuantUsComboStrategies** | Strategy | US combo strategies (Russell+IBIT, leveraged) | Active |
| **UsEquitySnapshotPipelines** | Snapshot | US equity feature snapshots, rankings, promotion evidence | Active |
| **HkEquitySnapshotPipelines** | Snapshot | HK equity feature snapshots and manifests | Active |
| **CryptoLivePoolPipelines** | Snapshot | Crypto live pool artifacts for rotation strategies | Active |
| **CharlesSchwabPlatform** | Execution | Schwab execution via schwab-py REST API on Cloud Run | Active |
| **InteractiveBrokersPlatform** | Execution | IBKR execution via ib_insync on Cloud Run | Active |
| **LongBridgePlatform** | Execution | LongBridge via LongPort OpenAPI on Cloud Run | Active |
| **BinancePlatform** | Execution | Binance execution on GH Actions VPS | Active |
| **FirstradePlatform** | Execution | Firstrade execution (emerging) | Active |

---

*This document is maintained in QuantPlatformKit/docs/ARCHITECTURE.md and should be updated when new repositories are added or architectural patterns evolve. Version: 1.0 (2026-06-30).*
