# Market-data access-layer design

Status: proposal. Not yet adopted by any consumer.

The [standard](market-data-standard.md) defines the semantics; the [inventory](market-data-inventory.md) lists the identified consumers. This document describes the shared contract, configuration and migration order for a future implementation. No consumer implementation, dependency upgrade, runtime change or deployment is included.

## 1. Smallest shared contract in QPK

Extend the existing `src/quant_platform_kit/data/` and keep network acquisition in the current pipelines and broker adapter modules. Do not create a market-data service, scheduler, database, broker registry or second research orchestrator.

Reuse these existing boundaries:

- `common/ports.py`: `DecisionDataArtifactPort` loads immutable, digest-bound decision inputs; `ExecutionQuotePort` handles short-lived execution quotes. The legacy mixed `MarketDataPort` remains a migration boundary.
- `data/manifest.py`, `data/version.py`, `data/research_input.py`, `data/decision_data_binding.py`, `data/decision_price_series_artifact.py`: extend the existing versioned manifests and binding validation with semantic metadata. Preserve existing canonicalizations and frozen roots.
- `data/multisource_assurance.py`: preserve independently acquired source observations and current VERIFIED/DEGRADED/PARKED behaviour. Selecting a fallback must not bypass a candidate's requirement for two agreeing sources.
- `ibkr/market_data.py`, `schwab/market_data.py`, `longbridge/market_data.py`, `binance/market_data.py`: retain provider SDK differences; promote only the common result contract. Indicator calculations remain separate from normalized acquisition.

The first implementation should prove two existing US research acquisition callers share semantics before factoring provider code. Ordinary strategies consume a supplied frame or artifact without importing provider SDKs.

## 2. Interfaces and ownership

These signatures describe future interfaces; they are not exported APIs.

| Interface | Contract | Owner |
|---|---|---|
| `HistoricalRequest` | Instrument IDs, UTC bounds, frequency, mandatory `price_basis`, purpose, decision cutoff, market/session profile, source policy, expected coverage | QPK data contract, constructed by the pipeline/research consumer |
| `SourceObservation` | Actual provider/feed/mode, retained source root/digest, source timestamps, unmodified native fields, status/reason | Thin provider adapter in the existing producer module |
| `NormalizedDataset` | Typed bars/series plus standard metadata, actual coverage, action/calendar versions, source/content digests, manifest binding | QPK normalization/validation plus provider-specific mapping |
| `fetch_history(request, *, adapter, store, clock)` | Returns a READY dataset or a typed unavailable/invalid/unsupported/coverage status; no strategy, account or order side effects | Small explicit acquisition function |
| `load_verified_price_series(symbol, *, binding_id, binding_sha256)` | Existing artifact port; verifies frozen input identity and request semantics before returning values | Existing decision-data adapter |
| `get_execution_quote(symbol)` | Existing execution quote port; broker source time, bid/ask/last, age and tradability checks; never synthesizes a quote from adjusted history | Existing platform adapter |

Historical decision prices and execution quotes remain separate types and purposes, even when they share the same instrument. Do not silently add fields to the legacy `PriceSeries` and claim every consumer validates them. A versioned manifest-backed envelope carries semantics while a thin checked adapter returns the existing numeric structure. A naked numeric series is not conformance evidence.

Provider adapters map capabilities explicitly:

| Adapter | Native mode and design issue |
|---|---|
| Alpaca | Preserve `feed` and `adjustment`; apply the Basic SIP delay before fetching; record effective bounds; paginate every symbol; verify native daily session scope. |
| IBKR | Pin `whatToShow`, `useRTH`, contract identity, bar size and API date format. `TRADES` cannot satisfy raw or dividend-adjusted requests. Never take over a production Gateway session. |
| Schwab | Keep the existing SDK and retry behaviour; expose its documented/verified history basis separately from execution quotes. Preserve a timestamp's source rather than treating client fetch time as quote time. |
| LongPort | Explicit adjustment enum and trade-session enum, timezone conversion and source close semantics. US signal and HK research profiles are distinct. |
| Yahoo/yfinance | One shared normalization recipe for existing callers after conformance tests; explicit `auto_adjust` choice, source/library version, symbol aliases and action support. Preserve research-only licensing/quality restrictions. |
| Twelve Data | Existing split-only source observations and independent Yahoo cross-check; respect endpoint/plan limits and assurance gates. Not an interchangeable total-return feed. |
| AkShare | Underlying endpoint/version and `qfq` factors/actions; explicitly identify the Yahoo fallback. Preserve unavailable history and lack of strict historical point-in-time. |
| Binance | Venue/pair/currency identity, UTC interval, pagination and completed-kline filter; raw spot prices with token events separate. |
| Injected CSV/context | Verify the existing manifest/root, not just column names. Reject unknown provider/basis/time semantics for conforming new research. |

## 3. Configuration

Use one non-secret `market_data` config object, validated before network or storage access. These are proposed shared schema fields, not new environment aliases. No configuration is written by this proposal.

| Field | Default / requirement |
|---|---|
| `schema_version` | `qsl.market_data_config.v1` |
| `purpose` | Required: `research`, `decision`, `display` or `execution_quote`; no inherited live authority |
| `instrument_ids`, `price_basis` | Required, no implicit basis; quote requests require contemporaneous `raw_unadjusted` plus their quote type |
| `primary.provider`, `primary.feed` | Market/purpose profile from the standard; US history `alpaca`/`sip`, US recent `alpaca`/`iex`; actual values retained in result |
| `fallback.providers` | Ordered candidates from the standard, empty until explicitly selected |
| `fallback.allow_source_change` | `false`; a selected fallback still creates a separately identified source result |
| `provider_options.alpaca.plan` | `basic`; entitlement declaration is not proof of a paid subscription |
| `provider_options.alpaca` delay/feed adapter mapping | Maps `ALPACA_SIP_MIN_DELAY_MINUTES`, `ALPACA_FEED_HISTORICAL`, `ALPACA_FEED_RECENT`; historical SIP default/minimum `16`, recent default `iex` |
| `provider_options.<provider>.base_url` | Official public provider endpoint from the current adapter; override must preserve provider identity and approved transport policy. No private host defaults. |
| `market_profile`, `market_timezone`, `calendar_id` | Market defaults in the standard; timezone/venue mismatches rejected |
| `calendar_version`, `calendar_schedule_digest` | Required pinned version/schedule for a frozen dataset; no moving `latest` default |
| `session_scope`, `close_kind` | `regular`, `last_eligible_trade` for a daily signal profile; adapter capability check required; unproven native bars remain `provider_native` |
| `finalization_delay_seconds` | Explicit per-adapter/profile before acquisition; no universal zero-latency default |
| `storage.object_root` | Required approved cloud root; no default bucket/project or local path |
| `storage.namespace` | `market-data/v1`, configurable; existing frozen candidate paths retain their contracts |
| `storage.retention_policy_id` | Required rights/retention policy; no automatic deletion |
| `cache.enabled` | `false` until approved cloud storage is injected; request-local memory reuse may be enabled independently |
| `cache.namespace` | `market-data-cache/v1`, configurable |
| `cache.completed_history` | Immutable versioned entries; a new vendor revision creates a new entry |
| `cache.mutable_ttl_seconds` | `0` (no persistent reuse); a positive TTL never extends source freshness or quote validity |
| `validation.expected_sessions`, `validation.max_age_seconds` | Derived from the explicit request/profile and existing consumer policy; no relaxed global default |

Resolution order: versioned package/market-profile defaults, then versioned consumer config, then explicitly documented non-secret environment/CLI overrides. Record the resolved non-secret configuration and its binding. Overrides cannot change a frozen candidate's identity in place or bypass minimum-delay/entitlement, basis, calendar, risk or permission checks.

Alpaca segment rules: the feed-window planner in UsEquitySnapshotPipelines maps these three environment names once; the shared layer adds no competing aliases. The planner returns disjoint inclusive time windows, with the recent segment starting one microsecond after the historical bound. Native daily bar timestamps can still overlap across segments; do not merge their OHLCV. `ALPACA_FEED_RECENT` accepts `iex` or `none`; there is no recent SIP and no retry-to-IEX after a 401/403.

## 4. Acquisition, cache and validation flow

1. Resolve and bind the instrument/profile, required basis, UTC coverage, decision cutoff and approved source policy. Validate capabilities and entitlements without attempting an unauthorized endpoint.
2. Compute an identity from provider, feed, endpoint/adjustment mode, instrument/venue/currency, frequency, requested/effective bounds, session/close policy, calendar/action versions, transformation/adapter version and access-policy/retention scope. A symbol/date-only key is insufficient.
3. Load an exact immutable cloud object or acquire through the selected adapter in approved cloud compute. Store native responses in approved storage, then normalize. No real data is materialized on developer machines or committed to Git.
4. Validate schema, finite numeric fields, units, OHLC relationships, sorting/duplicates, expected sessions/inception/suspensions, completed bars, availability cutoff, action coverage and requested basis. Missing is not zero and does not become a non-trading day without evidence.
5. Verify source/content/manifest digests, the existing decision binding and any required multisource assurance. Atomically publish a new immutable generation. Cache-hit validation verifies identity, bytes, license scope and freshness; it never changes fetch/availability time.
6. Return values with their bound provenance and quality. Consumers receive unavailable/incomplete on a failed contract. A stale cache or IEX value cannot satisfy a SIP/full-market request without an explicitly new source policy and dataset identity.

Error handling: classify 401/403, quota, transient transport and invalid payload separately. Respect the existing bounded retry policy; the shared layer does not create another retry loop around it. A 401/403 stops the affected acquisition; do not change feed and retry after an entitlement failure. A preplanned IEX segment cannot satisfy a trading decision that requires SIP.

## 5. Migration order and risk

This is a future plan, not authorization to execute it. Each consumer migrates in its own pull request with explicit source/basis pins, and is confirmed by the maintainer before adoption. The default remains the existing path; there is no global switch.

| Wave | Consumers | Risk and acceptance evidence |
|---|---|---|
| 0 | QPK manifest/normalization/ports and existing source assurance | Medium: changing identity/serialization can invalidate evidence. Synthetic golden vectors, old-root compatibility and rejection cases first. No remote data fetch. |
| 1 | Existing US research collectors, then HK/CN/crypto collectors | Medium/high: source rights, adjusted basis and calendar differences. Run source conformance in approved cloud only when separately authorized. Preserve old objects and independent-source gates. |
| 2 | Research loaders/runners, strategy mathematical cores and plugin replay paths | Medium: changed signals/returns and lost point-in-time. Migrate one frozen input first, compare on identical permitted inputs, rerun only the affected evidence under its own authorization. |
| 3 | Benchmark publisher, revision policy, worker storage/read model and website chart projection | Medium: misleading benchmark comparison or accidental history overwrite. Keep price/total-return and ETF/index IDs visible and preserve current revision authorization. |
| 4 | Platform historical input adapters in an isolated no-order/offline path, one platform at a time | High: platform signal history differs from research. Verify semantic mapping and dependency pin using synthetic or separately approved cloud replay. |
| 5 (last) | Live decision consumers for IBKR, Schwab, LongBridge, Firstrade and Binance | Highest: explicit per-consumer provider/feed/basis/calendar/adapter/binding pins and a separately authorized adoption change. Any future QMT or Alpaca live consumer follows the same rule. No test orders. |

A future adoption must explicitly bind `provider + feed + price_basis + session/calendar profile + adapter version + QPK version + decision artifact identity`. Within wave 2, migrate an artifact loader before its replay, strategy or plot consumers. Within wave 5, the maintainer chooses the account and platform order. There is no implicit fallback on an exception. Existing order-path protections (reconcile-only mode, the unknown-result resend guard, duplicate-order protection) and risk limits are not changed by any migration step. Rollback returns to the previously approved compatible input/profile; it does not erase evidence, change ledger history or resend unknown orders.

## 6. Verification plan

Before a shared implementation is claimed conforming, use synthetic fixtures for split/reverse-split, distribution double-counting, missing adjusted-close entries, float/decimal serialization, action revisions, DST, early closes, HK/CN lunch/half-days, crypto day completion, pagination, inception/delisting, source-change cache separation, stale/invalid cache, truncated SIP coverage and late data. Perturb future events and ensure earlier decisions are unchanged.

Then compare only separately authorized cloud observations under identical instrument/basis/session policies, with predeclared tolerances. Report differences in provider trade filtering, corporate actions and timestamps instead of averaging them away. Empirical IBKR comparisons may guide a specific adoption but do not establish universal provider equivalence.
