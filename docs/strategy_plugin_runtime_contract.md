# Strategy Plugin Runtime Contract

[简体中文](./strategy_plugin_runtime_contract.zh-CN.md)

This document describes how platform runtimes consume sidecar strategy plugin
artifacts, such as a Crisis Response plugin produced by an upstream snapshot or
research pipeline.

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
artifact and is fixed to notification-only `shadow`.

Suggested environment variable name: `STRATEGY_PLUGIN_MOUNTS_JSON`.

Recommended value:

```json
{
  "strategy_plugins": [
    {
      "strategy": "tqqq_growth_income",
      "plugin": "crisis_response_shadow",
      "signal_path": "/path/to/strategy-artifacts/us_equity/tqqq_growth_income/plugins/crisis_response_shadow/latest_signal.json",
      "enabled": true
    }
  ]
}
```

Use `expected_mode` only as a fail-closed runtime guard. It does not select
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

Do not put `mode` in the platform mount config. `expected_mode` may be used only
as a fail-closed guard and should be `shadow` when present. Artifacts declaring
`paper`, `advisory`, or `live` are rejected.

## Plugin Definitions

The shared kit owns plugin compatibility through a registry-style
`StrategyPluginDefinition`. Platform repos should not hard-code which strategies
a plugin supports; they should call the shared parser/loader and let it reject
unsupported mounts or artifacts.

The default registry currently defines versioned plugin contracts:

| Plugin | Schema versions | Supported strategies | Status | Supported mode | Escalated alert channel |
| --- | --- | --- | --- | --- | --- |
| `market_regime_control` | `market_regime_control.v1` | `tqqq_growth_income`, `global_etf_rotation`, `russell_1000_multi_factor_defensive`, `tech_communication_pullback_enhancement`, `mega_cap_leader_rotation_top50_balanced` | default | `shadow` | `email`, `sms`, `push`, `telegram` |
| `crisis_response_shadow` | `crisis_response_shadow.v1` | `tqqq_growth_income` | deprecated; successor `market_regime_control` | `shadow` | `email`, `sms`, `push`, `telegram` |
| `macro_risk_governor` | `macro_risk_governor.v1` | `tqqq_growth_income` | deprecated; successor `market_regime_control` | `shadow` | `email`, `sms`, `push`, `telegram` |
| `taco_rebound_shadow` | `taco_rebound_shadow.v2` | `tqqq_growth_income` | deprecated; successor `market_regime_control` | `shadow` | `email`, `sms`, `push`, `telegram` |

Deprecated plugins remain loadable for historical backtests and staged rollout.
New strategy integrations should mount `market_regime_control` and read the
artifact's `notification` and `position_control` sections. The old TACO artifact
is notification-only. It may escalate a manual-review alert when a TACO-style
rebound context is active, but it must not recommend position size, mutate live
allocation, or imply broker order permission.

To expand a plugin later, update the shared definition or pass an explicit
definition registry into the parser/loader. This keeps future plugin eligibility
changes out of platform runtime code.

SOXL/SOXX is intentionally not listed as a `market_regime_control` runtime
mount. Broad macro and crisis signals for SOXL should be delivered through a
general notification artifact and reviewed manually unless a future backtest
promotes an explicit strategy-level opt-in.

## Runtime Loader

Use `quant_platform_kit.common.strategy_plugins`:

```python
from quant_platform_kit.common.strategy_plugins import (
    build_strategy_plugin_alert_messages,
    build_strategy_plugin_notification_lines,
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
notification_lines = build_strategy_plugin_notification_lines(signals, locale="zh-CN")
alert_messages = build_strategy_plugin_alert_messages(signals)
```

The loader validates:

- the artifact is a JSON object
- `strategy` and `plugin` match the configured mount
- `mode`, `configured_mode`, and `effective_mode` are `shadow`
- optional `expected_mode` matches `effective_mode`
- duplicate platform mounts are rejected
- platform mount config does not set `mode`

## Behavior Boundary

For `shadow`, platform runtimes should only add logs, runtime report fields, and
notification context.

Artifacts may include display-only i18n fields:

- `localized_messages.schema_version = strategy_plugin_messages.v1`
- `localized_messages.notification.en-US` / `localized_messages.notification.zh-CN`
- `localized_messages.log.en-US` / `localized_messages.log.zh-CN`
- `log_record.schema_version = strategy_plugin_log.v1`

Platform renderers may use these fields for notification and log text. Trading
logic must continue to read machine fields such as `schema_version`,
`canonical_route`, `suggested_action`, `reason_codes`, and `position_control`.

`paper`, `advisory`, and `live` plugin modes are not supported by the shared
contract. Platforms should not maintain plugin ledgers or execute plugin-driven
allocation changes from this sidecar path.

## Escalated Alerts

The shared kit owns the platform-neutral alert policy. A plugin signal escalates
when any of the following is true:

- `canonical_route` is not `no_action`
- `suggested_action` is `defend` or `blocked`
- `would_trade_if_enabled` is `true`

Platforms may still choose their delivery sinks, but shared escalation helpers
are available for email and SMS:

- `quant_platform_kit.notifications.strategy_plugin_email.publish_strategy_plugin_email_alerts()`
- `quant_platform_kit.notifications.strategy_plugin_sms.publish_strategy_plugin_sms_alerts()`

The publishers build the shared subject/body, prefix platform context, return
structured sent/skipped/failed diagnostics, and can use marker stores to skip
alert keys that were already sent for that channel.

Delivery credentials, routes, and transport settings are platform runtime
configuration. The plugin artifact and strategy code only decide whether an
escalated alert should exist; they do not decide how a platform delivers it.

This keeps the Crisis Response plugin behavior consistent across IBKR, Schwab,
LongBridge, Firstrade, and future platform runtimes.
