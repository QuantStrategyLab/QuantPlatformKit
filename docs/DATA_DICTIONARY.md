# Data Dictionary

## Artifact Types

### Feature Snapshots (CSV)
Produced by SnapshotPipelines. Columns vary by strategy profile.

| Column | Type | Description |
|--------|------|-------------|
| symbol | string | Ticker symbol |
| score | float | Composite feature score |
| rank | int | Ranking position (1-based) |
| as_of | date | Snapshot evaluation date |
| momentum_score | float | Momentum factor score |
| quality_score | float | Quality factor score |
| dividend_yield | float | Dividend yield percentage |

### Live Pool (JSON)
Produced by CryptoLivePoolPipelines.

| Field | Type | Description |
|-------|------|-------------|
| symbols | string[] | Ordered list of selected symbols |
| symbol_map | object | Symbol → metadata mapping |
| as_of_date | date | Pool selection date |
| ranking | object[] | Full ranking with scores |
| btc_cycle_indicators | object | BTC cycle metrics |

### Signal Bundle (JSON)
Produced by MarketSignalSources. Schema version: `market_signal_bundle.v1`.

| Field | Type | Description |
|-------|------|-------------|
| signal_bundle | object | Top-level bundle container |
| derived_indicators | object | Computed technical indicators |
| btc_cycle | object | BTC cycle metrics (AHR999, Mayer Multiple) |
| quality_report | object | Data quality assessment |

### Execution Report (JSON)
Produced by platform repos at runtime.

| Field | Type | Description |
|-------|------|-------------|
| run_id | string | Unique execution run identifier |
| strategy_profile | string | Canonical profile name |
| as_of | datetime | Execution timestamp |
| orders | object[] | Submitted orders with status |
| portfolio_snapshot | object | Pre/post execution portfolio state |
| diagnostics | object | Signal details and risk flags |

## Versioning Policy

All artifacts include version metadata:
- `contract_version` — the artifact format version (e.g., `feature_snapshot.v1`)
- `schema_version` — the JSON schema version for structured artifacts
- `generated_at` — ISO 8601 timestamp of artifact creation
- `sha256` — content hash for integrity verification

Version changes require:
1. Increment the version in the producing pipeline
2. Update all consumers before deploying
3. Maintain backward compatibility for one version cycle
