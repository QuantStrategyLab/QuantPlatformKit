# Strategy Plugin Runtime Contract

This document describes how platform runtimes consume sidecar strategy plugin
artifacts, such as the Crisis Response plugin produced by
`UsEquitySnapshotPipelines`.

## Ownership

- Strategy plugin artifacts are produced upstream by snapshot / research
  pipelines.
- Platform runtimes consume the latest plugin artifact and attach it to logs,
  runtime reports, and notifications.
- Broker order placement remains in platform repositories.
- Strategy formulas remain in strategy repositories.

## Platform Mount Config

Platform config should only decide which plugin artifacts are mounted for a
strategy. It must not select the plugin mode. The mode lives inside the plugin
artifact and is the single behavior contract.

Suggested environment variable name: `STRATEGY_PLUGIN_MOUNTS_JSON`.

Recommended value:

```json
{
  "strategy_plugins": [
    {
      "strategy": "tqqq_growth_income",
      "plugin": "crisis_response_shadow",
      "signal_path": "gs://qsl-runtime-logs-interactivebrokersquant/strategy-artifacts/us_equity/tqqq_growth_income/plugins/crisis_response_shadow/latest_signal.json",
      "enabled": true
    }
  ]
}
```

Use `expected_mode` only as a fail-closed deployment guard. It does not select
or reinterpret the mode:

```json
{
  "strategy_plugins": [
    {
      "strategy": "tqqq_growth_income",
      "plugin": "crisis_response_shadow",
      "signal_path": "/var/strategy-artifacts/tqqq_growth_income/plugins/crisis_response_shadow/latest_signal.json",
      "enabled": true,
      "expected_mode": "shadow"
    }
  ]
}
```

Do not put `mode` in the platform mount config. If the artifact says `paper`,
the platform implements `paper`; if it says `live`, the platform implements
`live` subject to risk checks and kill switches.

## Runtime Loader

Use `quant_platform_kit.common.strategy_plugins`:

```python
from quant_platform_kit.common.strategy_plugins import (
    build_strategy_plugin_report_payload,
    load_configured_strategy_plugin_signals,
    parse_strategy_plugin_mounts,
)

mounts = parse_strategy_plugin_mounts(raw_json_config)
signals = load_configured_strategy_plugin_signals(
    mounts,
    strategy_profile=current_strategy_profile,
)
report_section = build_strategy_plugin_report_payload(signals)
```

The loader validates:

- the artifact is a JSON object
- `strategy` and `plugin` match the configured mount
- `mode`, `configured_mode`, and `effective_mode` are one of `shadow`, `paper`,
  `advisory`, or `live`
- optional `expected_mode` matches `effective_mode`
- duplicate platform mounts are rejected
- platform mount config does not set `mode`

## Behavior Boundary

For `shadow`, platform runtimes should only add logs, runtime report fields, and
notification context.

For `paper`, platform runtimes may maintain a simulated plugin ledger, but must
not mutate real allocations.

For `advisory`, platform runtimes may surface a recommendation that requires
human confirmation.

For `live`, platform runtimes may allow execution only through explicit platform
risk budgets, kill switches, and data-freshness checks.
