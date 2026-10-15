# Market-data source inventory (summary)

A static source scan of 25 repositories read 1783 source files and identified 393 consumer/contract/acquisition boundaries and 30 findings. No runtime, account or market data was read. The full per-file inventory is kept outside the repository and is available from the maintainers on request.

## Per-repository consumer counts by migration wave

| Repository | Rows | W0 | W1 | W2 | W3 | W4 | W5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| BinancePlatform | 12 |  |  | 2 |  |  | 10 |
| CharlesSchwabPlatform | 10 |  |  | 2 |  |  | 8 |
| CnEquitySnapshotPipelines | 7 |  | 2 | 5 |  |  |  |
| CnEquityStrategies | 32 |  |  | 32 |  |  |  |
| CryptoLivePoolPipelines | 10 |  | 1 | 9 |  |  |  |
| CryptoStrategies | 13 |  |  | 13 |  |  |  |
| FirstradePlatform | 4 |  |  |  |  |  | 4 |
| HkEquitySnapshotPipelines | 5 |  | 2 | 3 |  |  |  |
| HkEquityStrategies | 16 |  | 1 | 15 |  |  |  |
| InteractiveBrokersPlatform | 11 |  |  | 2 |  |  | 9 |
| LongBridgePlatform | 8 |  |  |  |  |  | 8 |
| MarketSignalSources | 12 |  | 1 | 11 |  |  |  |
| PoliticalEventTrackingResearch | 2 |  |  | 2 |  |  |  |
| QmtPlatform | 2 |  |  |  |  | 2 |  |
| QuantAdvisorResearch | 3 |  | 1 | 2 |  |  |  |
| QuantPlatformKit | 25 | 25 |  |  |  |  |  |
| QuantRuntimeSettings | 8 |  |  |  | 8 |  |  |
| QuantStrategyPlugins | 26 |  | 1 | 25 |  |  |  |
| ResearchSignalContextPipelines | 9 |  | 1 | 8 |  |  |  |
| UsEquitySnapshotPipelines | 116 |  | 16 | 100 |  |  |  |
| UsEquityStrategies | 62 |  |  | 62 |  |  |  |

Repositories with no rows: AIAuditBridge, AlpacaPlatform, IBKRGatewayManager, SchwabTokenAutoRefresher.

Waves:

- W0: shared contract in QPK.
- W1: research acquisition.
- W2: research and injected consumers.
- W3: website projections and benchmark publisher.
- W4: isolated platform inputs.
- W5: live decision paths (last).

## Role counts

| Role | Count |
|---|---:|
| series/feature consumer | 270 |
| artifact/CSV input boundary | 75 |
| provider acquisition/normalization | 21 |
| provider acquisition entry/contract | 9 |
| benchmark/FX display or publication boundary | 8 |
| manifest/binding/validation contract | 6 |
| historical universe/membership input boundary | 1 |
| price artifact and synthetic-fixture contract | 1 |
| synthetic history transformation | 1 |
| execution quote wrapper | 1 |

## Findings

| ID | Category | Finding | Main location |
|---|---|---|---|
| DS-01 | basis conflict | QPK tries `ADJUSTED_LAST` then `TRADES` and returns the same series type; strict acquisition forbids this fallback. | QuantPlatformKit/src/quant_platform_kit/ibkr/market_data.py |
| DS-02 | basis conflict | The IBKR signal proxy suppresses `ADJUSTED_LAST` and uses `TRADES`, so signal and research inputs need separate identities. | InteractiveBrokersPlatform/application/runtime_strategy_adapters.py |
| DS-03 | basis conflict | `auto_adjust=False` selects split-only Close, but falls back to Adj Close while other OHLC columns stay independently taken. | InteractiveBrokersPlatform/application/runtime_strategy_adapters.py |
| DS-04 | basis conflict | Raw, split-only and dividend-aware datasets coexist for the same US instruments and are not interchangeable. | UsEquitySnapshotPipelines/scripts/acquire_batch_a_v2_price_snapshots_alpaca.py |
| DS-05 | duplicate code | Two Yahoo download modules contain 8 identical top-level functions with diverging download policies. | UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/yfinance_prices.py |
| DS-06 | duplicate code | Several repos own separate Yahoo request and normalization policies. | UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/yfinance_prices.py |
| DS-07 | duplicate code | Several Alpaca collectors each own their own request or publication logic. | UsEquitySnapshotPipelines/scripts/acquire_batch_a_v2_price_snapshots_alpaca.py |
| DS-08 | basis conflict | QAR prefers `adjclose` but takes `quote.close` when a value is absent, changing dividend treatment without a per-row basis marker. | QuantAdvisorResearch/src/quant_advisor_research/market_confirmation.py |
| DS-09 | basis conflict | The context downloader falls back from `adjclose` to `close` and does not bind a canonical `price_basis`. | ResearchSignalContextPipelines/src/research_signal_context_pipelines/context_bundle.py |
| DS-10 | basis conflict | AkShare `qfq`, Tencent `qfq` and Yahoo `adjclose` are summarized as `adjusted_close_equivalent` without proven factor equivalence. | CnEquitySnapshotPipelines/src/cn_equity_snapshot_pipelines/akshare_market_history.py |
| DS-11 | basis conflict | LongBridge `ForwardAdjust`/Intraday and yfinance `auto_adjust=True` differ in dividend reinvestment, factor anchors and session semantics. | HkEquitySnapshotPipelines/src/hk_equity_snapshot_pipelines/low_vol_dividend_longbridge_snapshot.py |
| DS-12 | provenance | `PricePoint`/`PriceSeries` do not require provider, feed, basis, calendar or digests, unlike the newer decision-data contracts. | QuantPlatformKit/src/quant_platform_kit/common/models.py |
| DS-13 | calendar | The parser uses `America/New_York` but the read model returns `Asia/Shanghai`, which can mislead joins and display. | QuantRuntimeSettings/web/strategy-switch-console/infrastructure/market_benchmark/market_benchmark.js |
| DS-14 | calendar | The website publisher drops all current New York dates while research checks the actual session close. | QuantRuntimeSettings/scripts/sync_market_benchmark_closes.mjs |
| DS-15 | calendar | US session logic exists as pinned exchange calendars and local holiday rules, separately maintained with different versions. | UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/lifecycle/soxl_pit_input_packager.py |
| DS-16 | calendar | Universe audit and a LongBridge fallback use weekday ranges, which include holidays and cannot prove actual sessions. | UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/universe_audit_engine.py |
| DS-17 | calendar | The CN calendar is a finite hand-maintained holiday set with a stated date range, distinct from the exchange-calendar profiles. | QuantPlatformKit/src/quant_platform_kit/common/cn_equity_calendar.py |
| DS-18 | calendar | Some consumers strip timezones or derive dates in UTC rather than market-local time. | UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/yfinance_prices.py |
| DS-19 | calendar | Binance helpers take the last returned daily row without proving that bar has closed. | QuantPlatformKit/src/quant_platform_kit/binance/market_data.py |
| DS-20 | provenance | A per-symbol CSV cache is updated in place with no provider/basis/calendar identity in the filename. | CryptoLivePoolPipelines/src/binance_client.py |
| DS-21 | provenance | Schwab `QuoteSnapshot` stamps `as_of` from the client clock, conflating fetch time with quote time. | QuantPlatformKit/src/quant_platform_kit/schwab/market_data.py |
| DS-22 | basis conflict | HK staging chooses volume or turnover or 0, while QAR uses 0 when volume is absent; these are different units and missing is not zero. | HkEquitySnapshotPipelines/src/hk_equity_snapshot_pipelines/low_vol_dividend_longbridge_snapshot.py |
| DS-23 | calendar | The HK strategy downloader drops dates missing any instrument, hiding inception, suspension or missing-data periods. | HkEquityStrategies/src/hk_equity_strategies/backtest/yfinance_market_data.py |
| DS-24 | basis conflict | `total_return_adjusted` and `SPLIT_ADJUSTED_PRICE_RETURN` contracts coexist; adjusted prices alone do not specify a reinvested index. | UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/lifecycle/soxl_core_only_p1_binding.py |
| DS-25 | provenance | Website price indices and dividend-aware ETF research are different series and must state that difference in comparisons. | QuantRuntimeSettings/web/strategy-switch-console/infrastructure/market_benchmark/market_benchmark.js |
| DS-26 | synthetic | The legacy TECL mode applies 3x daily return minus fixed annual expense/252 with a -99% loss clamp, lacking the financing and real/synthetic/bridge contract. | UsEquitySnapshotPipelines/src/us_equity_snapshot_pipelines/tecl_xlk_trend_income_research_inputs.py |
| DS-27 | point-in-time | Current-only constituents and factor snapshots are not historical point-in-time; adjusted prices cannot fix universe survivorship. | CnEquitySnapshotPipelines/src/cn_equity_snapshot_pipelines/index_membership.py |
| DS-28 | config | The website benchmark publisher's sync URL is configurable but its source default is tied to a personal deployment. | QuantRuntimeSettings/scripts/sync_market_benchmark_closes.mjs |
| DS-29 | config | The Alpaca SIP access diagnostic passes the date cutoff as the end bound with `feed=sip` and has no configurable free-plan delay or feed policy. | UsEquitySnapshotPipelines/.github/workflows/alpaca-sip-access-diagnostic.yml |
| DS-30 | config (resolved) | The Alpaca feed-window planner enforces a minimum SIP delay of 16 minutes, matching the standard. | UsEquitySnapshotPipelines/scripts/alpaca_feed_windows.py |

## Known limits

The static scan did not verify: broker entitlements, source licenses and retention, RTH equivalence of native daily bars, corporate-action factor equivalence, pre-2016 source coverage, deployed versions, or dynamic plugin inputs.

## Per-row fields

The full inventory records these fields per consumer: `consumer_id, repo, revision, file, consumer_role, provider, plan_constraints, price_basis, adjustment_application, timezone, session_close, trading_calendar, corporate_actions, cache_storage, config_keys_env_vars, evidence, migration_wave, migration_risk`.
