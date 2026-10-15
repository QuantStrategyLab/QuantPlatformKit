# Market-data source inventory (source snapshot, draft)

2026-10-15; all 25 QuantStrategyLab default branches enumerated. Read-only source inventory, not a deployment, account or entitlement audit. File-level rows combine functions/modes in one module; each row records actual declarations or explicitly marks inherited/unknown semantics. No market/account API, cloud object content, credential file or real data was read/downloaded.

The standalone job `inventory.csv` contains the same per-consumer fields. This Markdown copy is the public, generic evidence artifact. [Standard](market-data-standard.md) and [design/migration waves](market-data-access-layer-design.md) remain proposals.

## Scope and coverage

- 25 repositories; 1783 allowlisted source files scanned; 391 identified consumer/contract/acquisition boundaries; 527 keyword candidates excluded as non-consumers/control-only. Files under credential/token/secret names, `.env`, raw data, fixtures, generated artifacts and dependency trees were excluded before content reads. Selected workflows were inspected as source because they embed acquisition or invoke collectors.
- Tests/fixtures were not counted as market-data consumers. Submodule/dependency code is represented by its owning repository snapshot, not recounted as copied code. No runtime branch or other job's worktree was edited. Static inventory cannot establish dynamic custom-plugin coverage, production versions, effective overrides or paid entitlements; those remain explicit adoption checks.
- `Inherited/unknown_legacy` is an evidence limit, not an assertion that the actual runtime has no metadata. Package/data contracts and quote boundaries are included because losing basis/time semantics there affects downstream consumers. A provider family in a row may be selectable rather than always active.

## Repository snapshots

| Repository | Source SHA | Consumer rows | Coverage result |
|---|---|---:|---|
| [AIAuditBridge](https://github.com/QuantStrategyLab/AIAuditBridge/tree/4769cf6de39012b0691027c35d33aef30edbef3a) | `4769cf6de39012b0691027c35d33aef30edbef3a` | 0 | No market-price consumer established; infrastructure/auth/control-only source matches were excluded |
| [AlpacaPlatform](https://github.com/QuantStrategyLab/AlpacaPlatform/tree/28f7fc90c8b4d758ac87c179c933fea5772726e7) | `28f7fc90c8b4d758ac87c179c933fea5772726e7` | 0 | No market-price consumer established; infrastructure/auth/control-only source matches were excluded |
| [BinancePlatform](https://github.com/QuantStrategyLab/BinancePlatform/tree/76937ed06de1c6e5a76e807892f8bca4030ab4d1) | `76937ed06de1c6e5a76e807892f8bca4030ab4d1` | 12 | Source consumers below; runtime adoption not inspected |
| [CharlesSchwabPlatform](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/tree/f0b84329b6c8de8b10dd38eaa7fda93d310daf85) | `f0b84329b6c8de8b10dd38eaa7fda93d310daf85` | 10 | Source consumers below; runtime adoption not inspected |
| [CnEquitySnapshotPipelines](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/tree/3ac8ad07a26ef5988284c7169dadd3b3b83cba44) | `3ac8ad07a26ef5988284c7169dadd3b3b83cba44` | 7 | Source consumers below; runtime adoption not inspected |
| [CnEquityStrategies](https://github.com/QuantStrategyLab/CnEquityStrategies/tree/ab06f26d95514e9e52931586cd769eb8dbae89cf) | `ab06f26d95514e9e52931586cd769eb8dbae89cf` | 32 | Source consumers below; runtime adoption not inspected |
| [CryptoLivePoolPipelines](https://github.com/QuantStrategyLab/CryptoLivePoolPipelines/tree/deb2298b31fd2516dba9ac3e65e85137b3e54d09) | `deb2298b31fd2516dba9ac3e65e85137b3e54d09` | 10 | Source consumers below; runtime adoption not inspected |
| [CryptoStrategies](https://github.com/QuantStrategyLab/CryptoStrategies/tree/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a) | `15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a` | 13 | Source consumers below; runtime adoption not inspected |
| [FirstradePlatform](https://github.com/QuantStrategyLab/FirstradePlatform/tree/537ab80bb76dfc6b29591a5951152b905ffbf813) | `537ab80bb76dfc6b29591a5951152b905ffbf813` | 4 | Source consumers below; runtime adoption not inspected |
| [HkEquitySnapshotPipelines](https://github.com/QuantStrategyLab/HkEquitySnapshotPipelines/tree/27490948fb83d121d864cfc426483a5ba0122410) | `27490948fb83d121d864cfc426483a5ba0122410` | 4 | Source consumers below; runtime adoption not inspected |
| [HkEquityStrategies](https://github.com/QuantStrategyLab/HkEquityStrategies/tree/838b8d826ccdaed40ab19bed0ec64e201499836d) | `838b8d826ccdaed40ab19bed0ec64e201499836d` | 16 | Source consumers below; runtime adoption not inspected |
| [IBKRGatewayManager](https://github.com/QuantStrategyLab/IBKRGatewayManager/tree/6531b80dda707430e804d067e5417cf7794040e8) | `6531b80dda707430e804d067e5417cf7794040e8` | 0 | No market-price consumer established; infrastructure/auth/control-only source matches were excluded |
| [InteractiveBrokersPlatform](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/tree/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a) | `8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a` | 11 | Source consumers below; runtime adoption not inspected |
| [LongBridgePlatform](https://github.com/QuantStrategyLab/LongBridgePlatform/tree/93f73736d0698f3d8d285563f510ae0dcbbf661d) | `93f73736d0698f3d8d285563f510ae0dcbbf661d` | 8 | Source consumers below; runtime adoption not inspected |
| [MarketSignalSources](https://github.com/QuantStrategyLab/MarketSignalSources/tree/dd204e2b637d6ec389fe75f94c027372d28b471a) | `dd204e2b637d6ec389fe75f94c027372d28b471a` | 12 | Source consumers below; runtime adoption not inspected |
| [PoliticalEventTrackingResearch](https://github.com/QuantStrategyLab/PoliticalEventTrackingResearch/tree/6f43c401fdac817506f70a8ef936e8c6c7402f63) | `6f43c401fdac817506f70a8ef936e8c6c7402f63` | 2 | Source consumers below; runtime adoption not inspected |
| [QmtPlatform](https://github.com/QuantStrategyLab/QmtPlatform/tree/31d23526bbb5b73f5f140e692640e227ec57f219) | `31d23526bbb5b73f5f140e692640e227ec57f219` | 2 | Source consumers below; runtime adoption not inspected |
| [QuantAdvisorResearch](https://github.com/QuantStrategyLab/QuantAdvisorResearch/tree/eac68deafc46e77befa019b9670f1cd96e1d41b1) | `eac68deafc46e77befa019b9670f1cd96e1d41b1` | 3 | Source consumers below; runtime adoption not inspected |
| [QuantPlatformKit](https://github.com/QuantStrategyLab/QuantPlatformKit/tree/2b29055a5bd54501f370bc6c1b2b2005b305848c) | `2b29055a5bd54501f370bc6c1b2b2005b305848c` | 25 | Source consumers below; runtime adoption not inspected |
| [QuantRuntimeSettings](https://github.com/QuantStrategyLab/QuantRuntimeSettings/tree/850723f254dd0d2f0af7875b65b0f90de3b9c921) | `850723f254dd0d2f0af7875b65b0f90de3b9c921` | 8 | Source consumers below; runtime adoption not inspected |
| [QuantStrategyPlugins](https://github.com/QuantStrategyLab/QuantStrategyPlugins/tree/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a) | `e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a` | 26 | Source consumers below; runtime adoption not inspected |
| [ResearchSignalContextPipelines](https://github.com/QuantStrategyLab/ResearchSignalContextPipelines/tree/a41745a925c2d676df00c3111f6f75f5bb236288) | `a41745a925c2d676df00c3111f6f75f5bb236288` | 9 | Source consumers below; runtime adoption not inspected |
| [SchwabTokenAutoRefresher](https://github.com/QuantStrategyLab/SchwabTokenAutoRefresher/tree/1e29d5ab5ed71ceb79491b7a20ea218e9f044efe) | `1e29d5ab5ed71ceb79491b7a20ea218e9f044efe` | 0 | No market-price consumer established; infrastructure/auth/control-only source matches were excluded |
| [UsEquitySnapshotPipelines](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/tree/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb) | `d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb` | 116 | Source consumers below; runtime adoption not inspected |
| [UsEquityStrategies](https://github.com/QuantStrategyLab/UsEquityStrategies/tree/76e04b18180f21f7e04bd1f6e116a3206e2c30fc) | `76e04b18180f21f7e04bd1f6e116a3206e2c30fc` | 61 | Source consumers below; runtime adoption not inspected |

## Data configuration resolution index

Only key names and source references are recorded; no current values, private storage names or credential references were read. Consumer rows link to their caller resolver where data options are supplied outside the consuming module. Fixed candidate source identities remain contracts, not arbitrary overrides.

| Repository / resolver | Market-data config/env keys and definition anchors |
|---|---|
| CharlesSchwabPlatform/runtime_config_support.py | [`FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR`](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/runtime_config_support.py#L324); [`FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/runtime_config_support.py#L331); [`FEATURE_SNAPSHOT_FALLBACK_MODE`](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/runtime_config_support.py#L320); [`FEATURE_SNAPSHOT_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/runtime_config_support.py#L330); [`SCHWAB_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR`](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/runtime_config_support.py#L323); [`SCHWAB_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/runtime_config_support.py#L329); [`SCHWAB_FEATURE_SNAPSHOT_FALLBACK_MODE`](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/runtime_config_support.py#L319); [`SCHWAB_FEATURE_SNAPSHOT_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/runtime_config_support.py#L328); [`SCHWAB_MARKET_SIGNAL_CACHE_DIR`](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/runtime_config_support.py#L294); [`SCHWAB_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI`](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/runtime_config_support.py#L290); [`SCHWAB_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/runtime_config_support.py#L311); [`SCHWAB_MARKET_SIGNAL_FALLBACK_MODE`](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/runtime_config_support.py#L305); [`SCHWAB_MARKET_SIGNAL_HANDOFF_INDEX_URI`](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/runtime_config_support.py#L282); [`SCHWAB_MARKET_SIGNAL_HANDOFF_MANIFEST_URI`](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/runtime_config_support.py#L286); [`SCHWAB_MARKET_SIGNAL_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/runtime_config_support.py#L310); [`SCHWAB_MARKET_SIGNAL_REQUIRED`](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/runtime_config_support.py#L299) |
| FirstradePlatform/runtime_config_support.py | [`FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR`](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/runtime_config_support.py#L312); [`FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/runtime_config_support.py#L319); [`FEATURE_SNAPSHOT_FALLBACK_MODE`](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/runtime_config_support.py#L308); [`FEATURE_SNAPSHOT_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/runtime_config_support.py#L318); [`FIRSTRADE_DEBUG_POSITION_SNAPSHOT`](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/runtime_config_support.py#L254); [`FIRSTRADE_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR`](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/runtime_config_support.py#L311); [`FIRSTRADE_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/runtime_config_support.py#L317); [`FIRSTRADE_FEATURE_SNAPSHOT_FALLBACK_MODE`](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/runtime_config_support.py#L307); [`FIRSTRADE_FEATURE_SNAPSHOT_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/runtime_config_support.py#L316); [`FIRSTRADE_MARKET_SIGNAL_CACHE_DIR`](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/runtime_config_support.py#L285); [`FIRSTRADE_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI`](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/runtime_config_support.py#L281); [`FIRSTRADE_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/runtime_config_support.py#L299); [`FIRSTRADE_MARKET_SIGNAL_FALLBACK_MODE`](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/runtime_config_support.py#L505); [`FIRSTRADE_MARKET_SIGNAL_HANDOFF_INDEX_URI`](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/runtime_config_support.py#L477); [`FIRSTRADE_MARKET_SIGNAL_HANDOFF_MANIFEST_URI`](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/runtime_config_support.py#L277); [`FIRSTRADE_MARKET_SIGNAL_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/runtime_config_support.py#L298); [`FIRSTRADE_MARKET_SIGNAL_REQUIRED`](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/runtime_config_support.py#L489) |
| InteractiveBrokersPlatform/runtime_config_support.py | [`FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L422); [`FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L429); [`FEATURE_SNAPSHOT_FALLBACK_MODE`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L418); [`FEATURE_SNAPSHOT_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L428); [`IBKR_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L421); [`IBKR_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L427); [`IBKR_FEATURE_SNAPSHOT_FALLBACK_MODE`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L417); [`IBKR_FEATURE_SNAPSHOT_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L426); [`IBKR_MARKET`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L381); [`IBKR_MARKET_CALENDAR`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L438); [`IBKR_MARKET_CURRENCY`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L443); [`IBKR_MARKET_DATA_SYMBOL_SUFFIX`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L448); [`IBKR_MARKET_EXCHANGE`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L453); [`IBKR_MARKET_SIGNAL_CACHE_DIR`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L514); [`IBKR_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L510); [`IBKR_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L531); [`IBKR_MARKET_SIGNAL_FALLBACK_MODE`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L525); [`IBKR_MARKET_SIGNAL_HANDOFF_INDEX_URI`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L502); [`IBKR_MARKET_SIGNAL_HANDOFF_MANIFEST_URI`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L506); [`IBKR_MARKET_SIGNAL_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L530); [`IBKR_MARKET_SIGNAL_REQUIRED`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L519); [`IBKR_MARKET_TIMEZONE`](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/runtime_config_support.py#L457) |
| LongBridgePlatform/runtime_config_support.py | [`FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L470); [`FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L477); [`FEATURE_SNAPSHOT_FALLBACK_MODE`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L466); [`FEATURE_SNAPSHOT_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L476); [`LONGBRIDGE_DEBUG_POSITION_SNAPSHOT`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L406); [`LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L469); [`LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L475); [`LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_MODE`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L465); [`LONGBRIDGE_FEATURE_SNAPSHOT_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L474); [`LONGBRIDGE_MARKET`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L334); [`LONGBRIDGE_MARKET_CALENDAR`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L350); [`LONGBRIDGE_MARKET_SIGNAL_CACHE_DIR`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L440); [`LONGBRIDGE_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L436); [`LONGBRIDGE_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L457); [`LONGBRIDGE_MARKET_SIGNAL_FALLBACK_MODE`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L451); [`LONGBRIDGE_MARKET_SIGNAL_HANDOFF_INDEX_URI`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L428); [`LONGBRIDGE_MARKET_SIGNAL_HANDOFF_MANIFEST_URI`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L432); [`LONGBRIDGE_MARKET_SIGNAL_MAX_STALE_DAYS`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L456); [`LONGBRIDGE_MARKET_SIGNAL_REQUIRED`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L445); [`LONGBRIDGE_MARKET_TIMEZONE`](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/runtime_config_support.py#L356) |
| QmtPlatform/runtime_config_support.py | [`QMT_MARKET_HISTORY_PATH`](https://github.com/QuantStrategyLab/QmtPlatform/blob/31d23526bbb5b73f5f140e692640e227ec57f219/runtime_config_support.py#L44) |

## Conflicts, duplication and explicit evidence gaps

30 identified items. “Confirmed” describes the pinned source behavior; it does not establish deployment, a financial loss or provider numerical equivalence. Intentional frozen variants are identified separately from bugs. Unknown runtime, entitlement or empirical results remain unknown.

### DS-01 — IBKR generic history changes adjustment mode on fallback

**Confirmed semantic conflict.** QPK tries ADJUSTED_LAST then TRADES and returns the same PriceSeries type. Strict acquisition forbids this fallback. A successful generic return does not establish dividend-aware history.

Evidence: [QuantPlatformKit/src/quant_platform_kit/ibkr/market_data.py:345](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/ibkr/market_data.py#L345); [QuantPlatformKit/src/quant_platform_kit/ibkr/market_data.py:449](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/ibkr/market_data.py#L449); [QuantPlatformKit/src/quant_platform_kit/common/models.py:16](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/common/models.py#L16).

### DS-02 — IBKR signal path intentionally suppresses adjusted history

**Confirmed semantic conflict.** The platform signal proxy suppresses ADJUSTED_LAST and uses TRADES; research acquisition still requests strict adjusted history. SOXL/SOXX and TQQQ signal/research inputs therefore require separate identities. This is source evidence, not proof of an unintended deployed change.

Evidence: [InteractiveBrokersPlatform/application/runtime_strategy_adapters.py:78](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/application/runtime_strategy_adapters.py#L78); [InteractiveBrokersPlatform/application/runtime_strategy_adapters.py:95](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/application/runtime_strategy_adapters.py#L95); [UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/lifecycle/soxl_adjusted_last_acquisition.py:627](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_adjusted_last_acquisition.py#L627).

### DS-03 — Yahoo Close fallback can change basis and mix OHLC semantics in IBKR

**Confirmed fallback conflict.** auto_adjust=False selects split-only Close; if absent, Adj Close is selected while other OHLC columns remain independently taken from the frame. This is not a fully raw-price conversion. Missing requested basis should be unavailable, not reclassified silently.

Evidence: [InteractiveBrokersPlatform/application/runtime_strategy_adapters.py:112](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/application/runtime_strategy_adapters.py#L112); [InteractiveBrokersPlatform/application/runtime_strategy_adapters.py:133](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/application/runtime_strategy_adapters.py#L133); [InteractiveBrokersPlatform/application/runtime_strategy_adapters.py:154](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/application/runtime_strategy_adapters.py#L154).

### DS-04 — Same US instruments have raw, split-only and dividend-aware datasets

**Explicitly different candidate contracts.** Alpaca all in Batch A, raw SIP+actions in RS04/QQQM/BOXX, strict IBKR ADJUSTED_LAST, Twelve/Yahoo split-only and yfinance adjusted paths coexist. These are not interchangeable caches or evidence. Existing frozen contracts may intentionally differ; preserve each identity.

Evidence: [UsEquitySnapshotPipelines/scripts/acquire_batch_a_v2_price_snapshots_alpaca.py:56](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_batch_a_v2_price_snapshots_alpaca.py#L56); [UsEquitySnapshotPipelines/scripts/rs04_cloud_archive.py:207](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/rs04_cloud_archive.py#L207); [UsEquitySnapshotPipelines/scripts/acquire_qqqm_boxx_raw_history.py:294](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_qqqm_boxx_raw_history.py#L294); [UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_free_split_close_p1.py:56](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_free_split_close_p1.py#L56).

### DS-05 — Two Yahoo download modules contain 8 identical function implementations

**Confirmed duplicate code.** AST comparison (excluding line positions) found 8 identical top-level functions: symbol candidate/normalization/proxy helpers, normalize_yfinance_download, _optional_float and field extraction. Their surrounding download policies have diverged, so only common normalization should be considered for reuse.

Evidence: [UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/yfinance_prices.py:42](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/yfinance_prices.py#L42); [QuantStrategyPlugins/src/quant_strategy_plugins/yfinance_prices.py:20](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/yfinance_prices.py#L20); [UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/yfinance_prices.py:184](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/yfinance_prices.py#L184); [QuantStrategyPlugins/src/quant_strategy_plugins/yfinance_prices.py:119](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/yfinance_prices.py#L119).

### DS-06 — Yahoo chart fetching/normalization is independently implemented in several repos

**Confirmed duplicated acquisition.** UESP, QSP/yfinance, HK strategy downloader, QAR confirmation, context pipelines, CN history and the JS website publisher own separate request/normalization policies. This is repeated acquisition logic; it does not imply all functions or outputs are equivalent.

Evidence: [UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/yfinance_prices.py:267](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/yfinance_prices.py#L267); [QuantAdvisorResearch/src/quant_advisor_research/market_confirmation.py:415](https://github.com/QuantStrategyLab/QuantAdvisorResearch/blob/eac68deafc46e77befa019b9670f1cd96e1d41b1/src/quant_advisor_research/market_confirmation.py#L415); [ResearchSignalContextPipelines/src/research_signal_context_pipelines/context_bundle.py:94](https://github.com/QuantStrategyLab/ResearchSignalContextPipelines/blob/a41745a925c2d676df00c3111f6f75f5bb236288/src/research_signal_context_pipelines/context_bundle.py#L94); [CnEquitySnapshotPipelines/src/cn_equity_snapshot_pipelines/akshare_market_history.py:496](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/akshare_market_history.py#L496); [QuantRuntimeSettings/scripts/sync_market_benchmark_closes.mjs:49](https://github.com/QuantStrategyLab/QuantRuntimeSettings/blob/850723f254dd0d2f0af7875b65b0f90de3b9c921/scripts/sync_market_benchmark_closes.mjs#L49).

### DS-07 — Alpaca request/coverage logic is repeated across collectors

**Confirmed duplicated acquisition.** Batch A, Global ETF, SOXL, TQQQ, raw-history and RS04 collectors each own request or publication logic. Extract only genuinely identical transport/normalization after comparing fixed source/candidate constraints; do not collapse raw and adjusted contracts.

Evidence: [UsEquitySnapshotPipelines/scripts/acquire_batch_a_v2_price_snapshots_alpaca.py:56](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_batch_a_v2_price_snapshots_alpaca.py#L56); [UsEquitySnapshotPipelines/scripts/acquire_global_etf_learning_inputs_alpaca.py:70](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_global_etf_learning_inputs_alpaca.py#L70); [UsEquitySnapshotPipelines/scripts/acquire_soxl_core_only_p1_inputs_alpaca.py:182](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_soxl_core_only_p1_inputs_alpaca.py#L182); [UsEquitySnapshotPipelines/scripts/acquire_tqqq_core_only_p1_inputs_alpaca.py:200](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_tqqq_core_only_p1_inputs_alpaca.py#L200); [UsEquitySnapshotPipelines/scripts/rs04_cloud_archive.py:207](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/rs04_cloud_archive.py#L207).

### DS-08 — QAR substitutes split-only close for missing adjusted close per row

**Confirmed fallback conflict.** The confirmation adapter prefers adjclose but takes quote close when a value is absent. A series can therefore have changing dividend treatment without a per-row basis marker.

Evidence: [QuantAdvisorResearch/src/quant_advisor_research/market_confirmation.py:432](https://github.com/QuantStrategyLab/QuantAdvisorResearch/blob/eac68deafc46e77befa019b9670f1cd96e1d41b1/src/quant_advisor_research/market_confirmation.py#L432); [QuantAdvisorResearch/src/quant_advisor_research/market_confirmation.py:439](https://github.com/QuantStrategyLab/QuantAdvisorResearch/blob/eac68deafc46e77befa019b9670f1cd96e1d41b1/src/quant_advisor_research/market_confirmation.py#L439).

### DS-09 — Research context downloader has the same per-row adjustment fallback

**Confirmed fallback conflict.** normalize_yahoo_chart_payload falls back from adjclose to close. Its output PriceRow/derived returns do not bind a canonical price_basis, and partial-download policy can shrink coverage.

Evidence: [ResearchSignalContextPipelines/src/research_signal_context_pipelines/context_bundle.py:130](https://github.com/QuantStrategyLab/ResearchSignalContextPipelines/blob/a41745a925c2d676df00c3111f6f75f5bb236288/src/research_signal_context_pipelines/context_bundle.py#L130); [ResearchSignalContextPipelines/src/research_signal_context_pipelines/context_bundle.py:137](https://github.com/QuantStrategyLab/ResearchSignalContextPipelines/blob/a41745a925c2d676df00c3111f6f75f5bb236288/src/research_signal_context_pipelines/context_bundle.py#L137); [ResearchSignalContextPipelines/src/research_signal_context_pipelines/context_bundle.py:157](https://github.com/QuantStrategyLab/ResearchSignalContextPipelines/blob/a41745a925c2d676df00c3111f6f75f5bb236288/src/research_signal_context_pipelines/context_bundle.py#L157).

### DS-10 — CN adjusted_close_equivalent groups several provider adjustment methods

**Confirmed source-policy ambiguity.** AkShare qfq, Tencent qfq/qfq_identity and Yahoo adjclose are recorded as source_price_bases but summarized as adjusted_close_equivalent. Hybrid fallback can switch Yahoo to Tencent. Numerical/factor equivalence is unproven; retain the exact source basis rather than normalize by label alone.

Evidence: [CnEquitySnapshotPipelines/src/cn_equity_snapshot_pipelines/akshare_market_history.py:40](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/akshare_market_history.py#L40); [CnEquitySnapshotPipelines/src/cn_equity_snapshot_pipelines/akshare_market_history.py:437](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/akshare_market_history.py#L437); [CnEquitySnapshotPipelines/src/cn_equity_snapshot_pipelines/akshare_market_history.py:579](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/akshare_market_history.py#L579); [CnEquitySnapshotPipelines/src/cn_equity_snapshot_pipelines/akshare_market_history.py:644](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/akshare_market_history.py#L644).

### DS-11 — HK ForwardAdjust and Yahoo auto_adjust=True are different source contracts

**Unverified equivalence.** LongBridge research requests ForwardAdjust/Intraday, while public HK staging and strategy backtests request yfinance auto_adjust=True. Dividend reinvestment, factor anchors, session semantics and rights have not been proven equal.

Evidence: [HkEquitySnapshotPipelines/src/hk_equity_snapshot_pipelines/low_vol_dividend_longbridge_snapshot.py:480](https://github.com/QuantStrategyLab/HkEquitySnapshotPipelines/blob/27490948fb83d121d864cfc426483a5ba0122410/src/hk_equity_snapshot_pipelines/low_vol_dividend_longbridge_snapshot.py#L480); [HkEquitySnapshotPipelines/src/hk_equity_snapshot_pipelines/low_vol_dividend_public_snapshot.py:124](https://github.com/QuantStrategyLab/HkEquitySnapshotPipelines/blob/27490948fb83d121d864cfc426483a5ba0122410/src/hk_equity_snapshot_pipelines/low_vol_dividend_public_snapshot.py#L124); [HkEquityStrategies/src/hk_equity_strategies/backtest/yfinance_market_data.py:54](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/backtest/yfinance_market_data.py#L54).

### DS-12 — Legacy numeric series/quotes do not carry full price provenance

**Confirmed schema gap.** PricePoint/PriceSeries do not require provider, feed, basis, calendar or source/content digests. Newer decision-data/artifact contracts carry adjustment and root bindings, so expanding naked series alone would discard existing protection.

Evidence: [QuantPlatformKit/src/quant_platform_kit/common/models.py:9](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/common/models.py#L9); [QuantPlatformKit/src/quant_platform_kit/common/ports.py:19](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/common/ports.py#L19); [QuantPlatformKit/src/quant_platform_kit/data/decision_data_binding.py:97](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/data/decision_data_binding.py#L97).

### DS-13 — Website benchmark session dates are New York; returned timezone says Shanghai

**Confirmed metadata conflict.** Parser uses America/New_York for observationDate, while buildMarketBenchmarkReadModel returns timezone Asia/Shanghai. This can mislead joins/display consumers even when the stored date string is correct.

Evidence: [QuantRuntimeSettings/web/strategy-switch-console/infrastructure/market_benchmark/market_benchmark.js:157](https://github.com/QuantStrategyLab/QuantRuntimeSettings/blob/850723f254dd0d2f0af7875b65b0f90de3b9c921/web/strategy-switch-console/infrastructure/market_benchmark/market_benchmark.js#L157); [QuantRuntimeSettings/web/strategy-switch-console/infrastructure/market_benchmark/market_benchmark.js:189](https://github.com/QuantStrategyLab/QuantRuntimeSettings/blob/850723f254dd0d2f0af7875b65b0f90de3b9c921/web/strategy-switch-console/infrastructure/market_benchmark/market_benchmark.js#L189).

### DS-14 — Website stores only previous-date bars, research uses completed-session clocks

**Confirmed clock-policy difference.** The website publisher drops all current New York dates even after a valid close; exchange-calendar research checks the actual session close. The policies have different freshness. Do not claim identical as-of coverage.

Evidence: [QuantRuntimeSettings/scripts/sync_market_benchmark_closes.mjs:82](https://github.com/QuantStrategyLab/QuantRuntimeSettings/blob/850723f254dd0d2f0af7875b65b0f90de3b9c921/scripts/sync_market_benchmark_closes.mjs#L82); [UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_free_split_close_p1.py:192](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_free_split_close_p1.py#L192).

### DS-15 — US session logic exists as pinned exchange calendars and local holiday rules

**Confirmed calendar duplication.** UESP SOXL/TQQQ frozen rules, newer exchange_calendars paths and platform calendar hooks are separately maintained. Their calendar/source versions differ; no actual session-set comparison was run in this job.

Evidence: [UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/lifecycle/soxl_pit_input_packager.py:175](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_pit_input_packager.py#L175); [UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/lifecycle/tqqq_core_only_p1_binding.py:586](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/tqqq_core_only_p1_binding.py#L586); [UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p1_binding.py:73](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p1_binding.py#L73).

### DS-16 — Weekday ranges are used where exchange-session identity is needed

**Confirmed calendar mismatch risk.** Universe audit expected coverage uses pandas bdate_range; LongBridge adapter can fabricate fallback dates using bdate_range. Weekday dates include exchange holidays and cannot prove the actual bar sessions.

Evidence: [UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/universe_audit_engine.py:140](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/universe_audit_engine.py#L140); [LongBridgePlatform/application/runtime_broker_adapters.py:137](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/application/runtime_broker_adapters.py#L137).

### DS-17 — CN calendar is a finite hand-maintained holiday set

**Confirmed calendar maintenance gap.** QPK defines SSE/SZSE weekday holidays with a stated supported date range. This is a different calendar authority/version from the exchange-calendar profiles in new research; extensions and exceptional days need explicit verification.

Evidence: [QuantPlatformKit/src/quant_platform_kit/common/cn_equity_calendar.py:8](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/common/cn_equity_calendar.py#L8); [CnEquitySnapshotPipelines/src/cn_equity_snapshot_pipelines/akshare_market_history.py:224](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/akshare_market_history.py#L224).

### DS-18 — Some consumers strip timezones or derive dates in UTC rather than market local time

**Confirmed timezone-normalization difference.** Yahoo normalization drops tz information after UTC conversion; QAR/CN chart adapters derive UTC dates. LongPort QPK handles native naive times using process-local meaning, while the platform adapter can replace tzinfo with UTC. Asian exchange dates and naive timestamps therefore need adapter-specific verification.

Evidence: [UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/yfinance_prices.py:336](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/yfinance_prices.py#L336); [QuantAdvisorResearch/src/quant_advisor_research/market_confirmation.py:443](https://github.com/QuantStrategyLab/QuantAdvisorResearch/blob/eac68deafc46e77befa019b9670f1cd96e1d41b1/src/quant_advisor_research/market_confirmation.py#L443); [CnEquitySnapshotPipelines/src/cn_equity_snapshot_pipelines/akshare_market_history.py:518](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/akshare_market_history.py#L518); [QuantPlatformKit/src/quant_platform_kit/longbridge/market_data.py:111](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/longbridge/market_data.py#L111); [LongBridgePlatform/application/runtime_broker_adapters.py:94](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/application/runtime_broker_adapters.py#L94).

### DS-19 — Binance helpers can use the last returned daily row without completed-kline filtering

**Confirmed unlabelled session risk.** QPK indicator helpers take the last row/last valid row; pipeline klines pagination is keyed on daily open. The inspected boundaries do not independently prove that the final returned bar has closed. No live incomplete-bar incident is claimed.

Evidence: [QuantPlatformKit/src/quant_platform_kit/binance/market_data.py:17](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/binance/market_data.py#L17); [QuantPlatformKit/src/quant_platform_kit/binance/market_data.py:48](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/binance/market_data.py#L48); [QuantPlatformKit/src/quant_platform_kit/binance/market_data.py:127](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/binance/market_data.py#L127); [CryptoLivePoolPipelines/src/binance_client.py:167](https://github.com/QuantStrategyLab/CryptoLivePoolPipelines/blob/deb2298b31fd2516dba9ac3e65e85137b3e54d09/src/binance_client.py#L167).

### DS-20 — Crypto CSV cache is keyed by symbol, with mutable merge/update semantics

**Confirmed cache identity gap.** A configured raw_dir/<symbol>.csv is updated/deduplicated in place, with no provider/basis/calendar identity in the filename. It cannot serve as a frozen canonical input without a bound immutable manifest; no cache-content read was performed.

Evidence: [CryptoLivePoolPipelines/src/binance_client.py:205](https://github.com/QuantStrategyLab/CryptoLivePoolPipelines/blob/deb2298b31fd2516dba9ac3e65e85137b3e54d09/src/binance_client.py#L205); [CryptoLivePoolPipelines/src/binance_client.py:230](https://github.com/QuantStrategyLab/CryptoLivePoolPipelines/blob/deb2298b31fd2516dba9ac3e65e85137b3e54d09/src/binance_client.py#L230).

### DS-21 — Several broker quote adapters stamp client fetch time

**Confirmed provenance/freshness gap.** Schwab QuoteSnapshot as_of is set from datetime.now. Client observation time and provider quote time are different facts. New envelopes need both without relaxing existing quote freshness/execution checks.

Evidence: [QuantPlatformKit/src/quant_platform_kit/schwab/market_data.py:131](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/schwab/market_data.py#L131); [QuantPlatformKit/src/quant_platform_kit/common/models.py:29](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/common/models.py#L29).

### DS-22 — HK volume can substitute turnover; QAR missing volume becomes zero

**Confirmed unit/unknown-value ambiguity.** LongBridge HK staging chooses volume or turnover or 0, while QAR uses 0 when volume is absent. Turnover currency and share volume are different units, and missing is not observed zero.

Evidence: [HkEquitySnapshotPipelines/src/hk_equity_snapshot_pipelines/low_vol_dividend_longbridge_snapshot.py:502](https://github.com/QuantStrategyLab/HkEquitySnapshotPipelines/blob/27490948fb83d121d864cfc426483a5ba0122410/src/hk_equity_snapshot_pipelines/low_vol_dividend_longbridge_snapshot.py#L502); [QuantAdvisorResearch/src/quant_advisor_research/market_confirmation.py:446](https://github.com/QuantStrategyLab/QuantAdvisorResearch/blob/eac68deafc46e77befa019b9670f1cd96e1d41b1/src/quant_advisor_research/market_confirmation.py#L446).

### DS-23 — HK strategy downloader drops dates missing any configured instrument

**Confirmed sample-selection difference.** dropna(how=any) intersects the observed universe dates, potentially hiding inception, suspension or missing-data periods. This differs from explicit expected-session/gap reporting and must not silently define a stress/OOS sample.

Evidence: [HkEquityStrategies/src/hk_equity_strategies/backtest/yfinance_market_data.py:63](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/backtest/yfinance_market_data.py#L63); [UsEquitySnapshotPipelines/scripts/acquire_batch_a_v2_price_snapshots_alpaca.py:309](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_batch_a_v2_price_snapshots_alpaca.py#L309).

### DS-24 — Legacy total_return_adjusted and split-price return contracts coexist

**Confirmed return-label difference.** Alpaca all and IBKR adjusted evidence use total_return_adjusted; V7 split-only observations explicitly use SPLIT_ADJUSTED_PRICE_RETURN. Dividend-aware adjusted prices do not by themselves specify a reinvested total-return index or accounting treatment.

Evidence: [UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p1_binding.py:198](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p1_binding.py#L198); [UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/lifecycle/tqqq_acquisition_orchestration.py:471](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/tqqq_acquisition_orchestration.py#L471); [UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_v7_long_horizon_risk_observation.py:49](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_v7_long_horizon_risk_observation.py#L49).

### DS-25 — Website price-index benchmarks and dividend-aware ETF research are not the same series

**Confirmed benchmark distinction.** The website stores price indices; research may use adjusted ETFs or total-return approximations. Portfolio return comparison must state this difference, currency, interval and external-flow qualification. Do not swap index and ETF IDs as provider fallback.

Evidence: [QuantRuntimeSettings/web/strategy-switch-console/infrastructure/market_benchmark/market_benchmark.js:166](https://github.com/QuantStrategyLab/QuantRuntimeSettings/blob/850723f254dd0d2f0af7875b65b0f90de3b9c921/web/strategy-switch-console/infrastructure/market_benchmark/market_benchmark.js#L166); [QuantStrategyPlugins/src/quant_strategy_plugins/yfinance_prices.py:213](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/yfinance_prices.py#L213).

### DS-26 — Legacy TECL synthetic mode does not satisfy UBPS v0.2 extended-history semantics

**Confirmed synthetic-model incompatibility.** It applies 3x underlying daily return minus fixed annual expense/252 and clamps daily loss at -99%, then builds a synthetic target series. It lacks the new model's financing/termination and per-row real/synthetic/bridge contract. This is a separate research mode, not an accepted real+synthetic splice. Do not rewrite old evidence or call it real performance.

Evidence: [UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/tecl_xlk_trend_income_research_inputs.py:61](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/tecl_xlk_trend_income_research_inputs.py#L61); [UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/tecl_xlk_trend_income_research_inputs.py:65](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/tecl_xlk_trend_income_research_inputs.py#L65); [UsEquityStrategies/src/us_equity_strategies/research/soxl_v7_derisk_history.py:28](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/soxl_v7_derisk_history.py#L28); [UsEquityStrategies/src/us_equity_strategies/research/soxl_v7_derisk_history.py:176](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/soxl_v7_derisk_history.py#L176).

### DS-27 — Current-only constituents and factor/dividend snapshots are not historical PIT

**Confirmed quality/authority separation.** CN index-membership capture documents that removed historical members are unavailable. MarketSignalSources/feature consumers need actual historical availability and source-root bindings; adjusted prices alone cannot fix universe survivorship or revised context.

Evidence: [CnEquitySnapshotPipelines/src/cn_equity_snapshot_pipelines/index_membership.py:1](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/index_membership.py#L1); [QuantPlatformKit/src/quant_platform_kit/common/feature_snapshot.py:37](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/common/feature_snapshot.py#L37).

### DS-28 — Website benchmark publisher has a personal-host default

**Confirmed generic-config gap.** The sync URL is configurable but its source default is tied to a personal deployment. The draft requires a required configured endpoint or generic disabled default. This PR intentionally does not edit that consumer or reproduce the host in documentation.

Evidence: [QuantRuntimeSettings/scripts/sync_market_benchmark_closes.mjs:40](https://github.com/QuantStrategyLab/QuantRuntimeSettings/blob/850723f254dd0d2f0af7875b65b0f90de3b9c921/scripts/sync_market_benchmark_closes.mjs#L40).

### DS-29 — The snapshot diagnostic pins SIP without a configurable free-plan cutoff/feed policy

**Confirmed plan/design gap; fix owned elsewhere.** At the audited revision it passes date_cutoff to end, adjustment=all and feed=sip. The Basic-plan 16-minute safety bound is now required by the owner. A historical date cutoff alone does not establish a recent-SIP violation; this inventory does not independently diagnose the earlier 403. live_cfg3 owns the successor fix and its config keys.

Evidence: [UsEquitySnapshotPipelines/.github/workflows/alpaca-sip-access-diagnostic.yml:64](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/.github/workflows/alpaca-sip-access-diagnostic.yml#L64); [UsEquitySnapshotPipelines/scripts/acquire_batch_a_v2_price_snapshots_alpaca.py:56](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_batch_a_v2_price_snapshots_alpaca.py#L56).

### DS-30 — Companion Alpaca minimum delay is now aligned at 16 minutes

**Resolved companion-PR discrepancy.** Initial PR #543 head 039b1b12b028ab51b92e349b7c57bd7fdea0e046 defaulted to 16 but accepted >=15. Its follow-up head 4d64d01ee90151e02495e48773d32cad4866bbeb raises the accepted minimum to 16, matching this job. It retains the same keys, separate feed segments and stop-on-error behavior. This is source-level resolution in the owning PR, not evidence of scheduled-consumer adoption or deployment. No companion code was edited here.

Evidence: [UsEquitySnapshotPipelines/scripts/alpaca_feed_windows.py:15 (initial)](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/039b1b12b028ab51b92e349b7c57bd7fdea0e046/scripts/alpaca_feed_windows.py#L15); [UsEquitySnapshotPipelines/scripts/alpaca_feed_windows.py:15 (follow-up)](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/4d64d01ee90151e02495e48773d32cad4866bbeb/scripts/alpaca_feed_windows.py#L15).

## Coordination findings and limits

- Owner update from `ibkr_close_compare`, 2026-10-15: IBKR PR #602 changes Yahoo Adj Close to Close with auto_adjust=False: dividend+split adjusted to split-only, not fully raw. Missing Close still falls back to Adj Close; IBKR ADJUSTED_LAST is suppressed for signals. Vocabulary agreed: `raw_unadjusted`, `split_adjusted`, `split_dividend_adjusted`, `total_return_index`; no implicit default/fallback.
- Four deployment profiles were reported by that job: SOXL/SOXX trend income, TQQQ growth income, global ETF rotation and Russell Top50 leader rotation. The latter two consume feature snapshots; upstream basis changes are separate experiments. PR #588 prefetch is gated to nasdaq_sp500_smart_dca (0 of these 4). PR #601 affects the derived-indicator semiconductor path; pinned UES trend_ma_window defaults to 140, while effective production overrides remain unbound. These are attributed owner findings, not this job's live readback.
- [IBKR Draft PR #542](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/pull/542), inspected head `cf267fcc28375f6de6b6c35e9cf992a68d507768`, is aggregation-only, not a replay generator. Empirical results remain **0/8 target-windows**, **NOT_COMPUTED**, pending frozen cloud replay inputs, actual inception, effective configuration and UBPS cost/options coverage. Its owner currently recommends fixing explicit basis/OHLC/fallback first. No CAGR/MDD/return delta is invented; no code/branch/workflow from that job was edited or run here.
- `live_cfg2` finished without a feed/delay PR or new keys; its evidence did not retain a sanitized 403 body. Subsequent owner instruction confirms the free plan and assigns the fix to `live_cfg3`. [Companion PR #543](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/pull/543), latest inspected open head `4d64d01ee90151e02495e48773d32cad4866bbeb`, delivers `ALPACA_SIP_MIN_DELAY_MINUTES=16` with minimum 16, `ALPACA_FEED_RECENT=iex`, `ALPACA_FEED_HISTORICAL=sip` for the manual diagnostic/reusable planner. It does not change scheduled/frozen producers or trading consumers. This draft reuses those exact names, preserves separate feed segments, and records the earlier >=15 versus >=16 discrepancy and its resolution as DS-30. It does not take over that implementation or claim it is deployed.
- UBPS v0.2 owner draft, 2026-10-15, sections 3/8.2/9 was read as documentation. Its real/synthetic/bridge labels and provenance requirements are reflected in the standard; its adoption, financial thresholds and existing candidate-specific gates are separate owner decisions.
- Actual broker entitlements, source licenses/retention, native daily-bar RTH equivalence, corporate-action factor equivalence, pre-2016 source coverage, deployed QPK/strategy pins, effective overrides and dynamic custom-plugin inputs were not verified. These are concrete missing inputs for adoption, not grounds for modifying a runtime or weakening a gate.

## Consumer inventory and migration order

Rows are ordered by proposed migration wave (0 shared contract; 1 research acquisition; 2 research/injected consumers; 3 website projections; 4 isolated/unconfigured platform inputs; 5 live paths last). The wave is a future plan, not a runtime change. Every row has its own risk note. Source references are pinned to the table above.

### MD-001 — QuantPlatformKit: src/quant_platform_kit/binance/market_data.py

- Role: provider acquisition/normalization. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: UTC; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: lookback_days.
- Evidence: [src/quant_platform_kit/binance/market_data.py:22](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/binance/market_data.py#L22).

### MD-002 — QuantPlatformKit: src/quant_platform_kit/common/feature_snapshot.py

- Role: artifact/CSV input boundary. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: timezone.
- Evidence: [src/quant_platform_kit/common/feature_snapshot.py:11](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/common/feature_snapshot.py#L11); [src/quant_platform_kit/common/feature_snapshot.py:76](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/common/feature_snapshot.py#L76).

### MD-003 — QuantPlatformKit: src/quant_platform_kit/common/ports.py

- Role: artifact/CSV input boundary. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: binding_sha256.
- Evidence: [src/quant_platform_kit/common/ports.py:6](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/common/ports.py#L6).

### MD-004 — QuantPlatformKit: src/quant_platform_kit/ibkr/market_data.py

- Role: provider acquisition/normalization. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: IBKR. Historical-data entitlement, pacing and isolated approved session required; actual plan unverified.
- Price basis: Strict API ADJUSTED_LAST only; generic API ADJUSTED_LAST then TRADES. Adjustment: Generic fallback changes dividend policy; returned PriceSeries lacks selected mode.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, duration, timezone.
- Evidence: [src/quant_platform_kit/ibkr/market_data.py:5](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/ibkr/market_data.py#L5); [src/quant_platform_kit/ibkr/market_data.py:187](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/ibkr/market_data.py#L187); [src/quant_platform_kit/ibkr/market_data.py:349](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/ibkr/market_data.py#L349).

### MD-005 — QuantPlatformKit: src/quant_platform_kit/longbridge/market_data.py

- Role: provider acquisition/normalization. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: LongPort/LongBridge quote/history adapter. Market-specific quote entitlement not inspected.
- Price basis: Provider ForwardAdjust history; exact split/dividend mapping not independently certified. Adjustment: Native adjustment enum, distinct from last_done execution quote.
- Time / session / calendar: America/New_York/UTC; Explicit completed-session/calendar hook present; preserve exact upstream clock and finality policy; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: timezone.
- Evidence: [src/quant_platform_kit/longbridge/market_data.py:5](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/longbridge/market_data.py#L5); [src/quant_platform_kit/longbridge/market_data.py:159](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/longbridge/market_data.py#L159); [src/quant_platform_kit/longbridge/market_data.py:183](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/longbridge/market_data.py#L183).

### MD-006 — QuantPlatformKit: src/quant_platform_kit/schwab/market_data.py

- Role: provider acquisition/normalization. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Schwab history/quotes via injected broker adapter. Authorized API/account data entitlement not inspected.
- Price basis: Existing history path declares split_adjusted; execution quotes use contemporaneous units. Adjustment: Broker convention; no independent distribution/factor verification in this inventory.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, timezone.
- Evidence: [src/quant_platform_kit/schwab/market_data.py:5](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/schwab/market_data.py#L5); [src/quant_platform_kit/schwab/market_data.py:110](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/schwab/market_data.py#L110).

### MD-007 — QuantPlatformKit: scripts/verify_fractional_dca_execution.py

- Role: series/feature consumer. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [scripts/verify_fractional_dca_execution.py:110](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/scripts/verify_fractional_dca_execution.py#L110).

### MD-008 — QuantPlatformKit: src/quant_platform_kit/common/history.py

- Role: series/feature consumer. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/quant_platform_kit/common/history.py:6](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/common/history.py#L6).

### MD-009 — QuantPlatformKit: src/quant_platform_kit/common/indicators.py

- Role: series/feature consumer. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/quant_platform_kit/common/indicators.py:7](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/common/indicators.py#L7).

### MD-010 — QuantPlatformKit: src/quant_platform_kit/common/models.py

- Role: series/feature consumer. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/quant_platform_kit/common/models.py:9](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/common/models.py#L9).

### MD-011 — QuantPlatformKit: src/quant_platform_kit/common/port_adapters.py

- Role: series/feature consumer. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/quant_platform_kit/common/port_adapters.py:6](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/common/port_adapters.py#L6).

### MD-012 — QuantPlatformKit: src/quant_platform_kit/common/runtime_inputs.py

- Role: series/feature consumer. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, timezone.
- Evidence: [src/quant_platform_kit/common/runtime_inputs.py:4](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/common/runtime_inputs.py#L4); [src/quant_platform_kit/common/runtime_inputs.py:237](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/common/runtime_inputs.py#L237).

### MD-013 — QuantPlatformKit: src/quant_platform_kit/common/small_account_compatibility.py

- Role: series/feature consumer. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/quant_platform_kit/common/small_account_compatibility.py:67](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/common/small_account_compatibility.py#L67).

### MD-014 — QuantPlatformKit: src/quant_platform_kit/common/strategies.py

- Role: series/feature consumer. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/quant_platform_kit/common/strategies.py:755](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/common/strategies.py#L755).

### MD-015 — QuantPlatformKit: src/quant_platform_kit/data/__init__.py

- Role: manifest/binding/validation contract. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/quant_platform_kit/data/__init__.py:45](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/data/__init__.py#L45).

### MD-016 — QuantPlatformKit: src/quant_platform_kit/data/decision_data_binding.py

- Role: manifest/binding/validation contract. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, as_of, binding_sha256.
- Evidence: [src/quant_platform_kit/data/decision_data_binding.py:87](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/data/decision_data_binding.py#L87); [src/quant_platform_kit/data/decision_data_binding.py:201](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/data/decision_data_binding.py#L201).

### MD-017 — QuantPlatformKit: src/quant_platform_kit/data/decision_price_series_artifact.py

- Role: manifest/binding/validation contract. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/quant_platform_kit/data/decision_price_series_artifact.py:121](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/data/decision_price_series_artifact.py#L121); [src/quant_platform_kit/data/decision_price_series_artifact.py:131](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/data/decision_price_series_artifact.py#L131).

### MD-018 — QuantPlatformKit: src/quant_platform_kit/data/multisource_assurance.py

- Role: manifest/binding/validation contract. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Independently injected source observations; no HTTP/broker/storage I/O. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Explicit adjustment_basis identifier and source root per observation. Adjustment: Compare compatible sources; never silently select provider.
- Time / session / calendar: Inherited/undeclared at this boundary; Per-source date_cutoff/session set; no external calendar fetched; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, date_cutoff, source.
- Evidence: [src/quant_platform_kit/data/multisource_assurance.py:1](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/data/multisource_assurance.py#L1); [src/quant_platform_kit/data/multisource_assurance.py:137](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/data/multisource_assurance.py#L137).

### MD-019 — QuantPlatformKit: src/quant_platform_kit/data/research_input.py

- Role: manifest/binding/validation contract. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, as_of, calendar_id, source, timezone.
- Evidence: [src/quant_platform_kit/data/research_input.py:32](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/data/research_input.py#L32); [src/quant_platform_kit/data/research_input.py:33](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/data/research_input.py#L33).

### MD-020 — QuantPlatformKit: src/quant_platform_kit/data/research_mandate.py

- Role: manifest/binding/validation contract. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: timezone.
- Evidence: [src/quant_platform_kit/data/research_mandate.py:7](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/data/research_mandate.py#L7); [src/quant_platform_kit/data/research_mandate.py:607](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/data/research_mandate.py#L607).

### MD-021 — QuantPlatformKit: src/quant_platform_kit/ibkr/runtime_inputs.py

- Role: series/feature consumer. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/quant_platform_kit/ibkr/runtime_inputs.py:21](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/ibkr/runtime_inputs.py#L21).

### MD-022 — QuantPlatformKit: src/quant_platform_kit/longbridge/portfolio.py

- Role: series/feature consumer. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: LongPort/LongBridge quote/history adapter. Market-specific quote entitlement not inspected.
- Price basis: Provider ForwardAdjust history; exact split/dividend mapping not independently certified. Adjustment: Native adjustment enum, distinct from last_done execution quote.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/quant_platform_kit/longbridge/portfolio.py:6](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/longbridge/portfolio.py#L6).

### MD-023 — QuantPlatformKit: src/quant_platform_kit/strategy_lifecycle/contracts.py

- Role: series/feature consumer. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: UTC; Inherited; no local completed-session proof established; XHKG/XNYS/XSHG.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: calendar_id, source, timezone.
- Evidence: [src/quant_platform_kit/strategy_lifecycle/contracts.py:9](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/strategy_lifecycle/contracts.py#L9); [src/quant_platform_kit/strategy_lifecycle/contracts.py:179](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/strategy_lifecycle/contracts.py#L179).

### MD-024 — QuantPlatformKit: src/quant_platform_kit/strategy_lifecycle/forward_observation_receipt.py

- Role: series/feature consumer. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/quant_platform_kit/strategy_lifecycle/forward_observation_receipt.py:129](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/strategy_lifecycle/forward_observation_receipt.py#L129).

### MD-025 — QuantPlatformKit: src/quant_platform_kit/strategy_lifecycle/live_equity.py

- Role: series/feature consumer. Proposed migration wave **0**. Medium: shared envelope/digest or adapter semantics affect multiple consumers; preserve frozen roots and existing ports.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: UTC; Inherited; no local completed-session proof established; XHKG/XNYS/XSHG.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: adjustment, as_of, calendar_id, source, timezone.
- Evidence: [src/quant_platform_kit/strategy_lifecycle/live_equity.py:13](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/strategy_lifecycle/live_equity.py#L13); [src/quant_platform_kit/strategy_lifecycle/live_equity.py:233](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/strategy_lifecycle/live_equity.py#L233); [src/quant_platform_kit/strategy_lifecycle/live_equity.py:879](https://github.com/QuantStrategyLab/QuantPlatformKit/blob/2b29055a5bd54501f370bc6c1b2b2005b305848c/src/quant_platform_kit/strategy_lifecycle/live_equity.py#L879).

### MD-026 — CnEquitySnapshotPipelines: src/cn_equity_snapshot_pipelines/akshare_market_history.py

- Role: provider acquisition/normalization. Proposed migration wave **1**. Medium/high: preserve source rights, basis, session and immutable old datasets; cloud-only conformance before adoption.
- Provider / plan: AkShare underlying public endpoint; Tencent qfq / Yahoo adjclose selectable in market-history adapter. Public endpoint access/rights not verified; no paid subscription assumed.
- Price basis: Provider-specific akshare_qfq / tencent_qfq / tencent_qfq_identity / yahoo_adjusted_close; not proven equivalent. Adjustment: Provider forward adjustment; hybrid path can select another provider; explicit source identity required.
- Time / session / calendar: UTC; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: end_date, price_basis, source, start_date, timezone.
- Evidence: [src/cn_equity_snapshot_pipelines/akshare_market_history.py:11](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/akshare_market_history.py#L11); [src/cn_equity_snapshot_pipelines/akshare_market_history.py:40](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/akshare_market_history.py#L40).

### MD-027 — CnEquitySnapshotPipelines: src/cn_equity_snapshot_pipelines/akshare_staging.py

- Role: provider acquisition/normalization. Proposed migration wave **1**. Medium/high: preserve source rights, basis, session and immutable old datasets; cloud-only conformance before adoption.
- Provider / plan: AkShare stock_zh_a_hist and factor/dividend endpoints. Public endpoint access/rights not verified; no paid subscription assumed.
- Price basis: AkShare qfq history. Adjustment: Server-side adjust=qfq; factor and dividend observations are separate inputs.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, timezone.
- Evidence: [src/cn_equity_snapshot_pipelines/akshare_staging.py:4](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/akshare_staging.py#L4); [src/cn_equity_snapshot_pipelines/akshare_staging.py:40](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/akshare_staging.py#L40); [src/cn_equity_snapshot_pipelines/akshare_staging.py:79](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/akshare_staging.py#L79).

### MD-028 — CryptoLivePoolPipelines: src/binance_client.py

- Role: provider acquisition/normalization. Proposed migration wave **1**. Medium/high: preserve source rights, basis, session and immutable old datasets; cloud-only conformance before adoption.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: end_date, output_path, start_date.
- Evidence: [src/binance_client.py:56](https://github.com/QuantStrategyLab/CryptoLivePoolPipelines/blob/deb2298b31fd2516dba9ac3e65e85137b3e54d09/src/binance_client.py#L56).

### MD-029 — HkEquitySnapshotPipelines: src/hk_equity_snapshot_pipelines/low_vol_dividend_longbridge_snapshot.py

- Role: provider acquisition/normalization. Proposed migration wave **1**. Medium/high: preserve source rights, basis, session and immutable old datasets; cloud-only conformance before adoption.
- Provider / plan: LongPort/LongBridge quote/history adapter. Market-specific quote entitlement not inspected.
- Price basis: Provider ForwardAdjust history; exact split/dividend mapping not independently certified. Adjustment: Native adjustment enum, distinct from last_done execution quote.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, timezone.
- Evidence: [src/hk_equity_snapshot_pipelines/low_vol_dividend_longbridge_snapshot.py:7](https://github.com/QuantStrategyLab/HkEquitySnapshotPipelines/blob/27490948fb83d121d864cfc426483a5ba0122410/src/hk_equity_snapshot_pipelines/low_vol_dividend_longbridge_snapshot.py#L7); [src/hk_equity_snapshot_pipelines/low_vol_dividend_longbridge_snapshot.py:27](https://github.com/QuantStrategyLab/HkEquitySnapshotPipelines/blob/27490948fb83d121d864cfc426483a5ba0122410/src/hk_equity_snapshot_pipelines/low_vol_dividend_longbridge_snapshot.py#L27); [src/hk_equity_snapshot_pipelines/low_vol_dividend_longbridge_snapshot.py:480](https://github.com/QuantStrategyLab/HkEquitySnapshotPipelines/blob/27490948fb83d121d864cfc426483a5ba0122410/src/hk_equity_snapshot_pipelines/low_vol_dividend_longbridge_snapshot.py#L480).

### MD-030 — HkEquitySnapshotPipelines: src/hk_equity_snapshot_pipelines/low_vol_dividend_public_snapshot.py

- Role: provider acquisition/normalization. Proposed migration wave **1**. Medium/high: preserve source rights, basis, session and immutable old datasets; cloud-only conformance before adoption.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, timezone.
- Evidence: [src/hk_equity_snapshot_pipelines/low_vol_dividend_public_snapshot.py:6](https://github.com/QuantStrategyLab/HkEquitySnapshotPipelines/blob/27490948fb83d121d864cfc426483a5ba0122410/src/hk_equity_snapshot_pipelines/low_vol_dividend_public_snapshot.py#L6); [src/hk_equity_snapshot_pipelines/low_vol_dividend_public_snapshot.py:30](https://github.com/QuantStrategyLab/HkEquitySnapshotPipelines/blob/27490948fb83d121d864cfc426483a5ba0122410/src/hk_equity_snapshot_pipelines/low_vol_dividend_public_snapshot.py#L30); [src/hk_equity_snapshot_pipelines/low_vol_dividend_public_snapshot.py:124](https://github.com/QuantStrategyLab/HkEquitySnapshotPipelines/blob/27490948fb83d121d864cfc426483a5ba0122410/src/hk_equity_snapshot_pipelines/low_vol_dividend_public_snapshot.py#L124).

### MD-031 — HkEquityStrategies: src/hk_equity_strategies/backtest/yfinance_market_data.py

- Role: provider acquisition/normalization. Proposed migration wave **1**. Medium/high: preserve source rights, basis, session and immutable old datasets; cloud-only conformance before adoption.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/hk_equity_strategies/backtest/yfinance_market_data.py:34](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/backtest/yfinance_market_data.py#L34); [src/hk_equity_strategies/backtest/yfinance_market_data.py:54](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/backtest/yfinance_market_data.py#L54); [src/hk_equity_strategies/backtest/yfinance_market_data.py:79](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/backtest/yfinance_market_data.py#L79).

### MD-032 — MarketSignalSources: src/market_signal_sources/providers/treasury_rates.py

- Role: provider acquisition/normalization. Proposed migration wave **1**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: US Treasury published rates. Public-source rate adapter; reuse/availability terms require dataset policy.
- Price basis: Not a price: rate tenor/unit and observation/availability/revision required. Adjustment: No price adjustment.
- Time / session / calendar: Inherited/undeclared at this boundary; Rate observation/publication day, not equity close; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: feed, timezone.
- Evidence: [src/market_signal_sources/providers/treasury_rates.py:3](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/src/market_signal_sources/providers/treasury_rates.py#L3); [src/market_signal_sources/providers/treasury_rates.py:25](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/src/market_signal_sources/providers/treasury_rates.py#L25).

### MD-033 — QuantAdvisorResearch: src/quant_advisor_research/market_confirmation.py

- Role: provider acquisition/normalization. Proposed migration wave **1**. Medium/high: preserve source rights, basis, session and immutable old datasets; cloud-only conformance before adoption.
- Provider / plan: Yahoo chart, direct then configured proxy paths. Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: Prefers adjclose; row can fall back to quote close when adjusted value missing. Adjustment: No coherent OHLC transformation here (close-only PriceBar); missing adjusted data changes effective basis.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/quant_advisor_research/market_confirmation.py:17](https://github.com/QuantStrategyLab/QuantAdvisorResearch/blob/eac68deafc46e77befa019b9670f1cd96e1d41b1/src/quant_advisor_research/market_confirmation.py#L17); [src/quant_advisor_research/market_confirmation.py:432](https://github.com/QuantStrategyLab/QuantAdvisorResearch/blob/eac68deafc46e77befa019b9670f1cd96e1d41b1/src/quant_advisor_research/market_confirmation.py#L432).

### MD-034 — QuantStrategyPlugins: src/quant_strategy_plugins/yfinance_prices.py

- Role: provider acquisition/normalization. Proposed migration wave **1**. Medium/high: preserve source rights, basis, session and immutable old datasets; cloud-only conformance before adoption.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): YFINANCE_PROXY; data parameters/schema fields: as_of.
- Evidence: [src/quant_strategy_plugins/yfinance_prices.py:17](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/yfinance_prices.py#L17); [src/quant_strategy_plugins/yfinance_prices.py:177](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/yfinance_prices.py#L177); [src/quant_strategy_plugins/yfinance_prices.py:213](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/yfinance_prices.py#L213).

### MD-035 — ResearchSignalContextPipelines: scripts/build_theme_momentum_snapshot.py

- Role: provider acquisition/normalization. Proposed migration wave **1**. Medium/high: preserve source rights, basis, session and immutable old datasets; cloud-only conformance before adoption.
- Provider / plan: Yahoo chart or explicitly supplied price CSV. Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: Yahoo adjclose preferred, quote.close fallback per missing row; CSV basis inherited. Adjustment: Close-only normalization; adjusted-value fallback is a semantic change, not certified equivalent.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, start_date.
- Evidence: [scripts/build_theme_momentum_snapshot.py:16](https://github.com/QuantStrategyLab/ResearchSignalContextPipelines/blob/a41745a925c2d676df00c3111f6f75f5bb236288/scripts/build_theme_momentum_snapshot.py#L16); [scripts/build_theme_momentum_snapshot.py:63](https://github.com/QuantStrategyLab/ResearchSignalContextPipelines/blob/a41745a925c2d676df00c3111f6f75f5bb236288/scripts/build_theme_momentum_snapshot.py#L63).

### MD-036 — UsEquitySnapshotPipelines: .github/workflows/alpaca-sip-access-diagnostic.yml

- Role: provider acquisition/normalization. Proposed migration wave **1**. Medium/high: preserve source rights, basis, session and immutable old datasets; cloud-only conformance before adoption.
- Provider / plan: Alpaca (SIP unless this row explicitly says otherwise). Owner Basic/free: recent SIP excluded; require end <= now-16min; IEX recent is a distinct feed.
- Price basis: Declared vendor adjustment; see basis anchor (legacy total_return_adjusted is not certified wealth index). Adjustment: Alpaca server adjustment; retain actual feed/adjustment request and source digest.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider-adjusted events; independent full action/PIT history not established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY, ALPACA_AUTHENTICATION_FAILED, ALPACA_RATE_LIMITED, ALPACA_REQUEST_REJECTED, ALPACA_SECRET_NOT_CONFIGURED, ALPACA_SIP_ACCESS_FORBIDDEN, ALPACA_SIP_ACCESS_OK, ALPACA_SIP_ACCESS_PARTIALLY_AVAILABLE, ALPACA_SIP_DIAGNOSTIC, ALPACA_TRANSPORT_UNAVAILABLE; data parameters/schema fields: adjustment, feed.
- Evidence: [.github/workflows/alpaca-sip-access-diagnostic.yml:65](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/.github/workflows/alpaca-sip-access-diagnostic.yml#L65).

### MD-037 — UsEquitySnapshotPipelines: scripts/diagnose_twelve_data_daily.py

- Role: provider acquisition/normalization. Proposed migration wave **1**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Twelve Data split-only source + Yahoo independent verifier (per frozen contract). Provider tier not queried; existing license/rate and two-source gates remain.
- Price basis: split_adjusted (candidate-specific source-assurance policy). Adjustment: Twelve adjust=splits / Yahoo quote close, no dividend-adjusted substitution.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): TWELVE_DATA_API_KEY; No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/diagnose_twelve_data_daily.py:1](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/diagnose_twelve_data_daily.py#L1).

### MD-038 — UsEquitySnapshotPipelines: scripts/rs04_cloud_archive.py

- Role: provider acquisition/normalization. Proposed migration wave **1**. Medium/high: preserve source rights, basis, session and immutable old datasets; cloud-only conformance before adoption.
- Provider / plan: Alpaca SIP bars + corporate-action endpoint, configured approved cloud archive. Owner Basic/free: recent SIP excluded; require end <= now-16min; IEX recent is a distinct feed.
- Price basis: raw_unadjusted requested (adjustment=raw). Adjustment: Raw bars and separate retained corporate-action pages; immutable archive manifest.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Provider-adjusted events; independent full action/PIT history not established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY, RS04_INPUT_ROOT; data parameters/schema fields: adjustment, feed, input_root, source, timezone.
- Evidence: [scripts/rs04_cloud_archive.py:16](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/rs04_cloud_archive.py#L16); [scripts/rs04_cloud_archive.py:160](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/rs04_cloud_archive.py#L160); [scripts/rs04_cloud_archive.py:207](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/rs04_cloud_archive.py#L207).

### MD-039 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/pipelines/global_etf_rotation_snapshot.py

- Role: provider acquisition/normalization. Proposed migration wave **1**. Medium/high: preserve source rights, basis, session and immutable old datasets; cloud-only conformance before adoption.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, output_dir.
- Evidence: [src/us_equity_snapshot_pipelines/pipelines/global_etf_rotation_snapshot.py:21](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/pipelines/global_etf_rotation_snapshot.py#L21); [src/us_equity_snapshot_pipelines/pipelines/global_etf_rotation_snapshot.py:136](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/pipelines/global_etf_rotation_snapshot.py#L136).

### MD-040 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/twelve_data_daily.py

- Role: provider acquisition/normalization. Proposed migration wave **1**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Twelve Data split-only source + Yahoo independent verifier (per frozen contract). Provider tier not queried; existing license/rate and two-source gates remain.
- Price basis: split_adjusted (candidate-specific source-assurance policy). Adjustment: Twelve adjust=splits / Yahoo quote close, no dividend-adjusted substitution.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: source.
- Evidence: [src/us_equity_snapshot_pipelines/twelve_data_daily.py:29](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/twelve_data_daily.py#L29); [src/us_equity_snapshot_pipelines/twelve_data_daily.py:142](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/twelve_data_daily.py#L142).

### MD-041 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/yahoo_finance_daily.py

- Role: provider acquisition/normalization. Proposed migration wave **1**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_adjusted explicitly declared by assurance adapter. Adjustment: Yahoo chart quote close selected, not dividend-aware adjclose.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: price_field.
- Evidence: [src/us_equity_snapshot_pipelines/yahoo_finance_daily.py:3](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/yahoo_finance_daily.py#L3); [src/us_equity_snapshot_pipelines/yahoo_finance_daily.py:30](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/yahoo_finance_daily.py#L30).

### MD-042 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/yfinance_prices.py

- Role: provider acquisition/normalization. Proposed migration wave **1**. Medium/high: preserve source rights, basis, session and immutable old datasets; cloud-only conformance before adoption.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: Selectable adjusted_close (dividend-aware) or close (split-only); default adjusted_close. Adjustment: auto_adjust derived from price_field; chart OHLC scaled by adjclose/close for adjusted mode.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): YFINANCE_PROXY; data parameters/schema fields: as_of, price_field, timezone.
- Evidence: [src/us_equity_snapshot_pipelines/yfinance_prices.py:6](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/yfinance_prices.py#L6); [src/us_equity_snapshot_pipelines/yfinance_prices.py:22](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/yfinance_prices.py#L22); [src/us_equity_snapshot_pipelines/yfinance_prices.py:35](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/yfinance_prices.py#L35).

### MD-043 — UsEquitySnapshotPipelines: scripts/acquire_batch_a_v2_price_snapshots_alpaca.py

- Role: provider acquisition entry/contract. Proposed migration wave **1**. Medium/high: preserve source rights, basis, session and immutable old datasets; cloud-only conformance before adoption.
- Provider / plan: Alpaca (SIP unless this row explicitly says otherwise). Owner Basic/free: recent SIP excluded; require end <= now-16min; IEX recent is a distinct feed.
- Price basis: split_dividend_adjusted requested with Alpaca adjustment=all; legacy candidate label total_return_adjusted retained. Adjustment: Alpaca server adjustment; retain actual feed/adjustment request and source digest.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Provider-adjusted events; independent full action/PIT history not established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY; data parameters/schema fields: adjustment, as_of, feed, price_field, timezone.
- Evidence: [scripts/acquire_batch_a_v2_price_snapshots_alpaca.py:32](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_batch_a_v2_price_snapshots_alpaca.py#L32); [scripts/acquire_batch_a_v2_price_snapshots_alpaca.py:33](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_batch_a_v2_price_snapshots_alpaca.py#L33); [scripts/acquire_batch_a_v2_price_snapshots_alpaca.py:414](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_batch_a_v2_price_snapshots_alpaca.py#L414).

### MD-044 — UsEquitySnapshotPipelines: scripts/acquire_global_etf_learning_inputs_alpaca.py

- Role: provider acquisition entry/contract. Proposed migration wave **1**. Medium/high: preserve source rights, basis, session and immutable old datasets; cloud-only conformance before adoption.
- Provider / plan: Alpaca (SIP unless this row explicitly says otherwise). Owner Basic/free: recent SIP excluded; require end <= now-16min; IEX recent is a distinct feed.
- Price basis: split_dividend_adjusted requested with Alpaca adjustment=all; legacy candidate label total_return_adjusted retained. Adjustment: Alpaca server adjustment; retain actual feed/adjustment request and source digest.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Provider-adjusted events; independent full action/PIT history not established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, feed.
- Evidence: [scripts/acquire_global_etf_learning_inputs_alpaca.py:59](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_global_etf_learning_inputs_alpaca.py#L59); [scripts/acquire_global_etf_learning_inputs_alpaca.py:71](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_global_etf_learning_inputs_alpaca.py#L71); [scripts/acquire_global_etf_learning_inputs_alpaca.py:79](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_global_etf_learning_inputs_alpaca.py#L79).

### MD-045 — UsEquitySnapshotPipelines: scripts/acquire_qqqm_boxx_raw_history.py

- Role: provider acquisition entry/contract. Proposed migration wave **1**. Medium/high: preserve source rights, basis, session and immutable old datasets; cloud-only conformance before adoption.
- Provider / plan: Alpaca SIP. Owner Basic/free: recent SIP excluded; require end <= now-16min; IEX recent is a distinct feed.
- Price basis: raw_unadjusted requested (adjustment=raw). Adjustment: Provider raw mode; corporate actions must be handled separately.
- Time / session / calendar: America/New_York/UTC; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Provider-adjusted events; independent full action/PIT history not established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY; data parameters/schema fields: adjustment, feed, source, timezone.
- Evidence: [scripts/acquire_qqqm_boxx_raw_history.py:121](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_qqqm_boxx_raw_history.py#L121); [scripts/acquire_qqqm_boxx_raw_history.py:234](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_qqqm_boxx_raw_history.py#L234); [scripts/acquire_qqqm_boxx_raw_history.py:294](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_qqqm_boxx_raw_history.py#L294).

### MD-046 — UsEquitySnapshotPipelines: scripts/acquire_soxl_core_only_free_split_close_p1.py

- Role: provider acquisition entry/contract. Proposed migration wave **1**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Twelve Data split-only source + Yahoo independent verifier (per frozen contract). Provider tier not queried; existing license/rate and two-source gates remain.
- Price basis: split_adjusted (candidate-specific source-assurance policy). Adjustment: Twelve adjust=splits / Yahoo quote close, no dividend-adjusted substitution.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: source.
- Evidence: [scripts/acquire_soxl_core_only_free_split_close_p1.py:1](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_soxl_core_only_free_split_close_p1.py#L1).

### MD-047 — UsEquitySnapshotPipelines: scripts/acquire_soxl_core_only_p1_inputs_alpaca.py

- Role: provider acquisition entry/contract. Proposed migration wave **1**. Medium/high: preserve source rights, basis, session and immutable old datasets; cloud-only conformance before adoption.
- Provider / plan: Alpaca (SIP unless this row explicitly says otherwise). Owner Basic/free: recent SIP excluded; require end <= now-16min; IEX recent is a distinct feed.
- Price basis: split_dividend_adjusted requested with Alpaca adjustment=all; legacy candidate label total_return_adjusted retained. Adjustment: Alpaca server adjustment; retain actual feed/adjustment request and source digest.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Provider-adjusted events; independent full action/PIT history not established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, calendar_id, feed, timezone.
- Evidence: [scripts/acquire_soxl_core_only_p1_inputs_alpaca.py:159](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_soxl_core_only_p1_inputs_alpaca.py#L159); [scripts/acquire_soxl_core_only_p1_inputs_alpaca.py:161](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_soxl_core_only_p1_inputs_alpaca.py#L161); [scripts/acquire_soxl_core_only_p1_inputs_alpaca.py:210](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_soxl_core_only_p1_inputs_alpaca.py#L210).

### MD-048 — UsEquitySnapshotPipelines: scripts/acquire_soxl_tqqq_promotion_inputs_ibkr.py

- Role: provider acquisition entry/contract. Proposed migration wave **1**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: IBKR historical adapter / injected IBKR artifact. Historical-data entitlement, pacing and isolated approved session required; actual plan unverified.
- Price basis: split_dividend_adjusted for ADJUSTED_LAST; split_adjusted for TRADES; actual selected mode must be pinned. Adjustment: Provider-side historical adjustment; TRADES is not raw_unadjusted.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/acquire_soxl_tqqq_promotion_inputs_ibkr.py:114](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_soxl_tqqq_promotion_inputs_ibkr.py#L114).

### MD-049 — UsEquitySnapshotPipelines: scripts/acquire_tqqq_core_only_free_ohlcv_p1.py

- Role: provider acquisition entry/contract. Proposed migration wave **1**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Twelve Data split-only source + Yahoo independent verifier (per frozen contract). Provider tier not queried; existing license/rate and two-source gates remain.
- Price basis: split_adjusted (candidate-specific source-assurance policy). Adjustment: Twelve adjust=splits / Yahoo quote close, no dividend-adjusted substitution.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/acquire_tqqq_core_only_free_ohlcv_p1.py:7](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_tqqq_core_only_free_ohlcv_p1.py#L7).

### MD-050 — UsEquitySnapshotPipelines: scripts/acquire_tqqq_core_only_p1_inputs_alpaca.py

- Role: provider acquisition entry/contract. Proposed migration wave **1**. Medium/high: preserve source rights, basis, session and immutable old datasets; cloud-only conformance before adoption.
- Provider / plan: Alpaca (SIP unless this row explicitly says otherwise). Owner Basic/free: recent SIP excluded; require end <= now-16min; IEX recent is a distinct feed.
- Price basis: split_dividend_adjusted requested with Alpaca adjustment=all; legacy candidate label total_return_adjusted retained. Adjustment: Alpaca server adjustment; retain actual feed/adjustment request and source digest.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Provider-adjusted events; independent full action/PIT history not established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, calendar_id, feed, timezone.
- Evidence: [scripts/acquire_tqqq_core_only_p1_inputs_alpaca.py:177](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_tqqq_core_only_p1_inputs_alpaca.py#L177); [scripts/acquire_tqqq_core_only_p1_inputs_alpaca.py:179](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_tqqq_core_only_p1_inputs_alpaca.py#L179); [scripts/acquire_tqqq_core_only_p1_inputs_alpaca.py:227](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_tqqq_core_only_p1_inputs_alpaca.py#L227).

### MD-051 — UsEquitySnapshotPipelines: scripts/acquire_tqqq_core_only_p1_inputs_ibkr.py

- Role: provider acquisition entry/contract. Proposed migration wave **1**. Medium/high: preserve source rights, basis, session and immutable old datasets; cloud-only conformance before adoption.
- Provider / plan: IBKR historical adapter / injected IBKR artifact. Historical-data entitlement, pacing and isolated approved session required; actual plan unverified.
- Price basis: split_dividend_adjusted for ADJUSTED_LAST; split_adjusted for TRADES; actual selected mode must be pinned. Adjustment: Provider-side historical adjustment; TRADES is not raw_unadjusted.
- Time / session / calendar: America/New_York/UTC; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: calendar_id, feed, timezone.
- Evidence: [scripts/acquire_tqqq_core_only_p1_inputs_ibkr.py:32](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_tqqq_core_only_p1_inputs_ibkr.py#L32); [scripts/acquire_tqqq_core_only_p1_inputs_ibkr.py:69](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_tqqq_core_only_p1_inputs_ibkr.py#L69); [scripts/acquire_tqqq_core_only_p1_inputs_ibkr.py:76](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/acquire_tqqq_core_only_p1_inputs_ibkr.py#L76).

### MD-052 — BinancePlatform: research/backtest.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [research/backtest.py:154](https://github.com/QuantStrategyLab/BinancePlatform/blob/76937ed06de1c6e5a76e807892f8bca4030ab4d1/research/backtest.py#L154).

### MD-053 — BinancePlatform: run_cycle_replay.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: timezone.
- Evidence: [run_cycle_replay.py:8](https://github.com/QuantStrategyLab/BinancePlatform/blob/76937ed06de1c6e5a76e807892f8bca4030ab4d1/run_cycle_replay.py#L8); [run_cycle_replay.py:83](https://github.com/QuantStrategyLab/BinancePlatform/blob/76937ed06de1c6e5a76e807892f8bca4030ab4d1/run_cycle_replay.py#L83).

### MD-054 — CharlesSchwabPlatform: scripts/release_evidence_parity_check.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Schwab history/quotes via injected broker adapter. Authorized API/account data entitlement not inspected.
- Price basis: Existing history path declares split_adjusted; execution quotes use contemporaneous units. Adjustment: Broker convention; no independent distribution/factor verification in this inventory.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/release_evidence_parity_check.py:112](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/scripts/release_evidence_parity_check.py#L112); [scripts/release_evidence_parity_check.py:207](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/scripts/release_evidence_parity_check.py#L207); [scripts/release_evidence_parity_check.py:227](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/scripts/release_evidence_parity_check.py#L227).

### MD-055 — CharlesSchwabPlatform: scripts/strategy_parity_check.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Schwab history/quotes via injected broker adapter. Authorized API/account data entitlement not inspected.
- Price basis: Existing history path declares split_adjusted; execution quotes use contemporaneous units. Adjustment: Broker convention; no independent distribution/factor verification in this inventory.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/strategy_parity_check.py:72](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/scripts/strategy_parity_check.py#L72); [scripts/strategy_parity_check.py:79](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/scripts/strategy_parity_check.py#L79).

### MD-056 — CnEquitySnapshotPipelines: src/cn_equity_snapshot_pipelines/dividend_quality.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, timezone.
- Evidence: [src/cn_equity_snapshot_pipelines/dividend_quality.py:4](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/dividend_quality.py#L4); [src/cn_equity_snapshot_pipelines/dividend_quality.py:15](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/dividend_quality.py#L15).

### MD-057 — CnEquitySnapshotPipelines: src/cn_equity_snapshot_pipelines/index_membership.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: timezone.
- Evidence: [src/cn_equity_snapshot_pipelines/index_membership.py:36](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/index_membership.py#L36); [src/cn_equity_snapshot_pipelines/index_membership.py:323](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/index_membership.py#L323).

### MD-058 — CnEquitySnapshotPipelines: src/cn_equity_snapshot_pipelines/akshare_enrichment.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: AkShare underlying public endpoint; Tencent qfq / Yahoo adjclose selectable in market-history adapter. Public endpoint access/rights not verified; no paid subscription assumed.
- Price basis: Provider-specific akshare_qfq / tencent_qfq / tencent_qfq_identity / yahoo_adjusted_close; not proven equivalent. Adjustment: Provider forward adjustment; hybrid path can select another provider; explicit source identity required.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: adjustment, as_of, timezone.
- Evidence: [src/cn_equity_snapshot_pipelines/akshare_enrichment.py:3](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/akshare_enrichment.py#L3); [src/cn_equity_snapshot_pipelines/akshare_enrichment.py:55](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/akshare_enrichment.py#L55); [src/cn_equity_snapshot_pipelines/akshare_enrichment.py:70](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/akshare_enrichment.py#L70).

### MD-059 — CnEquitySnapshotPipelines: src/cn_equity_snapshot_pipelines/index_etf_input_publish.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: AkShare underlying public endpoint; Tencent qfq / Yahoo adjclose selectable in market-history adapter. Public endpoint access/rights not verified; no paid subscription assumed.
- Price basis: Provider-specific akshare_qfq / tencent_qfq / tencent_qfq_identity / yahoo_adjusted_close; not proven equivalent. Adjustment: Provider forward adjustment; hybrid path can select another provider; explicit source identity required.
- Time / session / calendar: Asia/Shanghai; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: adjustment, calendar_id, end_date, source, timezone.
- Evidence: [src/cn_equity_snapshot_pipelines/index_etf_input_publish.py:11](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/index_etf_input_publish.py#L11); [src/cn_equity_snapshot_pipelines/index_etf_input_publish.py:65](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/index_etf_input_publish.py#L65); [src/cn_equity_snapshot_pipelines/index_etf_input_publish.py:189](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/index_etf_input_publish.py#L189).

### MD-060 — CnEquitySnapshotPipelines: src/cn_equity_snapshot_pipelines/research_input_publish.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: AkShare underlying public endpoint; Tencent qfq / Yahoo adjclose selectable in market-history adapter. Public endpoint access/rights not verified; no paid subscription assumed.
- Price basis: Provider-specific akshare_qfq / tencent_qfq / tencent_qfq_identity / yahoo_adjusted_close; not proven equivalent. Adjustment: Provider forward adjustment; hybrid path can select another provider; explicit source identity required.
- Time / session / calendar: Asia/Shanghai; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: adjustment, calendar_id, price_basis, source, timezone.
- Evidence: [src/cn_equity_snapshot_pipelines/research_input_publish.py:8](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/research_input_publish.py#L8); [src/cn_equity_snapshot_pipelines/research_input_publish.py:58](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/research_input_publish.py#L58); [src/cn_equity_snapshot_pipelines/research_input_publish.py:77](https://github.com/QuantStrategyLab/CnEquitySnapshotPipelines/blob/3ac8ad07a26ef5988284c7169dadd3b3b83cba44/src/cn_equity_snapshot_pipelines/research_input_publish.py#L77).

### MD-061 — CnEquityStrategies: scripts/research_cn_chinext_tactical_rotation_proxy_backtest.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/research_cn_chinext_tactical_rotation_proxy_backtest.py:30](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_chinext_tactical_rotation_proxy_backtest.py#L30); [scripts/research_cn_chinext_tactical_rotation_proxy_backtest.py:42](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_chinext_tactical_rotation_proxy_backtest.py#L42); [scripts/research_cn_chinext_tactical_rotation_proxy_backtest.py:55](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_chinext_tactical_rotation_proxy_backtest.py#L55).

### MD-062 — CnEquityStrategies: scripts/research_cn_index_etf_tactical_rotation_proxy_backtest.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/research_cn_index_etf_tactical_rotation_proxy_backtest.py:55](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_index_etf_tactical_rotation_proxy_backtest.py#L55); [scripts/research_cn_index_etf_tactical_rotation_proxy_backtest.py:71](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_index_etf_tactical_rotation_proxy_backtest.py#L71); [scripts/research_cn_index_etf_tactical_rotation_proxy_backtest.py:86](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_index_etf_tactical_rotation_proxy_backtest.py#L86).

### MD-063 — CnEquityStrategies: scripts/research_cn_industry_etf_rotation_validation.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/research_cn_industry_etf_rotation_validation.py:57](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_industry_etf_rotation_validation.py#L57); [scripts/research_cn_industry_etf_rotation_validation.py:79](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_industry_etf_rotation_validation.py#L79); [scripts/research_cn_industry_etf_rotation_validation.py:93](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_industry_etf_rotation_validation.py#L93).

### MD-064 — CnEquityStrategies: scripts/research_cn_thematic_stock_rotation_proxy.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/research_cn_thematic_stock_rotation_proxy.py:50](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_thematic_stock_rotation_proxy.py#L50); [scripts/research_cn_thematic_stock_rotation_proxy.py:72](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_thematic_stock_rotation_proxy.py#L72); [scripts/research_cn_thematic_stock_rotation_proxy.py:118](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_thematic_stock_rotation_proxy.py#L118).

### MD-065 — CnEquityStrategies: scripts/run_walk_forward_backtest.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: output_path.
- Evidence: [scripts/run_walk_forward_backtest.py:83](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/run_walk_forward_backtest.py#L83); [scripts/run_walk_forward_backtest.py:338](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/run_walk_forward_backtest.py#L338).

### MD-066 — CnEquityStrategies: scripts/research_cn_chinext_growth_momentum_quality_proxy_backtest.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [scripts/research_cn_chinext_growth_momentum_quality_proxy_backtest.py:43](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_chinext_growth_momentum_quality_proxy_backtest.py#L43); [scripts/research_cn_chinext_growth_momentum_quality_proxy_backtest.py:196](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_chinext_growth_momentum_quality_proxy_backtest.py#L196); [scripts/research_cn_chinext_growth_momentum_quality_proxy_backtest.py:278](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_chinext_growth_momentum_quality_proxy_backtest.py#L278).

### MD-067 — CnEquityStrategies: scripts/research_cn_dividend_quality_snapshot_proxy_backtest.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Request/process memory cache or caller-selected store; source/basis cache identity requires review.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [scripts/research_cn_dividend_quality_snapshot_proxy_backtest.py:58](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_dividend_quality_snapshot_proxy_backtest.py#L58); [scripts/research_cn_dividend_quality_snapshot_proxy_backtest.py:102](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_dividend_quality_snapshot_proxy_backtest.py#L102); [scripts/research_cn_dividend_quality_snapshot_proxy_backtest.py:170](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_dividend_quality_snapshot_proxy_backtest.py#L170).

### MD-068 — CnEquityStrategies: scripts/research_cn_etf_momentum_stock_combo_proxy_backtest.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/research_cn_etf_momentum_stock_combo_proxy_backtest.py:42](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_etf_momentum_stock_combo_proxy_backtest.py#L42); [scripts/research_cn_etf_momentum_stock_combo_proxy_backtest.py:54](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_etf_momentum_stock_combo_proxy_backtest.py#L54).

### MD-069 — CnEquityStrategies: scripts/research_cn_etf_pool_and_params_comparison.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/research_cn_etf_pool_and_params_comparison.py:62](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_etf_pool_and_params_comparison.py#L62); [scripts/research_cn_etf_pool_and_params_comparison.py:72](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_etf_pool_and_params_comparison.py#L72); [scripts/research_cn_etf_pool_and_params_comparison.py:85](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_etf_pool_and_params_comparison.py#L85).

### MD-070 — CnEquityStrategies: scripts/research_cn_live_candidate_evaluation.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/research_cn_live_candidate_evaluation.py:43](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_live_candidate_evaluation.py#L43).

### MD-071 — CnEquityStrategies: scripts/research_cn_strategy_validation.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/research_cn_strategy_validation.py:36](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_strategy_validation.py#L36); [scripts/research_cn_strategy_validation.py:47](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_strategy_validation.py#L47); [scripts/research_cn_strategy_validation.py:60](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_strategy_validation.py#L60).

### MD-072 — CnEquityStrategies: scripts/research_cn_us_long_horizon_comparison.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Request/process memory cache or caller-selected store; source/basis cache identity requires review.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/research_cn_us_long_horizon_comparison.py:103](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_us_long_horizon_comparison.py#L103); [scripts/research_cn_us_long_horizon_comparison.py:130](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_us_long_horizon_comparison.py#L130); [scripts/research_cn_us_long_horizon_comparison.py:172](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/scripts/research_cn_us_long_horizon_comparison.py#L172).

### MD-073 — CnEquityStrategies: src/cn_equity_strategies/backtest/dividend_snapshot_proxy_helpers.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/cn_equity_strategies/backtest/dividend_snapshot_proxy_helpers.py:47](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/backtest/dividend_snapshot_proxy_helpers.py#L47); [src/cn_equity_strategies/backtest/dividend_snapshot_proxy_helpers.py:49](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/backtest/dividend_snapshot_proxy_helpers.py#L49).

### MD-074 — CnEquityStrategies: src/cn_equity_strategies/backtest/index_etf_research_job.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/cn_equity_strategies/backtest/index_etf_research_job.py:16](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/backtest/index_etf_research_job.py#L16); [src/cn_equity_strategies/backtest/index_etf_research_job.py:81](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/backtest/index_etf_research_job.py#L81).

### MD-075 — CnEquityStrategies: src/cn_equity_strategies/backtest/index_etf_strict_runner.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Asia/Shanghai; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: adjustment, end_date, start_date, timezone.
- Evidence: [src/cn_equity_strategies/backtest/index_etf_strict_runner.py:3](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/backtest/index_etf_strict_runner.py#L3); [src/cn_equity_strategies/backtest/index_etf_strict_runner.py:12](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/backtest/index_etf_strict_runner.py#L12); [src/cn_equity_strategies/backtest/index_etf_strict_runner.py:121](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/backtest/index_etf_strict_runner.py#L121).

### MD-076 — CnEquityStrategies: src/cn_equity_strategies/backtest/orchestrator_runner.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; XSHG.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: calendar_id, lookback_days, timezone.
- Evidence: [src/cn_equity_strategies/backtest/orchestrator_runner.py:5](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/backtest/orchestrator_runner.py#L5); [src/cn_equity_strategies/backtest/orchestrator_runner.py:36](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/backtest/orchestrator_runner.py#L36).

### MD-077 — CnEquityStrategies: src/cn_equity_strategies/backtest/proxy_simulator.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/cn_equity_strategies/backtest/proxy_simulator.py:9](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/backtest/proxy_simulator.py#L9); [src/cn_equity_strategies/backtest/proxy_simulator.py:109](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/backtest/proxy_simulator.py#L109).

### MD-078 — CnEquityStrategies: src/cn_equity_strategies/catalog.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/cn_equity_strategies/catalog.py:18](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/catalog.py#L18).

### MD-079 — CnEquityStrategies: src/cn_equity_strategies/combo_manifests.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/cn_equity_strategies/combo_manifests.py:12](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/combo_manifests.py#L12).

### MD-080 — CnEquityStrategies: src/cn_equity_strategies/research/momentum_stock_history.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/cn_equity_strategies/research/momentum_stock_history.py:18](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/research/momentum_stock_history.py#L18); [src/cn_equity_strategies/research/momentum_stock_history.py:35](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/research/momentum_stock_history.py#L35); [src/cn_equity_strategies/research/momentum_stock_history.py:62](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/research/momentum_stock_history.py#L62).

### MD-081 — CnEquityStrategies: src/cn_equity_strategies/runtime_adapters.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/cn_equity_strategies/runtime_adapters.py:11](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/runtime_adapters.py#L11).

### MD-082 — CnEquityStrategies: src/cn_equity_strategies/strategies/cn_chinext_growth_momentum_quality.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/cn_equity_strategies/strategies/cn_chinext_growth_momentum_quality.py:37](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/strategies/cn_chinext_growth_momentum_quality.py#L37).

### MD-083 — CnEquityStrategies: src/cn_equity_strategies/strategies/cn_chinext_growth_momentum_quality_snapshot.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/cn_equity_strategies/strategies/cn_chinext_growth_momentum_quality_snapshot.py:39](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/strategies/cn_chinext_growth_momentum_quality_snapshot.py#L39).

### MD-084 — CnEquityStrategies: src/cn_equity_strategies/strategies/cn_chinext_tactical_rotation.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/cn_equity_strategies/strategies/cn_chinext_tactical_rotation.py:34](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/strategies/cn_chinext_tactical_rotation.py#L34).

### MD-085 — CnEquityStrategies: src/cn_equity_strategies/strategies/cn_dividend_quality_snapshot.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/cn_equity_strategies/strategies/cn_dividend_quality_snapshot.py:43](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/strategies/cn_dividend_quality_snapshot.py#L43).

### MD-086 — CnEquityStrategies: src/cn_equity_strategies/strategies/cn_equity_combo.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment.
- Evidence: [src/cn_equity_strategies/strategies/cn_equity_combo.py:14](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/strategies/cn_equity_combo.py#L14); [src/cn_equity_strategies/strategies/cn_equity_combo.py:243](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/strategies/cn_equity_combo.py#L243).

### MD-087 — CnEquityStrategies: src/cn_equity_strategies/strategies/cn_index_etf_tactical_rotation.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/cn_equity_strategies/strategies/cn_index_etf_tactical_rotation.py:43](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/strategies/cn_index_etf_tactical_rotation.py#L43).

### MD-088 — CnEquityStrategies: src/cn_equity_strategies/strategies/cn_industry_etf_rotation.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/cn_equity_strategies/strategies/cn_industry_etf_rotation.py:33](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/strategies/cn_industry_etf_rotation.py#L33).

### MD-089 — CnEquityStrategies: src/cn_equity_strategies/strategies/cn_industry_etf_rotation_aggressive.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/cn_equity_strategies/strategies/cn_industry_etf_rotation_aggressive.py:35](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/strategies/cn_industry_etf_rotation_aggressive.py#L35).

### MD-090 — CnEquityStrategies: src/cn_equity_strategies/strategies/cn_star_growth_momentum_quality.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/cn_equity_strategies/strategies/cn_star_growth_momentum_quality.py:37](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/strategies/cn_star_growth_momentum_quality.py#L37).

### MD-091 — CnEquityStrategies: src/cn_equity_strategies/strategies/etf_rotation_core.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/cn_equity_strategies/strategies/etf_rotation_core.py:59](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/strategies/etf_rotation_core.py#L59); [src/cn_equity_strategies/strategies/etf_rotation_core.py:106](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/strategies/etf_rotation_core.py#L106).

### MD-092 — CnEquityStrategies: src/cn_equity_strategies/strategies/industry_etf_rotation_core.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/cn_equity_strategies/strategies/industry_etf_rotation_core.py:67](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/strategies/industry_etf_rotation_core.py#L67); [src/cn_equity_strategies/strategies/industry_etf_rotation_core.py:77](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/strategies/industry_etf_rotation_core.py#L77); [src/cn_equity_strategies/strategies/industry_etf_rotation_core.py:123](https://github.com/QuantStrategyLab/CnEquityStrategies/blob/ab06f26d95514e9e52931586cd769eb8dbae89cf/src/cn_equity_strategies/strategies/industry_etf_rotation_core.py#L123).

### MD-093 — CryptoLivePoolPipelines: scripts/download_history.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: end_date, raw_dir, start_date.
- Evidence: [scripts/download_history.py:21](https://github.com/QuantStrategyLab/CryptoLivePoolPipelines/blob/deb2298b31fd2516dba9ac3e65e85137b3e54d09/scripts/download_history.py#L21).

### MD-094 — CryptoLivePoolPipelines: src/external_data.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: UTC; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/external_data.py:48](https://github.com/QuantStrategyLab/CryptoLivePoolPipelines/blob/deb2298b31fd2516dba9ac3e65e85137b3e54d09/src/external_data.py#L48); [src/external_data.py:617](https://github.com/QuantStrategyLab/CryptoLivePoolPipelines/blob/deb2298b31fd2516dba9ac3e65e85137b3e54d09/src/external_data.py#L617).

### MD-095 — CryptoLivePoolPipelines: src/pipeline.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/pipeline.py:47](https://github.com/QuantStrategyLab/CryptoLivePoolPipelines/blob/deb2298b31fd2516dba9ac3e65e85137b3e54d09/src/pipeline.py#L47).

### MD-096 — CryptoLivePoolPipelines: src/utils.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/utils.py:130](https://github.com/QuantStrategyLab/CryptoLivePoolPipelines/blob/deb2298b31fd2516dba9ac3e65e85137b3e54d09/src/utils.py#L130); [src/utils.py:185](https://github.com/QuantStrategyLab/CryptoLivePoolPipelines/blob/deb2298b31fd2516dba9ac3e65e85137b3e54d09/src/utils.py#L185).

### MD-097 — CryptoLivePoolPipelines: scripts/export_lifecycle_preflight_inputs.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: UTC; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: output_dir.
- Evidence: [scripts/export_lifecycle_preflight_inputs.py:33](https://github.com/QuantStrategyLab/CryptoLivePoolPipelines/blob/deb2298b31fd2516dba9ac3e65e85137b3e54d09/scripts/export_lifecycle_preflight_inputs.py#L33); [scripts/export_lifecycle_preflight_inputs.py:49](https://github.com/QuantStrategyLab/CryptoLivePoolPipelines/blob/deb2298b31fd2516dba9ac3e65e85137b3e54d09/scripts/export_lifecycle_preflight_inputs.py#L49).

### MD-098 — CryptoLivePoolPipelines: src/backtest.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/backtest.py:46](https://github.com/QuantStrategyLab/CryptoLivePoolPipelines/blob/deb2298b31fd2516dba9ac3e65e85137b3e54d09/src/backtest.py#L46); [src/backtest.py:297](https://github.com/QuantStrategyLab/CryptoLivePoolPipelines/blob/deb2298b31fd2516dba9ac3e65e85137b3e54d09/src/backtest.py#L297).

### MD-099 — CryptoLivePoolPipelines: src/features.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/features.py:32](https://github.com/QuantStrategyLab/CryptoLivePoolPipelines/blob/deb2298b31fd2516dba9ac3e65e85137b3e54d09/src/features.py#L32).

### MD-100 — CryptoLivePoolPipelines: src/indicators.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/indicators.py:28](https://github.com/QuantStrategyLab/CryptoLivePoolPipelines/blob/deb2298b31fd2516dba9ac3e65e85137b3e54d09/src/indicators.py#L28).

### MD-101 — CryptoLivePoolPipelines: src/labels.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/labels.py:22](https://github.com/QuantStrategyLab/CryptoLivePoolPipelines/blob/deb2298b31fd2516dba9ac3e65e85137b3e54d09/src/labels.py#L22).

### MD-102 — CryptoStrategies: scripts/run_walk_forward_backtest.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: calendar_id, output_path.
- Evidence: [scripts/run_walk_forward_backtest.py:35](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/scripts/run_walk_forward_backtest.py#L35); [scripts/run_walk_forward_backtest.py:337](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/scripts/run_walk_forward_backtest.py#L337).

### MD-103 — CryptoStrategies: scripts/research_combo_dynamic_backtest.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: adjustment, as_of.
- Evidence: [scripts/research_combo_dynamic_backtest.py:7](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/scripts/research_combo_dynamic_backtest.py#L7); [scripts/research_combo_dynamic_backtest.py:74](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/scripts/research_combo_dynamic_backtest.py#L74).

### MD-104 — CryptoStrategies: scripts/research_crypto_combo_backtest.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/research_crypto_combo_backtest.py:142](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/scripts/research_crypto_combo_backtest.py#L142); [scripts/research_crypto_combo_backtest.py:181](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/scripts/research_crypto_combo_backtest.py#L181).

### MD-105 — CryptoStrategies: scripts/research_crypto_dca_backtest.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [scripts/research_crypto_dca_backtest.py:83](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/scripts/research_crypto_dca_backtest.py#L83); [scripts/research_crypto_dca_backtest.py:90](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/scripts/research_crypto_dca_backtest.py#L90).

### MD-106 — CryptoStrategies: src/crypto_strategies/backtest/combo_replay.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Request/process memory cache or caller-selected store; source/basis cache identity requires review.
- Config/env keys (names only): data parameters/schema fields: timezone.
- Evidence: [src/crypto_strategies/backtest/combo_replay.py:4](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/src/crypto_strategies/backtest/combo_replay.py#L4).

### MD-107 — CryptoStrategies: src/crypto_strategies/backtest/combo_simulator.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/crypto_strategies/backtest/combo_simulator.py:50](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/src/crypto_strategies/backtest/combo_simulator.py#L50); [src/crypto_strategies/backtest/combo_simulator.py:194](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/src/crypto_strategies/backtest/combo_simulator.py#L194).

### MD-108 — CryptoStrategies: src/crypto_strategies/backtest/live_pool_simulator.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/crypto_strategies/backtest/live_pool_simulator.py:265](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/src/crypto_strategies/backtest/live_pool_simulator.py#L265); [src/crypto_strategies/backtest/live_pool_simulator.py:350](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/src/crypto_strategies/backtest/live_pool_simulator.py#L350).

### MD-109 — CryptoStrategies: src/crypto_strategies/backtest/orchestrator_runner.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: calendar_id, lookback_days, timezone.
- Evidence: [src/crypto_strategies/backtest/orchestrator_runner.py:6](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/src/crypto_strategies/backtest/orchestrator_runner.py#L6); [src/crypto_strategies/backtest/orchestrator_runner.py:48](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/src/crypto_strategies/backtest/orchestrator_runner.py#L48).

### MD-110 — CryptoStrategies: src/crypto_strategies/strategies/crypto_btc_dca.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: UTC; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/crypto_strategies/strategies/crypto_btc_dca.py:78](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/src/crypto_strategies/strategies/crypto_btc_dca.py#L78); [src/crypto_strategies/strategies/crypto_btc_dca.py:221](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/src/crypto_strategies/strategies/crypto_btc_dca.py#L221).

### MD-111 — CryptoStrategies: src/crypto_strategies/strategies/crypto_equity_combo.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: adjustment.
- Evidence: [src/crypto_strategies/strategies/crypto_equity_combo.py:9](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/src/crypto_strategies/strategies/crypto_equity_combo.py#L9); [src/crypto_strategies/strategies/crypto_equity_combo.py:87](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/src/crypto_strategies/strategies/crypto_equity_combo.py#L87).

### MD-112 — CryptoStrategies: src/crypto_strategies/strategies/crypto_live_pool_rotation/core.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/crypto_strategies/strategies/crypto_live_pool_rotation/core.py:94](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/src/crypto_strategies/strategies/crypto_live_pool_rotation/core.py#L94).

### MD-113 — CryptoStrategies: src/crypto_strategies/strategies/crypto_live_pool_rotation/rotation.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Request/process memory cache or caller-selected store; source/basis cache identity requires review.
- Config/env keys (names only): data parameters/schema fields: timezone.
- Evidence: [src/crypto_strategies/strategies/crypto_live_pool_rotation/rotation.py:6](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/src/crypto_strategies/strategies/crypto_live_pool_rotation/rotation.py#L6); [src/crypto_strategies/strategies/crypto_live_pool_rotation/rotation.py:25](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/src/crypto_strategies/strategies/crypto_live_pool_rotation/rotation.py#L25).

### MD-114 — CryptoStrategies: src/crypto_strategies/strategies/crypto_trend_rotation.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/crypto_strategies/strategies/crypto_trend_rotation.py:43](https://github.com/QuantStrategyLab/CryptoStrategies/blob/15ae4ba01b4e9b2c2de78a1bd46d92691098ee5a/src/crypto_strategies/strategies/crypto_trend_rotation.py#L43).

### MD-115 — HkEquitySnapshotPipelines: src/hk_equity_snapshot_pipelines/low_vol_dividend_quality.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/hk_equity_snapshot_pipelines/low_vol_dividend_quality.py:13](https://github.com/QuantStrategyLab/HkEquitySnapshotPipelines/blob/27490948fb83d121d864cfc426483a5ba0122410/src/hk_equity_snapshot_pipelines/low_vol_dividend_quality.py#L13).

### MD-116 — HkEquitySnapshotPipelines: src/hk_equity_snapshot_pipelines/snapshot_proxy_backtest.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: UTC; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, source.
- Evidence: [src/hk_equity_snapshot_pipelines/snapshot_proxy_backtest.py:40](https://github.com/QuantStrategyLab/HkEquitySnapshotPipelines/blob/27490948fb83d121d864cfc426483a5ba0122410/src/hk_equity_snapshot_pipelines/snapshot_proxy_backtest.py#L40); [src/hk_equity_snapshot_pipelines/snapshot_proxy_backtest.py:223](https://github.com/QuantStrategyLab/HkEquitySnapshotPipelines/blob/27490948fb83d121d864cfc426483a5ba0122410/src/hk_equity_snapshot_pipelines/snapshot_proxy_backtest.py#L223); [src/hk_equity_snapshot_pipelines/snapshot_proxy_backtest.py:226](https://github.com/QuantStrategyLab/HkEquitySnapshotPipelines/blob/27490948fb83d121d864cfc426483a5ba0122410/src/hk_equity_snapshot_pipelines/snapshot_proxy_backtest.py#L226).

### MD-117 — HkEquityStrategies: scripts/build_lifecycle_preflight.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: output_dir, output_path, timezone.
- Evidence: [scripts/build_lifecycle_preflight.py:11](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/scripts/build_lifecycle_preflight.py#L11); [scripts/build_lifecycle_preflight.py:26](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/scripts/build_lifecycle_preflight.py#L26).

### MD-118 — HkEquityStrategies: scripts/research_hk_equity_combo_backtest.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [scripts/research_hk_equity_combo_backtest.py:47](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/scripts/research_hk_equity_combo_backtest.py#L47).

### MD-119 — HkEquityStrategies: scripts/research_hk_global_etf_tactical_rotation_backtest.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [scripts/research_hk_global_etf_tactical_rotation_backtest.py:17](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/scripts/research_hk_global_etf_tactical_rotation_backtest.py#L17).

### MD-120 — HkEquityStrategies: src/hk_equity_strategies/backtest/combo_simulator.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, source.
- Evidence: [src/hk_equity_strategies/backtest/combo_simulator.py:71](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/backtest/combo_simulator.py#L71); [src/hk_equity_strategies/backtest/combo_simulator.py:227](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/backtest/combo_simulator.py#L227).

### MD-121 — HkEquityStrategies: src/hk_equity_strategies/backtest/etf_rotation_simulator.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/hk_equity_strategies/backtest/etf_rotation_simulator.py:29](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/backtest/etf_rotation_simulator.py#L29); [src/hk_equity_strategies/backtest/etf_rotation_simulator.py:35](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/backtest/etf_rotation_simulator.py#L35).

### MD-122 — HkEquityStrategies: src/hk_equity_strategies/backtest/orchestrator_runner.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: UTC; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: lookback_days, timezone.
- Evidence: [src/hk_equity_strategies/backtest/orchestrator_runner.py:8](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/backtest/orchestrator_runner.py#L8); [src/hk_equity_strategies/backtest/orchestrator_runner.py:52](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/backtest/orchestrator_runner.py#L52).

### MD-123 — HkEquityStrategies: src/hk_equity_strategies/catalog.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/hk_equity_strategies/catalog.py:19](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/catalog.py#L19).

### MD-124 — HkEquityStrategies: src/hk_equity_strategies/combo_entrypoints.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/hk_equity_strategies/combo_entrypoints.py:27](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/combo_entrypoints.py#L27).

### MD-125 — HkEquityStrategies: src/hk_equity_strategies/combo_manifests.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/hk_equity_strategies/combo_manifests.py:24](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/combo_manifests.py#L24).

### MD-126 — HkEquityStrategies: src/hk_equity_strategies/runtime_adapters.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/hk_equity_strategies/runtime_adapters.py:12](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/runtime_adapters.py#L12).

### MD-127 — HkEquityStrategies: src/hk_equity_strategies/runtime_market_data_policy.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: source.
- Evidence: [src/hk_equity_strategies/runtime_market_data_policy.py:19](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/runtime_market_data_policy.py#L19); [src/hk_equity_strategies/runtime_market_data_policy.py:24](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/runtime_market_data_policy.py#L24).

### MD-128 — HkEquityStrategies: src/hk_equity_strategies/strategies/etf_rotation_core.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/hk_equity_strategies/strategies/etf_rotation_core.py:41](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/strategies/etf_rotation_core.py#L41); [src/hk_equity_strategies/strategies/etf_rotation_core.py:87](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/strategies/etf_rotation_core.py#L87).

### MD-129 — HkEquityStrategies: src/hk_equity_strategies/strategies/hk_equity_combo.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: adjustment.
- Evidence: [src/hk_equity_strategies/strategies/hk_equity_combo.py:34](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/strategies/hk_equity_combo.py#L34); [src/hk_equity_strategies/strategies/hk_equity_combo.py:72](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/strategies/hk_equity_combo.py#L72).

### MD-130 — HkEquityStrategies: src/hk_equity_strategies/strategies/hk_global_etf_tactical_rotation.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/hk_equity_strategies/strategies/hk_global_etf_tactical_rotation.py:45](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/strategies/hk_global_etf_tactical_rotation.py#L45).

### MD-131 — HkEquityStrategies: src/hk_equity_strategies/strategies/hk_low_vol_dividend_quality_snapshot.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/hk_equity_strategies/strategies/hk_low_vol_dividend_quality_snapshot.py:39](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/strategies/hk_low_vol_dividend_quality_snapshot.py#L39); [src/hk_equity_strategies/strategies/hk_low_vol_dividend_quality_snapshot.py:122](https://github.com/QuantStrategyLab/HkEquityStrategies/blob/838b8d826ccdaed40ab19bed0ec64e201499836d/src/hk_equity_strategies/strategies/hk_low_vol_dividend_quality_snapshot.py#L122).

### MD-132 — InteractiveBrokersPlatform: scripts/release_evidence_parity_check.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/release_evidence_parity_check.py:112](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/scripts/release_evidence_parity_check.py#L112); [scripts/release_evidence_parity_check.py:207](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/scripts/release_evidence_parity_check.py#L207); [scripts/release_evidence_parity_check.py:227](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/scripts/release_evidence_parity_check.py#L227).

### MD-133 — InteractiveBrokersPlatform: scripts/strategy_parity_check.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: IBKR TRADES for signals; yfinance history fallback/probe. Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_adjusted intended; missing Yahoo Close falls back to split_dividend_adjusted Adj Close. Adjustment: ADJUSTED_LAST suppressed by signal proxy; yfinance auto_adjust=False; fallback OHLC coherence unresolved.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/strategy_parity_check.py:72](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/scripts/strategy_parity_check.py#L72); [scripts/strategy_parity_check.py:79](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/scripts/strategy_parity_check.py#L79).

### MD-134 — MarketSignalSources: scripts/publish_ibit_btc_platform_handoff.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: UTC; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/publish_ibit_btc_platform_handoff.py:34](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/scripts/publish_ibit_btc_platform_handoff.py#L34).

### MD-135 — MarketSignalSources: src/market_signal_sources/artifacts/quality_report.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/market_signal_sources/artifacts/quality_report.py:47](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/src/market_signal_sources/artifacts/quality_report.py#L47).

### MD-136 — MarketSignalSources: src/market_signal_sources/cli/export_us_equity_context_research_csv.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/market_signal_sources/cli/export_us_equity_context_research_csv.py:29](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/src/market_signal_sources/cli/export_us_equity_context_research_csv.py#L29).

### MD-137 — MarketSignalSources: src/market_signal_sources/cli/export_us_equity_price_proxy_research_csv.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/market_signal_sources/cli/export_us_equity_price_proxy_research_csv.py:42](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/src/market_signal_sources/cli/export_us_equity_price_proxy_research_csv.py#L42).

### MD-138 — MarketSignalSources: src/market_signal_sources/derived/us_equity/nasdaq_sp500_context.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/market_signal_sources/derived/us_equity/nasdaq_sp500_context.py:229](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/src/market_signal_sources/derived/us_equity/nasdaq_sp500_context.py#L229); [src/market_signal_sources/derived/us_equity/nasdaq_sp500_context.py:832](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/src/market_signal_sources/derived/us_equity/nasdaq_sp500_context.py#L832).

### MD-139 — MarketSignalSources: src/market_signal_sources/providers/local_csv.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, source.
- Evidence: [src/market_signal_sources/providers/local_csv.py:58](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/src/market_signal_sources/providers/local_csv.py#L58); [src/market_signal_sources/providers/local_csv.py:70](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/src/market_signal_sources/providers/local_csv.py#L70).

### MD-140 — MarketSignalSources: src/market_signal_sources/artifacts/historical_combo_p1_input.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/market_signal_sources/artifacts/historical_combo_p1_input.py:4](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/src/market_signal_sources/artifacts/historical_combo_p1_input.py#L4).

### MD-141 — MarketSignalSources: src/market_signal_sources/artifacts/historical_price_panel.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, calendar_id, source.
- Evidence: [src/market_signal_sources/artifacts/historical_price_panel.py:4](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/src/market_signal_sources/artifacts/historical_price_panel.py#L4); [src/market_signal_sources/artifacts/historical_price_panel.py:25](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/src/market_signal_sources/artifacts/historical_price_panel.py#L25); [src/market_signal_sources/artifacts/historical_price_panel.py:35](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/src/market_signal_sources/artifacts/historical_price_panel.py#L35).

### MD-142 — MarketSignalSources: src/market_signal_sources/derived/crypto/btc_cycle.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: UTC; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/market_signal_sources/derived/crypto/btc_cycle.py:30](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/src/market_signal_sources/derived/crypto/btc_cycle.py#L30); [src/market_signal_sources/derived/crypto/btc_cycle.py:91](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/src/market_signal_sources/derived/crypto/btc_cycle.py#L91).

### MD-143 — MarketSignalSources: src/market_signal_sources/derived/technical_indicators.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/market_signal_sources/derived/technical_indicators.py:40](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/src/market_signal_sources/derived/technical_indicators.py#L40); [src/market_signal_sources/derived/technical_indicators.py:84](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/src/market_signal_sources/derived/technical_indicators.py#L84).

### MD-144 — MarketSignalSources: src/market_signal_sources/derived/us_equity/semiconductor_rotation.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/market_signal_sources/derived/us_equity/semiconductor_rotation.py:66](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/src/market_signal_sources/derived/us_equity/semiconductor_rotation.py#L66); [src/market_signal_sources/derived/us_equity/semiconductor_rotation.py:71](https://github.com/QuantStrategyLab/MarketSignalSources/blob/dd204e2b637d6ec389fe75f94c027372d28b471a/src/market_signal_sources/derived/us_equity/semiconductor_rotation.py#L71).

### MD-145 — PoliticalEventTrackingResearch: src/political_event_tracking_research/event_study.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected research price history. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited close/return semantics; no provider/basis enforcement established. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Event/price availability must be supplied; not a broker session query; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/political_event_tracking_research/event_study.py:8](https://github.com/QuantStrategyLab/PoliticalEventTrackingResearch/blob/6f43c401fdac817506f70a8ef936e8c6c7402f63/src/political_event_tracking_research/event_study.py#L8).

### MD-146 — PoliticalEventTrackingResearch: src/political_event_tracking_research/tracker.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/political_event_tracking_research/tracker.py:8](https://github.com/QuantStrategyLab/PoliticalEventTrackingResearch/blob/6f43c401fdac817506f70a8ef936e8c6c7402f63/src/political_event_tracking_research/tracker.py#L8).

### MD-147 — QuantAdvisorResearch: src/quant_advisor_research/advisory_report.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: UTC; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/quant_advisor_research/advisory_report.py:18](https://github.com/QuantStrategyLab/QuantAdvisorResearch/blob/eac68deafc46e77befa019b9670f1cd96e1d41b1/src/quant_advisor_research/advisory_report.py#L18); [src/quant_advisor_research/advisory_report.py:291](https://github.com/QuantStrategyLab/QuantAdvisorResearch/blob/eac68deafc46e77befa019b9670f1cd96e1d41b1/src/quant_advisor_research/advisory_report.py#L291).

### MD-148 — QuantAdvisorResearch: src/quant_advisor_research/recommendation_review.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Request/process memory cache or caller-selected store; source/basis cache identity requires review.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, start_date.
- Evidence: [src/quant_advisor_research/recommendation_review.py:13](https://github.com/QuantStrategyLab/QuantAdvisorResearch/blob/eac68deafc46e77befa019b9670f1cd96e1d41b1/src/quant_advisor_research/recommendation_review.py#L13); [src/quant_advisor_research/recommendation_review.py:195](https://github.com/QuantStrategyLab/QuantAdvisorResearch/blob/eac68deafc46e77befa019b9670f1cd96e1d41b1/src/quant_advisor_research/recommendation_review.py#L195).

### MD-149 — QuantStrategyPlugins: src/quant_strategy_plugins/macro_external_context.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, timezone.
- Evidence: [src/quant_strategy_plugins/macro_external_context.py:7](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/macro_external_context.py#L7); [src/quant_strategy_plugins/macro_external_context.py:14](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/macro_external_context.py#L14).

### MD-150 — QuantStrategyPlugins: src/quant_strategy_plugins/russell_1000_multi_factor_defensive_snapshot.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, lookback_days.
- Evidence: [src/quant_strategy_plugins/russell_1000_multi_factor_defensive_snapshot.py:9](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/russell_1000_multi_factor_defensive_snapshot.py#L9); [src/quant_strategy_plugins/russell_1000_multi_factor_defensive_snapshot.py:83](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/russell_1000_multi_factor_defensive_snapshot.py#L83).

### MD-151 — QuantStrategyPlugins: scripts/backtest_macro_risk_governor_params.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/backtest_macro_risk_governor_params.py:33](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/scripts/backtest_macro_risk_governor_params.py#L33); [scripts/backtest_macro_risk_governor_params.py:51](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/scripts/backtest_macro_risk_governor_params.py#L51).

### MD-152 — QuantStrategyPlugins: scripts/backtest_volatility_delever_thresholds.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/backtest_volatility_delever_thresholds.py:43](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/scripts/backtest_volatility_delever_thresholds.py#L43); [scripts/backtest_volatility_delever_thresholds.py:44](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/scripts/backtest_volatility_delever_thresholds.py#L44).

### MD-153 — QuantStrategyPlugins: src/quant_strategy_plugins/ai_audit.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): AI_GATEWAY_SOURCE_REPO; data parameters/schema fields: base_url, source.
- Evidence: [src/quant_strategy_plugins/ai_audit.py:469](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/ai_audit.py#L469).

### MD-154 — QuantStrategyPlugins: src/quant_strategy_plugins/benchmark_drawdown_guard.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/quant_strategy_plugins/benchmark_drawdown_guard.py:85](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/benchmark_drawdown_guard.py#L85).

### MD-155 — QuantStrategyPlugins: src/quant_strategy_plugins/crisis_context_research.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, output_dir, start_date.
- Evidence: [src/quant_strategy_plugins/crisis_context_research.py:19](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/crisis_context_research.py#L19); [src/quant_strategy_plugins/crisis_context_research.py:212](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/crisis_context_research.py#L212).

### MD-156 — QuantStrategyPlugins: src/quant_strategy_plugins/crisis_regime_guard_research.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, output_dir, start_date.
- Evidence: [src/quant_strategy_plugins/crisis_regime_guard_research.py:23](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/crisis_regime_guard_research.py#L23); [src/quant_strategy_plugins/crisis_regime_guard_research.py:100](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/crisis_regime_guard_research.py#L100).

### MD-157 — QuantStrategyPlugins: src/quant_strategy_plugins/crisis_response_research.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, output_dir, start_date.
- Evidence: [src/quant_strategy_plugins/crisis_response_research.py:35](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/crisis_response_research.py#L35); [src/quant_strategy_plugins/crisis_response_research.py:189](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/crisis_response_research.py#L189).

### MD-158 — QuantStrategyPlugins: src/quant_strategy_plugins/crisis_response_shadow_plugin.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, start_date, timezone.
- Evidence: [src/quant_strategy_plugins/crisis_response_shadow_plugin.py:4](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/crisis_response_shadow_plugin.py#L4); [src/quant_strategy_plugins/crisis_response_shadow_plugin.py:70](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/crisis_response_shadow_plugin.py#L70).

### MD-159 — QuantStrategyPlugins: src/quant_strategy_plugins/macro_risk_governor_plugin.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, timezone.
- Evidence: [src/quant_strategy_plugins/macro_risk_governor_plugin.py:4](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/macro_risk_governor_plugin.py#L4); [src/quant_strategy_plugins/macro_risk_governor_plugin.py:13](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/macro_risk_governor_plugin.py#L13).

### MD-160 — QuantStrategyPlugins: src/quant_strategy_plugins/panic_reversal_shadow_plugin.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, start_date, timezone.
- Evidence: [src/quant_strategy_plugins/panic_reversal_shadow_plugin.py:4](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/panic_reversal_shadow_plugin.py#L4); [src/quant_strategy_plugins/panic_reversal_shadow_plugin.py:21](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/panic_reversal_shadow_plugin.py#L21).

### MD-161 — QuantStrategyPlugins: src/quant_strategy_plugins/plugin_lineage.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: output_dir.
- Evidence: [src/quant_strategy_plugins/plugin_lineage.py:40](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/plugin_lineage.py#L40).

### MD-162 — QuantStrategyPlugins: src/quant_strategy_plugins/plugin_signal_utils.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/quant_strategy_plugins/plugin_signal_utils.py:11](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/plugin_signal_utils.py#L11); [src/quant_strategy_plugins/plugin_signal_utils.py:18](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/plugin_signal_utils.py#L18).

### MD-163 — QuantStrategyPlugins: src/quant_strategy_plugins/qqq_price_regime_observer_v2.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/quant_strategy_plugins/qqq_price_regime_observer_v2.py:93](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/qqq_price_regime_observer_v2.py#L93).

### MD-164 — QuantStrategyPlugins: src/quant_strategy_plugins/rates_context_observer_research.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: timezone.
- Evidence: [src/quant_strategy_plugins/rates_context_observer_research.py:9](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/rates_context_observer_research.py#L9).

### MD-165 — QuantStrategyPlugins: src/quant_strategy_plugins/semiconductor_regime_observer_research.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Explicit completed-session/calendar hook present; preserve exact upstream clock and finality policy; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: adjustment, calendar_id, date_cutoff, timezone.
- Evidence: [src/quant_strategy_plugins/semiconductor_regime_observer_research.py:3](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/semiconductor_regime_observer_research.py#L3); [src/quant_strategy_plugins/semiconductor_regime_observer_research.py:14](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/semiconductor_regime_observer_research.py#L14); [src/quant_strategy_plugins/semiconductor_regime_observer_research.py:34](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/semiconductor_regime_observer_research.py#L34).

### MD-166 — QuantStrategyPlugins: src/quant_strategy_plugins/strategy_plugin_runner.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/quant_strategy_plugins/strategy_plugin_runner.py:1433](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/strategy_plugin_runner.py#L1433).

### MD-167 — QuantStrategyPlugins: src/quant_strategy_plugins/taco_panic_rebound_backtest.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, output_dir, start_date.
- Evidence: [src/quant_strategy_plugins/taco_panic_rebound_backtest.py:22](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/taco_panic_rebound_backtest.py#L22); [src/quant_strategy_plugins/taco_panic_rebound_backtest.py:145](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/taco_panic_rebound_backtest.py#L145).

### MD-168 — QuantStrategyPlugins: src/quant_strategy_plugins/taco_panic_rebound_overlay_compare.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, output_dir, source, start_date.
- Evidence: [src/quant_strategy_plugins/taco_panic_rebound_overlay_compare.py:19](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/taco_panic_rebound_overlay_compare.py#L19); [src/quant_strategy_plugins/taco_panic_rebound_overlay_compare.py:108](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/taco_panic_rebound_overlay_compare.py#L108).

### MD-169 — QuantStrategyPlugins: src/quant_strategy_plugins/taco_panic_rebound_research.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, output_dir.
- Evidence: [src/quant_strategy_plugins/taco_panic_rebound_research.py:11](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/taco_panic_rebound_research.py#L11); [src/quant_strategy_plugins/taco_panic_rebound_research.py:450](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/taco_panic_rebound_research.py#L450).

### MD-170 — QuantStrategyPlugins: src/quant_strategy_plugins/taco_rebound_shadow_plugin.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, timezone.
- Evidence: [src/quant_strategy_plugins/taco_rebound_shadow_plugin.py:4](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/taco_rebound_shadow_plugin.py#L4); [src/quant_strategy_plugins/taco_rebound_shadow_plugin.py:31](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/taco_rebound_shadow_plugin.py#L31).

### MD-171 — QuantStrategyPlugins: src/quant_strategy_plugins/tqqq_market_regime_control_present.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/quant_strategy_plugins/tqqq_market_regime_control_present.py:406](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/tqqq_market_regime_control_present.py#L406).

### MD-172 — QuantStrategyPlugins: src/quant_strategy_plugins/tqqq_research_input_bundle.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/quant_strategy_plugins/tqqq_research_input_bundle.py:27](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/tqqq_research_input_bundle.py#L27); [src/quant_strategy_plugins/tqqq_research_input_bundle.py:336](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/tqqq_research_input_bundle.py#L336).

### MD-173 — QuantStrategyPlugins: src/quant_strategy_plugins/volatility_delever_price_rebound.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, lookback_days.
- Evidence: [src/quant_strategy_plugins/volatility_delever_price_rebound.py:125](https://github.com/QuantStrategyLab/QuantStrategyPlugins/blob/e2fe5a7734dd7915b3ba6e93cfd1cdb21207002a/src/quant_strategy_plugins/volatility_delever_price_rebound.py#L125).

### MD-174 — ResearchSignalContextPipelines: scripts/backtest_signal_overlay.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [scripts/backtest_signal_overlay.py:15](https://github.com/QuantStrategyLab/ResearchSignalContextPipelines/blob/a41745a925c2d676df00c3111f6f75f5bb236288/scripts/backtest_signal_overlay.py#L15).

### MD-175 — ResearchSignalContextPipelines: scripts/build_context_bundle.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo chart or explicitly supplied price CSV. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Yahoo adjclose preferred, quote.close fallback per missing row; CSV basis inherited. Adjustment: Close-only normalization; adjusted-value fallback is a semantic change, not certified equivalent.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, timezone.
- Evidence: [scripts/build_context_bundle.py:23](https://github.com/QuantStrategyLab/ResearchSignalContextPipelines/blob/a41745a925c2d676df00c3111f6f75f5bb236288/scripts/build_context_bundle.py#L23); [scripts/build_context_bundle.py:62](https://github.com/QuantStrategyLab/ResearchSignalContextPipelines/blob/a41745a925c2d676df00c3111f6f75f5bb236288/scripts/build_context_bundle.py#L62).

### MD-176 — ResearchSignalContextPipelines: scripts/extract_price_history.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, source.
- Evidence: [scripts/extract_price_history.py:12](https://github.com/QuantStrategyLab/ResearchSignalContextPipelines/blob/a41745a925c2d676df00c3111f6f75f5bb236288/scripts/extract_price_history.py#L12).

### MD-177 — ResearchSignalContextPipelines: scripts/publish_theme_snapshot_pr.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/publish_theme_snapshot_pr.py:45](https://github.com/QuantStrategyLab/ResearchSignalContextPipelines/blob/a41745a925c2d676df00c3111f6f75f5bb236288/scripts/publish_theme_snapshot_pr.py#L45).

### MD-178 — ResearchSignalContextPipelines: src/research_signal_context_pipelines/context_bundle.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo chart or explicitly supplied price CSV. Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: Yahoo adjclose preferred, quote.close fallback per missing row; CSV basis inherited. Adjustment: Close-only normalization; adjusted-value fallback is a semantic change, not certified equivalent.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, lookback_days, source, start_date, timezone.
- Evidence: [src/research_signal_context_pipelines/context_bundle.py:15](https://github.com/QuantStrategyLab/ResearchSignalContextPipelines/blob/a41745a925c2d676df00c3111f6f75f5bb236288/src/research_signal_context_pipelines/context_bundle.py#L15); [src/research_signal_context_pipelines/context_bundle.py:91](https://github.com/QuantStrategyLab/ResearchSignalContextPipelines/blob/a41745a925c2d676df00c3111f6f75f5bb236288/src/research_signal_context_pipelines/context_bundle.py#L91); [src/research_signal_context_pipelines/context_bundle.py:130](https://github.com/QuantStrategyLab/ResearchSignalContextPipelines/blob/a41745a925c2d676df00c3111f6f75f5bb236288/src/research_signal_context_pipelines/context_bundle.py#L130).

### MD-179 — ResearchSignalContextPipelines: src/research_signal_context_pipelines/overlay_backtest.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: end_date, start_date, timezone.
- Evidence: [src/research_signal_context_pipelines/overlay_backtest.py:9](https://github.com/QuantStrategyLab/ResearchSignalContextPipelines/blob/a41745a925c2d676df00c3111f6f75f5bb236288/src/research_signal_context_pipelines/overlay_backtest.py#L9); [src/research_signal_context_pipelines/overlay_backtest.py:45](https://github.com/QuantStrategyLab/ResearchSignalContextPipelines/blob/a41745a925c2d676df00c3111f6f75f5bb236288/src/research_signal_context_pipelines/overlay_backtest.py#L45).

### MD-180 — ResearchSignalContextPipelines: src/research_signal_context_pipelines/price_history.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: end_date, start_date.
- Evidence: [src/research_signal_context_pipelines/price_history.py:48](https://github.com/QuantStrategyLab/ResearchSignalContextPipelines/blob/a41745a925c2d676df00c3111f6f75f5bb236288/src/research_signal_context_pipelines/price_history.py#L48).

### MD-181 — ResearchSignalContextPipelines: src/research_signal_context_pipelines/theme_momentum.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/research_signal_context_pipelines/theme_momentum.py:11](https://github.com/QuantStrategyLab/ResearchSignalContextPipelines/blob/a41745a925c2d676df00c3111f6f75f5bb236288/src/research_signal_context_pipelines/theme_momentum.py#L11).

### MD-182 — UsEquitySnapshotPipelines: scripts/build_scheduled_ibit_dca_research.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: price_field.
- Evidence: [scripts/build_scheduled_ibit_dca_research.py:19](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/build_scheduled_ibit_dca_research.py#L19).

### MD-183 — UsEquitySnapshotPipelines: scripts/diagnose_multisource_daily_assurance.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Twelve Data split-only source + Yahoo independent verifier (per frozen contract). Provider tier not queried; existing license/rate and two-source gates remain.
- Price basis: split_adjusted (candidate-specific source-assurance policy). Adjustment: Twelve adjust=splits / Yahoo quote close, no dividend-adjusted substitution.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): TWELVE_DATA_API_KEY; data parameters/schema fields: adjustment, source.
- Evidence: [scripts/diagnose_multisource_daily_assurance.py:17](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/diagnose_multisource_daily_assurance.py#L17); [scripts/diagnose_multisource_daily_assurance.py:45](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/diagnose_multisource_daily_assurance.py#L45); [scripts/diagnose_multisource_daily_assurance.py:46](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/diagnose_multisource_daily_assurance.py#L46).

### MD-184 — UsEquitySnapshotPipelines: scripts/read_research_input_archive_metadata.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Alpaca (SIP unless this row explicitly says otherwise). Owner Basic/free: recent SIP excluded; require end <= now-16min; IEX recent is a distinct feed.
- Price basis: Declared vendor adjustment; see basis anchor (legacy total_return_adjusted is not certified wealth index). Adjustment: Alpaca server adjustment; retain actual feed/adjustment request and source digest.
- Time / session / calendar: America/New_York/UTC; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Provider-adjusted events; independent full action/PIT history not established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): SOURCE_COMMIT_ENV, SOURCE_DIR_ENV; data parameters/schema fields: adjustment, binding_sha256, feed, timezone.
- Evidence: [scripts/read_research_input_archive_metadata.py:10](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/read_research_input_archive_metadata.py#L10); [scripts/read_research_input_archive_metadata.py:24](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/read_research_input_archive_metadata.py#L24); [scripts/read_research_input_archive_metadata.py:47](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/read_research_input_archive_metadata.py#L47).

### MD-185 — UsEquitySnapshotPipelines: scripts/research_levered_overlay_guards.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, start_date.
- Evidence: [scripts/research_levered_overlay_guards.py:29](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/research_levered_overlay_guards.py#L29).

### MD-186 — UsEquitySnapshotPipelines: scripts/research_soxl_dynamic_volatility_delever_thresholds.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, output_dir.
- Evidence: [scripts/research_soxl_dynamic_volatility_delever_thresholds.py:22](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/research_soxl_dynamic_volatility_delever_thresholds.py#L22); [scripts/research_soxl_dynamic_volatility_delever_thresholds.py:44](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/research_soxl_dynamic_volatility_delever_thresholds.py#L44).

### MD-187 — UsEquitySnapshotPipelines: scripts/research_tqqq_volatility_delever_thresholds.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: output_dir.
- Evidence: [scripts/research_tqqq_volatility_delever_thresholds.py:20](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/research_tqqq_volatility_delever_thresholds.py#L20).

### MD-188 — UsEquitySnapshotPipelines: scripts/run_russell_core_case.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Alpaca (SIP unless this row explicitly says otherwise). Owner Basic/free: recent SIP excluded; require end <= now-16min; IEX recent is a distinct feed.
- Price basis: Declared vendor adjustment; see basis anchor (legacy total_return_adjusted is not certified wealth index). Adjustment: Alpaca server adjustment; retain actual feed/adjustment request and source digest.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Provider-adjusted events; independent full action/PIT history not established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY; data parameters/schema fields: adjustment, feed, source.
- Evidence: [scripts/run_russell_core_case.py:16](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/run_russell_core_case.py#L16); [scripts/run_russell_core_case.py:38](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/run_russell_core_case.py#L38); [scripts/run_russell_core_case.py:98](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/run_russell_core_case.py#L98).

### MD-189 — UsEquitySnapshotPipelines: scripts/run_soxl_core_only_free_split_close_p3_evidence.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: source.
- Evidence: [scripts/run_soxl_core_only_free_split_close_p3_evidence.py:5](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/run_soxl_core_only_free_split_close_p3_evidence.py#L5).

### MD-190 — UsEquitySnapshotPipelines: scripts/run_soxl_three_asset_learning.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: price_basis.
- Evidence: [scripts/run_soxl_three_asset_learning.py:119](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/run_soxl_three_asset_learning.py#L119); [scripts/run_soxl_three_asset_learning.py:627](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/run_soxl_three_asset_learning.py#L627); [scripts/run_soxl_three_asset_learning.py:1355](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/run_soxl_three_asset_learning.py#L1355).

### MD-191 — UsEquitySnapshotPipelines: scripts/run_soxl_v7_nonlive_forward_observation.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/run_soxl_v7_nonlive_forward_observation.py:17](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/run_soxl_v7_nonlive_forward_observation.py#L17).

### MD-192 — UsEquitySnapshotPipelines: scripts/sweep_levered_income_layer.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: output_dir.
- Evidence: [scripts/sweep_levered_income_layer.py:27](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/sweep_levered_income_layer.py#L27).

### MD-193 — UsEquitySnapshotPipelines: scripts/sweep_tecl_xlk_trend_income.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: output_dir.
- Evidence: [scripts/sweep_tecl_xlk_trend_income.py:16](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/sweep_tecl_xlk_trend_income.py#L16).

### MD-194 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/input_sources.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: source.
- Evidence: [src/us_equity_snapshot_pipelines/input_sources.py:208](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/input_sources.py#L208).

### MD-195 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/intraday_crash_circuit_breaker_research.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of, output_path, start_date.
- Evidence: [src/us_equity_snapshot_pipelines/intraday_crash_circuit_breaker_research.py:17](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/intraday_crash_circuit_breaker_research.py#L17); [src/us_equity_snapshot_pipelines/intraday_crash_circuit_breaker_research.py:61](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/intraday_crash_circuit_breaker_research.py#L61).

### MD-196 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/intraday_scheme_validation.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, output_path.
- Evidence: [src/us_equity_snapshot_pipelines/intraday_scheme_validation.py:35](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/intraday_scheme_validation.py#L35); [src/us_equity_snapshot_pipelines/intraday_scheme_validation.py:44](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/intraday_scheme_validation.py#L44).

### MD-197 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/russell_research_runner.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: UTC; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, timezone.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/russell_research_runner.py:69](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/russell_research_runner.py#L69); [src/us_equity_snapshot_pipelines/lifecycle/russell_research_runner.py:108](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/russell_research_runner.py#L108).

### MD-198 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_free_split_close_p1.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Twelve Data split-only source + Yahoo independent verifier (per frozen contract). Provider tier not queried; existing license/rate and two-source gates remain.
- Price basis: split_adjusted (candidate-specific source-assurance policy). Adjustment: Twelve adjust=splits / Yahoo quote close, no dividend-adjusted substitution.
- Time / session / calendar: America/New_York; Explicit completed-session/calendar hook present; preserve exact upstream clock and finality policy; XNYS.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, calendar_id, date_cutoff, source, timezone.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_free_split_close_p1.py:28](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_free_split_close_p1.py#L28); [src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_free_split_close_p1.py:51](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_free_split_close_p1.py#L51); [src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_free_split_close_p1.py:56](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_free_split_close_p1.py#L56).

### MD-199 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_free_split_close_p3_input_materializer.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Twelve Data split-only source + Yahoo independent verifier (per frozen contract). Provider tier not queried; existing license/rate and two-source gates remain.
- Price basis: split_adjusted (candidate-specific source-assurance policy). Adjustment: Twelve adjust=splits / Yahoo quote close, no dividend-adjusted substitution.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: binding_sha256, date_cutoff, price_field, source.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_free_split_close_p3_input_materializer.py:1](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_free_split_close_p3_input_materializer.py#L1).

### MD-200 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p3_input_materializer.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Alpaca (SIP unless this row explicitly says otherwise). Owner Basic/free: recent SIP excluded; require end <= now-16min; IEX recent is a distinct feed.
- Price basis: Declared vendor adjustment; see basis anchor (legacy total_return_adjusted is not certified wealth index). Adjustment: Alpaca server adjustment; retain actual feed/adjustment request and source digest.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider-adjusted events; independent full action/PIT history not established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: binding_sha256, price_field, source.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p3_input_materializer.py:201](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p3_input_materializer.py#L201); [src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p3_input_materializer.py:340](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p3_input_materializer.py#L340).

### MD-201 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_v7_forward_confirmation_p4_evidence.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_v7_forward_confirmation_p4_evidence.py:94](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_v7_forward_confirmation_p4_evidence.py#L94).

### MD-202 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/soxl_v7_twelve_single_source_r6.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Twelve Data split-only source + Yahoo independent verifier (per frozen contract). Provider tier not queried; existing license/rate and two-source gates remain.
- Price basis: split_adjusted (candidate-specific source-assurance policy). Adjustment: Twelve adjust=splits / Yahoo quote close, no dividend-adjusted substitution.
- Time / session / calendar: America/New_York; Explicit completed-session/calendar hook present; preserve exact upstream clock and finality policy; XNYS.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, binding_sha256, calendar_id, date_cutoff, price_field, source, timezone.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/soxl_v7_twelve_single_source_r6.py:38](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_v7_twelve_single_source_r6.py#L38); [src/us_equity_snapshot_pipelines/lifecycle/soxl_v7_twelve_single_source_r6.py:69](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_v7_twelve_single_source_r6.py#L69); [src/us_equity_snapshot_pipelines/lifecycle/soxl_v7_twelve_single_source_r6.py:70](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_v7_twelve_single_source_r6.py#L70).

### MD-203 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/monthly_publish_window.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; NYSE.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/us_equity_snapshot_pipelines/monthly_publish_window.py:4](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/monthly_publish_window.py#L4); [src/us_equity_snapshot_pipelines/monthly_publish_window.py:41](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/monthly_publish_window.py#L41).

### MD-204 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/pipelines/russell_1000_multi_factor_defensive_snapshot.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, lookback_days.
- Evidence: [src/us_equity_snapshot_pipelines/pipelines/russell_1000_multi_factor_defensive_snapshot.py:9](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/pipelines/russell_1000_multi_factor_defensive_snapshot.py#L9); [src/us_equity_snapshot_pipelines/pipelines/russell_1000_multi_factor_defensive_snapshot.py:83](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/pipelines/russell_1000_multi_factor_defensive_snapshot.py#L83).

### MD-205 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/pipelines/soxl_soxx_trend_income_backtest.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, output_dir, start_date.
- Evidence: [src/us_equity_snapshot_pipelines/pipelines/soxl_soxx_trend_income_backtest.py:15](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/pipelines/soxl_soxx_trend_income_backtest.py#L15); [src/us_equity_snapshot_pipelines/pipelines/soxl_soxx_trend_income_backtest.py:85](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/pipelines/soxl_soxx_trend_income_backtest.py#L85).

### MD-206 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/pipelines/tecl_xlk_trend_income_backtest.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, output_dir.
- Evidence: [src/us_equity_snapshot_pipelines/pipelines/tecl_xlk_trend_income_backtest.py:15](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/pipelines/tecl_xlk_trend_income_backtest.py#L15); [src/us_equity_snapshot_pipelines/pipelines/tecl_xlk_trend_income_backtest.py:85](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/pipelines/tecl_xlk_trend_income_backtest.py#L85).

### MD-207 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/publish.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: source.
- Evidence: [src/us_equity_snapshot_pipelines/publish.py:86](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/publish.py#L86); [src/us_equity_snapshot_pipelines/publish.py:99](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/publish.py#L99).

### MD-208 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/research/ibit_smart_dca_research.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of, price_field.
- Evidence: [src/us_equity_snapshot_pipelines/research/ibit_smart_dca_research.py:17](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/research/ibit_smart_dca_research.py#L17); [src/us_equity_snapshot_pipelines/research/ibit_smart_dca_research.py:108](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/research/ibit_smart_dca_research.py#L108).

### MD-209 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/soxl_soxx_trend_income_archive.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, output_dir, output_path, timezone.
- Evidence: [src/us_equity_snapshot_pipelines/soxl_soxx_trend_income_archive.py:8](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/soxl_soxx_trend_income_archive.py#L8); [src/us_equity_snapshot_pipelines/soxl_soxx_trend_income_archive.py:31](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/soxl_soxx_trend_income_archive.py#L31); [src/us_equity_snapshot_pipelines/soxl_soxx_trend_income_archive.py:350](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/soxl_soxx_trend_income_archive.py#L350).

### MD-210 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/tqqq_growth_income_archive.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, output_dir, output_path, timezone.
- Evidence: [src/us_equity_snapshot_pipelines/tqqq_growth_income_archive.py:8](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/tqqq_growth_income_archive.py#L8); [src/us_equity_snapshot_pipelines/tqqq_growth_income_archive.py:35](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/tqqq_growth_income_archive.py#L35); [src/us_equity_snapshot_pipelines/tqqq_growth_income_archive.py:516](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/tqqq_growth_income_archive.py#L516).

### MD-211 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/tqqq_r1_snapshot.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, calendar_id, output_dir, price_field, source, timezone.
- Evidence: [src/us_equity_snapshot_pipelines/tqqq_r1_snapshot.py:35](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/tqqq_r1_snapshot.py#L35); [src/us_equity_snapshot_pipelines/tqqq_r1_snapshot.py:142](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/tqqq_r1_snapshot.py#L142); [src/us_equity_snapshot_pipelines/tqqq_r1_snapshot.py:656](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/tqqq_r1_snapshot.py#L656).

### MD-212 — UsEquitySnapshotPipelines: scripts/build_monthly_russell_crash_brake_research.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: source.
- Evidence: [scripts/build_monthly_russell_crash_brake_research.py:22](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/build_monthly_russell_crash_brake_research.py#L22).

### MD-213 — UsEquitySnapshotPipelines: scripts/build_monthly_russell_crash_brake_review_chain.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/build_monthly_russell_crash_brake_review_chain.py:62](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/build_monthly_russell_crash_brake_review_chain.py#L62).

### MD-214 — UsEquitySnapshotPipelines: scripts/build_tecl_xlk_long_history_inputs.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: output_dir.
- Evidence: [scripts/build_tecl_xlk_long_history_inputs.py:18](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/build_tecl_xlk_long_history_inputs.py#L18).

### MD-215 — UsEquitySnapshotPipelines: scripts/check_snapshot_artifact_health.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/check_snapshot_artifact_health.py:66](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/check_snapshot_artifact_health.py#L66).

### MD-216 — UsEquitySnapshotPipelines: scripts/compare_global_etf_learning_benchmarks.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: source.
- Evidence: [scripts/compare_global_etf_learning_benchmarks.py:64](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/compare_global_etf_learning_benchmarks.py#L64); [scripts/compare_global_etf_learning_benchmarks.py:165](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/compare_global_etf_learning_benchmarks.py#L165).

### MD-217 — UsEquitySnapshotPipelines: scripts/diagnose_r3_v2_free_source_assurance.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Twelve Data split-only source + Yahoo independent verifier (per frozen contract). Provider tier not queried; existing license/rate and two-source gates remain.
- Price basis: split_adjusted (candidate-specific source-assurance policy). Adjustment: Twelve adjust=splits / Yahoo quote close, no dividend-adjusted substitution.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): TWELVE_DATA_API_KEY; data parameters/schema fields: adjustment, calendar_id, source.
- Evidence: [scripts/diagnose_r3_v2_free_source_assurance.py:14](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/diagnose_r3_v2_free_source_assurance.py#L14); [scripts/diagnose_r3_v2_free_source_assurance.py:24](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/diagnose_r3_v2_free_source_assurance.py#L24); [scripts/diagnose_r3_v2_free_source_assurance.py:201](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/diagnose_r3_v2_free_source_assurance.py#L201).

### MD-218 — UsEquitySnapshotPipelines: scripts/diagnose_r3_v2_price_only_assurance.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Twelve Data split-only source + Yahoo independent verifier (per frozen contract). Provider tier not queried; existing license/rate and two-source gates remain.
- Price basis: split_adjusted (candidate-specific source-assurance policy). Adjustment: Twelve adjust=splits / Yahoo quote close, no dividend-adjusted substitution.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): TWELVE_DATA_API_KEY; data parameters/schema fields: adjustment, calendar_id, source.
- Evidence: [scripts/diagnose_r3_v2_price_only_assurance.py:4](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/diagnose_r3_v2_price_only_assurance.py#L4); [scripts/diagnose_r3_v2_price_only_assurance.py:18](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/diagnose_r3_v2_price_only_assurance.py#L18); [scripts/diagnose_r3_v2_price_only_assurance.py:28](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/diagnose_r3_v2_price_only_assurance.py#L28).

### MD-219 — UsEquitySnapshotPipelines: scripts/run_global_etf_learning_replay.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Alpaca (SIP unless this row explicitly says otherwise). Owner Basic/free: recent SIP excluded; require end <= now-16min; IEX recent is a distinct feed.
- Price basis: Declared vendor adjustment; see basis anchor (legacy total_return_adjusted is not certified wealth index). Adjustment: Alpaca server adjustment; retain actual feed/adjustment request and source digest.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider-adjusted events; independent full action/PIT history not established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, feed, source.
- Evidence: [scripts/run_global_etf_learning_replay.py:47](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/run_global_etf_learning_replay.py#L47); [scripts/run_global_etf_learning_replay.py:75](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/run_global_etf_learning_replay.py#L75); [scripts/run_global_etf_learning_replay.py:96](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/run_global_etf_learning_replay.py#L96).

### MD-220 — UsEquitySnapshotPipelines: scripts/run_soxl_core_only_p3_isolated.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of, source.
- Evidence: [scripts/run_soxl_core_only_p3_isolated.py:46](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/run_soxl_core_only_p3_isolated.py#L46).

### MD-221 — UsEquitySnapshotPipelines: scripts/soxl_v7_r5_native_archive.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Twelve Data split-only source + Yahoo independent verifier (per frozen contract). Provider tier not queried; existing license/rate and two-source gates remain.
- Price basis: split_adjusted (candidate-specific source-assurance policy). Adjustment: Twelve adjust=splits / Yahoo quote close, no dividend-adjusted substitution.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): TWELVE_DATA_API_KEY; No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/soxl_v7_r5_native_archive.py:24](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/soxl_v7_r5_native_archive.py#L24).

### MD-222 — UsEquitySnapshotPipelines: scripts/soxl_v7_r6_twelve_single_source.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Twelve Data split-only source + Yahoo independent verifier (per frozen contract). Provider tier not queried; existing license/rate and two-source gates remain.
- Price basis: split_adjusted (candidate-specific source-assurance policy). Adjustment: Twelve adjust=splits / Yahoo quote close, no dividend-adjusted substitution.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): TWELVE_DATA_API_KEY; data parameters/schema fields: date_cutoff.
- Evidence: [scripts/soxl_v7_r6_twelve_single_source.py:287](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/soxl_v7_r6_twelve_single_source.py#L287); [scripts/soxl_v7_r6_twelve_single_source.py:309](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/soxl_v7_r6_twelve_single_source.py#L309).

### MD-223 — UsEquitySnapshotPipelines: scripts/stage_snapshot_source_inputs.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/stage_snapshot_source_inputs.py:13](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/stage_snapshot_source_inputs.py#L13).

### MD-224 — UsEquitySnapshotPipelines: scripts/validate_monthly_russell_crash_brake_inputs.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/validate_monthly_russell_crash_brake_inputs.py:10](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/validate_monthly_russell_crash_brake_inputs.py#L10).

### MD-225 — UsEquitySnapshotPipelines: scripts/validate_snapshot_artifact_layout.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/validate_snapshot_artifact_layout.py:37](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/scripts/validate_snapshot_artifact_layout.py#L37).

### MD-226 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/artifacts.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, timezone.
- Evidence: [src/us_equity_snapshot_pipelines/artifacts.py:6](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/artifacts.py#L6); [src/us_equity_snapshot_pipelines/artifacts.py:177](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/artifacts.py#L177).

### MD-227 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/backtest_windows.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/us_equity_snapshot_pipelines/backtest_windows.py:20](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/backtest_windows.py#L20); [src/us_equity_snapshot_pipelines/backtest_windows.py:106](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/backtest_windows.py#L106).

### MD-228 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/dynamic_mega_universe.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/us_equity_snapshot_pipelines/dynamic_mega_universe.py:7](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/dynamic_mega_universe.py#L7); [src/us_equity_snapshot_pipelines/dynamic_mega_universe.py:22](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/dynamic_mega_universe.py#L22).

### MD-229 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/evidence.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; NYSE/XNYS.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: timezone.
- Evidence: [src/us_equity_snapshot_pipelines/evidence.py:16](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/evidence.py#L16); [src/us_equity_snapshot_pipelines/evidence.py:34](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/evidence.py#L34).

### MD-230 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/global_etf_offensive_rotation_research.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, output_dir, start_date.
- Evidence: [src/us_equity_snapshot_pipelines/global_etf_offensive_rotation_research.py:17](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/global_etf_offensive_rotation_research.py#L17); [src/us_equity_snapshot_pipelines/global_etf_offensive_rotation_research.py:106](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/global_etf_offensive_rotation_research.py#L106).

### MD-231 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/global_etf_rotation_universe_sensitivity.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_snapshot_pipelines/global_etf_rotation_universe_sensitivity.py:14](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/global_etf_rotation_universe_sensitivity.py#L14); [src/us_equity_snapshot_pipelines/global_etf_rotation_universe_sensitivity.py:80](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/global_etf_rotation_universe_sensitivity.py#L80).

### MD-232 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/intraday_scheme_research.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: adjustment, as_of, output_path.
- Evidence: [src/us_equity_snapshot_pipelines/intraday_scheme_research.py:156](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/intraday_scheme_research.py#L156); [src/us_equity_snapshot_pipelines/intraday_scheme_research.py:340](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/intraday_scheme_research.py#L340).

### MD-233 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/decision_data_projection.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: adjustment, as_of, source.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/decision_data_projection.py:113](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/decision_data_projection.py#L113); [src/us_equity_snapshot_pipelines/lifecycle/decision_data_projection.py:114](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/decision_data_projection.py#L114); [src/us_equity_snapshot_pipelines/lifecycle/decision_data_projection.py:149](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/decision_data_projection.py#L149).

### MD-234 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/levered_strategy_benchmark.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/levered_strategy_benchmark.py:5](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/levered_strategy_benchmark.py#L5).

### MD-235 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/soxl_acquisition_orchestration.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: IBKR historical adapter / injected IBKR artifact. Historical-data entitlement, pacing and isolated approved session required; actual plan unverified.
- Price basis: split_dividend_adjusted for ADJUSTED_LAST; split_adjusted for TRADES; actual selected mode must be pinned. Adjustment: Provider-side historical adjustment; TRADES is not raw_unadjusted.
- Time / session / calendar: America/New_York/UTC; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: calendar_id, timezone.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/soxl_acquisition_orchestration.py:154](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_acquisition_orchestration.py#L154); [src/us_equity_snapshot_pipelines/lifecycle/soxl_acquisition_orchestration.py:427](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_acquisition_orchestration.py#L427); [src/us_equity_snapshot_pipelines/lifecycle/soxl_acquisition_orchestration.py:440](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_acquisition_orchestration.py#L440).

### MD-236 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/soxl_adjusted_last_acquisition.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: IBKR historical adapter / injected IBKR artifact. Historical-data entitlement, pacing and isolated approved session required; actual plan unverified.
- Price basis: split_dividend_adjusted for ADJUSTED_LAST; split_adjusted for TRADES; actual selected mode must be pinned. Adjustment: Provider-side historical adjustment; TRADES is not raw_unadjusted.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/soxl_adjusted_last_acquisition.py:22](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_adjusted_last_acquisition.py#L22); [src/us_equity_snapshot_pipelines/lifecycle/soxl_adjusted_last_acquisition.py:627](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_adjusted_last_acquisition.py#L627).

### MD-237 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p1_binding.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Alpaca (SIP unless this row explicitly says otherwise). Owner Basic/free: recent SIP excluded; require end <= now-16min; IEX recent is a distinct feed.
- Price basis: Declared vendor adjustment; see basis anchor (legacy total_return_adjusted is not certified wealth index). Adjustment: Alpaca server adjustment; retain actual feed/adjustment request and source digest.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Provider-adjusted events; independent full action/PIT history not established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, calendar_id, feed, source, timezone.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p1_binding.py:18](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p1_binding.py#L18); [src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p1_binding.py:84](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p1_binding.py#L84); [src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p1_binding.py:197](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p1_binding.py#L197).

### MD-238 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p1_publisher.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Alpaca (SIP unless this row explicitly says otherwise). Owner Basic/free: recent SIP excluded; require end <= now-16min; IEX recent is a distinct feed.
- Price basis: Declared vendor adjustment; see basis anchor (legacy total_return_adjusted is not certified wealth index). Adjustment: Alpaca server adjustment; retain actual feed/adjustment request and source digest.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Provider-adjusted events; independent full action/PIT history not established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, calendar_id, feed, source, timezone.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p1_publisher.py:54](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p1_publisher.py#L54); [src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p1_publisher.py:56](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p1_publisher.py#L56); [src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p1_publisher.py:178](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p1_publisher.py#L178).

### MD-239 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_v7_long_horizon_risk_observation.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: calendar_id, price_field, source.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_v7_long_horizon_risk_observation.py:47](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_v7_long_horizon_risk_observation.py#L47); [src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_v7_long_horizon_risk_observation.py:49](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_v7_long_horizon_risk_observation.py#L49).

### MD-240 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/soxl_isolated_research.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: UTC; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Request/process memory cache or caller-selected store; source/basis cache identity requires review.
- Config/env keys (names only): data parameters/schema fields: price_field, source.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/soxl_isolated_research.py:406](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_isolated_research.py#L406); [src/us_equity_snapshot_pipelines/lifecycle/soxl_isolated_research.py:611](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_isolated_research.py#L611).

### MD-241 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/soxl_pit_input_packager.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: America/New_York; Explicit completed-session/calendar hook present; preserve exact upstream clock and finality policy; XNYS.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, calendar_id, source, timezone.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/soxl_pit_input_packager.py:55](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_pit_input_packager.py#L55); [src/us_equity_snapshot_pipelines/lifecycle/soxl_pit_input_packager.py:103](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_pit_input_packager.py#L103); [src/us_equity_snapshot_pipelines/lifecycle/soxl_pit_input_packager.py:502](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_pit_input_packager.py#L502).

### MD-242 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/soxl_pit_regime_component_producer.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: calendar_id, source, timezone.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/soxl_pit_regime_component_producer.py:11](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_pit_regime_component_producer.py#L11); [src/us_equity_snapshot_pipelines/lifecycle/soxl_pit_regime_component_producer.py:98](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_pit_regime_component_producer.py#L98); [src/us_equity_snapshot_pipelines/lifecycle/soxl_pit_regime_component_producer.py:244](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_pit_regime_component_producer.py#L244).

### MD-243 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/soxl_promotion_runner.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, as_of, calendar_id, price_field, source, timezone.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/soxl_promotion_runner.py:14](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_promotion_runner.py#L14); [src/us_equity_snapshot_pipelines/lifecycle/soxl_promotion_runner.py:448](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_promotion_runner.py#L448); [src/us_equity_snapshot_pipelines/lifecycle/soxl_promotion_runner.py:1364](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_promotion_runner.py#L1364).

### MD-244 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/soxl_three_asset_paired_shadow.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/soxl_three_asset_paired_shadow.py:245](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_three_asset_paired_shadow.py#L245).

### MD-245 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/soxl_v7_nonlive_forward_observation.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/soxl_v7_nonlive_forward_observation.py:19](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_v7_nonlive_forward_observation.py#L19); [src/us_equity_snapshot_pipelines/lifecycle/soxl_v7_nonlive_forward_observation.py:53](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_v7_nonlive_forward_observation.py#L53).

### MD-246 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/soxl_v7_research_review.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Explicit completed-session/calendar hook present; preserve exact upstream clock and finality policy; XNYS.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/soxl_v7_research_review.py:13](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_v7_research_review.py#L13); [src/us_equity_snapshot_pipelines/lifecycle/soxl_v7_research_review.py:36](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/soxl_v7_research_review.py#L36).

### MD-247 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/tqqq_acquisition_orchestration.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: IBKR historical adapter / injected IBKR artifact. Historical-data entitlement, pacing and isolated approved session required; actual plan unverified.
- Price basis: split_dividend_adjusted for ADJUSTED_LAST; split_adjusted for TRADES; actual selected mode must be pinned. Adjustment: Provider-side historical adjustment; TRADES is not raw_unadjusted.
- Time / session / calendar: America/New_York/UTC; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: adjustment, calendar_id, source, timezone.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/tqqq_acquisition_orchestration.py:63](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/tqqq_acquisition_orchestration.py#L63); [src/us_equity_snapshot_pipelines/lifecycle/tqqq_acquisition_orchestration.py:470](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/tqqq_acquisition_orchestration.py#L470); [src/us_equity_snapshot_pipelines/lifecycle/tqqq_acquisition_orchestration.py:501](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/tqqq_acquisition_orchestration.py#L501).

### MD-248 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/tqqq_core_only_free_ohlcv_p1.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Twelve Data split-only source + Yahoo independent verifier (per frozen contract). Provider tier not queried; existing license/rate and two-source gates remain.
- Price basis: split_adjusted (candidate-specific source-assurance policy). Adjustment: Twelve adjust=splits / Yahoo quote close, no dividend-adjusted substitution.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: source.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/tqqq_core_only_free_ohlcv_p1.py:71](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/tqqq_core_only_free_ohlcv_p1.py#L71); [src/us_equity_snapshot_pipelines/lifecycle/tqqq_core_only_free_ohlcv_p1.py:136](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/tqqq_core_only_free_ohlcv_p1.py#L136).

### MD-249 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/tqqq_core_only_p1_binding.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Twelve Data split-only source + Yahoo independent verifier (per frozen contract). Provider tier not queried; existing license/rate and two-source gates remain.
- Price basis: split_adjusted (candidate-specific source-assurance policy). Adjustment: Twelve adjust=splits / Yahoo quote close, no dividend-adjusted substitution.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, binding_sha256, calendar_id, feed, source, timezone.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/tqqq_core_only_p1_binding.py:48](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/tqqq_core_only_p1_binding.py#L48); [src/us_equity_snapshot_pipelines/lifecycle/tqqq_core_only_p1_binding.py:135](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/tqqq_core_only_p1_binding.py#L135); [src/us_equity_snapshot_pipelines/lifecycle/tqqq_core_only_p1_binding.py:642](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/tqqq_core_only_p1_binding.py#L642).

### MD-250 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/tqqq_p2_v2_synthetic_evidence.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, timezone.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/tqqq_p2_v2_synthetic_evidence.py:8](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/tqqq_p2_v2_synthetic_evidence.py#L8); [src/us_equity_snapshot_pipelines/lifecycle/tqqq_p2_v2_synthetic_evidence.py:26](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/tqqq_p2_v2_synthetic_evidence.py#L26).

### MD-251 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/tqqq_promotion_runner.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, end_date, start_date.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/tqqq_promotion_runner.py:56](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/tqqq_promotion_runner.py#L56); [src/us_equity_snapshot_pipelines/lifecycle/tqqq_promotion_runner.py:94](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/tqqq_promotion_runner.py#L94); [src/us_equity_snapshot_pipelines/lifecycle/tqqq_promotion_runner.py:108](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/tqqq_promotion_runner.py#L108).

### MD-252 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/lifecycle/tqqq_v7_relative_benchmark_policy.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_snapshot_pipelines/lifecycle/tqqq_v7_relative_benchmark_policy.py:3](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/lifecycle/tqqq_v7_relative_benchmark_policy.py#L3).

### MD-253 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_concentration_variants.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, output_dir.
- Evidence: [src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_concentration_variants.py:15](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_concentration_variants.py#L15); [src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_concentration_variants.py:21](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_concentration_variants.py#L21).

### MD-254 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_crash_brake_liquidity_followup.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_crash_brake_liquidity_followup.py:24](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_crash_brake_liquidity_followup.py#L24).

### MD-255 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_crash_brake_research.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, output_dir.
- Evidence: [src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_crash_brake_research.py:33](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_crash_brake_research.py#L33); [src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_crash_brake_research.py:107](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_crash_brake_research.py#L107).

### MD-256 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_crash_brake_stress_followup.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_crash_brake_stress_followup.py:144](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_crash_brake_stress_followup.py#L144).

### MD-257 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_dynamic_validation.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, start_date.
- Evidence: [src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_dynamic_validation.py:14](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_dynamic_validation.py#L14); [src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_dynamic_validation.py:192](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_dynamic_validation.py#L192).

### MD-258 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_frequency_risk_research.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, output_dir.
- Evidence: [src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_frequency_risk_research.py:26](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_frequency_risk_research.py#L26); [src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_frequency_risk_research.py:632](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_frequency_risk_research.py#L632).

### MD-259 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_liquidity_diagnostics.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_liquidity_diagnostics.py:48](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_liquidity_diagnostics.py#L48); [src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_liquidity_diagnostics.py:58](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_liquidity_diagnostics.py#L58).

### MD-260 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_robustness.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, output_dir.
- Evidence: [src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_robustness.py:25](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_robustness.py#L25).

### MD-261 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_shadow_live_ledger.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: timezone.
- Evidence: [src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_shadow_live_ledger.py:4](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_shadow_live_ledger.py#L4); [src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_shadow_live_ledger.py:401](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_shadow_live_ledger.py#L401).

### MD-262 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_stress_readiness.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_stress_readiness.py:208](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_stress_readiness.py#L208); [src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_stress_readiness.py:332](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_stress_readiness.py#L332).

### MD-263 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_walk_forward.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date.
- Evidence: [src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_walk_forward.py:19](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_walk_forward.py#L19); [src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_walk_forward.py:37](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/mega_cap_leader_rotation_walk_forward.py#L37).

### MD-264 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/pipelines/mag7_leveraged_pullback_backtest.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, output_dir, start_date.
- Evidence: [src/us_equity_snapshot_pipelines/pipelines/mag7_leveraged_pullback_backtest.py:16](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/pipelines/mag7_leveraged_pullback_backtest.py#L16); [src/us_equity_snapshot_pipelines/pipelines/mag7_leveraged_pullback_backtest.py:134](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/pipelines/mag7_leveraged_pullback_backtest.py#L134).

### MD-265 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/pipelines/mega_cap_leader_rotation_backtest.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, output_dir.
- Evidence: [src/us_equity_snapshot_pipelines/pipelines/mega_cap_leader_rotation_backtest.py:14](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/pipelines/mega_cap_leader_rotation_backtest.py#L14); [src/us_equity_snapshot_pipelines/pipelines/mega_cap_leader_rotation_backtest.py:356](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/pipelines/mega_cap_leader_rotation_backtest.py#L356).

### MD-266 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/pipelines/mega_cap_leader_rotation_snapshot.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/us_equity_snapshot_pipelines/pipelines/mega_cap_leader_rotation_snapshot.py:13](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/pipelines/mega_cap_leader_rotation_snapshot.py#L13); [src/us_equity_snapshot_pipelines/pipelines/mega_cap_leader_rotation_snapshot.py:61](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/pipelines/mega_cap_leader_rotation_snapshot.py#L61).

### MD-267 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/pipelines/new_r1000_residual_strength_20_snapshot.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/us_equity_snapshot_pipelines/pipelines/new_r1000_residual_strength_20_snapshot.py:14](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/pipelines/new_r1000_residual_strength_20_snapshot.py#L14); [src/us_equity_snapshot_pipelines/pipelines/new_r1000_residual_strength_20_snapshot.py:51](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/pipelines/new_r1000_residual_strength_20_snapshot.py#L51).

### MD-268 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/pipelines/russell_1000_multi_factor_backtest.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, start_date.
- Evidence: [src/us_equity_snapshot_pipelines/pipelines/russell_1000_multi_factor_backtest.py:58](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/pipelines/russell_1000_multi_factor_backtest.py#L58); [src/us_equity_snapshot_pipelines/pipelines/russell_1000_multi_factor_backtest.py:67](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/pipelines/russell_1000_multi_factor_backtest.py#L67).

### MD-269 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/plugin_signal_utils.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/us_equity_snapshot_pipelines/plugin_signal_utils.py:11](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/plugin_signal_utils.py#L11); [src/us_equity_snapshot_pipelines/plugin_signal_utils.py:18](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/plugin_signal_utils.py#L18).

### MD-270 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/research/crisis_regime_guard_research.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, output_dir, start_date.
- Evidence: [src/us_equity_snapshot_pipelines/research/crisis_regime_guard_research.py:23](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/research/crisis_regime_guard_research.py#L23); [src/us_equity_snapshot_pipelines/research/crisis_regime_guard_research.py:100](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/research/crisis_regime_guard_research.py#L100).

### MD-271 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/research/leaps_growth_overlay_research.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/us_equity_snapshot_pipelines/research/leaps_growth_overlay_research.py:15](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/research/leaps_growth_overlay_research.py#L15); [src/us_equity_snapshot_pipelines/research/leaps_growth_overlay_research.py:130](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/research/leaps_growth_overlay_research.py#L130).

### MD-272 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/research/memory_semiconductor_momentum_research.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: output_dir.
- Evidence: [src/us_equity_snapshot_pipelines/research/memory_semiconductor_momentum_research.py:23](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/research/memory_semiconductor_momentum_research.py#L23).

### MD-273 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/russell_1000_history.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: UTC; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: end_date, feed, output_path, source, start_date, timezone.
- Evidence: [src/us_equity_snapshot_pipelines/russell_1000_history.py:6](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/russell_1000_history.py#L6); [src/us_equity_snapshot_pipelines/russell_1000_history.py:178](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/russell_1000_history.py#L178).

### MD-274 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/russell_1000_inputs.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, start_date, timezone.
- Evidence: [src/us_equity_snapshot_pipelines/russell_1000_inputs.py:7](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/russell_1000_inputs.py#L7); [src/us_equity_snapshot_pipelines/russell_1000_inputs.py:22](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/russell_1000_inputs.py#L22).

### MD-275 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/russell_1000_proxy_long_history.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/us_equity_snapshot_pipelines/russell_1000_proxy_long_history.py:64](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/russell_1000_proxy_long_history.py#L64); [src/us_equity_snapshot_pipelines/russell_1000_proxy_long_history.py:68](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/russell_1000_proxy_long_history.py#L68).

### MD-276 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/strategy_plugin_runner.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_snapshot_pipelines/strategy_plugin_runner.py:50](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/strategy_plugin_runner.py#L50).

### MD-277 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/tecl_xlk_trend_income_research_inputs.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, source.
- Evidence: [src/us_equity_snapshot_pipelines/tecl_xlk_trend_income_research_inputs.py:9](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/tecl_xlk_trend_income_research_inputs.py#L9); [src/us_equity_snapshot_pipelines/tecl_xlk_trend_income_research_inputs.py:29](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/tecl_xlk_trend_income_research_inputs.py#L29).

### MD-278 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/tqqq_local_no_order_present.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/us_equity_snapshot_pipelines/tqqq_local_no_order_present.py:222](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/tqqq_local_no_order_present.py#L222); [src/us_equity_snapshot_pipelines/tqqq_local_no_order_present.py:264](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/tqqq_local_no_order_present.py#L264); [src/us_equity_snapshot_pipelines/tqqq_local_no_order_present.py:437](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/tqqq_local_no_order_present.py#L437).

### MD-279 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/tqqq_local_no_order_runner.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/us_equity_snapshot_pipelines/tqqq_local_no_order_runner.py:287](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/tqqq_local_no_order_runner.py#L287).

### MD-280 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/universe_audit_contracts.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_snapshot_pipelines/universe_audit_contracts.py:116](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/universe_audit_contracts.py#L116).

### MD-281 — UsEquitySnapshotPipelines: src/us_equity_snapshot_pipelines/universe_audit_engine.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/us_equity_snapshot_pipelines/universe_audit_engine.py:56](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/universe_audit_engine.py#L56); [src/us_equity_snapshot_pipelines/universe_audit_engine.py:63](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/d3217b2297dbde7c3ce7f56ff6b9ef2c99ea2fbb/src/us_equity_snapshot_pipelines/universe_audit_engine.py#L63).

### MD-282 — UsEquityStrategies: docs/research/first_compounding_20260925/r7_joint_account_compare.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: calendar_id, source.
- Evidence: [docs/research/first_compounding_20260925/r7_joint_account_compare.py:95](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/docs/research/first_compounding_20260925/r7_joint_account_compare.py#L95); [docs/research/first_compounding_20260925/r7_joint_account_compare.py:267](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/docs/research/first_compounding_20260925/r7_joint_account_compare.py#L267).

### MD-283 — UsEquityStrategies: scripts/research_us_equity_combo_backtest.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: end_date, start_date.
- Evidence: [scripts/research_us_equity_combo_backtest.py:8](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/scripts/research_us_equity_combo_backtest.py#L8); [scripts/research_us_equity_combo_backtest.py:149](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/scripts/research_us_equity_combo_backtest.py#L149); [scripts/research_us_equity_combo_backtest.py:625](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/scripts/research_us_equity_combo_backtest.py#L625).

### MD-284 — UsEquityStrategies: scripts/run_ux1_async_job.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/run_ux1_async_job.py:424](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/scripts/run_ux1_async_job.py#L424).

### MD-285 — UsEquityStrategies: scripts/run_walk_forward_backtest.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; NYSE.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of, output_path, timezone.
- Evidence: [scripts/run_walk_forward_backtest.py:12](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/scripts/run_walk_forward_backtest.py#L12); [scripts/run_walk_forward_backtest.py:419](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/scripts/run_walk_forward_backtest.py#L419).

### MD-286 — UsEquityStrategies: src/us_equity_strategies/backtests/smart_dca_research_cli.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: source.
- Evidence: [src/us_equity_strategies/backtests/smart_dca_research_cli.py:422](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/backtests/smart_dca_research_cli.py#L422); [src/us_equity_strategies/backtests/smart_dca_research_cli.py:1899](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/backtests/smart_dca_research_cli.py#L1899).

### MD-287 — UsEquityStrategies: src/us_equity_strategies/research/batch_a_member_pack.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_strategies/research/batch_a_member_pack.py:1](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/batch_a_member_pack.py#L1).

### MD-288 — UsEquityStrategies: src/us_equity_strategies/research/soxl_alpaca_input_adapter.py

- Role: artifact/CSV input boundary. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Alpaca (SIP unless this row explicitly says otherwise). Owner Basic/free: recent SIP excluded; require end <= now-16min; IEX recent is a distinct feed.
- Price basis: Declared vendor adjustment; see basis anchor (legacy total_return_adjusted is not certified wealth index). Adjustment: Alpaca server adjustment; retain actual feed/adjustment request and source digest.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Provider-adjusted events; independent full action/PIT history not established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, as_of, binding_sha256, calendar_id, date_cutoff, feed, price_field, source, timezone.
- Evidence: [src/us_equity_strategies/research/soxl_alpaca_input_adapter.py:5](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/soxl_alpaca_input_adapter.py#L5); [src/us_equity_strategies/research/soxl_alpaca_input_adapter.py:138](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/soxl_alpaca_input_adapter.py#L138); [src/us_equity_strategies/research/soxl_alpaca_input_adapter.py:238](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/soxl_alpaca_input_adapter.py#L238).

### MD-289 — UsEquityStrategies: docs/research/first_compounding_20260925/boxx_outer_cash_attribution.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: source.
- Evidence: [docs/research/first_compounding_20260925/boxx_outer_cash_attribution.py:1](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/docs/research/first_compounding_20260925/boxx_outer_cash_attribution.py#L1).

### MD-290 — UsEquityStrategies: docs/research/first_compounding_20260925/boxx_outer_cash_compare.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: source, timezone.
- Evidence: [docs/research/first_compounding_20260925/boxx_outer_cash_compare.py:10](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/docs/research/first_compounding_20260925/boxx_outer_cash_compare.py#L10); [docs/research/first_compounding_20260925/boxx_outer_cash_compare.py:41](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/docs/research/first_compounding_20260925/boxx_outer_cash_compare.py#L41).

### MD-291 — UsEquityStrategies: docs/research/first_compounding_20260925/phase4_qqqm_tqqq_boxx_compare.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: source.
- Evidence: [docs/research/first_compounding_20260925/phase4_qqqm_tqqq_boxx_compare.py:47](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/docs/research/first_compounding_20260925/phase4_qqqm_tqqq_boxx_compare.py#L47); [docs/research/first_compounding_20260925/phase4_qqqm_tqqq_boxx_compare.py:209](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/docs/research/first_compounding_20260925/phase4_qqqm_tqqq_boxx_compare.py#L209).

### MD-292 — UsEquityStrategies: docs/research/first_compounding_20260925/phase5_capital_scale_compare.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [docs/research/first_compounding_20260925/phase5_capital_scale_compare.py:50](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/docs/research/first_compounding_20260925/phase5_capital_scale_compare.py#L50).

### MD-293 — UsEquityStrategies: docs/research/first_compounding_20260925/phase5_schwab_first_open_contract.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [docs/research/first_compounding_20260925/phase5_schwab_first_open_contract.py:30](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/docs/research/first_compounding_20260925/phase5_schwab_first_open_contract.py#L30).

### MD-294 — UsEquityStrategies: docs/research/first_compounding_20260925/phase5_schwab_first_open_dry_run.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [docs/research/first_compounding_20260925/phase5_schwab_first_open_dry_run.py:36](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/docs/research/first_compounding_20260925/phase5_schwab_first_open_dry_run.py#L36).

### MD-295 — UsEquityStrategies: docs/research/first_compounding_20260925/r8_promotion_runner.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: calendar_id, source, timezone.
- Evidence: [docs/research/first_compounding_20260925/r8_promotion_runner.py:15](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/docs/research/first_compounding_20260925/r8_promotion_runner.py#L15); [docs/research/first_compounding_20260925/r8_promotion_runner.py:40](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/docs/research/first_compounding_20260925/r8_promotion_runner.py#L40).

### MD-296 — UsEquityStrategies: docs/research/first_compounding_20260925/small_account_demo.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: calendar_id, source.
- Evidence: [docs/research/first_compounding_20260925/small_account_demo.py:46](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/docs/research/first_compounding_20260925/small_account_demo.py#L46); [docs/research/first_compounding_20260925/small_account_demo.py:56](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/docs/research/first_compounding_20260925/small_account_demo.py#L56).

### MD-297 — UsEquityStrategies: docs/research/first_compounding_20260925/tqqq_cash_budget_compare.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [docs/research/first_compounding_20260925/tqqq_cash_budget_compare.py:4](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/docs/research/first_compounding_20260925/tqqq_cash_budget_compare.py#L4).

### MD-298 — UsEquityStrategies: scripts/run_batch_a_from_gcs.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/run_batch_a_from_gcs.py:24](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/scripts/run_batch_a_from_gcs.py#L24).

### MD-299 — UsEquityStrategies: scripts/run_c3_batch_a_existing_member_baseline.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/run_c3_batch_a_existing_member_baseline.py:184](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/scripts/run_c3_batch_a_existing_member_baseline.py#L184).

### MD-300 — UsEquityStrategies: src/us_equity_strategies/backtest/combo_simulator.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/us_equity_strategies/backtest/combo_simulator.py:73](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/backtest/combo_simulator.py#L73).

### MD-301 — UsEquityStrategies: src/us_equity_strategies/backtest/etf_rotation_simulator.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/us_equity_strategies/backtest/etf_rotation_simulator.py:34](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/backtest/etf_rotation_simulator.py#L34); [src/us_equity_strategies/backtest/etf_rotation_simulator.py:130](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/backtest/etf_rotation_simulator.py#L130).

### MD-302 — UsEquityStrategies: src/us_equity_strategies/backtest/orchestrator_runner.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: lookback_days, timezone.
- Evidence: [src/us_equity_strategies/backtest/orchestrator_runner.py:5](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/backtest/orchestrator_runner.py#L5); [src/us_equity_strategies/backtest/orchestrator_runner.py:75](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/backtest/orchestrator_runner.py#L75).

### MD-303 — UsEquityStrategies: src/us_equity_strategies/backtest/soxl_trend_simulator.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/us_equity_strategies/backtest/soxl_trend_simulator.py:36](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/backtest/soxl_trend_simulator.py#L36); [src/us_equity_strategies/backtest/soxl_trend_simulator.py:116](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/backtest/soxl_trend_simulator.py#L116).

### MD-304 — UsEquityStrategies: src/us_equity_strategies/backtest/spy_boxx_monthly_trend_learning.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of, timezone.
- Evidence: [src/us_equity_strategies/backtest/spy_boxx_monthly_trend_learning.py:6](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/backtest/spy_boxx_monthly_trend_learning.py#L6); [src/us_equity_strategies/backtest/spy_boxx_monthly_trend_learning.py:350](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/backtest/spy_boxx_monthly_trend_learning.py#L350).

### MD-305 — UsEquityStrategies: src/us_equity_strategies/backtests/ibit_smart_dca.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/us_equity_strategies/backtests/ibit_smart_dca.py:34](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/backtests/ibit_smart_dca.py#L34); [src/us_equity_strategies/backtests/ibit_smart_dca.py:93](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/backtests/ibit_smart_dca.py#L93).

### MD-306 — UsEquityStrategies: src/us_equity_strategies/backtests/smart_dca_research.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: UTC; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, start_date.
- Evidence: [src/us_equity_strategies/backtests/smart_dca_research.py:523](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/backtests/smart_dca_research.py#L523); [src/us_equity_strategies/backtests/smart_dca_research.py:544](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/backtests/smart_dca_research.py#L544).

### MD-307 — UsEquityStrategies: src/us_equity_strategies/research/batch_a_dataset.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, as_of, feed, price_field, timezone.
- Evidence: [src/us_equity_strategies/research/batch_a_dataset.py:29](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/batch_a_dataset.py#L29); [src/us_equity_strategies/research/batch_a_dataset.py:30](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/batch_a_dataset.py#L30); [src/us_equity_strategies/research/batch_a_dataset.py:388](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/batch_a_dataset.py#L388).

### MD-308 — UsEquityStrategies: src/us_equity_strategies/research/c3_batch_a_existing_member_baseline.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: timezone.
- Evidence: [src/us_equity_strategies/research/c3_batch_a_existing_member_baseline.py:610](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/c3_batch_a_existing_member_baseline.py#L610); [src/us_equity_strategies/research/c3_batch_a_existing_member_baseline.py:631](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/c3_batch_a_existing_member_baseline.py#L631).

### MD-309 — UsEquityStrategies: src/us_equity_strategies/research/execution_model_adapter.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: feed, price_basis.
- Evidence: [src/us_equity_strategies/research/execution_model_adapter.py:5](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/execution_model_adapter.py#L5); [src/us_equity_strategies/research/execution_model_adapter.py:39](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/execution_model_adapter.py#L39).

### MD-310 — UsEquityStrategies: src/us_equity_strategies/research/global_etf_absolute_volatility.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_strategies/research/global_etf_absolute_volatility.py:28](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/global_etf_absolute_volatility.py#L28); [src/us_equity_strategies/research/global_etf_absolute_volatility.py:47](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/global_etf_absolute_volatility.py#L47).

### MD-311 — UsEquityStrategies: src/us_equity_strategies/research/kelly_core_return_generator.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_strategies/research/kelly_core_return_generator.py:18](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/kelly_core_return_generator.py#L18); [src/us_equity_strategies/research/kelly_core_return_generator.py:175](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/kelly_core_return_generator.py#L175).

### MD-312 — UsEquityStrategies: src/us_equity_strategies/research/kelly_private_runner.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Alpaca (SIP unless this row explicitly says otherwise). Owner Basic/free: recent SIP excluded; require end <= now-16min; IEX recent is a distinct feed.
- Price basis: Declared vendor adjustment; see basis anchor (legacy total_return_adjusted is not certified wealth index). Adjustment: Alpaca server adjustment; retain actual feed/adjustment request and source digest.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider-adjusted events; independent full action/PIT history not established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: source.
- Evidence: [src/us_equity_strategies/research/kelly_private_runner.py:70](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/kelly_private_runner.py#L70); [src/us_equity_strategies/research/kelly_private_runner.py:131](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/kelly_private_runner.py#L131); [src/us_equity_strategies/research/kelly_private_runner.py:171](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/kelly_private_runner.py#L171).

### MD-313 — UsEquityStrategies: src/us_equity_strategies/research/local_member_replay_input.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: calendar_id, source.
- Evidence: [src/us_equity_strategies/research/local_member_replay_input.py:65](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/local_member_replay_input.py#L65).

### MD-314 — UsEquityStrategies: src/us_equity_strategies/research/optimized_member_identity.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: adjustment, calendar_id.
- Evidence: [src/us_equity_strategies/research/optimized_member_identity.py:78](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/optimized_member_identity.py#L78); [src/us_equity_strategies/research/optimized_member_identity.py:88](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/optimized_member_identity.py#L88); [src/us_equity_strategies/research/optimized_member_identity.py:466](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/optimized_member_identity.py#L466).

### MD-315 — UsEquityStrategies: src/us_equity_strategies/research/optimized_strategy_replay.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: America/New_York/UTC; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: calendar_id, end_date, source, start_date, timezone.
- Evidence: [src/us_equity_strategies/research/optimized_strategy_replay.py:172](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/optimized_strategy_replay.py#L172); [src/us_equity_strategies/research/optimized_strategy_replay.py:1073](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/optimized_strategy_replay.py#L1073).

### MD-316 — UsEquityStrategies: src/us_equity_strategies/research/portfolio_candidate_adapter.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_strategies/research/portfolio_candidate_adapter.py:108](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/portfolio_candidate_adapter.py#L108).

### MD-317 — UsEquityStrategies: src/us_equity_strategies/research/r3_joint_evidence.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: price_field.
- Evidence: [src/us_equity_strategies/research/r3_joint_evidence.py:1326](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/r3_joint_evidence.py#L1326); [src/us_equity_strategies/research/r3_joint_evidence.py:1418](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/r3_joint_evidence.py#L1418).

### MD-318 — UsEquityStrategies: src/us_equity_strategies/research/rs04_b3.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: adjustment.
- Evidence: [src/us_equity_strategies/research/rs04_b3.py:3](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/rs04_b3.py#L3); [src/us_equity_strategies/research/rs04_b3.py:4](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/rs04_b3.py#L4).

### MD-319 — UsEquityStrategies: src/us_equity_strategies/research/rs04_b3_live.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: source.
- Evidence: [src/us_equity_strategies/research/rs04_b3_live.py:103](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/rs04_b3_live.py#L103).

### MD-320 — UsEquityStrategies: src/us_equity_strategies/research/rs04_b3_runner.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_strategies/research/rs04_b3_runner.py:4](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/rs04_b3_runner.py#L4); [src/us_equity_strategies/research/rs04_b3_runner.py:349](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/rs04_b3_runner.py#L349).

### MD-321 — UsEquityStrategies: src/us_equity_strategies/research/soxl_core_optimization.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, calendar_id, source.
- Evidence: [src/us_equity_strategies/research/soxl_core_optimization.py:167](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/soxl_core_optimization.py#L167); [src/us_equity_strategies/research/soxl_core_optimization.py:343](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/soxl_core_optimization.py#L343).

### MD-322 — UsEquityStrategies: src/us_equity_strategies/research/soxl_manual_learning.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, source, start_date, timezone.
- Evidence: [src/us_equity_strategies/research/soxl_manual_learning.py:16](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/soxl_manual_learning.py#L16); [src/us_equity_strategies/research/soxl_manual_learning.py:780](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/soxl_manual_learning.py#L780).

### MD-323 — UsEquityStrategies: src/us_equity_strategies/research/soxl_soxx_offline_input_contract.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, price_field.
- Evidence: [src/us_equity_strategies/research/soxl_soxx_offline_input_contract.py:111](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/soxl_soxx_offline_input_contract.py#L111); [src/us_equity_strategies/research/soxl_soxx_offline_input_contract.py:129](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/soxl_soxx_offline_input_contract.py#L129).

### MD-324 — UsEquityStrategies: src/us_equity_strategies/research/soxl_soxx_typed_baseline_result.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: source.
- Evidence: [src/us_equity_strategies/research/soxl_soxx_typed_baseline_result.py:13](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/soxl_soxx_typed_baseline_result.py#L13).

### MD-325 — UsEquityStrategies: src/us_equity_strategies/research/soxl_v7_derisk.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_strategies/research/soxl_v7_derisk.py:127](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/soxl_v7_derisk.py#L127).

### MD-326 — UsEquityStrategies: src/us_equity_strategies/research/soxl_v7_derisk_study.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_strategies/research/soxl_v7_derisk_study.py:157](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/soxl_v7_derisk_study.py#L157).

### MD-327 — UsEquityStrategies: src/us_equity_strategies/research/tqqq_core_optimization.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, calendar_id, source, timezone.
- Evidence: [src/us_equity_strategies/research/tqqq_core_optimization.py:22](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/tqqq_core_optimization.py#L22); [src/us_equity_strategies/research/tqqq_core_optimization.py:410](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/tqqq_core_optimization.py#L410).

### MD-328 — UsEquityStrategies: src/us_equity_strategies/research/tqqq_offline_input_contract.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Yahoo Finance chart / yfinance (or injected CSV). Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: split_dividend_adjusted when auto_adjust=True/adjclose is used; alternate modes require explicit declaration. Adjustment: Vendor adjusted close / yfinance OHLC scaling; retain library/endpoint version.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, price_field.
- Evidence: [src/us_equity_strategies/research/tqqq_offline_input_contract.py:84](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/tqqq_offline_input_contract.py#L84).

### MD-329 — UsEquityStrategies: src/us_equity_strategies/research/tqqq_plugin_release_retention.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_strategies/research/tqqq_plugin_release_retention.py:173](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/tqqq_plugin_release_retention.py#L173).

### MD-330 — UsEquityStrategies: src/us_equity_strategies/research/tqqq_qqq_guard_cash_research.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; XNYS.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of, calendar_id, timezone.
- Evidence: [src/us_equity_strategies/research/tqqq_qqq_guard_cash_research.py:15](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/tqqq_qqq_guard_cash_research.py#L15); [src/us_equity_strategies/research/tqqq_qqq_guard_cash_research.py:73](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/tqqq_qqq_guard_cash_research.py#L73); [src/us_equity_strategies/research/tqqq_qqq_guard_cash_research.py:366](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/tqqq_qqq_guard_cash_research.py#L366).

### MD-331 — UsEquityStrategies: src/us_equity_strategies/research/tqqq_typed_baseline_result.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: source.
- Evidence: [src/us_equity_strategies/research/tqqq_typed_baseline_result.py:14](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/research/tqqq_typed_baseline_result.py#L14).

### MD-332 — UsEquityStrategies: src/us_equity_strategies/strategies/global_etf_rotation.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; NYSE.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: end_date, start_date, timezone.
- Evidence: [src/us_equity_strategies/strategies/global_etf_rotation.py:46](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/strategies/global_etf_rotation.py#L46).

### MD-333 — UsEquityStrategies: src/us_equity_strategies/strategies/ibit_smart_dca.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: UTC; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of.
- Evidence: [src/us_equity_strategies/strategies/ibit_smart_dca.py:489](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/strategies/ibit_smart_dca.py#L489); [src/us_equity_strategies/strategies/ibit_smart_dca.py:749](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/strategies/ibit_smart_dca.py#L749).

### MD-334 — UsEquityStrategies: src/us_equity_strategies/strategies/mega_cap_leader_rotation.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; NYSE; pandas business-day range also used (not exchange calendar).
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, start_date.
- Evidence: [src/us_equity_strategies/strategies/mega_cap_leader_rotation.py:175](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/strategies/mega_cap_leader_rotation.py#L175); [src/us_equity_strategies/strategies/mega_cap_leader_rotation.py:802](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/strategies/mega_cap_leader_rotation.py#L802).

### MD-335 — UsEquityStrategies: src/us_equity_strategies/strategies/nasdaq_sp500_smart_dca.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: America/New_York/UTC; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_strategies/strategies/nasdaq_sp500_smart_dca.py:116](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/strategies/nasdaq_sp500_smart_dca.py#L116); [src/us_equity_strategies/strategies/nasdaq_sp500_smart_dca.py:236](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/strategies/nasdaq_sp500_smart_dca.py#L236).

### MD-336 — UsEquityStrategies: src/us_equity_strategies/strategies/qqq_tech_enhancement.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; NYSE; pandas business-day range also used (not exchange calendar).
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, start_date.
- Evidence: [src/us_equity_strategies/strategies/qqq_tech_enhancement.py:139](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/strategies/qqq_tech_enhancement.py#L139); [src/us_equity_strategies/strategies/qqq_tech_enhancement.py:600](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/strategies/qqq_tech_enhancement.py#L600).

### MD-337 — UsEquityStrategies: src/us_equity_strategies/strategies/soxl_soxx_trend_income.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_strategies/strategies/soxl_soxx_trend_income.py:516](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/strategies/soxl_soxx_trend_income.py#L516).

### MD-338 — UsEquityStrategies: src/us_equity_strategies/strategies/tecl_xlk_trend_income.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_strategies/strategies/tecl_xlk_trend_income.py:510](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/strategies/tecl_xlk_trend_income.py#L510).

### MD-339 — UsEquityStrategies: src/us_equity_strategies/strategies/tqqq_dual_drive_core.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_strategies/strategies/tqqq_dual_drive_core.py:11](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/strategies/tqqq_dual_drive_core.py#L11).

### MD-340 — UsEquityStrategies: src/us_equity_strategies/strategies/tqqq_growth_income.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_strategies/strategies/tqqq_growth_income.py:398](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/strategies/tqqq_growth_income.py#L398).

### MD-341 — UsEquityStrategies: src/us_equity_strategies/strategies/us_equity_combo_core.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_strategies/strategies/us_equity_combo_core.py:205](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/strategies/us_equity_combo_core.py#L205).

### MD-342 — UsEquityStrategies: src/us_equity_strategies/strategies/us_equity_combo_leveraged.py

- Role: series/feature consumer. Proposed migration wave **2**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [src/us_equity_strategies/strategies/us_equity_combo_leveraged.py:158](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/76e04b18180f21f7e04bd1f6e116a3206e2c30fc/src/us_equity_strategies/strategies/us_equity_combo_leveraged.py#L158).

### MD-343 — QuantRuntimeSettings: scripts/market_benchmark_revision_policy.mjs

- Role: benchmark/FX display or publication boundary. Proposed migration wave **3**. Medium: preserve benchmark/FX identity, as-of interval, revision/409 protection and missing data.
- Provider / plan: Stored benchmark projections / configured FX inputs; Yahoo publisher is the current index source. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Price-index close for benchmarks; FX base/quote/time/source must be declared separately. Adjustment: quote.close selected; preserves separate index series IDs.
- Time / session / calendar: Inherited/undeclared at this boundary; Publisher keeps observation dates before current New York date; read model labels Asia/Shanghai; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured console projection store; immutable points + explicit approved revision path; private URL omitted.
- Config/env keys (names only): data parameters/schema fields: source.
- Evidence: [scripts/market_benchmark_revision_policy.mjs:114](https://github.com/QuantStrategyLab/QuantRuntimeSettings/blob/850723f254dd0d2f0af7875b65b0f90de3b9c921/scripts/market_benchmark_revision_policy.mjs#L114).

### MD-344 — QuantRuntimeSettings: scripts/sync_market_benchmark_closes.mjs

- Role: benchmark/FX display or publication boundary. Proposed migration wave **3**. Medium: preserve benchmark/FX identity, as-of interval, revision/409 protection and missing data.
- Provider / plan: Stored benchmark projections / configured FX inputs; Yahoo publisher is the current index source. Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: Price-index close for benchmarks; FX base/quote/time/source must be declared separately. Adjustment: quote.close selected; preserves separate index series IDs.
- Time / session / calendar: America/New_York; Publisher keeps observation dates before current New York date; read model labels Asia/Shanghai; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Configured console projection store; immutable points + explicit approved revision path; private URL omitted.
- Config/env keys (names only): MARKET_BENCHMARK_APPLY_REVISION, MARKET_BENCHMARK_DRY_RUN, MARKET_BENCHMARK_RANGE, MARKET_BENCHMARK_REVISION_PAYLOAD_JSON, MARKET_BENCHMARK_REVISION_TOKEN, MARKET_BENCHMARK_SYNC_TOKEN, MARKET_BENCHMARK_SYNC_URL; data parameters/schema fields: source.
- Evidence: [scripts/sync_market_benchmark_closes.mjs:47](https://github.com/QuantStrategyLab/QuantRuntimeSettings/blob/850723f254dd0d2f0af7875b65b0f90de3b9c921/scripts/sync_market_benchmark_closes.mjs#L47); [scripts/sync_market_benchmark_closes.mjs:72](https://github.com/QuantStrategyLab/QuantRuntimeSettings/blob/850723f254dd0d2f0af7875b65b0f90de3b9c921/scripts/sync_market_benchmark_closes.mjs#L72).

### MD-345 — QuantRuntimeSettings: web/strategy-switch-console/frontend/src/OverviewPage.tsx

- Role: benchmark/FX display or publication boundary. Proposed migration wave **3**. Medium: preserve benchmark/FX identity, as-of interval, revision/409 protection and missing data.
- Provider / plan: Stored benchmark projections / configured FX inputs; Yahoo publisher is the current index source. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Price-index close for benchmarks; FX base/quote/time/source must be declared separately. Adjustment: quote.close selected; preserves separate index series IDs.
- Time / session / calendar: Asia/Shanghai; Publisher keeps observation dates before current New York date; read model labels Asia/Shanghai; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured console projection store; immutable points + explicit approved revision path; private URL omitted.
- Config/env keys (names only): data parameters/schema fields: source.
- Evidence: [web/strategy-switch-console/frontend/src/OverviewPage.tsx:39](https://github.com/QuantStrategyLab/QuantRuntimeSettings/blob/850723f254dd0d2f0af7875b65b0f90de3b9c921/web/strategy-switch-console/frontend/src/OverviewPage.tsx#L39).

### MD-346 — QuantRuntimeSettings: web/strategy-switch-console/frontend/src/marketBenchmark.ts

- Role: benchmark/FX display or publication boundary. Proposed migration wave **3**. Medium: preserve benchmark/FX identity, as-of interval, revision/409 protection and missing data.
- Provider / plan: Stored benchmark projections / configured FX inputs; Yahoo publisher is the current index source. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Price-index close for benchmarks; FX base/quote/time/source must be declared separately. Adjustment: quote.close selected; preserves separate index series IDs.
- Time / session / calendar: Inherited/undeclared at this boundary; Publisher keeps observation dates before current New York date; read model labels Asia/Shanghai; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured console projection store; immutable points + explicit approved revision path; private URL omitted.
- Config/env keys (names only): data parameters/schema fields: timezone.
- Evidence: [web/strategy-switch-console/frontend/src/marketBenchmark.ts:8](https://github.com/QuantStrategyLab/QuantRuntimeSettings/blob/850723f254dd0d2f0af7875b65b0f90de3b9c921/web/strategy-switch-console/frontend/src/marketBenchmark.ts#L8); [web/strategy-switch-console/frontend/src/marketBenchmark.ts:15](https://github.com/QuantStrategyLab/QuantRuntimeSettings/blob/850723f254dd0d2f0af7875b65b0f90de3b9c921/web/strategy-switch-console/frontend/src/marketBenchmark.ts#L15).

### MD-347 — QuantRuntimeSettings: web/strategy-switch-console/frontend/src/presentation.ts

- Role: benchmark/FX display or publication boundary. Proposed migration wave **3**. Medium: preserve benchmark/FX identity, as-of interval, revision/409 protection and missing data.
- Provider / plan: Stored benchmark projections / configured FX inputs; Yahoo publisher is the current index source. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Price-index close for benchmarks; FX base/quote/time/source must be declared separately. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: America/New_York/Asia/Shanghai/UTC; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Request/process memory cache or caller-selected store; source/basis cache identity requires review.
- Config/env keys (names only): data parameters/schema fields: feed, source, timezone.
- Evidence: [web/strategy-switch-console/frontend/src/presentation.ts:303](https://github.com/QuantStrategyLab/QuantRuntimeSettings/blob/850723f254dd0d2f0af7875b65b0f90de3b9c921/web/strategy-switch-console/frontend/src/presentation.ts#L303); [web/strategy-switch-console/frontend/src/presentation.ts:498](https://github.com/QuantStrategyLab/QuantRuntimeSettings/blob/850723f254dd0d2f0af7875b65b0f90de3b9c921/web/strategy-switch-console/frontend/src/presentation.ts#L498).

### MD-348 — QuantRuntimeSettings: web/strategy-switch-console/infrastructure/market_benchmark/market_benchmark.js

- Role: benchmark/FX display or publication boundary. Proposed migration wave **3**. Medium: preserve benchmark/FX identity, as-of interval, revision/409 protection and missing data.
- Provider / plan: Stored benchmark projections / configured FX inputs; Yahoo publisher is the current index source. Public/personal research access; no entitlement/SLA or redistribution rights verified.
- Price basis: Price-index close for benchmarks; FX base/quote/time/source must be declared separately. Adjustment: quote.close selected; preserves separate index series IDs.
- Time / session / calendar: America/New_York/Asia/Shanghai; Publisher keeps observation dates before current New York date; read model labels Asia/Shanghai; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Configured console projection store; immutable points + explicit approved revision path; private URL omitted.
- Config/env keys (names only): data parameters/schema fields: timezone.
- Evidence: [web/strategy-switch-console/infrastructure/market_benchmark/market_benchmark.js:2](https://github.com/QuantStrategyLab/QuantRuntimeSettings/blob/850723f254dd0d2f0af7875b65b0f90de3b9c921/web/strategy-switch-console/infrastructure/market_benchmark/market_benchmark.js#L2); [web/strategy-switch-console/infrastructure/market_benchmark/market_benchmark.js:157](https://github.com/QuantStrategyLab/QuantRuntimeSettings/blob/850723f254dd0d2f0af7875b65b0f90de3b9c921/web/strategy-switch-console/infrastructure/market_benchmark/market_benchmark.js#L157).

### MD-349 — QuantRuntimeSettings: web/strategy-switch-console/infrastructure/market_benchmark/market_benchmark_revision.js

- Role: benchmark/FX display or publication boundary. Proposed migration wave **3**. Medium: preserve benchmark/FX identity, as-of interval, revision/409 protection and missing data.
- Provider / plan: Stored benchmark projections / configured FX inputs; Yahoo publisher is the current index source. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Price-index close for benchmarks; FX base/quote/time/source must be declared separately. Adjustment: quote.close selected; preserves separate index series IDs.
- Time / session / calendar: Inherited/undeclared at this boundary; Publisher keeps observation dates before current New York date; read model labels Asia/Shanghai; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured console projection store; immutable points + explicit approved revision path; private URL omitted.
- Config/env keys (names only): data parameters/schema fields: source.
- Evidence: [web/strategy-switch-console/infrastructure/market_benchmark/market_benchmark_revision.js:101](https://github.com/QuantStrategyLab/QuantRuntimeSettings/blob/850723f254dd0d2f0af7875b65b0f90de3b9c921/web/strategy-switch-console/infrastructure/market_benchmark/market_benchmark_revision.js#L101).

### MD-350 — QuantRuntimeSettings: web/strategy-switch-console/worker.js

- Role: benchmark/FX display or publication boundary. Proposed migration wave **3**. Medium: preserve benchmark/FX identity, as-of interval, revision/409 protection and missing data.
- Provider / plan: Stored benchmark projections / configured FX inputs; Yahoo publisher is the current index source. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Price-index close for benchmarks; FX base/quote/time/source must be declared separately. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: America/New_York/Asia/Shanghai; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured console bindings/object projections; actual private binding values not read.
- Config/env keys (names only): data parameters/schema fields: binding_sha256, source, timezone.
- Evidence: [web/strategy-switch-console/worker.js:72](https://github.com/QuantStrategyLab/QuantRuntimeSettings/blob/850723f254dd0d2f0af7875b65b0f90de3b9c921/web/strategy-switch-console/worker.js#L72); [web/strategy-switch-console/worker.js:310](https://github.com/QuantStrategyLab/QuantRuntimeSettings/blob/850723f254dd0d2f0af7875b65b0f90de3b9c921/web/strategy-switch-console/worker.js#L310).

### MD-351 — QmtPlatform: application/qmt_client.py

- Role: artifact/CSV input boundary. Proposed migration wave **4**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected market-history CSV (no QMT market-data download implemented at this boundary). Inherited source entitlement/retention; no account/subscription query.
- Price basis: unknown_legacy/injected close; CSV schema alone does not certify basis. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller/config-selected CSV or artifact root in approved cloud; local-capable path is source capability, not authorization to use the Mac.
- Config/env keys (names only): data parameters/schema fields: as_of, timezone; caller resolver runtime_config_support.py:44 exposes QMT_MARKET_HISTORY_PATH.
- Evidence: [application/qmt_client.py:6](https://github.com/QuantStrategyLab/QmtPlatform/blob/31d23526bbb5b73f5f140e692640e227ec57f219/application/qmt_client.py#L6); [application/qmt_client.py:36](https://github.com/QuantStrategyLab/QmtPlatform/blob/31d23526bbb5b73f5f140e692640e227ec57f219/application/qmt_client.py#L36).

### MD-352 — QmtPlatform: runtime_preflight.py

- Role: series/feature consumer. Proposed migration wave **4**. Medium: retain upstream basis, availability and immutable binding; compare affected decisions/results.
- Provider / plan: Injected market-history CSV (no QMT market-data download implemented at this boundary). Inherited source entitlement/retention; no account/subscription query.
- Price basis: unknown_legacy/injected close; CSV schema alone does not certify basis. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, timezone; caller resolver runtime_config_support.py:44 exposes QMT_MARKET_HISTORY_PATH.
- Evidence: [runtime_preflight.py:7](https://github.com/QuantStrategyLab/QmtPlatform/blob/31d23526bbb5b73f5f140e692640e227ec57f219/runtime_preflight.py#L7); [runtime_preflight.py:173](https://github.com/QuantStrategyLab/QmtPlatform/blob/31d23526bbb5b73f5f140e692640e227ec57f219/runtime_preflight.py#L173).

### MD-353 — BinancePlatform: application/cycle_service.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: timezone.
- Evidence: [application/cycle_service.py:8](https://github.com/QuantStrategyLab/BinancePlatform/blob/76937ed06de1c6e5a76e807892f8bca4030ab4d1/application/cycle_service.py#L8); [application/cycle_service.py:150](https://github.com/QuantStrategyLab/BinancePlatform/blob/76937ed06de1c6e5a76e807892f8bca4030ab4d1/application/cycle_service.py#L150).

### MD-354 — BinancePlatform: application/execution_service.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [application/execution_service.py:25](https://github.com/QuantStrategyLab/BinancePlatform/blob/76937ed06de1c6e5a76e807892f8bca4030ab4d1/application/execution_service.py#L25).

### MD-355 — BinancePlatform: application/portfolio_service.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: timezone.
- Evidence: [application/portfolio_service.py:6](https://github.com/QuantStrategyLab/BinancePlatform/blob/76937ed06de1c6e5a76e807892f8bca4030ab4d1/application/portfolio_service.py#L6); [application/portfolio_service.py:41](https://github.com/QuantStrategyLab/BinancePlatform/blob/76937ed06de1c6e5a76e807892f8bca4030ab4d1/application/portfolio_service.py#L41).

### MD-356 — BinancePlatform: infra/binance_runtime.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [infra/binance_runtime.py:12](https://github.com/QuantStrategyLab/BinancePlatform/blob/76937ed06de1c6e5a76e807892f8bca4030ab4d1/infra/binance_runtime.py#L12).

### MD-357 — BinancePlatform: main.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: lookback_days, output_path.
- Evidence: [main.py:396](https://github.com/QuantStrategyLab/BinancePlatform/blob/76937ed06de1c6e5a76e807892f8bca4030ab4d1/main.py#L396).

### MD-358 — BinancePlatform: market_snapshot_support.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: timezone.
- Evidence: [market_snapshot_support.py:26](https://github.com/QuantStrategyLab/BinancePlatform/blob/76937ed06de1c6e5a76e807892f8bca4030ab4d1/market_snapshot_support.py#L26); [market_snapshot_support.py:46](https://github.com/QuantStrategyLab/BinancePlatform/blob/76937ed06de1c6e5a76e807892f8bca4030ab4d1/market_snapshot_support.py#L46).

### MD-359 — BinancePlatform: reporting/status_reports.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [reporting/status_reports.py:38](https://github.com/QuantStrategyLab/BinancePlatform/blob/76937ed06de1c6e5a76e807892f8bca4030ab4d1/reporting/status_reports.py#L38).

### MD-360 — BinancePlatform: runtime_support.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Request/process memory cache or caller-selected store; source/basis cache identity requires review.
- Config/env keys (names only): data parameters/schema fields: timezone.
- Evidence: [runtime_support.py:11](https://github.com/QuantStrategyLab/BinancePlatform/blob/76937ed06de1c6e5a76e807892f8bca4030ab4d1/runtime_support.py#L11); [runtime_support.py:798](https://github.com/QuantStrategyLab/BinancePlatform/blob/76937ed06de1c6e5a76e807892f8bca4030ab4d1/runtime_support.py#L798).

### MD-361 — BinancePlatform: scripts/validate_runtime_startup.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract.
- Evidence: [scripts/validate_runtime_startup.py:258](https://github.com/QuantStrategyLab/BinancePlatform/blob/76937ed06de1c6e5a76e807892f8bca4030ab4d1/scripts/validate_runtime_startup.py#L258).

### MD-362 — BinancePlatform: strategy_runtime.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Binance spot / supplied Binance history. Public endpoint limits/venue access; no entitlement/account query.
- Price basis: raw_unadjusted spot; base/quote asset and venue identity required. Adjustment: No equity adjustment; token redenomination/migration events require separate handling.
- Time / session / calendar: Inherited/undeclared at this boundary; UTC daily interval; last returned row is not by itself completed-bar evidence; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Token listing/delisting/redenomination history not supplied by an equity action model.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: timezone.
- Evidence: [strategy_runtime.py:6](https://github.com/QuantStrategyLab/BinancePlatform/blob/76937ed06de1c6e5a76e807892f8bca4030ab4d1/strategy_runtime.py#L6); [strategy_runtime.py:164](https://github.com/QuantStrategyLab/BinancePlatform/blob/76937ed06de1c6e5a76e807892f8bca4030ab4d1/strategy_runtime.py#L164).

### MD-363 — CharlesSchwabPlatform: application/runtime_broker_adapters.py

- Role: artifact/CSV input boundary. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Schwab history/quotes via injected broker adapter. Authorized API/account data entitlement not inspected.
- Price basis: Existing history path declares split_adjusted; execution quotes use contemporaneous units. Adjustment: Broker convention; no independent distribution/factor verification in this inventory.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Request/process memory cache or caller-selected store; source/basis cache identity requires review.
- Config/env keys (names only): data parameters/schema fields: adjustment, as_of, price_basis, source, timezone; caller resolver runtime_config_support.py:282 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_MODE, SCHWAB_FEATURE_SNAPSHOT_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_CACHE_DIR, SCHWAB_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, SCHWAB_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_FALLBACK_MODE, SCHWAB_MARKET_SIGNAL_HANDOFF_INDEX_URI, SCHWAB_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, SCHWAB_MARKET_SIGNAL_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_REQUIRED.
- Evidence: [application/runtime_broker_adapters.py:8](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/application/runtime_broker_adapters.py#L8); [application/runtime_broker_adapters.py:25](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/application/runtime_broker_adapters.py#L25); [application/runtime_broker_adapters.py:27](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/application/runtime_broker_adapters.py#L27).

### MD-364 — CharlesSchwabPlatform: application/runtime_strategy_adapters.py

- Role: artifact/CSV input boundary. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Schwab history/quotes via injected broker adapter. Authorized API/account data entitlement not inspected.
- Price basis: Existing history path declares split_adjusted; execution quotes use contemporaneous units. Adjustment: Broker convention; no independent distribution/factor verification in this inventory.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract; caller resolver runtime_config_support.py:282 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_MODE, SCHWAB_FEATURE_SNAPSHOT_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_CACHE_DIR, SCHWAB_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, SCHWAB_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_FALLBACK_MODE, SCHWAB_MARKET_SIGNAL_HANDOFF_INDEX_URI, SCHWAB_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, SCHWAB_MARKET_SIGNAL_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_REQUIRED.
- Evidence: [application/runtime_strategy_adapters.py:121](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/application/runtime_strategy_adapters.py#L121).

### MD-365 — CharlesSchwabPlatform: application/daily_loss_fact_producer.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Schwab history/quotes via injected broker adapter. Authorized API/account data entitlement not inspected.
- Price basis: Existing history path declares split_adjusted; execution quotes use contemporaneous units. Adjustment: Broker convention; no independent distribution/factor verification in this inventory.
- Time / session / calendar: UTC; Explicit completed-session/calendar hook present; preserve exact upstream clock and finality policy; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: as_of, end_date, start_date; caller resolver runtime_config_support.py:282 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_MODE, SCHWAB_FEATURE_SNAPSHOT_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_CACHE_DIR, SCHWAB_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, SCHWAB_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_FALLBACK_MODE, SCHWAB_MARKET_SIGNAL_HANDOFF_INDEX_URI, SCHWAB_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, SCHWAB_MARKET_SIGNAL_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_REQUIRED.
- Evidence: [application/daily_loss_fact_producer.py:197](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/application/daily_loss_fact_producer.py#L197).

### MD-366 — CharlesSchwabPlatform: application/execution_service.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Schwab history/quotes via injected broker adapter. Authorized API/account data entitlement not inspected.
- Price basis: Existing history path declares split_adjusted; execution quotes use contemporaneous units. Adjustment: Broker convention; no independent distribution/factor verification in this inventory.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract; caller resolver runtime_config_support.py:282 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_MODE, SCHWAB_FEATURE_SNAPSHOT_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_CACHE_DIR, SCHWAB_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, SCHWAB_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_FALLBACK_MODE, SCHWAB_MARKET_SIGNAL_HANDOFF_INDEX_URI, SCHWAB_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, SCHWAB_MARKET_SIGNAL_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_REQUIRED.
- Evidence: [application/execution_service.py:28](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/application/execution_service.py#L28).

### MD-367 — CharlesSchwabPlatform: application/rebalance_service.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Schwab history/quotes via injected broker adapter. Authorized API/account data entitlement not inspected.
- Price basis: Existing history path declares split_adjusted; execution quotes use contemporaneous units. Adjustment: Broker convention; no independent distribution/factor verification in this inventory.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, timezone; caller resolver runtime_config_support.py:282 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_MODE, SCHWAB_FEATURE_SNAPSHOT_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_CACHE_DIR, SCHWAB_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, SCHWAB_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_FALLBACK_MODE, SCHWAB_MARKET_SIGNAL_HANDOFF_INDEX_URI, SCHWAB_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, SCHWAB_MARKET_SIGNAL_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_REQUIRED.
- Evidence: [application/rebalance_service.py:9](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/application/rebalance_service.py#L9); [application/rebalance_service.py:471](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/application/rebalance_service.py#L471).

### MD-368 — CharlesSchwabPlatform: application/signal_provenance.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Schwab history/quotes via injected broker adapter. Authorized API/account data entitlement not inspected.
- Price basis: Existing history path declares split_adjusted; execution quotes use contemporaneous units. Adjustment: Broker convention; no independent distribution/factor verification in this inventory.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: price_basis, source, timezone; caller resolver runtime_config_support.py:282 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_MODE, SCHWAB_FEATURE_SNAPSHOT_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_CACHE_DIR, SCHWAB_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, SCHWAB_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_FALLBACK_MODE, SCHWAB_MARKET_SIGNAL_HANDOFF_INDEX_URI, SCHWAB_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, SCHWAB_MARKET_SIGNAL_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_REQUIRED.
- Evidence: [application/signal_provenance.py:13](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/application/signal_provenance.py#L13); [application/signal_provenance.py:20](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/application/signal_provenance.py#L20).

### MD-369 — CharlesSchwabPlatform: entrypoints/cloud_run.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Schwab history/quotes via injected broker adapter. Authorized API/account data entitlement not inspected.
- Price basis: Existing history path declares split_adjusted; execution quotes use contemporaneous units. Adjustment: Broker convention; no independent distribution/factor verification in this inventory.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: end_date, start_date, timezone; caller resolver runtime_config_support.py:282 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_MODE, SCHWAB_FEATURE_SNAPSHOT_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_CACHE_DIR, SCHWAB_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, SCHWAB_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_FALLBACK_MODE, SCHWAB_MARKET_SIGNAL_HANDOFF_INDEX_URI, SCHWAB_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, SCHWAB_MARKET_SIGNAL_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_REQUIRED.
- Evidence: [entrypoints/cloud_run.py:7](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/entrypoints/cloud_run.py#L7).

### MD-370 — CharlesSchwabPlatform: main.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Schwab history/quotes via injected broker adapter. Authorized API/account data entitlement not inspected.
- Price basis: Existing history path declares split_adjusted; execution quotes use contemporaneous units. Adjustment: Broker convention; no independent distribution/factor verification in this inventory.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract; caller resolver runtime_config_support.py:282 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, SCHWAB_FEATURE_SNAPSHOT_FALLBACK_MODE, SCHWAB_FEATURE_SNAPSHOT_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_CACHE_DIR, SCHWAB_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, SCHWAB_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_FALLBACK_MODE, SCHWAB_MARKET_SIGNAL_HANDOFF_INDEX_URI, SCHWAB_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, SCHWAB_MARKET_SIGNAL_MAX_STALE_DAYS, SCHWAB_MARKET_SIGNAL_REQUIRED.
- Evidence: [main.py:54](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/main.py#L54); [main.py:752](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/blob/f0b84329b6c8de8b10dd38eaa7fda93d310daf85/main.py#L752).

### MD-371 — FirstradePlatform: application/rebalance_service.py

- Role: artifact/CSV input boundary. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Firstrade OHLC and quote API through existing client. Authorized account/session access not inspected.
- Price basis: unknown_legacy for history (no adjustment request proven); quotes contemporaneous. Adjustment: No explicit action adjustment policy established in the inspected OHLC boundary.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: timezone; caller resolver runtime_config_support.py:254 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, FIRSTRADE_DEBUG_POSITION_SNAPSHOT, FIRSTRADE_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FIRSTRADE_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FIRSTRADE_FEATURE_SNAPSHOT_FALLBACK_MODE, FIRSTRADE_FEATURE_SNAPSHOT_MAX_STALE_DAYS, FIRSTRADE_MARKET_SIGNAL_CACHE_DIR, FIRSTRADE_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, FIRSTRADE_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, FIRSTRADE_MARKET_SIGNAL_FALLBACK_MODE, FIRSTRADE_MARKET_SIGNAL_HANDOFF_INDEX_URI, FIRSTRADE_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, FIRSTRADE_MARKET_SIGNAL_MAX_STALE_DAYS, FIRSTRADE_MARKET_SIGNAL_REQUIRED.
- Evidence: [application/rebalance_service.py:14](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/application/rebalance_service.py#L14); [application/rebalance_service.py:127](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/application/rebalance_service.py#L127).

### MD-372 — FirstradePlatform: application/runtime_broker_adapters.py

- Role: artifact/CSV input boundary. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Firstrade OHLC and quote API through existing client. Authorized account/session access not inspected.
- Price basis: unknown_legacy for history (no adjustment request proven); quotes contemporaneous. Adjustment: No explicit action adjustment policy established in the inspected OHLC boundary.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Request/process memory cache or caller-selected store; source/basis cache identity requires review.
- Config/env keys (names only): data parameters/schema fields: as_of, timezone; caller resolver runtime_config_support.py:254 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, FIRSTRADE_DEBUG_POSITION_SNAPSHOT, FIRSTRADE_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FIRSTRADE_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FIRSTRADE_FEATURE_SNAPSHOT_FALLBACK_MODE, FIRSTRADE_FEATURE_SNAPSHOT_MAX_STALE_DAYS, FIRSTRADE_MARKET_SIGNAL_CACHE_DIR, FIRSTRADE_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, FIRSTRADE_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, FIRSTRADE_MARKET_SIGNAL_FALLBACK_MODE, FIRSTRADE_MARKET_SIGNAL_HANDOFF_INDEX_URI, FIRSTRADE_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, FIRSTRADE_MARKET_SIGNAL_MAX_STALE_DAYS, FIRSTRADE_MARKET_SIGNAL_REQUIRED.
- Evidence: [application/runtime_broker_adapters.py:7](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/application/runtime_broker_adapters.py#L7); [application/runtime_broker_adapters.py:180](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/application/runtime_broker_adapters.py#L180).

### MD-373 — FirstradePlatform: application/execution_service.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Firstrade OHLC and quote API through existing client. Authorized account/session access not inspected.
- Price basis: unknown_legacy for history (no adjustment request proven); quotes contemporaneous. Adjustment: No explicit action adjustment policy established in the inspected OHLC boundary.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract; caller resolver runtime_config_support.py:254 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, FIRSTRADE_DEBUG_POSITION_SNAPSHOT, FIRSTRADE_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FIRSTRADE_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FIRSTRADE_FEATURE_SNAPSHOT_FALLBACK_MODE, FIRSTRADE_FEATURE_SNAPSHOT_MAX_STALE_DAYS, FIRSTRADE_MARKET_SIGNAL_CACHE_DIR, FIRSTRADE_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, FIRSTRADE_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, FIRSTRADE_MARKET_SIGNAL_FALLBACK_MODE, FIRSTRADE_MARKET_SIGNAL_HANDOFF_INDEX_URI, FIRSTRADE_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, FIRSTRADE_MARKET_SIGNAL_MAX_STALE_DAYS, FIRSTRADE_MARKET_SIGNAL_REQUIRED.
- Evidence: [application/execution_service.py:28](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/application/execution_service.py#L28).

### MD-374 — FirstradePlatform: entrypoints/cloud_run.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Firstrade OHLC and quote API through existing client. Authorized account/session access not inspected.
- Price basis: unknown_legacy for history (no adjustment request proven); quotes contemporaneous. Adjustment: No explicit action adjustment policy established in the inspected OHLC boundary.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; NYSE.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: end_date, start_date, timezone; caller resolver runtime_config_support.py:254 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, FIRSTRADE_DEBUG_POSITION_SNAPSHOT, FIRSTRADE_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FIRSTRADE_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FIRSTRADE_FEATURE_SNAPSHOT_FALLBACK_MODE, FIRSTRADE_FEATURE_SNAPSHOT_MAX_STALE_DAYS, FIRSTRADE_MARKET_SIGNAL_CACHE_DIR, FIRSTRADE_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, FIRSTRADE_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, FIRSTRADE_MARKET_SIGNAL_FALLBACK_MODE, FIRSTRADE_MARKET_SIGNAL_HANDOFF_INDEX_URI, FIRSTRADE_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, FIRSTRADE_MARKET_SIGNAL_MAX_STALE_DAYS, FIRSTRADE_MARKET_SIGNAL_REQUIRED.
- Evidence: [entrypoints/cloud_run.py:7](https://github.com/QuantStrategyLab/FirstradePlatform/blob/537ab80bb76dfc6b29591a5951152b905ffbf813/entrypoints/cloud_run.py#L7).

### MD-375 — InteractiveBrokersPlatform: strategy_runtime.py

- Role: artifact/CSV input boundary. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: IBKR TRADES for signals; yfinance history fallback/probe. Inherited source entitlement/retention; no account/subscription query.
- Price basis: split_adjusted intended; missing Yahoo Close falls back to split_dividend_adjusted Adj Close. Adjustment: ADJUSTED_LAST suppressed by signal proxy; yfinance auto_adjust=False; fallback OHLC coherence unresolved.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Request/process memory cache or caller-selected store; source/basis cache identity requires review.
- Config/env keys (names only): data parameters/schema fields: as_of, bar_size, duration, market_calendar; caller resolver runtime_config_support.py:381 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, IBKR_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, IBKR_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, IBKR_FEATURE_SNAPSHOT_FALLBACK_MODE, IBKR_FEATURE_SNAPSHOT_MAX_STALE_DAYS, IBKR_MARKET, IBKR_MARKET_CALENDAR, IBKR_MARKET_CURRENCY, IBKR_MARKET_DATA_SYMBOL_SUFFIX, IBKR_MARKET_EXCHANGE, IBKR_MARKET_SIGNAL_CACHE_DIR, IBKR_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, IBKR_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, IBKR_MARKET_SIGNAL_FALLBACK_MODE, IBKR_MARKET_SIGNAL_HANDOFF_INDEX_URI, IBKR_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, IBKR_MARKET_SIGNAL_MAX_STALE_DAYS, IBKR_MARKET_SIGNAL_REQUIRED, IBKR_MARKET_TIMEZONE.
- Evidence: [strategy_runtime.py:12](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/strategy_runtime.py#L12); [strategy_runtime.py:304](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/strategy_runtime.py#L304).

### MD-376 — InteractiveBrokersPlatform: application/execution_service.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: timezone; caller resolver runtime_config_support.py:381 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, IBKR_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, IBKR_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, IBKR_FEATURE_SNAPSHOT_FALLBACK_MODE, IBKR_FEATURE_SNAPSHOT_MAX_STALE_DAYS, IBKR_MARKET, IBKR_MARKET_CALENDAR, IBKR_MARKET_CURRENCY, IBKR_MARKET_DATA_SYMBOL_SUFFIX, IBKR_MARKET_EXCHANGE, IBKR_MARKET_SIGNAL_CACHE_DIR, IBKR_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, IBKR_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, IBKR_MARKET_SIGNAL_FALLBACK_MODE, IBKR_MARKET_SIGNAL_HANDOFF_INDEX_URI, IBKR_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, IBKR_MARKET_SIGNAL_MAX_STALE_DAYS, IBKR_MARKET_SIGNAL_REQUIRED, IBKR_MARKET_TIMEZONE.
- Evidence: [application/execution_service.py:12](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/application/execution_service.py#L12); [application/execution_service.py:598](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/application/execution_service.py#L598).

### MD-377 — InteractiveBrokersPlatform: application/ibkr_market_data.py

- Role: execution quote wrapper. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Injected IBKR quote fetcher, entitlement-error summary wrapper. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Contemporaneous broker quote semantics inherited from callable. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract; caller resolver runtime_config_support.py:381 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, IBKR_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, IBKR_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, IBKR_FEATURE_SNAPSHOT_FALLBACK_MODE, IBKR_FEATURE_SNAPSHOT_MAX_STALE_DAYS, IBKR_MARKET, IBKR_MARKET_CALENDAR, IBKR_MARKET_CURRENCY, IBKR_MARKET_DATA_SYMBOL_SUFFIX, IBKR_MARKET_EXCHANGE, IBKR_MARKET_SIGNAL_CACHE_DIR, IBKR_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, IBKR_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, IBKR_MARKET_SIGNAL_FALLBACK_MODE, IBKR_MARKET_SIGNAL_HANDOFF_INDEX_URI, IBKR_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, IBKR_MARKET_SIGNAL_MAX_STALE_DAYS, IBKR_MARKET_SIGNAL_REQUIRED, IBKR_MARKET_TIMEZONE.
- Evidence: [application/ibkr_market_data.py:18](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/application/ibkr_market_data.py#L18).

### MD-378 — InteractiveBrokersPlatform: application/runtime_broker_adapters.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, timezone; caller resolver runtime_config_support.py:381 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, IBKR_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, IBKR_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, IBKR_FEATURE_SNAPSHOT_FALLBACK_MODE, IBKR_FEATURE_SNAPSHOT_MAX_STALE_DAYS, IBKR_MARKET, IBKR_MARKET_CALENDAR, IBKR_MARKET_CURRENCY, IBKR_MARKET_DATA_SYMBOL_SUFFIX, IBKR_MARKET_EXCHANGE, IBKR_MARKET_SIGNAL_CACHE_DIR, IBKR_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, IBKR_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, IBKR_MARKET_SIGNAL_FALLBACK_MODE, IBKR_MARKET_SIGNAL_HANDOFF_INDEX_URI, IBKR_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, IBKR_MARKET_SIGNAL_MAX_STALE_DAYS, IBKR_MARKET_SIGNAL_REQUIRED, IBKR_MARKET_TIMEZONE.
- Evidence: [application/runtime_broker_adapters.py:6](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/application/runtime_broker_adapters.py#L6); [application/runtime_broker_adapters.py:38](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/application/runtime_broker_adapters.py#L38).

### MD-379 — InteractiveBrokersPlatform: application/runtime_strategy_adapters.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: IBKR TRADES for signals; yfinance history fallback/probe. Historical-data entitlement, pacing and isolated approved session required; actual plan unverified.
- Price basis: split_adjusted intended; missing Yahoo Close falls back to split_dividend_adjusted Adj Close. Adjustment: ADJUSTED_LAST suppressed by signal proxy; yfinance auto_adjust=False; fallback OHLC coherence unresolved.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Provider adjustments; action/PIT revision coverage not independently established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: as_of, bar_size, duration, price_basis, source; caller resolver runtime_config_support.py:381 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, IBKR_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, IBKR_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, IBKR_FEATURE_SNAPSHOT_FALLBACK_MODE, IBKR_FEATURE_SNAPSHOT_MAX_STALE_DAYS, IBKR_MARKET, IBKR_MARKET_CALENDAR, IBKR_MARKET_CURRENCY, IBKR_MARKET_DATA_SYMBOL_SUFFIX, IBKR_MARKET_EXCHANGE, IBKR_MARKET_SIGNAL_CACHE_DIR, IBKR_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, IBKR_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, IBKR_MARKET_SIGNAL_FALLBACK_MODE, IBKR_MARKET_SIGNAL_HANDOFF_INDEX_URI, IBKR_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, IBKR_MARKET_SIGNAL_MAX_STALE_DAYS, IBKR_MARKET_SIGNAL_REQUIRED, IBKR_MARKET_TIMEZONE.
- Evidence: [application/runtime_strategy_adapters.py:77](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/application/runtime_strategy_adapters.py#L77).

### MD-380 — InteractiveBrokersPlatform: application/signal_provenance.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: price_basis, source, timezone; caller resolver runtime_config_support.py:381 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, IBKR_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, IBKR_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, IBKR_FEATURE_SNAPSHOT_FALLBACK_MODE, IBKR_FEATURE_SNAPSHOT_MAX_STALE_DAYS, IBKR_MARKET, IBKR_MARKET_CALENDAR, IBKR_MARKET_CURRENCY, IBKR_MARKET_DATA_SYMBOL_SUFFIX, IBKR_MARKET_EXCHANGE, IBKR_MARKET_SIGNAL_CACHE_DIR, IBKR_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, IBKR_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, IBKR_MARKET_SIGNAL_FALLBACK_MODE, IBKR_MARKET_SIGNAL_HANDOFF_INDEX_URI, IBKR_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, IBKR_MARKET_SIGNAL_MAX_STALE_DAYS, IBKR_MARKET_SIGNAL_REQUIRED, IBKR_MARKET_TIMEZONE.
- Evidence: [application/signal_provenance.py:13](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/application/signal_provenance.py#L13); [application/signal_provenance.py:20](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/application/signal_provenance.py#L20).

### MD-381 — InteractiveBrokersPlatform: entrypoints/cloud_run.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; NYSE.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: end_date, start_date, timezone; caller resolver runtime_config_support.py:381 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, IBKR_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, IBKR_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, IBKR_FEATURE_SNAPSHOT_FALLBACK_MODE, IBKR_FEATURE_SNAPSHOT_MAX_STALE_DAYS, IBKR_MARKET, IBKR_MARKET_CALENDAR, IBKR_MARKET_CURRENCY, IBKR_MARKET_DATA_SYMBOL_SUFFIX, IBKR_MARKET_EXCHANGE, IBKR_MARKET_SIGNAL_CACHE_DIR, IBKR_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, IBKR_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, IBKR_MARKET_SIGNAL_FALLBACK_MODE, IBKR_MARKET_SIGNAL_HANDOFF_INDEX_URI, IBKR_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, IBKR_MARKET_SIGNAL_MAX_STALE_DAYS, IBKR_MARKET_SIGNAL_REQUIRED, IBKR_MARKET_TIMEZONE.
- Evidence: [entrypoints/cloud_run.py:11](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/entrypoints/cloud_run.py#L11).

### MD-382 — InteractiveBrokersPlatform: main.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Configured approved cloud object root and immutable manifest/generation; private names omitted.
- Config/env keys (names only): data parameters/schema fields: bar_size, duration, market_calendar, market_timezone; caller resolver runtime_config_support.py:381 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, IBKR_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, IBKR_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, IBKR_FEATURE_SNAPSHOT_FALLBACK_MODE, IBKR_FEATURE_SNAPSHOT_MAX_STALE_DAYS, IBKR_MARKET, IBKR_MARKET_CALENDAR, IBKR_MARKET_CURRENCY, IBKR_MARKET_DATA_SYMBOL_SUFFIX, IBKR_MARKET_EXCHANGE, IBKR_MARKET_SIGNAL_CACHE_DIR, IBKR_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, IBKR_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, IBKR_MARKET_SIGNAL_FALLBACK_MODE, IBKR_MARKET_SIGNAL_HANDOFF_INDEX_URI, IBKR_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, IBKR_MARKET_SIGNAL_MAX_STALE_DAYS, IBKR_MARKET_SIGNAL_REQUIRED, IBKR_MARKET_TIMEZONE.
- Evidence: [main.py:85](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/main.py#L85); [main.py:375](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/main.py#L375).

### MD-383 — InteractiveBrokersPlatform: scripts/print_strategy_switch_env_plan.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: Injected upstream artifact/series; provider not established at this boundary. Inherited source entitlement/retention; no account/subscription query.
- Price basis: Inherited/unknown_legacy; inspect the upstream binding, no automatic canonical mapping. Adjustment: No local adjustment established; numeric values inherit caller semantics.
- Time / session / calendar: Asia/Hong_Kong; Inherited; no local completed-session proof established; XHKG.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Request/process memory cache or caller-selected store; source/basis cache identity requires review.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract; caller resolver runtime_config_support.py:381 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, IBKR_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, IBKR_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, IBKR_FEATURE_SNAPSHOT_FALLBACK_MODE, IBKR_FEATURE_SNAPSHOT_MAX_STALE_DAYS, IBKR_MARKET, IBKR_MARKET_CALENDAR, IBKR_MARKET_CURRENCY, IBKR_MARKET_DATA_SYMBOL_SUFFIX, IBKR_MARKET_EXCHANGE, IBKR_MARKET_SIGNAL_CACHE_DIR, IBKR_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, IBKR_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, IBKR_MARKET_SIGNAL_FALLBACK_MODE, IBKR_MARKET_SIGNAL_HANDOFF_INDEX_URI, IBKR_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, IBKR_MARKET_SIGNAL_MAX_STALE_DAYS, IBKR_MARKET_SIGNAL_REQUIRED, IBKR_MARKET_TIMEZONE.
- Evidence: [scripts/print_strategy_switch_env_plan.py:62](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/scripts/print_strategy_switch_env_plan.py#L62); [scripts/print_strategy_switch_env_plan.py:72](https://github.com/QuantStrategyLab/InteractiveBrokersPlatform/blob/8e173b2bd1cb903f00ffbfe77e7f5f709aa00b7a/scripts/print_strategy_switch_env_plan.py#L72).

### MD-384 — LongBridgePlatform: application/runtime_broker_adapters.py

- Role: artifact/CSV input boundary. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: LongPort/LongBridge quote/history adapter. Market-specific quote entitlement not inspected.
- Price basis: Provider ForwardAdjust history; exact split/dividend mapping not independently certified. Adjustment: Native adjustment enum, distinct from last_done execution quote.
- Time / session / calendar: UTC; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates; pandas business-day range also used (not exchange calendar).
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Request/process memory cache or caller-selected store; source/basis cache identity requires review.
- Config/env keys (names only): data parameters/schema fields: as_of, timezone; caller resolver runtime_config_support.py:334 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, LONGBRIDGE_DEBUG_POSITION_SNAPSHOT, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_MODE, LONGBRIDGE_FEATURE_SNAPSHOT_MAX_STALE_DAYS, LONGBRIDGE_MARKET, LONGBRIDGE_MARKET_CALENDAR, LONGBRIDGE_MARKET_SIGNAL_CACHE_DIR, LONGBRIDGE_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, LONGBRIDGE_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, LONGBRIDGE_MARKET_SIGNAL_FALLBACK_MODE, LONGBRIDGE_MARKET_SIGNAL_HANDOFF_INDEX_URI, LONGBRIDGE_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, LONGBRIDGE_MARKET_SIGNAL_MAX_STALE_DAYS, LONGBRIDGE_MARKET_SIGNAL_REQUIRED, LONGBRIDGE_MARKET_TIMEZONE.
- Evidence: [application/runtime_broker_adapters.py:7](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/application/runtime_broker_adapters.py#L7); [application/runtime_broker_adapters.py:47](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/application/runtime_broker_adapters.py#L47); [application/runtime_broker_adapters.py:68](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/application/runtime_broker_adapters.py#L68).

### MD-385 — LongBridgePlatform: application/runtime_strategy_adapters.py

- Role: artifact/CSV input boundary. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: LongPort/LongBridge quote/history adapter. Market-specific quote entitlement not inspected.
- Price basis: Provider ForwardAdjust history; exact split/dividend mapping not independently certified. Adjustment: Native adjustment enum, distinct from last_done execution quote.
- Time / session / calendar: UTC; Inherited; no local completed-session proof established; NYSE/XNYS.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: end_date, start_date, timezone; caller resolver runtime_config_support.py:334 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, LONGBRIDGE_DEBUG_POSITION_SNAPSHOT, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_MODE, LONGBRIDGE_FEATURE_SNAPSHOT_MAX_STALE_DAYS, LONGBRIDGE_MARKET, LONGBRIDGE_MARKET_CALENDAR, LONGBRIDGE_MARKET_SIGNAL_CACHE_DIR, LONGBRIDGE_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, LONGBRIDGE_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, LONGBRIDGE_MARKET_SIGNAL_FALLBACK_MODE, LONGBRIDGE_MARKET_SIGNAL_HANDOFF_INDEX_URI, LONGBRIDGE_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, LONGBRIDGE_MARKET_SIGNAL_MAX_STALE_DAYS, LONGBRIDGE_MARKET_SIGNAL_REQUIRED, LONGBRIDGE_MARKET_TIMEZONE.
- Evidence: [application/runtime_strategy_adapters.py:7](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/application/runtime_strategy_adapters.py#L7); [application/runtime_strategy_adapters.py:90](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/application/runtime_strategy_adapters.py#L90).

### MD-386 — LongBridgePlatform: application/execution_service.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: LongPort/LongBridge quote/history adapter. Market-specific quote entitlement not inspected.
- Price basis: Provider ForwardAdjust history; exact split/dividend mapping not independently certified. Adjustment: Native adjustment enum, distinct from last_done execution quote.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract; caller resolver runtime_config_support.py:334 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, LONGBRIDGE_DEBUG_POSITION_SNAPSHOT, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_MODE, LONGBRIDGE_FEATURE_SNAPSHOT_MAX_STALE_DAYS, LONGBRIDGE_MARKET, LONGBRIDGE_MARKET_CALENDAR, LONGBRIDGE_MARKET_SIGNAL_CACHE_DIR, LONGBRIDGE_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, LONGBRIDGE_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, LONGBRIDGE_MARKET_SIGNAL_FALLBACK_MODE, LONGBRIDGE_MARKET_SIGNAL_HANDOFF_INDEX_URI, LONGBRIDGE_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, LONGBRIDGE_MARKET_SIGNAL_MAX_STALE_DAYS, LONGBRIDGE_MARKET_SIGNAL_REQUIRED, LONGBRIDGE_MARKET_TIMEZONE.
- Evidence: [application/execution_service.py:36](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/application/execution_service.py#L36).

### MD-387 — LongBridgePlatform: application/longbridge_portfolio.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: LongPort/LongBridge quote/history adapter. Market-specific quote entitlement not inspected.
- Price basis: Provider ForwardAdjust history; exact split/dividend mapping not independently certified. Adjustment: Native adjustment enum, distinct from last_done execution quote.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: source, timezone; caller resolver runtime_config_support.py:334 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, LONGBRIDGE_DEBUG_POSITION_SNAPSHOT, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_MODE, LONGBRIDGE_FEATURE_SNAPSHOT_MAX_STALE_DAYS, LONGBRIDGE_MARKET, LONGBRIDGE_MARKET_CALENDAR, LONGBRIDGE_MARKET_SIGNAL_CACHE_DIR, LONGBRIDGE_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, LONGBRIDGE_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, LONGBRIDGE_MARKET_SIGNAL_FALLBACK_MODE, LONGBRIDGE_MARKET_SIGNAL_HANDOFF_INDEX_URI, LONGBRIDGE_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, LONGBRIDGE_MARKET_SIGNAL_MAX_STALE_DAYS, LONGBRIDGE_MARKET_SIGNAL_REQUIRED, LONGBRIDGE_MARKET_TIMEZONE.
- Evidence: [application/longbridge_portfolio.py:4](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/application/longbridge_portfolio.py#L4); [application/longbridge_portfolio.py:73](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/application/longbridge_portfolio.py#L73).

### MD-388 — LongBridgePlatform: application/rebalance_service.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: LongPort/LongBridge quote/history adapter. Market-specific quote entitlement not inspected.
- Price basis: Provider ForwardAdjust history; exact split/dividend mapping not independently certified. Adjustment: Native adjustment enum, distinct from last_done execution quote.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract; caller resolver runtime_config_support.py:334 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, LONGBRIDGE_DEBUG_POSITION_SNAPSHOT, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_MODE, LONGBRIDGE_FEATURE_SNAPSHOT_MAX_STALE_DAYS, LONGBRIDGE_MARKET, LONGBRIDGE_MARKET_CALENDAR, LONGBRIDGE_MARKET_SIGNAL_CACHE_DIR, LONGBRIDGE_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, LONGBRIDGE_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, LONGBRIDGE_MARKET_SIGNAL_FALLBACK_MODE, LONGBRIDGE_MARKET_SIGNAL_HANDOFF_INDEX_URI, LONGBRIDGE_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, LONGBRIDGE_MARKET_SIGNAL_MAX_STALE_DAYS, LONGBRIDGE_MARKET_SIGNAL_REQUIRED, LONGBRIDGE_MARKET_TIMEZONE.
- Evidence: [application/rebalance_service.py:327](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/application/rebalance_service.py#L327).

### MD-389 — LongBridgePlatform: entrypoints/cloud_run.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: LongPort/LongBridge quote/history adapter. Market-specific quote entitlement not inspected.
- Price basis: Provider ForwardAdjust history; exact split/dividend mapping not independently certified. Adjustment: Native adjustment enum, distinct from last_done execution quote.
- Time / session / calendar: America/New_York; Inherited; no local completed-session proof established; NYSE.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Caller-supplied input/in-memory result; no private location inspected.
- Config/env keys (names only): data parameters/schema fields: end_date, start_date, timezone; caller resolver runtime_config_support.py:334 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, LONGBRIDGE_DEBUG_POSITION_SNAPSHOT, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_MODE, LONGBRIDGE_FEATURE_SNAPSHOT_MAX_STALE_DAYS, LONGBRIDGE_MARKET, LONGBRIDGE_MARKET_CALENDAR, LONGBRIDGE_MARKET_SIGNAL_CACHE_DIR, LONGBRIDGE_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, LONGBRIDGE_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, LONGBRIDGE_MARKET_SIGNAL_FALLBACK_MODE, LONGBRIDGE_MARKET_SIGNAL_HANDOFF_INDEX_URI, LONGBRIDGE_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, LONGBRIDGE_MARKET_SIGNAL_MAX_STALE_DAYS, LONGBRIDGE_MARKET_SIGNAL_REQUIRED, LONGBRIDGE_MARKET_TIMEZONE.
- Evidence: [entrypoints/cloud_run.py:7](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/entrypoints/cloud_run.py#L7).

### MD-390 — LongBridgePlatform: main.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: LongPort/LongBridge quote/history adapter. Market-specific quote entitlement not inspected.
- Price basis: Provider ForwardAdjust history; exact split/dividend mapping not independently certified. Adjustment: Native adjustment enum, distinct from last_done execution quote.
- Time / session / calendar: Inherited/undeclared at this boundary; Inherited; no local completed-session proof established; Inherited/undeclared; not inferred from weekday dates.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Request/process memory cache or caller-selected store; source/basis cache identity requires review.
- Config/env keys (names only): ACCOUNT_HISTORY_RECORDING_ENABLED; data parameters/schema fields: market_calendar, market_timezone, timezone; caller resolver runtime_config_support.py:334 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, LONGBRIDGE_DEBUG_POSITION_SNAPSHOT, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_MODE, LONGBRIDGE_FEATURE_SNAPSHOT_MAX_STALE_DAYS, LONGBRIDGE_MARKET, LONGBRIDGE_MARKET_CALENDAR, LONGBRIDGE_MARKET_SIGNAL_CACHE_DIR, LONGBRIDGE_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, LONGBRIDGE_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, LONGBRIDGE_MARKET_SIGNAL_FALLBACK_MODE, LONGBRIDGE_MARKET_SIGNAL_HANDOFF_INDEX_URI, LONGBRIDGE_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, LONGBRIDGE_MARKET_SIGNAL_MAX_STALE_DAYS, LONGBRIDGE_MARKET_SIGNAL_REQUIRED, LONGBRIDGE_MARKET_TIMEZONE.
- Evidence: [main.py:160](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/main.py#L160); [main.py:165](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/main.py#L165).

### MD-391 — LongBridgePlatform: scripts/print_strategy_switch_env_plan.py

- Role: series/feature consumer. Proposed migration wave **5**. High/live-last: separately approved per-consumer provider/feed/basis/calendar/QPK/binding pin; retain current runtime and all order/risk guards.
- Provider / plan: LongPort/LongBridge quote/history adapter. Market-specific quote entitlement not inspected.
- Price basis: Provider ForwardAdjust history; exact split/dividend mapping not independently certified. Adjustment: Native adjustment enum, distinct from last_done execution quote.
- Time / session / calendar: Asia/Hong_Kong; Inherited; no local completed-session proof established; XHKG.
- Corporate actions: Inherited; no complete local action ledger established.
- Cache/storage: Request/process memory cache or caller-selected store; source/basis cache identity requires review.
- Config/env keys (names only): No data-specific env lookup in this file; caller arguments/injected contract; caller resolver runtime_config_support.py:334 exposes FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, FEATURE_SNAPSHOT_FALLBACK_MODE, FEATURE_SNAPSHOT_MAX_STALE_DAYS, LONGBRIDGE_DEBUG_POSITION_SNAPSHOT, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_CACHE_DIR, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_MAX_STALE_DAYS, LONGBRIDGE_FEATURE_SNAPSHOT_FALLBACK_MODE, LONGBRIDGE_FEATURE_SNAPSHOT_MAX_STALE_DAYS, LONGBRIDGE_MARKET, LONGBRIDGE_MARKET_CALENDAR, LONGBRIDGE_MARKET_SIGNAL_CACHE_DIR, LONGBRIDGE_MARKET_SIGNAL_CONSUMPTION_AUDIT_URI, LONGBRIDGE_MARKET_SIGNAL_FALLBACK_MAX_STALE_DAYS, LONGBRIDGE_MARKET_SIGNAL_FALLBACK_MODE, LONGBRIDGE_MARKET_SIGNAL_HANDOFF_INDEX_URI, LONGBRIDGE_MARKET_SIGNAL_HANDOFF_MANIFEST_URI, LONGBRIDGE_MARKET_SIGNAL_MAX_STALE_DAYS, LONGBRIDGE_MARKET_SIGNAL_REQUIRED, LONGBRIDGE_MARKET_TIMEZONE.
- Evidence: [scripts/print_strategy_switch_env_plan.py:62](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/scripts/print_strategy_switch_env_plan.py#L62); [scripts/print_strategy_switch_env_plan.py:71](https://github.com/QuantStrategyLab/LongBridgePlatform/blob/93f73736d0698f3d8d285563f510ae0dcbbf661d/scripts/print_strategy_switch_env_plan.py#L71).
