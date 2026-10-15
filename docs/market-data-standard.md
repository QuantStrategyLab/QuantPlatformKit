# Unified market-data standard (draft)

Status: proposal for owner review, 2026-10-15. This document is not an adopted runtime contract. The accompanying PR changes Markdown only. It authorizes no collection, subscription, migration, configuration change, deployment, order, or merge.

Read with the [source inventory](market-data-inventory.md) and [access-layer design](market-data-access-layer-design.md). Inventory references identify source revisions, not deployed versions or account entitlements.

## 1. Decisions proposed

Use a small shared contract in QuantPlatformKit (QPK), with acquisition and licensed storage owned by the existing pipelines. Strategies and plugins receive immutable inputs. Broker execution quotes remain on the existing broker path. A universal provider for every market is neither available nor proposed.

| Market and purpose | Proposed primary | Explicit fallback and limits |
|---|---|---|
| US equity/ETF completed historical sessions | Alpaca historical SIP, Basic/free plan; explicit adjustment and completed-session checks | IBKR historical adapter in an already approved, isolated research environment with verified entitlement and the identical requested basis/session contract. No use of a production Gateway for research. Yahoo is an optional, separately configured research source where rights permit, never an implicit live substitute. |
| US recent observations | Alpaca IEX, explicitly labelled single-exchange coverage | Delayed SIP only when the consumer explicitly accepts its age. Changing IEX to SIP is a dataset/source change, not a retry with equivalent data. Broker execution quotes retain their current provider. |
| HK equity/ETF | LongPort/LongBridge with the market's authorized data entitlement and a pinned adjustment policy | Yahoo research inputs only under an explicit source profile and rights review. Forward-adjusted provider prices require a documented dividend policy before being equated with another source. |
| CN equity/ETF research | Existing AkShare source family with the underlying endpoint and `qfq` policy named | Existing Yahoo adapter only for supported instruments, separately identified. Neither adapter is promoted to an execution-grade source by this document. QMT execution observations remain broker/venue specific. |
| Crypto spot | Binance spot for Binance instruments, quote currency and venue fixed | No default cross-exchange fallback: a different venue/pair is a different instrument. Alternative venues require an explicit profile and comparison. Equity corporate-action rules do not imply that token redenominations, migrations or delistings are absent. |
| Indices, rates, constituents and research context | Explicit instrument/dataset-specific source: existing licensed index source, Treasury/rate adapter, or versioned context producer | An ETF is not an index substitute without an explicitly different benchmark ID. Today's constituents, revised macro values and current news do not reconstruct historical point-in-time inputs. |

The free Alpaca account is an owner-confirmed constraint. Basic supports recent IEX observations; SIP historical requests must exclude the most recent 15 minutes. The operational safety margin is **16 minutes**: for SIP, `effective_end = min(requested_end, now_utc - configured_delay)` with a Basic-plan minimum of 16 minutes. Record both bounds and any truncation. A strict request that loses required coverage returns unavailable; it must not pretend to have fulfilled the original interval. The delay does not by itself prove that a daily bar is complete. No paid upgrade is required or authorized. Provider coverage is not a promise of pre-2016 history. [Alpaca plan documentation](https://docs.alpaca.markets/us/docs/about-market-data-api)

The `live_cfg2` successor `live_cfg3` owns the immediate feed/delay implementation. [Companion PR #543](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/pull/543) provides `ALPACA_SIP_MIN_DELAY_MINUTES`, `ALPACA_FEED_HISTORICAL` and `ALPACA_FEED_RECENT`; reuse those exact names. Its inspected revision defaults to 16 minutes but accepts 15; this standard retains the owner-required minimum of 16. The design records the pinned PR revision, segment semantics and adoption limits.

For new general US historical research, the proposed profile explicitly requests `price_basis=split_dividend_adjusted` and Alpaca `adjustment=all`; every request must still name its basis. Existing split-only, raw-unit and frozen candidate profiles retain their declared semantics until a separately approved migration.

Fallback is request-wide by default. It creates a new immutable dataset identity, records the reason and actual source, and is allowed only by the consumer's profile. Do not fill individual missing rows from another source, switch price basis, or bypass an existing two-source assurance requirement. Frozen candidates retain their original source contract; adopting this proposal does not rewrite their evidence.

## 2. Explicit price semantics

Every request, normalized dataset, cache key, decision binding, research manifest and public summary that describes prices must carry `price_basis`. A generic `adjusted`, `close`, `auto_adjust`, provider name or filename is insufficient. Missing legacy metadata is `unknown_legacy` during inventory only; new conforming inputs reject it.

| `price_basis` | Meaning | Adjustment/accounting requirements |
|---|---|---|
| `raw_unadjusted` | Contemporaneous quoted/traded units; no retrospective corporate-action adjustment | Splits change units and quantities; dividends are separate cash events. Executable prices and quantities must be in contemporaneous units. |
| `split_adjusted` | Historical prices restated for splits/reverse splits only | Record factor orientation, anchor/as-of date, source and action revision. Dividend cash is not included in returns unless separately accounted for. Volume adjustment is separately declared. |
| `split_dividend_adjusted` | Provider-adjusted price history incorporating splits and distributions | Preserve the exact vendor mode and method. It is a research price series, not an executable price. Do not book the same dividends a second time. |
| `total_return_index` | An explicit reinvested wealth index | Record reinvestment date/price, gross/net tax treatment, currency, base value/date and action inputs. Not an OHLC or trade-price series. |

Use `return_basis=price_return|total_return` separately from `price_basis`, with a concrete return-construction method. A provider's adjusted-close ratio can support a specified total-return approximation, but is not automatically an audited total-return index. Existing `total_return_adjusted` labels in candidate contracts are legacy names: preserve them, map their actual vendor method in a new manifest, and do not silently certify them as reinvested wealth.

Adapter mappings must be tested against vendor semantics:

- Alpaca: `raw` → `raw_unadjusted`, `split` → `split_adjusted`, `all` → `split_dividend_adjusted` with any additional supported action types recorded. `dividend` alone needs an explicitly supported, separately described policy; it is not equivalent to `all`. Store the actual request parameter. [Historical bars parameters](https://docs.alpaca.markets/us/reference/stockbars)
- IBKR: `TRADES` historical equity bars are **split adjusted**, not raw contemporaneous history; `ADJUSTED_LAST` includes split/dividend adjustment. No automatic interchange. A raw request unsupported by the selected endpoint must fail as unsupported. Streaming `close`/prior-close fields have their own corporate-action rules and must not be classified solely from a historical `whatToShow`. [Historical bars](https://www.interactivebrokers.com/docs/tws-api/doc/md/historical-bars), [streaming fields](https://www.interactivebrokers.com/docs/tws-api/doc/md/streaming-data)
- Yahoo/yfinance: pass `auto_adjust` explicitly and retain the library version. The chart `quote.close` path is treated by the existing split-only assurance adapter as split adjusted; the `adjclose/close` path scales OHLC for dividend-aware research. Neither is assumed to be raw historical trade units. Null adjusted values must not silently change individual rows to another basis. [yfinance download reference](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html)
- LongPort `ForwardAdjust`, AkShare `qfq`, and Schwab's existing split-only convention remain named provider policies until their action/factor semantics are verified for the instrument. Do not translate the word “forward” into `total_return_index`.

Do not split-adjust volume with a dividend factor. Preserve `volume_basis`, native volume units and whether missing volume is unknown or zero. Raw OHLC, split-adjusted OHLC and a wealth index must have distinct dataset identities. Currency, listing/venue, instrument type, multiplier and symbol-validity dates are also part of identity; a ticker alone is insufficient.

## 3. Time, sessions and calendars

Store instants as timezone-aware UTC. Store `session_date` separately as the exchange-local trading date, plus `market_timezone`, `calendar_id`, pinned calendar package/version and the relevant schedule revision/digest. Reject ambiguous naive timestamps at new adapter boundaries. Provider-native daily date labels are dates, not midnight execution timestamps.

| Market | Default timezone/calendar profile | Session-close rule |
|---|---|---|
| US cash equities | `America/New_York`; XNYS as the shared US cash-session schedule, listing venue retained | Regular-session close from the pinned schedule, including DST, holidays, exceptional closures and early closes. A scheduled close is not proof of the primary exchange's official auction price. |
| HK equities | `Asia/Hong_Kong`; XHKG | Include lunch break, applicable closing auction and exceptional market notices. Full-day and half-day schedules remain distinct. |
| CN equities | `Asia/Shanghai`; XSHG/XSHE profile for the actual venue | Include lunch, exchange holidays, suspension and applicable auction rules. Stock T+1/lot/limit rules remain execution constraints. |
| Crypto spot | UTC; explicit `24x7` venue profile | Daily interval `[00:00Z, next 00:00Z)`, only after its closing instant plus declared provider finalization latency. No 252-session assumption. |

Defaults are selectable profile values, not hard-coded assumptions in consumers. Exchange exceptions override ordinary hours. US core hours and early closes must follow the exchange schedule rather than a fixed 16:00 or weekday-only test. [NYSE trading hours](https://www.nyse.com/markets/hours-calendars)

Required times: `bar_start_at`, `bar_end_at`, `session_close_at`, `provider_timestamp`, `fetched_at`, `available_at`, and `decision_as_of` where applicable. Preserve provider label semantics. `available_at` must be supported by the source/observation policy; it is not reconstructed by setting it equal to a historical session close. Later-fetched revised history is not strict vendor point-in-time data.

Define `session_scope=regular|extended|provider_native` and `close_kind=last_eligible_trade|official_auction|provider_native|wealth_index`. The canonical daily signal profile targets **completed regular sessions and last eligible trade**, not a guaranteed official auction. An adapter must demonstrate that its native bars satisfy that scope or explicitly aggregate eligible intraday observations under a versioned recipe. Unverified native daily bars remain `provider_native`; do not relabel them as RTH simply because their date is on XNYS. Source trade filters can differ even within RTH. Existing Alpaca `1Day` archives require this scope check before equivalence is claimed. [Alpaca bar behavior](https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data)

Only complete, available observations may feed a decision. A signal using session t's complete close can execute no earlier than the next authorized executable time, unless an existing frozen strategy proves a valid earlier information cutoff. Do not convert data latency into permission to submit orders. Cross-market joins use availability as of the decision instant, not equal date strings. Missing sessions remain explicit; never silently forward-fill a halt/delisting or drop stress periods by intersecting available dates.

## 4. Corporate actions and revisions

Keep versioned split, dividend/distribution, symbol-change, merger, spin-off, delisting and settlement events, including effective, announcement/availability, revision and fetch times. Preserve original instrument identity across symbol changes. Factors identify their source, orientation and anchor. Unknown actions or ambiguous factor mappings make a requested conversion unavailable.

Prefer the requested vendor basis when its documented semantics match the request. A raw-plus-actions reconstruction is a separate, versioned transformation with its own digest and tests. Never reverse a provider adjustment without the required action/factor inputs. Adjustment does not turn post-event knowledge into pre-event knowledge.

Observed market prices generally already reflect fund expenses; do not deduct fund expense ratios twice. A total-return construction accounts for distributions once. Execution/accounting uses real units, corporate-action quantity changes and actual cash independently of signal-price normalization. Preserve old objects when vendors revise history; new generations get new identities. A display revision does not alter frozen research or a broker ledger.

## 5. Provenance and content integrity

Each immutable result carries:

- Identity: schema version, instrument/listing/venue/currency, frequency, requested coverage, actual coverage, `price_basis`, `return_basis`, `volume_basis`, session scope and close kind.
- Actual source: `provider`, `feed`, endpoint class, vendor adjustment parameters, adapter/source code revision, provider/library version, plan/entitlement classification, acquisition bounds and fallback reason. Store no credential, secret reference name, private account or private host in public metadata.
- Time/calendar/action metadata from sections 3–4; declared gaps, duplicates, revisions, finality and PIT limitations.
- `source_digest`: SHA-256 of exact source-response bytes or the existing immutable source artifact's exact bytes, with immutable cloud object generation/version. Paged requests use an ordered page-digest manifest. No transport headers or authenticated URLs are included. For SDK sources without retained original response bytes, explicitly name the deterministic source-envelope serialization; do not call it a raw-wire digest.
- `content_digest`: SHA-256 of versioned canonical normalized records. `manifest_digest`: SHA-256 of the canonical metadata, content/source references and transformations, excluding its own digest field. Reuse existing manifest/binding roots; do not add a second evidence-signing service.

Proposed canonical content encoding `qsl.market_records.jsonl.v1`: UTF-8 without BOM; one compact object per line, LF including the last line; sorted ASCII field names; records sorted by instrument ID, bar end/session and source type; UTC timestamps with a fixed microsecond precision and `Z`; prices/volumes encoded as finite canonical decimal strings (no exponent, trailing fractional zeros, `-0`, NaN or infinity); integers in decimal, dates ISO-8601, explicit null only for permitted missing fields. Preserve the parsed source precision rather than serialize binary float representations. Duplicate identity keys reject. The manifest declares field set, units and decimal conversion/version. A future implementation must supply synthetic cross-language golden vectors before this encoding is used for frozen inputs. Existing artifacts keep their original digest algorithm and bytes.

Fetch timestamps and private storage locators belong to manifests, not the normalized price-content digest. Different feed/basis/session policies cannot share a cache identity even if their numerical content happens to hash equally. An instrument's identical values do not establish equivalent provenance or licensing.

## 6. Synthetic history: UBPS v0.2 compatibility

Follow the owner-review UBPS v0.2 draft (2026-10-15), section 8.2; this does not adopt its financial thresholds or change any existing candidate's gates.

- Per record: `source_type=real|synthetic_history|synthetic_bridge`. A synthetic fixture is separately labelled `evidence_class=synthetic_fixture`, never `real`.
- Synthetic manifest: real underlying/proxy identity and digest, leverage L, daily reset rule, fee and financing sources/day counts, drag model/version, target-index regime, train/validation windows and calibration version/status. Today's fee/rate cannot silently stand in for every past year.
- Before the first verified real anchor t0, modelled history may be used; from t0 onward retain real product levels and only real returns. Use one scale factor for the splice, no smoothing. A return crossing into t0 without a prior real observation is `synthetic_bridge` and counts as synthetic.
- Report dates/proportions and limitations prominently in tables, exports and charts. Produce independently rerun `full_synthetic_extended` and `real_only` strategy results, with their own initial capital/warmup and plugin ablations. Cropping the tail of an extended equity curve is not a real-only rerun.
- Daily close models cannot invent historical OHLC, volume, spread, options chains or next-open/stop fills. Missing equivalent inputs make the affected execution replay `NOT_COMPARABLE`.
- Keep full 2000–2002, 2008, 2020 and 2022 coverage where the underlying exists; distinguish `COVERAGE_BLOCKED` from `NOT_EXISTENT`. Synthetic history never counts as the product's realized performance or untouched real OOS evidence. Calibration `PASS` is model qualification, not strategy promotion or live authority.

## 7. Configurability, retention and publication

All provider endpoints, market profiles, calendars, dataset names, cloud roots, cache prefixes, retention settings and adapter selection are configuration values with documented defaults in the design. No personal domains, accounts, cloud projects, buckets, secret names or machine paths are defaults. Existing approved cloud configuration supplies private values at runtime; this job never reads or changes them.

Real market/account data remains in approved cloud storage/compute only. The Mac is for source and synthetic/document checks. Cache content inherits the source's license, retention and redistribution rules; a free/public endpoint is not a redistribution license. Retention is explicit per dataset and must not erase frozen evidence. Public docs contain generic references such as `<approved-object-root>` and aggregate code/coverage metadata, never prices, accounts or licensed response bodies.

Legacy datasets are not overwritten or retrospectively recertified. This proposal changes none of RECONCILE_ONLY, unknown-result anti-resend, 409 protection, existing risk/release gates, or the approved caps: SOXL 0.679, total 0.97, cash 0.03.
