# Multisource Daily Bar Data Assurance Gate

[简体中文](multisource-data-assurance.zh-CN.md)

`quant_platform_kit.data.multisource_assurance` is a pure validation layer shared across markets, strategies, platforms, and plugins. It performs no network calls, stores no quotes, accesses no brokers, and never backfills or rewrites missing data from another source.

Each market-data adapter emits an immutable `DailyBarSourceSnapshot` containing source ID, symbol, cutoff date, adjustment convention, source root digest, and the full OHLCV series. When an adapter is unavailable, it emits `DailyBarSourceObservation(status="UNAVAILABLE")` with a stable reason code such as `provider_auth_or_entitlement`—never raw error responses, keys, or price payloads.

Callers configure `MultiSourceDailyBarPolicy` explicitly:

- Required sources (at least two independent sources).
- Symbol, daily cutoff date, and adjustment convention.
- Allowed relative tolerances for OHLC prices and volume.

`assess_multisource_daily_bars` emits exactly one of three statuses:

- `VERIFIED`: all configured sources are available and trading-date coverage, adjustment convention, and OHLCV tolerances match; only this state can publish official research inputs or support strategy release.
- `DEGRADED`: at least one source has data, but a source is missing, conventions disagree, or values diverge; usable for diagnostics and shadow research only, never as primary data.
- `PARKED`: no usable sources exist; research and release cannot proceed.

Diagnostics record only status, stable reason codes, and immutable digests—never raw prices, paths, keys, or vendor response text. `report_sha256` flows into upstream P1 manifests and downstream evidence packages for end-to-end provenance traceability.

Release callers can set `require_data_assurance=True` and pass the report. Only a `VERIFIED` report digest binds into an immutable `StrategyReleaseManifest`; missing or degraded reports fail release readiness.

For SOXL, Alpaca SIP and Twelve Data EOD must remain separate source roots. When a free EOD feed cannot strictly match the strategy's required `total_return_adjusted` convention, the gate stops safely at `DEGRADED` instead of mixing incompatible feeds in backtests.
