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
| `market_regime_control` | `market_regime_control.v1` | `tqqq_growth_income`, `soxl_soxx_trend_income`, `global_etf_rotation`, `russell_top50_leader_rotation`, `russell_1000_multi_factor_defensive`, `mega_cap_leader_rotation_top50_balanced` | default | `shadow` | `email`, `sms`, `push`, `telegram` |
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

Tech/Communication Pullback Enhancement is also not listed because it remains
research-active without runtime trading authority
profile and should not appear in current configurable plugin mounts.

SOXL/SOXX is listed as a `market_regime_control` runtime mount. Its strategy
defaults may consume `risk_off` and deterministic
`position_control.volatility_delever_context` retention profiles, while
`risk_reduced` position impact remains disabled in the strategy config by
default. Broad market-regime notifications may still be published through the
separate `notification_targets.market_regime_notification` artifact for manual
review; notification-target artifacts cannot affect position sizing.
When a strategy-mounted market-regime artifact carries
`execution_controls.manual_review_notification_delegated = true`, platform
strategy runners should treat manual-review plugin-bot delivery as delegated to
that notification target. They may still attach the strategy artifact to runtime
metadata and may still report any actual position effect in the strategy run
notification.
SOXL retention profiles may include a deterministic SOXX price/volatility
rebound context. That context is backtestable hard-data evidence only and must
not promote TACO, panic reversal, AI audit, OSINT, or localized copy into
automatic position authority.

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

General notification artifacts use `notification_targets`, not synthetic
strategy names. They can be loaded and sent through the same notification and
alert builders, but they are not attached to strategy runtime metadata and
cannot authorize position changes:

```python
from quant_platform_kit.common.strategy_plugins import (
    load_configured_strategy_plugin_notification_target_signals,
    parse_strategy_plugin_notification_targets,
)

targets = parse_strategy_plugin_notification_targets(raw_json_config)
notification_signals = load_configured_strategy_plugin_notification_target_signals(targets)
notification_lines = build_strategy_plugin_notification_lines(
    notification_signals,
    locale="zh-CN",
)
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

Runtime reports retain an artifact's source `execution_controls` for audit, and
also publish `runtime_consumption`. Operators must use the latter for the
effective authority: the current shared contract reports `authority=shadow_only`,
`direct_position_control_allowed=false`, and no broker or live-allocation
permission even when a legacy V1 artifact requests position control.

Artifacts may include display-only i18n fields:

- `localized_messages.schema_version = strategy_plugin_messages.v1`
- `localized_messages.notification.en-US` / `localized_messages.notification.zh-CN`
- `localized_messages.log.en-US` / `localized_messages.log.zh-CN`
- `log_record.schema_version = strategy_plugin_log.v1`

Platform renderers may use these fields for notification and log text. Trading
logic must continue to read machine fields such as `schema_version`,
`canonical_route`, `suggested_action`, `reason_codes`, and `position_control`.
Shared `strategy_plugin_*` notification labels live in
`quant_platform_kit.common.notification_localization.STRATEGY_PLUGIN_I18N`;
broker platforms can merge them with local text through
`merge_strategy_plugin_i18n()` so the plugin alert wording stays consistent
across runtimes.

`paper`, `advisory`, and `live` plugin modes are not supported by the shared
contract. Platforms should not maintain plugin ledgers or execute plugin-driven
allocation changes from this sidecar path.

## Escalated Alerts

The shared kit owns the platform-neutral alert policy. A plugin signal escalates
when any of the following is true:

- `canonical_route` is not `no_action`
- `suggested_action` is `defend` or `blocked`
- `would_trade_if_enabled` is `true`

Legacy v1 artifacts may still expose `position_control_allowed = true` for
historical replay, but the V2 sidecar boundary does not honor that field as
allocation authority. A `defend` or `delever` plugin result remains an alert or
research input; only the owning strategy candidate and central Risk Gate may
produce a position target. Strategy artifacts can explicitly delegate
manual-review plugin-bot delivery with
`execution_controls.manual_review_notification_delegated = true` plus
`manual_review_notification_target`; those delegated alerts are sent once from
the matching `notification_targets` artifact. The plugin-alert stream remains
for non-delegated manual-review or notification-only cases, including
`notification_targets`, `blocked`, `watch_only`, and `notify_manual_review`
routes. Historical evidence fields such as `evidence_package_id`,
`evidence_valid_until`, and `bounded_budget` remain useful provenance, but they
do not restore direct position-control permission.

Platforms may still choose their delivery sinks, but shared escalation helpers
are available for email, SMS, push, and Telegram:

- `quant_platform_kit.notifications.strategy_plugin_alerts.publish_strategy_plugin_alerts()`
- `quant_platform_kit.notifications.strategy_plugin_email.publish_strategy_plugin_email_alerts()`
- `quant_platform_kit.notifications.strategy_plugin_sms.publish_strategy_plugin_sms_alerts()`
- `quant_platform_kit.notifications.strategy_plugin_push.publish_strategy_plugin_push_alerts()`
- `quant_platform_kit.notifications.strategy_plugin_telegram.publish_strategy_plugin_telegram_alerts()`

The publishers build the shared subject/body, prefix platform context, return
structured sent/skipped/failed diagnostics, and can use marker stores to skip
alert keys that were already sent for that channel.

Delivery credentials, routes, and transport settings are platform runtime
configuration. The plugin artifact and strategy code only decide whether an
escalated alert should exist; they do not decide how a platform delivers it.

This keeps the Crisis Response plugin behavior consistent across IBKR, Schwab,
LongBridge, Firstrade, and future platform runtimes.
