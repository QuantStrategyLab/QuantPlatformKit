# QuantStrategyLab Developer Guide

## Overview

QuantStrategyLab is a multi-market quantitative trading platform spanning 28 repositories. This guide helps new developers understand the system and start contributing.

## Repository Map

### Layer 1: Shared Foundation
| Repo | Purpose |
|------|---------|
| **QuantPlatformKit** | Core shared library: domain models, broker adapters, cloud abstraction, notifications, risk, backtest, data versioning |
| **QuantRuntimeSettings** | Runtime configuration center: JSON Schema, strategy switch console (JS/Cloudflare Workers) |

### Layer 2: Strategy Packages
| Repo | Market | Strategies |
|------|--------|-----------|
| **UsEquityStrategies** | US Equity | ETF rotation, Smart DCA, leader rotation, leveraged combos |
| **HkEquityStrategies** | HK Equity | Global ETF rotation, dividend quality, combo |
| **CnEquityStrategies** | CN A-shares | Industry ETF rotation, dividend quality, combo |
| **CryptoStrategies** | Crypto | BTC DCA, trend rotation, live pool rotation, combo |

### Layer 3: Data Pipelines
| Repo | Produces |
|------|----------|
| **UsEquitySnapshotPipelines** | Feature snapshots, rankings, backtest summaries for US equity strategies |
| **HkEquitySnapshotPipelines** | Factor snapshots, live-enablement evidence for HK strategies |
| **CnEquitySnapshotPipelines** | A-share factor snapshots via AkShare |
| **CryptoLivePoolPipelines** | Monthly live pool selection with ML ranking |
| **MarketSignalSources** | BTC cycle indicators, daily technicals, US equity context |
| **ResearchSignalContextPipelines** | Research-grade market context artifacts |

### Layer 4: Execution Platforms
| Repo | Broker | Deployment |
|------|--------|-----------|
| **InteractiveBrokersPlatform** | IBKR | Cloud Run (Flask) |
| **LongBridgePlatform** | LongBridge | Cloud Run (Flask) |
| **CharlesSchwabPlatform** | Schwab | Cloud Run (Flask) |
| **FirstradePlatform** | Firstrade | Cloud Run (Flask) |
| **BinancePlatform** | Binance | VPS (CLI) |
| **QmtPlatform** | QMT (paper) | Cloud Run (Flask) |

### Layer 5: Operations & Research
| Repo | Purpose |
|------|---------|
| **IBKRGatewayManager** | IBKR gateway VM lifecycle (Docker + TOTP) |
| **SchwabTokenAutoRefresher** | Schwab OAuth token refresh (Playwright) |
| **CodexAuditBridge** | AI audit gateway (Claude/GPT/Codex) |
| **QuantStrategyPlugins** | Sidecar risk plugins (regime, crisis, macro) |
| **QuantAdvisorResearch** | Advisory research publishing |
| **PoliticalEventTrackingResearch** | Political event RSS tracking |

## Development Workflow

1. **Create feature branch**: `git checkout -b feat/description`
2. **Make changes**: Follow existing code patterns
3. **Run checks**: `ruff check . && pytest tests/ -q`
4. **Commit**: `type(scope): description` format
5. **Push and create PR**: CI must pass before merge
6. **Merge**: PR merged with `admin` flag, branch deleted

## Key Patterns

### Strategy Interface
All strategies expose:
```python
PROFILE_NAME: str
build_target_weights(...) → (weights_dict, ranked_frame, metadata)
compute_signals(...) → (weights, signal_desc, is_emergency, status_desc, diagnostics)
extract_managed_symbols(...) → tuple[str, ...]
```

### Catalog Pattern
Every strategy package has a `catalog.py` with standardized accessor functions:
`get_strategy_definitions()`, `get_strategy_catalog()`, `get_runtime_enabled_profiles()`

### Broker Adapter
Platform repos implement broker-specific adapters conforming to QPK's `MarketDataPort`, `PortfolioPort`, `ExecutionPort` protocols.

### Dependency Pinning
All repos pin QPK via `QPK_PIN`. Run `python scripts/check_qpk_pin_consistency.py` to verify.
