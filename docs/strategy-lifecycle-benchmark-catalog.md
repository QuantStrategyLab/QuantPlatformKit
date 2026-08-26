# Lifecycle monitoring benchmark catalog

Promotion-grade monitoring must name the passive or unleveraged instrument used
to judge each strategy. A generic US-equity default such as SPY is not an
acceptable substitute for a leveraged-sector strategy.

Use a JSON file with this shape:

```json
{
  "schema_version": "qsl.strategy-benchmark-catalog.v1",
  "authority": {"monitoring_only": true, "no_order": true},
  "bindings": [
    {
      "strategy_profile": "soxl_soxx_trend_income",
      "benchmark_symbol": "buy_hold_SOXX",
      "benchmark_kind": "unleveraged_underlying",
      "relative_drawdown_required": true
    }
  ]
}
```

Run strict monitoring with:

```text
quant-lifecycle monitor --domain us_equity --strategy soxl_soxx_trend_income --live-stream-id longbridge-quant-sg-service --benchmark-catalog catalog.json --require-explicit-benchmark
```

Strict mode refuses to publish a snapshot when either the strategy binding or
its benchmark return series is absent. The catalog is monitoring-only and
never grants strategy, broker, or promotion authority.

## Account-safe live telemetry

Live account equity must be evaluated one account/runtime stream at a time.
When it runs in Cloud Run, QPK records the built-in `K_SERVICE` identity as
`lifecycle_stream_id`; other runtimes can set `LIFECYCLE_STREAM_ID`. The
stream becomes part of the storage path and the live-record deduplication key.

If the same strategy profile has records from more than one stream and no
stream is selected, the return collector omits that profile rather than
combining separate broker accounts into a false equity curve. `--live-stream-id`
is therefore required for promotion-grade monitoring of persisted live data.
This is still read-only monitoring: it cannot place orders, alter a strategy,
or promote a candidate.
