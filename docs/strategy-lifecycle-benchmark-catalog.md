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
quant-lifecycle monitor --domain us_equity --benchmark-catalog catalog.json --require-explicit-benchmark
```

Strict mode refuses to publish a snapshot when either the strategy binding or
its benchmark return series is absent. The catalog is monitoring-only and
never grants strategy, broker, or promotion authority.
