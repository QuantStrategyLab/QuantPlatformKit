"""Constants and core data models for strategy plugin artifacts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from quant_platform_kit.common._strategy_plugin_helpers import DEFAULT_PLUGIN_ARTIFACT_CACHE_DIR, _as_bool, _optional_string, _required_string

PLUGIN_CRISIS_RESPONSE_SHADOW = "crisis_response_shadow"
PLUGIN_MARKET_REGIME_CONTROL = "market_regime_control"
PLUGIN_MACRO_RISK_GOVERNOR = "macro_risk_governor"
PLUGIN_TACO_REBOUND_SHADOW = "taco_rebound_shadow"
PLUGIN_PANIC_REVERSAL_SHADOW = "panic_reversal_shadow"
GENERAL_MARKET_REGIME_NOTIFICATION_TARGET = "market_regime_notification"
PLUGIN_MODE_SHADOW = "shadow"
STRATEGY_PLUGIN_ALERT_CHANNEL_EMAIL = "email"
STRATEGY_PLUGIN_ALERT_CHANNEL_SMS = "sms"
STRATEGY_PLUGIN_ALERT_CHANNEL_PUSH = "push"
STRATEGY_PLUGIN_ALERT_CHANNEL_TELEGRAM = "telegram"
STRATEGY_PLUGIN_ALERT_CHANNEL_WEBHOOK = "webhook"
SUPPORTED_STRATEGY_PLUGIN_MODES = frozenset({PLUGIN_MODE_SHADOW})
STRATEGY_PLUGIN_NON_ALERT_ROUTES = frozenset({"no_action"})
STRATEGY_PLUGIN_ALERT_ACTIONS = frozenset({"defend", "blocked"})
STRATEGY_PLUGIN_AUTOMATED_POSITION_ACTIONS = frozenset({"defend", "delever"})
# Legacy v1 artifacts may still carry position-control-shaped metadata for
# replay and display.  The V2 sidecar contract makes that metadata
# non-authoritative: a plugin cannot directly mutate a strategy allocation.
STRATEGY_PLUGIN_DIRECT_POSITION_CONTROL_ALLOWED = False
CRISIS_RESPONSE_SHADOW_SUPPORTED_STRATEGIES = frozenset(
    {
        "tqqq_growth_income",
    }
)
TACO_REBOUND_SHADOW_SUPPORTED_STRATEGIES = frozenset({"tqqq_growth_income"})
MACRO_RISK_GOVERNOR_SUPPORTED_STRATEGIES = frozenset({"tqqq_growth_income"})
MARKET_REGIME_CONTROL_SUPPORTED_STRATEGIES = frozenset(
    {
        "tqqq_growth_income",
        "soxl_soxx_trend_income",
        "global_etf_rotation",
        "russell_top50_leader_rotation",
        "russell_1000_multi_factor_defensive",
        "mega_cap_leader_rotation_top50_balanced",
    }
)
STRATEGY_PLUGIN_NOTIFICATION_TARGETS: Mapping[str, frozenset[str]] = {
    PLUGIN_MARKET_REGIME_CONTROL: frozenset({GENERAL_MARKET_REGIME_NOTIFICATION_TARGET}),
}
STRATEGY_PLUGIN_SCHEMA_VERSIONS: Mapping[str, frozenset[str]] = {
    PLUGIN_CRISIS_RESPONSE_SHADOW: frozenset({"crisis_response_shadow.v1"}),
    PLUGIN_MARKET_REGIME_CONTROL: frozenset({"market_regime_control.v1"}),
    PLUGIN_MACRO_RISK_GOVERNOR: frozenset({"macro_risk_governor.v1"}),
    PLUGIN_TACO_REBOUND_SHADOW: frozenset({"taco_rebound_shadow.v2"}),
}


@dataclass(frozen=True)
class StrategyPluginDefinition:
    plugin: str
    supported_strategies: frozenset[str] | None = None
    supported_modes: frozenset[str] = field(default_factory=lambda: SUPPORTED_STRATEGY_PLUGIN_MODES)
    supported_schema_versions: frozenset[str] = field(default_factory=frozenset)
    default_schema_version: str | None = None
    deprecated: bool = False
    successor_plugin: str | None = None
    alert_channels: tuple[str, ...] = ()

    def normalized(self) -> "StrategyPluginDefinition":
        plugin = _required_string(self.plugin, field_name="plugin")
        supported_strategies = (
            frozenset(_required_string(strategy, field_name="supported_strategy") for strategy in self.supported_strategies)
            if self.supported_strategies is not None
            else None
        )
        supported_modes = frozenset(
            normalize_strategy_plugin_mode(mode, field_name="supported_mode")
            for mode in self.supported_modes
        )
        if not supported_modes:
            raise ValueError(f"strategy plugin definition for {plugin} must include at least one supported mode")
        supported_schema_versions = frozenset(
            _required_string(version, field_name="supported_schema_version")
            for version in self.supported_schema_versions
        )
        default_schema_version = _optional_string(self.default_schema_version)
        if default_schema_version is not None and supported_schema_versions and default_schema_version not in supported_schema_versions:
            raise ValueError(
                f"strategy plugin definition for {plugin} default_schema_version must be listed in supported_schema_versions"
            )
        successor_plugin = _optional_string(self.successor_plugin)
        alert_channels = tuple(
            _required_string(channel, field_name="alert_channel")
            for channel in self.alert_channels
        )
        return StrategyPluginDefinition(
            plugin=plugin,
            supported_strategies=supported_strategies,
            supported_modes=supported_modes,
            supported_schema_versions=supported_schema_versions,
            default_schema_version=default_schema_version,
            deprecated=bool(self.deprecated),
            successor_plugin=successor_plugin,
            alert_channels=alert_channels,
        )

    def supports_strategy(self, strategy: str) -> bool:
        if self.supported_strategies is None:
            return True
        return strategy in self.supported_strategies


DEFAULT_STRATEGY_PLUGIN_DEFINITIONS: Mapping[str, StrategyPluginDefinition] = {
    PLUGIN_CRISIS_RESPONSE_SHADOW: StrategyPluginDefinition(
        plugin=PLUGIN_CRISIS_RESPONSE_SHADOW,
        supported_strategies=CRISIS_RESPONSE_SHADOW_SUPPORTED_STRATEGIES,
        supported_modes=SUPPORTED_STRATEGY_PLUGIN_MODES,
        supported_schema_versions=STRATEGY_PLUGIN_SCHEMA_VERSIONS[PLUGIN_CRISIS_RESPONSE_SHADOW],
        default_schema_version="crisis_response_shadow.v1",
        deprecated=True,
        successor_plugin=PLUGIN_MARKET_REGIME_CONTROL,
        alert_channels=(
            STRATEGY_PLUGIN_ALERT_CHANNEL_EMAIL,
            STRATEGY_PLUGIN_ALERT_CHANNEL_SMS,
            STRATEGY_PLUGIN_ALERT_CHANNEL_PUSH,
            STRATEGY_PLUGIN_ALERT_CHANNEL_TELEGRAM,
        ),
    ),
    PLUGIN_TACO_REBOUND_SHADOW: StrategyPluginDefinition(
        plugin=PLUGIN_TACO_REBOUND_SHADOW,
        supported_strategies=TACO_REBOUND_SHADOW_SUPPORTED_STRATEGIES,
        supported_modes=SUPPORTED_STRATEGY_PLUGIN_MODES,
        supported_schema_versions=STRATEGY_PLUGIN_SCHEMA_VERSIONS[PLUGIN_TACO_REBOUND_SHADOW],
        default_schema_version="taco_rebound_shadow.v2",
        deprecated=True,
        successor_plugin=PLUGIN_MARKET_REGIME_CONTROL,
        alert_channels=(
            STRATEGY_PLUGIN_ALERT_CHANNEL_EMAIL,
            STRATEGY_PLUGIN_ALERT_CHANNEL_SMS,
            STRATEGY_PLUGIN_ALERT_CHANNEL_PUSH,
            STRATEGY_PLUGIN_ALERT_CHANNEL_TELEGRAM,
        ),
    ),
    PLUGIN_MARKET_REGIME_CONTROL: StrategyPluginDefinition(
        plugin=PLUGIN_MARKET_REGIME_CONTROL,
        supported_strategies=MARKET_REGIME_CONTROL_SUPPORTED_STRATEGIES,
        supported_modes=SUPPORTED_STRATEGY_PLUGIN_MODES,
        supported_schema_versions=STRATEGY_PLUGIN_SCHEMA_VERSIONS[PLUGIN_MARKET_REGIME_CONTROL],
        default_schema_version="market_regime_control.v1",
        alert_channels=(
            STRATEGY_PLUGIN_ALERT_CHANNEL_EMAIL,
            STRATEGY_PLUGIN_ALERT_CHANNEL_SMS,
            STRATEGY_PLUGIN_ALERT_CHANNEL_PUSH,
            STRATEGY_PLUGIN_ALERT_CHANNEL_TELEGRAM,
        ),
    ),
    PLUGIN_MACRO_RISK_GOVERNOR: StrategyPluginDefinition(
        plugin=PLUGIN_MACRO_RISK_GOVERNOR,
        supported_strategies=MACRO_RISK_GOVERNOR_SUPPORTED_STRATEGIES,
        supported_modes=SUPPORTED_STRATEGY_PLUGIN_MODES,
        supported_schema_versions=STRATEGY_PLUGIN_SCHEMA_VERSIONS[PLUGIN_MACRO_RISK_GOVERNOR],
        default_schema_version="macro_risk_governor.v1",
        deprecated=True,
        successor_plugin=PLUGIN_MARKET_REGIME_CONTROL,
        alert_channels=(
            STRATEGY_PLUGIN_ALERT_CHANNEL_EMAIL,
            STRATEGY_PLUGIN_ALERT_CHANNEL_SMS,
            STRATEGY_PLUGIN_ALERT_CHANNEL_PUSH,
            STRATEGY_PLUGIN_ALERT_CHANNEL_TELEGRAM,
        ),
    ),
}


@dataclass(frozen=True)
class StrategyPluginMountConfig:
    strategy: str
    plugin: str
    signal_path: str
    enabled: bool = True
    expected_mode: str | None = None
    expected_schema_version: str | None = None


@dataclass(frozen=True)
class StrategyPluginNotificationTargetConfig:
    notification_target: str
    plugin: str
    signal_path: str
    enabled: bool = True
    expected_mode: str | None = None
    expected_schema_version: str | None = None


@dataclass(frozen=True)
class StrategyPluginSignal:
    strategy: str
    plugin: str
    mode: str
    configured_mode: str
    effective_mode: str
    schema_version: str
    as_of: str
    canonical_route: str | None = None
    suggested_action: str | None = None
    would_trade_if_enabled: bool = False
    execution_controls: Mapping[str, Any] = field(default_factory=dict)
    payload: Mapping[str, Any] = field(default_factory=dict)
    source_uri: str | None = None
    local_path: str | None = None
    deprecated_plugin: bool = False
    successor_plugin: str | None = None
    supported_schema_versions: tuple[str, ...] = ()
    target_type: str = "strategy"
    notification_target: str = ""
    enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "strategy", _optional_string(self.strategy) or "")
        object.__setattr__(self, "plugin", _optional_string(self.plugin) or "")
        object.__setattr__(self, "mode", _optional_string(self.mode) or "")
        object.__setattr__(self, "configured_mode", _optional_string(self.configured_mode) or "")
        object.__setattr__(self, "effective_mode", _optional_string(self.effective_mode) or "")
        object.__setattr__(self, "schema_version", _optional_string(self.schema_version) or "")
        object.__setattr__(self, "as_of", _optional_string(self.as_of) or "")
        object.__setattr__(self, "canonical_route", _optional_string(self.canonical_route))
        object.__setattr__(self, "suggested_action", _optional_string(self.suggested_action))
        object.__setattr__(
            self,
            "would_trade_if_enabled",
            _as_bool(self.would_trade_if_enabled, default=False),
        )
        controls = dict(self.execution_controls) if isinstance(self.execution_controls, Mapping) else {}
        payload = dict(self.payload) if isinstance(self.payload, Mapping) else {}
        object.__setattr__(self, "execution_controls", controls)
        object.__setattr__(self, "payload", payload)
        object.__setattr__(self, "source_uri", _optional_string(self.source_uri))
        object.__setattr__(self, "local_path", _optional_string(self.local_path))
        object.__setattr__(self, "deprecated_plugin", bool(self.deprecated_plugin))
        object.__setattr__(self, "successor_plugin", _optional_string(self.successor_plugin))
        versions = self.supported_schema_versions
        if isinstance(versions, (str, bytes, Mapping)) or not isinstance(versions, Iterable):
            normalized_versions: tuple[str, ...] = ()
        else:
            normalized_versions = tuple(
                item for item in (_optional_string(version) for version in versions) if item
            )
        object.__setattr__(self, "supported_schema_versions", normalized_versions)
        object.__setattr__(self, "target_type", _optional_string(self.target_type) or "strategy")
        object.__setattr__(self, "notification_target", _optional_string(self.notification_target) or "")
        object.__setattr__(self, "enabled", _as_bool(self.enabled, default=True))

    @property
    def normalized_plugin(self) -> str:
        return self.plugin.lower() or "unknown"

    @property
    def normalized_route(self) -> str:
        return (self.canonical_route or "").lower() or "unknown"

    @property
    def normalized_action(self) -> str:
        return (self.suggested_action or "").lower() or "unknown"

    @property
    def normalized_target_type(self) -> str:
        return self.target_type.lower() or "strategy"

    def report_summary(self) -> dict[str, Any]:
        from quant_platform_kit.common._strategy_plugin_consumption import (
            _strategy_plugin_runtime_consumption_summary,
        )

        return {
            "strategy": self.strategy,
            "target_type": self.target_type,
            "notification_target": self.notification_target,
            "plugin": self.plugin,
            "mode": self.mode,
            "configured_mode": self.configured_mode,
            "effective_mode": self.effective_mode,
            "schema_version": self.schema_version,
            "deprecated_plugin": self.deprecated_plugin,
            "successor_plugin": self.successor_plugin,
            "supported_schema_versions": self.supported_schema_versions,
            "as_of": self.as_of,
            "canonical_route": self.canonical_route,
            "suggested_action": self.suggested_action,
            "would_trade_if_enabled": self.would_trade_if_enabled,
            "execution_controls": dict(self.execution_controls),
            "runtime_consumption": _strategy_plugin_runtime_consumption_summary(self),
            "source_uri": self.source_uri,
            "local_path": self.local_path,
        }



@dataclass(frozen=True)
class StrategyPluginAlertMessage:
    subject: str
    body: str
    alert_key: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


def normalize_strategy_plugin_mode(value: Any, *, field_name: str = "mode") -> str:
    mode = str(value or "").strip().lower()
    if mode not in SUPPORTED_STRATEGY_PLUGIN_MODES:
        modes = ", ".join(sorted(SUPPORTED_STRATEGY_PLUGIN_MODES))
        raise ValueError(f"{field_name} must be one of {modes}; got {value!r}")
    return mode


def normalize_strategy_plugin_definitions(
    plugin_definitions: Mapping[str, StrategyPluginDefinition] | Sequence[StrategyPluginDefinition] | None = None,
) -> Mapping[str, StrategyPluginDefinition]:
    raw_definitions = (
        DEFAULT_STRATEGY_PLUGIN_DEFINITIONS.values()
        if plugin_definitions is None
        else plugin_definitions.values()
        if isinstance(plugin_definitions, Mapping)
        else plugin_definitions
    )
    definitions: dict[str, StrategyPluginDefinition] = {}
    for definition in raw_definitions:
        if not isinstance(definition, StrategyPluginDefinition):
            raise TypeError("strategy plugin definitions must be StrategyPluginDefinition objects")
        normalized = definition.normalized()
        if normalized.plugin in definitions:
            raise ValueError(f"duplicate strategy plugin definition: plugin={normalized.plugin}")
        definitions[normalized.plugin] = normalized
    return definitions

