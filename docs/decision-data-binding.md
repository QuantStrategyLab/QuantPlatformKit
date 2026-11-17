# Decision Data Binding (v1)

[简体中文](decision-data-binding.zh-CN.md)

`DecisionDataBinding` records the historical market-data evidence behind a strategy decision, keeping it on a separate channel from broker account state, live execution quotes, and order submission:

```text
P1 data collection / multisource check -> frozen data artifact -> strategy decision
Broker account / positions -------------------------------------> execution risk controls
Execution real-time quotes -------------------------------------> sizing conversion & price protection
Order intent ---------------------------------------------------> broker execution
```

Bindings may contain only stable IDs, dates, adjustment conventions, source IDs, and SHA-256 digests. Never store API keys, account numbers, vendor URLs, signed URLs, raw market quotes, or vendor error payloads.

Three migration modes are supported:

- `legacy_runtime_fetch`: legacy runtime data fetch path; must explicitly mark `LEGACY` for observation rather than treating inputs as verified.
- `artifact_optional`: evaluates frozen artifacts alongside the legacy path without substituting artifacts for live execution quotes.
- `artifact_required`: requires strategy historical inputs to match the frozen artifact and bound digest; if missing or not `VERIFIED`, the runtime prohibits new risk.

`DecisionDataArtifactPort` loads verified historical decision data only, while `ExecutionQuotePort` supplies short-lived execution quotes only. Legacy `MarketDataPort` remains for migration compatibility; new strategy code must not reuse one port for both historical decisions and live order-entry protection.

## Portable daily price projection (v1)

P1 raw root layouts vary across strategies (e.g., OHLCV for TQQQ vs. adjusted closes for SOXL candidates), and platforms cannot guess private layouts. Any P1 root intended for runtime consumption must therefore also include:

- `decision-price-series.json`: conforms to `qpk.decision_price_series_artifact.v1`, supplying daily `as_of`, `close`, and nullable `volume` per symbol.
- `manifest.json`: follows `research_input_manifest.v1` and records the file size and SHA-256 of `decision-price-series.json` as a member entry.

At runtime, the consumer verifies canonicalized `manifest.json` against `artifact_sha256` from the public binding, verifies the member digest of `decision-price-series.json`, and checks `strategy_scope`, final trading date, adjustment convention, and source ID. Any mismatch prevents returning historical series.

`binding_sha256` is omitted from the projection to avoid a circular hash ("binding hashes manifest, manifest hashes projection"); the runtime recomputes and verifies binding identity on readback.

Storage locations come strictly from private deployment resolvers and must never appear in `RuntimeTarget`, console pages, or execution reports. P1 must still pass its own multisource validation; this projection is only a common verified handoff to platforms and never replaces P1, P3, or P4-P6 promotion gates.
