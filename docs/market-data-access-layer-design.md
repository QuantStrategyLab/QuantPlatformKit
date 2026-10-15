# Shared market-data access layer (draft)

Status: owner-review design, 2026-10-15; documentation only. No consumer implementation, dependency upgrade, runtime/configuration change, deployment, collection, order or merge is included. The [standard](market-data-standard.md) defines semantics; the [inventory](market-data-inventory.md) supplies revision-pinned evidence and consumer-by-consumer migration order/risk notes.

## 1. Put the smallest shared contract in QPK

Extend existing `src/quant_platform_kit/data/` and keep network acquisition in the current pipelines and broker adapter modules. Do not create a market-data service, scheduler, database, broker registry or second research orchestrator.

Reuse these existing boundaries, as identified in the inventory:

- `common/ports.py`: `DecisionDataArtifactPort` loads immutable, digest-bound decision inputs; `ExecutionQuotePort` handles short-lived execution quotes. The legacy mixed `MarketDataPort` remains a migration boundary, not a target to expand indefinitely.
- `data/manifest.py`, `data/version.py`, `data/research_input.py`, `data/decision_data_binding.py` and `data/decision_price_series_artifact.py`: extend the existing versioned manifests and binding validation with explicit semantic metadata. Preserve existing canonicalizations and frozen roots.
- `data/multisource_assurance.py`: preserve independently acquired source observations and current VERIFIED/DEGRADED/PARKED behavior. Selecting a fallback must not bypass a candidate's requirement for two agreeing sources.
- `ibkr/market_data.py`, `schwab/market_data.py`, `longbridge/market_data.py`, `binance/market_data.py`: retain provider SDK differences; promote only the common result contract. Indicator calculations remain separate from normalized data acquisition.

The first implementation should prove two existing US research acquisition callers share semantics before factoring provider code. US/HK/CN/crypto retain their market rules. Ordinary strategies consume a supplied frame/artifact without importing provider SDKs.

## 2. Proposed interfaces and ownership

These signatures describe future interfaces; they are not exported APIs in this PR.

| Object/interface | Required contract | Owner |
|---|---|---|
| `HistoricalRequest` | Instrument IDs, UTC bounds, frequency, mandatory `price_basis`, purpose, decision cutoff, market/session profile, source policy and expected coverage | QPK data contract, constructed by the pipeline/research consumer |
| `SourceObservation` | Actual provider/feed/mode, retained source root/digest, source timestamps, unmodified native fields, status/reason | Thin provider adapter in the existing producer repo/module |
| `NormalizedDataset` | Typed bars/series plus the standard's metadata, actual coverage, action/calendar versions, source/content digests and manifest binding | QPK normalization/validation plus provider-specific mapping |
| `fetch_history(request, *, adapter, store, clock)` | Returns READY dataset or typed unavailable/invalid/unsupported/coverage status; no strategy, account or order side effects | Small explicit acquisition function, not a dynamic plugin registry |
| `load_verified_price_series(symbol, *, binding_id, binding_sha256)` | Existing artifact port; verifies frozen input identity and request semantics before returning values | Existing decision-data adapter |
| `get_execution_quote(symbol)` | Existing execution quote port; broker source time, bid/ask/last, age and tradability checks; never synthesizes a quote from adjusted history | Existing platform adapter |

Do not silently add fields to legacy `PriceSeries` and claim every consumer validates them. A versioned manifest-backed envelope can carry semantics while a thin checked adapter returns the existing numeric structure. The adapter requires the expected binding/profile; a naked numeric series is not conformance evidence. Historical decision prices and execution quotes remain separate types/purposes, even when they share the same instrument.

Provider adapters map capabilities explicitly:

| Adapter | Native mode and key design issue |
|---|---|
| Alpaca | Preserve `feed` and `adjustment`; apply Basic SIP delay before fetching; record effective bounds; paginate every symbol; verify native daily session scope; reuse the `live_cfg2` / `live_cfg3` companion configuration names. |
| IBKR | Pin `whatToShow`, `useRTH`, contract identity, bar size and API date format. Strict adjusted requests reuse the existing strict adapter. TRADES cannot satisfy raw or dividend-adjusted requests. Never take over a production Gateway session. |
| Schwab | Keep the existing SDK and retry behavior; expose its documented/verified history basis separately from broker execution quotes. Preserve a timestamp's source rather than treating client fetch time as quote time. |
| LongPort | Explicit adjustment enum and trade-session enum, timezone conversion and source close semantics. US signal and HK research profiles are distinct. |
| Yahoo/yfinance | One shared normalization recipe for the existing callers after conformance tests; explicit auto-adjust choice, source/library version, symbol aliases and action support. Preserve research-only licensing/quality restrictions. |
| Twelve Data | Existing split-only source observations and independent Yahoo cross-check; respect endpoint/plan limits and current assurance gates. It is not an automatically interchangeable total-return feed. |
| AkShare | Underlying endpoint/version and qfq factors/actions; explicitly identify Yahoo fallback. Preserve unavailable history, current-only constituents and lack of strict historical PIT. |
| Binance | Venue/pair/currency identity, UTC interval, pagination and completed-kline filter; raw spot prices with token events separate; cache revisions cannot overwrite a frozen input. |
| Injected CSV/context | Verify the existing manifest/root, not just column names. Reject unknown provider/basis/time semantics for conforming new research; preserve legacy unknowns as nonconforming evidence. |

## 3. Configuration proposal and coordination

Use one non-secret `market_data` config object, validated before network/storage access. The following are proposed shared schema fields, **not new environment aliases**. Consumer configuration is explicit; no configuration is written by this PR.

| Field | Proposed default / requirement |
|---|---|
| `schema_version` | `qsl.market_data_config.v1` |
| `purpose` | Required: `research`, `decision`, `display` or `execution_quote`; no inherited live authority |
| `instrument_ids`, `price_basis` | Required, no implicit basis; quote requests require contemporaneous `raw_unadjusted` plus their quote type |
| `primary.provider`, `primary.feed` | Market/purpose profile from the standard; US history `alpaca`/`sip`, US recent observation `alpaca`/`iex`; actual values retained in result |
| `fallback.providers` | Ordered candidates from the standard, default empty until explicitly selected for that consumer |
| `fallback.allow_source_change` | `false`; a selected fallback still creates a separately identified source result |
| `provider_options.alpaca.plan` | `basic`; entitlement declaration is not proof of a paid subscription |
| `provider_options.alpaca` delay/feed adapter mapping | Map `ALPACA_SIP_MIN_DELAY_MINUTES`, `ALPACA_FEED_HISTORICAL`, `ALPACA_FEED_RECENT` from companion PR #543; historical SIP default/minimum 16 here; recent default IEX |
| `provider_options.<provider>.base_url` | Official public provider endpoint from the current adapter; override must preserve provider identity and approved transport policy. No private host defaults. |
| `market_profile`, `market_timezone`, `calendar_id` | Market defaults in the standard; timezone/venue mismatches rejected |
| `calendar_version`, `calendar_schedule_digest` | Required pinned version/schedule for a frozen dataset; no moving `latest` default |
| `session_scope`, `close_kind` | `regular`, `last_eligible_trade` for a daily signal profile; adapter capability check required; native bars without proof remain `provider_native` |
| `finalization_delay_seconds` | Explicit per-adapter/profile before enabling acquisition; no universal unverified zero-latency default |
| `storage.object_root` | Required approved cloud root; no default bucket/project or local path |
| `storage.namespace` | `market-data/v1`, configurable; existing frozen candidate paths retain their contracts |
| `storage.retention_policy_id` | Required rights/retention policy; no automatic deletion behavior |
| `cache.enabled` | `false` until approved cloud storage is injected; request-local memory reuse may be enabled independently |
| `cache.namespace` | `market-data-cache/v1`, configurable |
| `cache.completed_history` | Immutable versioned entries; new vendor revision creates a new entry |
| `cache.mutable_ttl_seconds` | `0` (no persistent reuse); a configured positive TTL never extends source freshness or quote validity |
| `validation.expected_sessions`, `validation.max_age_seconds` | Derived from the explicit request/profile and existing consumer policy; no relaxed global fallback default |

Resolution order for future adoption: versioned package/market-profile defaults → versioned consumer config → explicitly documented non-secret environment/CLI overrides. Record the resolved non-secret configuration and its binding. Overrides cannot change a frozen candidate's identity in place or bypass minimum delay/entitlement, basis, calendar, risk or permission checks. Current repo-specific precedence remains unchanged until its own migration PR is accepted.

### Coordination readback

The owner notes for `live_cfg2` confirm Basic/free entitlement and the 16-minute safety bound. That job finished without a feed/delay implementation. Its successor now has [UESP PR #543](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/pull/543), latest inspected at `4d64d01ee90151e02495e48773d32cad4866bbeb` (open when read):

| Existing companion key | Default | Shared-layer rule |
|---|---|---|
| `ALPACA_SIP_MIN_DELAY_MINUTES` | `16` | Reuse this exact name; this standard requires at least 16 for Basic SIP. The follow-up companion revision now enforces >=16 as well; DS-30 preserves the earlier discrepancy and its resolution. |
| `ALPACA_FEED_HISTORICAL` | `sip` | `sip` or explicitly selected `iex`; preserve actual feed per immutable segment. |
| `ALPACA_FEED_RECENT` | `iex` | `iex` or `none`; no recent SIP and no retry-to-IEX after a 401/403. |

The shared config adapter maps these existing environment names once; it does not introduce competing aliases. The companion planner returns disjoint inclusive time windows, with the recent segment starting one microsecond after the historical bound. Native daily bar timestamps can still overlap across segments; do not merge their OHLCV. The companion PR changes a manual diagnostic/reusable planner, not scheduled producers or consumers, and does not establish market-data parity or adoption. The base inventory predates it; treat this as a separately pinned coordination delta. Details: [companion window documentation](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/blob/4d64d01ee90151e02495e48773d32cad4866bbeb/docs/alpaca_free_plan_windows.md).

The `ibkr_close_compare` owner update and [Draft PR #542](https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/pull/542) (head `cf267fcc28375f6de6b6c35e9cf992a68d507768`) agree on the four basis enum values and separate signal basis from return accounting. That PR aggregates pre-existing paired ledgers; it does not generate replays. Empirical coverage remains **0/8 target-windows**, `NOT_COMPUTED`, pending frozen inputs, actual inception, effective configuration and UBPS costs/options evidence. The four reported profiles and #588/#601/#602 distinctions are in the inventory. Source terminology agreement does not quantify a strategy's actual return difference; this job performs no brokerage or price query.

## 4. Acquisition, cache and validation flow

1. Resolve and bind the instrument/profile, required basis, UTC coverage, decision cutoff and approved source policy. Validate capabilities/entitlements without attempting an unauthorized endpoint.
2. Compute an identity from provider, feed, endpoint/adjustment mode, instrument/venue/currency, frequency, requested/effective bounds, session/close policy, calendar/action versions, transformation/adapter version and access-policy/retention scope. A symbol/date-only key is insufficient. Keep private access-scope identifiers out of public manifests.
3. Load an exact immutable cloud object or acquire through the selected adapter in approved cloud compute. Store native responses in approved storage, then normalize. No real data is materialized on developer Macs or committed to Git.
4. Validate schema, finite numeric fields, units, OHLC relationships, sorting/duplicates, expected sessions/inception/suspensions, completed bars, availability cutoff, action coverage and requested basis. Rates/returns have their own numeric domains; do not impose positive equity-price rules on every dataset. Missing is not zero and does not become a non-trading day without evidence.
5. Verify source/content/manifest digests, existing decision binding and any required multisource assurance. Atomically publish a new immutable generation with the existing store's facilities; a mutable index may point to it only under the established publication policy. Cache-hit validation verifies identity, bytes, license scope and freshness; it never changes fetch/availability time.
6. Return values with their bound provenance/quality. Consumers receive unavailable/incomplete on a failed contract. A stale cache or IEX value cannot satisfy a SIP/full-market request without an explicitly new source policy and dataset identity.

No blind repeat of permission/entitlement failures. Classify 401/403, quota, transient transport and invalid payload separately. Respect existing bounded retry policy; the shared layer does not create another retry loop around it. Plan a separately labelled IEX recent-observation segment before acquisition when that profile permits it. A 401/403 stops the affected acquisition; do not change feed and retry after an entitlement failure. A preplanned IEX segment cannot satisfy a trading decision that requires SIP.

## 5. Consumer migration order and risk

This is a future plan, not authorization to execute it. The inventory gives a file-level row for each identified consumer, its configuration fields, proposed wave and specific risk. The order below applies within those waves; each consumer keeps an explicit source/basis pin. No all-repo dependency bump is proposed.

| Wave | Consumers / action in a future approved PR | Risk and acceptance evidence |
|---|---|---|
| 0 | QPK manifest/normalization/ports and existing source assurance | Medium: changing identity/serialization can invalidate evidence. Synthetic golden vectors, old-root compatibility and rejection cases first. No remote data fetch. |
| 1 | Existing US research collectors, then HK/CN/crypto collectors, each by the file rows in the inventory | Medium/high: source rights, adjusted basis and calendar differences. Reuse `live_cfg2`; run source conformance in approved cloud only when separately authorized. Preserve old objects and independent-source gates. |
| 2 | Research loaders/runners, strategy mathematical cores and plugin replay paths across the four strategy repos, QSP, UESP, research/context repos | Medium: changed signals/returns and lost PIT. Migrate one frozen input/consumer first, compare on identical permitted inputs, rerun only the affected evidence under its own authorization. No evidence equivalence assumed across basis changes. |
| 3 | QRS benchmark publisher, revision policy, worker storage/read model and website chart projection | Medium: misleading benchmark/portfolio comparison or accidental history overwrite. Keep price/total-return and ETF/index IDs visible, preserve current revision authorization and immutable old points. Browser reads existing projections; no provider credentials or fetching in the page. |
| 4 | Platform historical input adapters in an isolated no-order/offline path, one platform at a time | High: platform signal history differs from research. Verify semantic mapping and dependency pin using synthetic or separately approved cloud replay; execution quote/anti-resend/reconciliation paths remain independently checked. |
| 5 (last) | Live decision consumers for IBKR, Schwab, LongBridge, Firstrade and Binance; any future QMT/Alpaca admission | Highest: explicit per-consumer provider/feed/basis/calendar/adapter/binding pins and a separately authorized adoption/config change. Default remains the existing path; no automatic selection of the shared layer. Verify exact deployed pin/readback before claiming adoption. Preserve unique executor, unknown-result/409/RECONCILE_ONLY protections and caps. No test orders. |

Every inventory row has its own proposed wave/risk; several rows in the same repo can belong to different waves. Within wave 2, use the inventory row order (artifact loader before its replay/strategy/plot consumer). Within live wave 5, owner-approved account/platform order overrides any source-code ordering. An unconfigured component is not activated for the sake of completing a migration table.

A future adoption must explicitly bind `provider + feed + price_basis + session/calendar profile + adapter version + QPK version + decision artifact identity`. The precise config names belong in that consumer's PR. There is no global “unified=true” switch or implicit fallback on an exception. Rollback returns to the previously approved compatible input/profile; it does not erase evidence, change ledger history or resend unknown orders.

## 6. Verification plan for future implementation

Before a shared implementation is claimed conforming, use synthetic fixtures for split/reverse-split, distribution double-counting, missing adjusted-close entries, float/decimal serialization, action revisions, DST, early closes, HK/CN lunch/half-days, crypto day completion, pagination, inception/delisting, source-change cache separation, stale/invalid cache, truncated SIP coverage and late data. Perturb future events and ensure earlier decisions are unchanged.

Then compare only separately authorized cloud observations under identical instrument/basis/session policies, with predeclared tolerances. Report differences in provider trade filtering, corporate actions and timestamps instead of averaging them away. Empirical IBKR comparisons may guide a specific adoption but do not establish universal provider equivalence.

This documentation PR is validated for Markdown-only scope, source-link integrity, table completeness, English commit/PR metadata and absence of private infrastructure/data. It does not run data collectors, cloud workflows, backtests, broker APIs or orders, and its checks cannot establish runtime adoption or financial correctness.
