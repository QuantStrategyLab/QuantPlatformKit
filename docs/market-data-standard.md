# Market-data standard

Status: proposal. Not yet adopted by any consumer.

This standard defines how market data is named, priced, timed, fingerprinted and labelled in QuantPlatformKit (QPK) and the pipelines that use it. Read it with the [access-layer design](market-data-access-layer-design.md) and the [source inventory](market-data-inventory.md).

## 1. Per-market primary source and fallback

| Market and purpose | Primary | Fallback and limits |
|---|---|---|
| US equity/ETF completed historical sessions | Alpaca historical SIP, Basic (free) plan | IBKR historical adapter in an isolated, approved research environment with verified entitlement and the same basis/session contract. Yahoo is an optional, separately configured research source where rights permit. |
| US recent observations | Alpaca IEX, labelled single-exchange | Delayed SIP only when the consumer explicitly accepts its age. Broker execution quotes keep their current provider. |
| HK equity/ETF | LongPort/LongBridge with authorized entitlement and a pinned adjustment policy | Yahoo research inputs only under an explicit source profile and rights review. |
| CN equity/ETF research | AkShare source family with the endpoint and `qfq` policy named | Yahoo adapter only for supported instruments, separately identified. |
| Crypto spot | Binance spot for Binance instruments; quote currency and venue fixed | No default cross-exchange fallback. A different venue or pair is a different instrument. |
| Indices, rates, constituents, context | Explicit instrument- or dataset-specific source | An ETF is not an index substitute without a different benchmark ID. Today's constituents and revised values do not reconstruct historical point-in-time inputs. |

## 2. Alpaca free (Basic) plan

The Basic plan provides recent IEX observations; historical SIP requests must exclude the most recent 15 minutes. The operational safety margin is 16 minutes. For SIP, `effective_end = min(requested_end, now_utc - configured_delay)` with a Basic-plan minimum delay of 16 minutes. Record both bounds and any truncation. A strict request that loses required coverage returns unavailable; it must not claim to have fulfilled the original interval. The delay does not by itself prove that a daily bar is complete.

IEX and SIP are different sources. Changing IEX to SIP is a dataset/source change, never a retry with equivalent data. No paid upgrade is required or assumed. Provider coverage is not a promise of pre-2016 history. [Alpaca plan documentation](https://docs.alpaca.markets/us/docs/about-market-data-api)

The Alpaca feed-window planner in UsEquitySnapshotPipelines already uses these configuration names. Reuse them exactly:

| Name | Default | Meaning |
|---|---|---|
| `ALPACA_SIP_MIN_DELAY_MINUTES` | `16` | Minimum SIP delay for the Basic plan. |
| `ALPACA_FEED_HISTORICAL` | `sip` | Historical feed: `sip` or explicitly selected `iex`. |
| `ALPACA_FEED_RECENT` | `iex` | Recent feed: `iex` or `none`. No recent SIP and no retry-to-IEX after a 401/403. |

## 3. Fallback

Fallback is request-wide by default. It creates a new immutable dataset identity, records the reason and actual source, and is allowed only by the consumer's profile. Do not fill individual missing rows from another source, switch price basis, or bypass an existing two-source assurance requirement. Frozen candidates retain their original source contract; adopting this standard does not rewrite their evidence.

## 4. Price basis

Every request, normalized dataset, cache key, decision binding, research manifest and public summary that describes prices must carry `price_basis`. A generic `adjusted`, `close`, `auto_adjust`, provider name or filename is insufficient. Missing legacy metadata is `unknown_legacy` during inventory only; new conforming inputs reject it.

| `price_basis` | Meaning | Adjustment/accounting requirements |
|---|---|---|
| `raw_unadjusted` | Contemporaneous quoted/traded units; no retrospective corporate-action adjustment | Splits change units and quantities; dividends are separate cash events. Executable prices and quantities must be in contemporaneous units. |
| `split_adjusted` | Historical prices restated for splits and reverse splits only | Record factor orientation, anchor/as-of date, source and action revision. Dividend cash is not included in returns unless separately accounted for. Volume adjustment is separately declared. |
| `split_dividend_adjusted` | Provider-adjusted history incorporating splits and distributions | Preserve the exact vendor mode and method. It is a research price series, not an executable price. Do not book the same dividends a second time. |
| `total_return_index` | An explicit reinvested wealth index | Record reinvestment date/price, gross/net tax treatment, currency, base value/date and action inputs. Not an OHLC or trade-price series. |

Use `return_basis=price_return|total_return` separately from `price_basis`, with a concrete return-construction method. A provider's adjusted-close ratio can support a specified total-return approximation, but is not automatically an audited total-return index. Existing `total_return_adjusted` labels in candidate contracts are legacy names: keep them, record their actual vendor method in a new manifest, and do not treat them as a reinvested wealth index.

For new general US historical research, the default profile requests `price_basis=split_dividend_adjusted` with Alpaca `adjustment=all`. Every request must still name its basis. Existing split-only, raw-unit and frozen candidate profiles keep their declared semantics until they are migrated separately.

Adapter mappings must be tested against vendor semantics:

- Alpaca: `raw` maps to `raw_unadjusted`, `split` to `split_adjusted`, `all` to `split_dividend_adjusted`, with any additional supported action types recorded. `dividend` alone needs an explicitly described policy; it is not equivalent to `all`. Store the actual request parameter. [Historical bars parameters](https://docs.alpaca.markets/us/reference/stockbars)
- IBKR: `TRADES` historical equity bars are split adjusted, not raw contemporaneous history. `ADJUSTED_LAST` includes split and dividend adjustment. No automatic interchange. A raw request unsupported by the selected endpoint must fail as unsupported. Streaming `close`/prior-close fields have their own corporate-action rules. [Historical bars](https://www.interactivebrokers.com/docs/tws-api/doc/md/historical-bars), [streaming fields](https://www.interactivebrokers.com/docs/tws-api/doc/md/streaming-data)
- Yahoo/yfinance: pass `auto_adjust` explicitly and retain the library version. The chart `quote.close` path is treated by the existing split-only assurance adapter as split adjusted; the `adjclose/close` path scales OHLC for dividend-aware research. Neither is assumed to be raw historical trade units. Null adjusted values must not silently change rows to another basis. [yfinance download reference](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html)
- LongPort `ForwardAdjust`, AkShare `qfq`, and Schwab's split-only convention remain named provider policies until their action/factor semantics are verified. Do not translate the word "forward" into `total_return_index`.

Do not split-adjust volume with a dividend factor. Preserve `volume_basis`, native volume units, and whether missing volume is unknown or zero. Raw OHLC, split-adjusted OHLC and a wealth index must have distinct dataset identities. Currency, listing/venue, instrument type, multiplier and symbol-validity dates are also part of identity; a ticker alone is insufficient.

## 5. Time, sessions and calendars

Store instants as timezone-aware UTC. Store `session_date` separately as the exchange-local trading date, plus `market_timezone`, `calendar_id`, pinned calendar package/version and the relevant schedule revision/digest. Reject ambiguous naive timestamps at new adapter boundaries. Provider-native daily date labels are dates, not midnight execution timestamps.

The defaults below are selectable profile values, not assumptions hard-coded in consumers. Exchange exceptions override ordinary hours; do not use a fixed 16:00 or weekday-only test for US sessions.

| Market | Timezone / calendar | Session-close rule |
|---|---|---|
| US cash equities | `America/New_York`; XNYS | Regular-session close from the pinned schedule, including DST, holidays and early closes. A scheduled close is not proof of the primary exchange's official auction price. |
| HK equities | `Asia/Hong_Kong`; XHKG | Include lunch break, applicable closing auction and exceptional notices. Full-day and half-day schedules remain distinct. |
| CN equities | `Asia/Shanghai`; XSHG/XSHE | Include lunch, holidays, suspension and applicable auction rules. |
| Crypto spot | UTC; `24x7` profile | Daily interval `[00:00Z, next 00:00Z)`, only after its closing instant plus declared provider finalization latency. No 252-session assumption. |

Required times: `bar_start_at`, `bar_end_at`, `session_close_at`, `provider_timestamp`, `fetched_at`, `available_at`, and `decision_as_of` where applicable. `available_at` must be supported by the source/observation policy; it is not reconstructed by setting it equal to a historical session close.

Define `session_scope=regular|extended|provider_native` and `close_kind=last_eligible_trade|official_auction|provider_native|wealth_index`. The canonical daily signal profile targets completed regular sessions and last eligible trade. An adapter must demonstrate that its native bars satisfy that scope or explicitly aggregate eligible intraday observations under a versioned recipe. Unverified native daily bars remain `provider_native`. [NYSE trading hours](https://www.nyse.com/markets/hours-calendars)

Only complete, available observations may feed a decision. A signal that uses session t's close can execute no earlier than the next permitted execution time, unless an existing frozen strategy proves a valid earlier information cutoff. Data latency is never permission to submit orders. Cross-market joins use availability as of the decision instant. Missing sessions remain explicit; never silently forward-fill a halt or delisting, and do not drop stress periods by intersecting available dates.

## 6. Corporate actions and revisions

Keep versioned split, dividend/distribution, symbol-change, merger, spin-off, delisting and settlement events, including effective, announcement/availability, revision and fetch times. Preserve original instrument identity across symbol changes. Factors identify their source, orientation and anchor. Unknown actions or ambiguous factor mappings make a requested conversion unavailable.

Prefer the requested vendor basis when its documented semantics match the request. A raw-plus-actions reconstruction is a separate, versioned transformation with its own digest and tests. Never reverse a provider adjustment without the required action/factor inputs. Observed market prices generally already reflect fund expenses; do not deduct fund expense ratios twice. Preserve old objects when vendors revise history; new generations get new identities.

## 7. Provenance and fingerprints

Each immutable result carries:

- Identity: schema version, instrument/listing/venue/currency, frequency, requested coverage, actual coverage, `price_basis`, `return_basis`, `volume_basis`, session scope and close kind.
- Actual source: `provider`, `feed`, endpoint class, vendor adjustment parameters, adapter/source code revision, provider/library version, plan/entitlement classification, acquisition bounds and fallback reason. No credential, secret reference name, private account or private host appears in public metadata.
- Time, calendar and action metadata, plus declared gaps, duplicates, revisions, finality and point-in-time limitations.
- `source_digest`: SHA-256 of the exact source-response bytes or the existing immutable source artifact's exact bytes, with immutable cloud object generation/version. Paged requests use an ordered page-digest manifest. No transport headers or authenticated URLs are included. For SDK sources without retained original response bytes, name the deterministic source-envelope serialization; do not call it a raw-wire digest.
- `content_digest`: SHA-256 of the versioned canonical normalized records. `manifest_digest`: SHA-256 of the canonical metadata, content/source references and transformations, excluding its own digest field.

Proposed canonical content encoding `qsl.market_records.jsonl.v1`: UTF-8 without BOM; one compact object per line, LF including the last line; sorted ASCII field names; records sorted by instrument ID, bar end/session and source type; UTC timestamps with fixed microsecond precision and `Z`; prices/volumes as finite canonical decimal strings; integers in decimal, dates ISO-8601, explicit null only for permitted missing fields. Preserve parsed source precision rather than serialize binary float representations. Duplicate identity keys reject. A future implementation must supply synthetic cross-language golden vectors before this encoding is used for frozen inputs. Existing artifacts keep their original digest algorithm and bytes.

Fetch timestamps and private storage locators belong to manifests, not the price-content digest. Different feed/basis/session policies cannot share a cache identity even if their numerical content hashes equally.

## 8. Synthetic history

Each record carries `source_type=real|synthetic_history|synthetic_bridge`. A synthetic fixture is separately labelled `evidence_class=synthetic_fixture`, never `real`.

The synthetic manifest records the real underlying/proxy identity and digest, leverage, daily reset rule, fee and financing sources and day counts, drag model/version, target-index regime, train/validation windows and calibration version/status. Before the first verified real anchor t0, modelled history may be used; from t0 onward keep real product levels and only real returns. Use one scale factor for the splice, no smoothing. A return crossing into t0 without a prior real observation is `synthetic_bridge` and counts as synthetic.

Report dates, proportions and limitations in tables, exports and charts. Produce independently rerun full-synthetic and real-only strategy results with their own initial capital, warmup and plugin ablations. Cropping the tail of an extended equity curve is not a real-only rerun. Daily close models cannot invent historical OHLC, volume, spread, options chains or next-open/stop fills; when the required inputs are missing, the affected execution replay is reported as not comparable. Keep full 2000-2002, 2008, 2020 and 2022 coverage where the underlying exists, and report a window as coverage-blocked when data is missing versus non-existent when the underlying did not exist. Synthetic history never counts as realized performance or untouched real out-of-sample evidence. Passing calibration qualifies the model; it does not promote a strategy.

## 9. Configurability, retention and publication

All provider endpoints, market profiles, calendars, dataset names, cloud roots, cache prefixes, retention settings and adapter selection are configuration values with documented defaults. No personal domains, accounts, cloud projects, buckets, secret names or machine paths are defaults.

Real market and account data stays in approved cloud storage and compute, never on developer machines or in Git. Cache content inherits the source's license, retention and redistribution rules; a free or public endpoint is not a redistribution license. Retention is explicit per dataset and must not erase frozen evidence. Public documents contain generic references such as `<approved-object-root>` and aggregate coverage metadata, never prices, accounts or licensed response bodies.

Legacy datasets are not overwritten or retrospectively recertified. This standard does not change order-path protections or risk limits.
