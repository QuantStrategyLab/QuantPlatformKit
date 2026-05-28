"""Shared runtime helpers for sidecar strategy plugin artifacts."""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from dataclasses import replace as dataclass_replace
from pathlib import Path
from typing import Any, Callable

PLUGIN_CRISIS_RESPONSE_SHADOW = "crisis_response_shadow"
PLUGIN_MARKET_REGIME_CONTROL = "market_regime_control"
PLUGIN_MACRO_RISK_GOVERNOR = "macro_risk_governor"
PLUGIN_TACO_REBOUND_SHADOW = "taco_rebound_shadow"
PLUGIN_MODE_SHADOW = "shadow"
STRATEGY_PLUGIN_ALERT_CHANNEL_EMAIL = "email"
STRATEGY_PLUGIN_ALERT_CHANNEL_SMS = "sms"
STRATEGY_PLUGIN_ALERT_CHANNEL_PUSH = "push"
STRATEGY_PLUGIN_ALERT_CHANNEL_TELEGRAM = "telegram"
SUPPORTED_STRATEGY_PLUGIN_MODES = frozenset({PLUGIN_MODE_SHADOW})
DEFAULT_PLUGIN_ARTIFACT_CACHE_DIR = Path(tempfile.gettempdir()) / "quant_strategy_plugin_artifacts"
STRATEGY_PLUGIN_NON_ALERT_ROUTES = frozenset({"no_action"})
STRATEGY_PLUGIN_ALERT_ACTIONS = frozenset({"defend", "blocked"})
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
        "global_etf_rotation",
        "russell_1000_multi_factor_defensive",
        "tech_communication_pullback_enhancement",
        "mega_cap_leader_rotation_top50_balanced",
    }
)
STRATEGY_PLUGIN_SCHEMA_VERSIONS: Mapping[str, frozenset[str]] = {
    PLUGIN_CRISIS_RESPONSE_SHADOW: frozenset({"crisis_response_shadow.v1"}),
    PLUGIN_MARKET_REGIME_CONTROL: frozenset({"market_regime_control.v1"}),
    PLUGIN_MACRO_RISK_GOVERNOR: frozenset({"macro_risk_governor.v1"}),
    PLUGIN_TACO_REBOUND_SHADOW: frozenset({"taco_rebound_shadow.v2"}),
}
_DEFAULT_STRATEGY_PLUGIN_ALERT_GUIDANCE: Mapping[tuple[str, str, str], str] = {
    (
        PLUGIN_CRISIS_RESPONSE_SHADOW,
        "true_crisis",
        "defend",
    ): (
        "Consider reducing leveraged exposure, moving to defensive or cash-like positions, "
        "and pausing new risk additions until the signal de-escalates."
    ),
    (
        PLUGIN_CRISIS_RESPONSE_SHADOW,
        "no_action",
        "blocked",
    ): (
        "The crisis route was blocked by a guard; review data freshness and context before "
        "acting on the signal."
    ),
    (
        PLUGIN_MACRO_RISK_GOVERNOR,
        "delever",
        "delever",
    ): (
        "Deterministic macro risk governor suggests reducing leveraged exposure while preserving "
        "unlevered risk exposure when the strategy opts in."
    ),
    (
        PLUGIN_MACRO_RISK_GOVERNOR,
        "crisis",
        "defend",
    ): (
        "Deterministic macro risk governor suggests moving the risk sleeve toward defensive or "
        "cash-like exposure until macro stress de-escalates."
    ),
    (
        PLUGIN_MARKET_REGIME_CONTROL,
        "risk_off",
        "defend",
    ): (
        "Unified market regime control blocks opportunity overlays and suggests moving risk exposure "
        "toward defensive or cash-like positions until the deterministic arbiter de-escalates."
    ),
    (
        PLUGIN_MARKET_REGIME_CONTROL,
        "risk_reduced",
        "delever",
    ): (
        "Unified market regime control suggests reducing leveraged exposure while preserving only the "
        "risk budget allowed by the strategy policy adapter."
    ),
    (
        PLUGIN_MARKET_REGIME_CONTROL,
        "opportunity_watch",
        "notify_manual_review",
    ): (
        "Manual review only: the unified arbiter allows the bounded TACO opportunity context, but it "
        "does not authorize broker orders or live allocation mutation."
    ),
    (
        PLUGIN_MARKET_REGIME_CONTROL,
        "blocked",
        "blocked",
    ): (
        "Unified market regime control was blocked by data-quality or freshness guards; review source "
        "artifacts before relying on the signal."
    ),
    (
        PLUGIN_TACO_REBOUND_SHADOW,
        "taco_rebound",
        "notify_manual_review",
    ): (
        "Manual review only: consider a small, pre-sized probe or staged entry with a "
        "predefined invalidation level; avoid full-size deployment from this alert alone."
    ),
}
_DEFAULT_STRATEGY_PLUGIN_ALERT_SCOPE_NOTE = (
    "Manual review notice only; the plugin does not place orders or change allocations."
)


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
class StrategyPluginSignal:
    strategy: str
    plugin: str
    mode: str
    configured_mode: str
    effective_mode: str
    schema_version: str
    as_of: str
    canonical_route: str | None
    suggested_action: str | None
    would_trade_if_enabled: bool
    execution_controls: Mapping[str, Any]
    payload: Mapping[str, Any]
    source_uri: str | None = None
    local_path: str | None = None
    deprecated_plugin: bool = False
    successor_plugin: str | None = None
    supported_schema_versions: tuple[str, ...] = ()

    def report_summary(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
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


def validate_strategy_plugin_compatibility(
    *,
    strategy: str,
    plugin: str,
    mode: str | None = None,
    plugin_definitions: Mapping[str, StrategyPluginDefinition] | Sequence[StrategyPluginDefinition] | None = None,
    source: str = "plugin",
) -> None:
    strategy_name = _required_string(strategy, field_name="strategy")
    plugin_name = _required_string(plugin, field_name="plugin")
    definitions = normalize_strategy_plugin_definitions(plugin_definitions)
    definition = definitions.get(plugin_name)
    if definition is None:
        return
    if not definition.supports_strategy(strategy_name):
        allowed = ", ".join(sorted(definition.supported_strategies or ())) or "any"
        raise ValueError(
            f"strategy plugin {plugin_name} does not support strategy {strategy_name} "
            f"in {source}; supported strategies: {allowed}"
        )
    if mode is None:
        return
    mode_name = normalize_strategy_plugin_mode(mode, field_name="mode")
    if mode_name not in definition.supported_modes:
        allowed_modes = ", ".join(sorted(definition.supported_modes))
        raise ValueError(
            f"strategy plugin {plugin_name} does not support mode {mode_name} "
            f"in {source}; supported modes: {allowed_modes}"
        )


def validate_strategy_plugin_schema_version(
    *,
    plugin: str,
    schema_version: str | None,
    expected_schema_version: str | None = None,
    plugin_definitions: Mapping[str, StrategyPluginDefinition] | Sequence[StrategyPluginDefinition] | None = None,
    source: str = "artifact",
) -> None:
    plugin_name = _required_string(plugin, field_name="plugin")
    normalized_schema_version = _optional_string(schema_version)
    normalized_expected_schema_version = _optional_string(expected_schema_version)
    if normalized_expected_schema_version is not None and normalized_schema_version != normalized_expected_schema_version:
        raise ValueError(
            "strategy plugin artifact schema_version mismatch: "
            f"expected {normalized_expected_schema_version}, got {normalized_schema_version or '<missing>'}"
        )
    definitions = normalize_strategy_plugin_definitions(plugin_definitions)
    definition = definitions.get(plugin_name)
    if definition is None or not definition.supported_schema_versions or normalized_schema_version is None:
        return
    if normalized_schema_version not in definition.supported_schema_versions:
        allowed = ", ".join(sorted(definition.supported_schema_versions))
        raise ValueError(
            f"strategy plugin {plugin_name} does not support schema_version {normalized_schema_version} "
            f"in {source}; supported schema versions: {allowed}"
        )


def parse_strategy_plugin_mounts(
    raw_config: str | Sequence[Mapping[str, Any]] | Mapping[str, Any] | None,
    *,
    plugin_definitions: Mapping[str, StrategyPluginDefinition] | Sequence[StrategyPluginDefinition] | None = None,
) -> tuple[StrategyPluginMountConfig, ...]:
    if raw_config is None or raw_config == "":
        return ()
    definitions = normalize_strategy_plugin_definitions(plugin_definitions)
    payload: Any
    if isinstance(raw_config, str):
        payload = json.loads(raw_config)
    else:
        payload = raw_config

    if isinstance(payload, Mapping):
        payload = payload.get("strategy_plugins", payload.get("plugins", ()))
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("strategy plugin mount config must be a JSON list or object with strategy_plugins")

    mounts: list[StrategyPluginMountConfig] = []
    seen: set[tuple[str, str]] = set()
    for item in payload:
        if not isinstance(item, Mapping):
            raise ValueError("each strategy plugin mount must be an object")
        if "mode" in item:
            raise ValueError("platform plugin mount config must not set mode; read mode from the plugin artifact")
        strategy = _required_string(item.get("strategy"), field_name="strategy")
        plugin = _required_string(item.get("plugin"), field_name="plugin")
        signal_path = _required_string(
            item.get("signal_path") or item.get("latest_signal_path") or item.get("path"),
            field_name="signal_path",
        )
        key = (strategy, plugin)
        if key in seen:
            raise ValueError(f"duplicate strategy plugin mount: strategy={strategy} plugin={plugin}")
        seen.add(key)
        expected_mode = item.get("expected_mode")
        normalized_expected_mode = (
            normalize_strategy_plugin_mode(expected_mode, field_name="expected_mode")
            if expected_mode is not None
            else None
        )
        expected_schema_version = _optional_string(item.get("expected_schema_version"))
        validate_strategy_plugin_schema_version(
            plugin=plugin,
            schema_version=expected_schema_version,
            expected_schema_version=expected_schema_version,
            plugin_definitions=definitions,
            source="mount",
        )
        validate_strategy_plugin_compatibility(
            strategy=strategy,
            plugin=plugin,
            mode=normalized_expected_mode,
            plugin_definitions=definitions,
            source="mount",
        )
        mounts.append(
            StrategyPluginMountConfig(
                strategy=strategy,
                plugin=plugin,
                signal_path=signal_path,
                enabled=_as_bool(item.get("enabled"), default=True),
                expected_mode=normalized_expected_mode,
                expected_schema_version=expected_schema_version,
            )
        )
    return tuple(mounts)


def load_configured_strategy_plugin_signals(
    mounts: Sequence[StrategyPluginMountConfig],
    *,
    strategy_profile: str | None = None,
    client_factory: Any = None,
    plugin_definitions: Mapping[str, StrategyPluginDefinition] | Sequence[StrategyPluginDefinition] | None = None,
) -> tuple[StrategyPluginSignal, ...]:
    selected_strategy = _optional_string(strategy_profile)
    definitions = normalize_strategy_plugin_definitions(plugin_definitions)
    signals: list[StrategyPluginSignal] = []
    for mount in mounts:
        if not mount.enabled:
            continue
        if selected_strategy is not None and mount.strategy != selected_strategy:
            continue
        validate_strategy_plugin_compatibility(
            strategy=mount.strategy,
            plugin=mount.plugin,
            mode=mount.expected_mode,
            plugin_definitions=definitions,
            source="mount",
        )
        signals.append(
            load_strategy_plugin_signal(
                mount.signal_path,
                expected_strategy=mount.strategy,
                expected_plugin=mount.plugin,
                expected_mode=mount.expected_mode,
                expected_schema_version=mount.expected_schema_version,
                client_factory=client_factory,
                plugin_definitions=definitions,
            )
        )
    return tuple(signals)


def load_strategy_plugin_signal(
    reference: str,
    *,
    expected_strategy: str | None = None,
    expected_plugin: str | None = None,
    expected_mode: str | None = None,
    expected_schema_version: str | None = None,
    client_factory: Any = None,
    plugin_definitions: Mapping[str, StrategyPluginDefinition] | Sequence[StrategyPluginDefinition] | None = None,
) -> StrategyPluginSignal:
    local_path, metadata = _materialize_artifact_path(reference, client_factory=client_factory)
    if not local_path.exists():
        raise FileNotFoundError(f"strategy plugin signal not found: {local_path}")
    payload = json.loads(local_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("strategy plugin signal must be a JSON object")
    return validate_strategy_plugin_signal_payload(
        payload,
        expected_strategy=expected_strategy,
        expected_plugin=expected_plugin,
        expected_mode=expected_mode,
        expected_schema_version=expected_schema_version,
        source_uri=metadata.get("source_uri"),
        local_path=str(local_path),
        plugin_definitions=plugin_definitions,
    )


def validate_strategy_plugin_signal_payload(
    payload: Mapping[str, Any],
    *,
    expected_strategy: str | None = None,
    expected_plugin: str | None = None,
    expected_mode: str | None = None,
    expected_schema_version: str | None = None,
    source_uri: str | None = None,
    local_path: str | None = None,
    plugin_definitions: Mapping[str, StrategyPluginDefinition] | Sequence[StrategyPluginDefinition] | None = None,
) -> StrategyPluginSignal:
    strategy = _required_string(payload.get("strategy"), field_name="strategy")
    plugin = _required_string(payload.get("plugin"), field_name="plugin")
    mode = normalize_strategy_plugin_mode(payload.get("mode"), field_name="mode")
    configured_mode = normalize_strategy_plugin_mode(
        payload.get("configured_mode", mode),
        field_name="configured_mode",
    )
    effective_mode = normalize_strategy_plugin_mode(
        payload.get("effective_mode", mode),
        field_name="effective_mode",
    )

    expected_strategy = _optional_string(expected_strategy)
    expected_plugin = _optional_string(expected_plugin)
    if expected_strategy is not None and strategy != expected_strategy:
        raise ValueError(f"strategy plugin artifact strategy mismatch: expected {expected_strategy}, got {strategy}")
    if expected_plugin is not None and plugin != expected_plugin:
        raise ValueError(f"strategy plugin artifact plugin mismatch: expected {expected_plugin}, got {plugin}")
    if expected_mode is not None:
        normalized_expected_mode = normalize_strategy_plugin_mode(expected_mode, field_name="expected_mode")
        if effective_mode != normalized_expected_mode:
            raise ValueError(
                "strategy plugin artifact mode mismatch: "
                f"expected {normalized_expected_mode}, got {effective_mode}"
            )
    validate_strategy_plugin_compatibility(
        strategy=strategy,
        plugin=plugin,
        mode=effective_mode,
        plugin_definitions=plugin_definitions,
        source="artifact",
    )
    schema_version = _optional_string(payload.get("schema_version")) or ""
    definitions = normalize_strategy_plugin_definitions(plugin_definitions)
    definition = definitions.get(plugin)
    validate_strategy_plugin_schema_version(
        plugin=plugin,
        schema_version=schema_version,
        expected_schema_version=expected_schema_version,
        plugin_definitions=definitions,
        source="artifact",
    )

    execution_controls = payload.get("execution_controls") or {}
    if not isinstance(execution_controls, Mapping):
        raise ValueError("strategy plugin signal execution_controls must be an object")

    return StrategyPluginSignal(
        strategy=strategy,
        plugin=plugin,
        mode=mode,
        configured_mode=configured_mode,
        effective_mode=effective_mode,
        schema_version=schema_version,
        as_of=_optional_string(payload.get("as_of")) or "",
        canonical_route=_optional_string(payload.get("canonical_route")),
        suggested_action=_optional_string(payload.get("suggested_action")),
        would_trade_if_enabled=_as_bool(payload.get("would_trade_if_enabled"), default=False),
        execution_controls=execution_controls,
        payload=dict(payload),
        source_uri=_optional_string(source_uri),
        local_path=_optional_string(local_path),
        deprecated_plugin=bool(definition.deprecated) if definition is not None else False,
        successor_plugin=definition.successor_plugin if definition is not None else None,
        supported_schema_versions=tuple(sorted(definition.supported_schema_versions)) if definition is not None else (),
    )


def build_strategy_plugin_report_payload(signals: Sequence[StrategyPluginSignal]) -> dict[str, Any]:
    return {
        "strategy_plugins": [signal.report_summary() for signal in signals],
    }


def build_strategy_plugin_metadata(signals: Sequence[StrategyPluginSignal]) -> dict[str, Any]:
    """Build portfolio-snapshot metadata consumed by deterministic strategies."""
    plugin_payloads: dict[str, Any] = {}
    summaries: dict[str, Any] = {}
    for signal in signals:
        execution_controls = getattr(signal, "execution_controls", {}) or {}
        if not isinstance(execution_controls, Mapping) or not _as_bool(
            execution_controls.get("strategy_runtime_metadata_allowed"),
            default=False,
        ):
            continue
        plugin = str(getattr(signal, "plugin", "") or "").strip()
        if not plugin:
            continue
        payload = dict(getattr(signal, "payload", {}) or {})
        plugin_payloads[plugin] = payload
        summaries[plugin] = signal.report_summary()
    if not plugin_payloads:
        return {}
    metadata: dict[str, Any] = {
        "strategy_plugins": plugin_payloads,
        "strategy_plugin_summaries": summaries,
    }
    metadata.update(plugin_payloads)
    return metadata


def attach_strategy_plugin_metadata(snapshot: Any, signals: Sequence[StrategyPluginSignal]) -> Any:
    """Return a snapshot copy with plugin payloads attached to metadata."""
    plugin_metadata = build_strategy_plugin_metadata(signals)
    if not plugin_metadata:
        return snapshot
    current_metadata = getattr(snapshot, "metadata", {}) or {}
    if not isinstance(current_metadata, Mapping):
        current_metadata = {}
    merged_metadata = {**dict(current_metadata), **plugin_metadata}
    try:
        return dataclass_replace(snapshot, metadata=merged_metadata)
    except TypeError:
        try:
            snapshot.metadata = merged_metadata
        except Exception:
            return snapshot
        return snapshot


def translate_strategy_plugin_value(
    category: str,
    raw_value: str | None,
    *,
    translator: Callable[..., str] | None = None,
) -> str:
    value = str(raw_value or "").strip() or "unknown"
    if translator is None:
        return value
    key = f"strategy_plugin_{category}_{value}"
    translated = translator(key)
    return translated if translated != key else value


def extract_strategy_plugin_localized_message(
    signal: StrategyPluginSignal,
    *,
    section: str,
    locale: str,
) -> str | None:
    payload = getattr(signal, "payload", {}) or {}
    if not isinstance(payload, Mapping):
        return None
    normalized_section = str(section or "").strip()
    normalized_locale = str(locale or "").strip()
    if not normalized_section or not normalized_locale:
        return None

    localized_messages = payload.get("localized_messages")
    if isinstance(localized_messages, Mapping):
        section_messages = localized_messages.get(normalized_section)
        if isinstance(section_messages, Mapping):
            localized = _optional_string(section_messages.get(normalized_locale))
            if localized:
                return localized
            default_locale = _optional_string(localized_messages.get("default_locale"))
            if default_locale:
                localized = _optional_string(section_messages.get(default_locale))
                if localized:
                    return localized

    if normalized_section == "notification":
        notification = payload.get("notification")
        if isinstance(notification, Mapping):
            notification_messages = notification.get("localized_messages")
            if isinstance(notification_messages, Mapping):
                localized = _optional_string(notification_messages.get(normalized_locale))
                if localized:
                    return localized
                default_locale = _optional_string(notification.get("default_locale"))
                if default_locale:
                    localized = _optional_string(notification_messages.get(default_locale))
                    if localized:
                        return localized
    return None


def build_strategy_plugin_notification_lines(
    signals: Sequence[StrategyPluginSignal],
    *,
    translator: Callable[..., str] | None = None,
    locale: str | None = None,
) -> tuple[str, ...]:
    lines: list[str] = []
    for signal in signals:
        localized_line = (
            extract_strategy_plugin_localized_message(signal, section="notification", locale=locale)
            if locale is not None
            else None
        )
        if localized_line:
            lines.append(localized_line)
            continue
        route = getattr(signal, "canonical_route", None) or "unknown_route"
        action = getattr(signal, "suggested_action", None) or "unknown_action"
        lines.append(
            _translate(
                translator,
                "strategy_plugin_line",
                fallback="Plugin: {plugin} | status: {route} | notice: {action}",
                plugin=translate_strategy_plugin_value("name", getattr(signal, "plugin", None), translator=translator),
                mode=translate_strategy_plugin_value("mode", getattr(signal, "effective_mode", None), translator=translator),
                route=translate_strategy_plugin_value("route", route, translator=translator),
                action=translate_strategy_plugin_value("action", action, translator=translator),
            )
        )
    return tuple(lines)


def should_alert_strategy_plugin_signal(signal: StrategyPluginSignal) -> bool:
    route = _normalize_strategy_plugin_field(getattr(signal, "canonical_route", None))
    action = _normalize_strategy_plugin_field(getattr(signal, "suggested_action", None))
    return (
        bool(getattr(signal, "would_trade_if_enabled", False))
        or route not in STRATEGY_PLUGIN_NON_ALERT_ROUTES
        or action in STRATEGY_PLUGIN_ALERT_ACTIONS
    )


def build_strategy_plugin_alert_guidance(
    signal: StrategyPluginSignal,
    *,
    translator: Callable[..., str] | None = None,
) -> str | None:
    plugin = _normalize_strategy_plugin_field(getattr(signal, "plugin", None))
    route = _normalize_strategy_plugin_field(getattr(signal, "canonical_route", None))
    action = _normalize_strategy_plugin_field(getattr(signal, "suggested_action", None))
    translated = _translate_first(
        translator,
        (
            f"strategy_plugin_guidance_{plugin}_{route}_{action}",
            f"strategy_plugin_guidance_{plugin}_{route}",
            f"strategy_plugin_guidance_{plugin}_{action}",
            f"strategy_plugin_guidance_{plugin}",
            f"strategy_plugin_guidance_{route}_{action}",
            f"strategy_plugin_guidance_{action}",
        ),
    )
    if translated:
        return translated
    return _DEFAULT_STRATEGY_PLUGIN_ALERT_GUIDANCE.get((plugin, route, action))


def build_strategy_plugin_alert_scope_note(
    signal: StrategyPluginSignal,
    *,
    translator: Callable[..., str] | None = None,
) -> str | None:
    controls = getattr(signal, "execution_controls", {}) or {}
    if not isinstance(controls, Mapping):
        controls = {}
    notification_profile = str(controls.get("notification_profile") or "").strip().lower()
    if notification_profile != "shadow_only" and any(
        _as_bool(controls.get(field), default=False)
        for field in (
            "broker_order_allowed",
            "repository_broker_write_allowed",
            "live_allocation_mutation_allowed",
            "repository_allocation_mutation_allowed",
            "allocation_recommendation_allowed",
            "position_sizing_allowed",
            "selection_allowed",
        )
    ):
        return None
    return (
        _translate_first(
            translator,
            (
                f"strategy_plugin_alert_scope_{_normalize_strategy_plugin_field(getattr(signal, 'plugin', None))}",
                "strategy_plugin_alert_scope",
            ),
        )
        or _DEFAULT_STRATEGY_PLUGIN_ALERT_SCOPE_NOTE
    )


def build_strategy_plugin_ai_audit_note(
    signal: StrategyPluginSignal,
    *,
    translator: Callable[..., str] | None = None,
) -> str | None:
    payload = getattr(signal, "payload", {}) or {}
    if not isinstance(payload, Mapping):
        return None
    ai_audit = payload.get("ai_audit")
    if not isinstance(ai_audit, Mapping) or not _as_bool(ai_audit.get("enabled"), default=False):
        return None
    status = _normalize_strategy_plugin_field(_optional_string(ai_audit.get("status")))
    if status == "ok":
        verdict = _optional_string(ai_audit.get("verdict")) or "unknown"
        assessment = _optional_string(ai_audit.get("route_assessment")) or "unknown"
        summary = _optional_string(ai_audit.get("summary")) or "no summary"
        return _translate(
            translator,
            "strategy_plugin_alert_ai_audit",
            fallback="AI audit: {status} | verdict={verdict} | assessment={assessment} | {summary}",
            status=status,
            verdict=verdict,
            assessment=assessment,
            summary=summary,
        )
    reason = _optional_string(ai_audit.get("skip_reason")) or _optional_string(ai_audit.get("error")) or "no detail"
    return _translate(
        translator,
        "strategy_plugin_alert_ai_audit_status",
        fallback="AI audit: {status} | {reason}",
        status=status,
        reason=reason,
    )


def build_strategy_plugin_alert_key(
    signal: StrategyPluginSignal,
    *,
    strategy_label: str | None = None,
    context_label: str | None = None,
    namespace: str = "strategy_plugin_alert",
) -> str:
    payload = {
        "namespace": _optional_key_part(namespace) or "strategy_plugin_alert",
        "context": _optional_key_part(context_label) or "default",
        "strategy": _optional_key_part(getattr(signal, "strategy", None)) or _optional_key_part(strategy_label) or "unknown",
        "plugin": _optional_key_part(getattr(signal, "plugin", None)) or "unknown",
        "mode": _optional_key_part(getattr(signal, "effective_mode", None)) or "unknown",
        "as_of": _optional_key_part(getattr(signal, "as_of", None)) or "unknown",
        "route": _optional_key_part(getattr(signal, "canonical_route", None)) or "unknown",
        "action": _optional_key_part(getattr(signal, "suggested_action", None)) or "unknown",
        "would_trade_if_enabled": bool(getattr(signal, "would_trade_if_enabled", False)),
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return "/".join(
        (
            _sanitize_key_part(payload["namespace"]),
            _sanitize_key_part(payload["context"]),
            _sanitize_key_part(payload["strategy"]),
            _sanitize_key_part(payload["plugin"]),
            _sanitize_key_part(payload["as_of"]),
            _sanitize_key_part(payload["route"]),
            _sanitize_key_part(payload["action"]),
            digest,
        )
    )


def build_strategy_plugin_alert_messages(
    signals: Sequence[StrategyPluginSignal],
    *,
    translator: Callable[..., str] | None = None,
    strategy_label: str | None = None,
    context_label: str | None = None,
    alert_namespace: str = "strategy_plugin_alert",
) -> tuple[StrategyPluginAlertMessage, ...]:
    messages: list[StrategyPluginAlertMessage] = []
    context = str(context_label or "").strip()
    for signal in signals:
        if not should_alert_strategy_plugin_signal(signal):
            continue
        route = getattr(signal, "canonical_route", None) or "unknown_route"
        action = getattr(signal, "suggested_action", None) or "unknown_action"
        plugin = translate_strategy_plugin_value("name", getattr(signal, "plugin", None), translator=translator)
        translated_mode = translate_strategy_plugin_value(
            "mode",
            getattr(signal, "effective_mode", None),
            translator=translator,
        )
        translated_route = translate_strategy_plugin_value("route", route, translator=translator)
        translated_action = translate_strategy_plugin_value("action", action, translator=translator)
        strategy = str(strategy_label or getattr(signal, "strategy", None) or "").strip() or "unknown"
        guidance = build_strategy_plugin_alert_guidance(signal, translator=translator)
        scope_note = build_strategy_plugin_alert_scope_note(signal, translator=translator)
        ai_audit_note = build_strategy_plugin_ai_audit_note(signal, translator=translator)
        subject = _translate(
            translator,
            "strategy_plugin_alert_subject",
            fallback="Strategy plugin alert: {plugin} | {route}",
            strategy=strategy,
            plugin=plugin,
            route=translated_route,
        )
        if context:
            subject = f"[{context}] {subject}"
        body_lines = [
            _translate(translator, "strategy_plugin_alert_title", fallback="Strategy Plugin Alert"),
            "",
        ]
        if context:
            body_lines.append(
                _translate(
                    translator,
                    "strategy_plugin_alert_context",
                    fallback="Context: {context}",
                    context=context,
                )
            )
        body_lines.extend(
            [
                _translate(
                    translator,
                    "strategy_plugin_alert_strategy",
                    fallback="Strategy: {strategy}",
                    strategy=strategy,
                ),
                _translate(
                    translator,
                    "strategy_plugin_alert_plugin",
                    fallback="Plugin: {plugin}",
                    plugin=plugin,
                ),
                _translate(
                    translator,
                    "strategy_plugin_alert_status",
                    fallback="Status: {route}",
                    route=translated_route,
                ),
                _translate(
                    translator,
                    "strategy_plugin_alert_action",
                    fallback="Notice: {action}",
                    action=translated_action,
                ),
                _translate(
                    translator,
                    "strategy_plugin_alert_mode",
                    fallback="Mode: {mode}",
                    mode=translated_mode,
                ),
                _translate(
                    translator,
                    "strategy_plugin_alert_as_of",
                    fallback="Signal as-of: {as_of}",
                    as_of=getattr(signal, "as_of", None) or "unknown",
                ),
            ]
        )
        if guidance:
            body_lines.append(
                _translate(
                    translator,
                    "strategy_plugin_alert_guidance",
                    fallback="Manual guidance: {guidance}",
                    guidance=guidance,
                )
            )
        if ai_audit_note:
            body_lines.append(ai_audit_note)
        if scope_note:
            body_lines.append(
                _translate(
                    translator,
                    "strategy_plugin_alert_scope_note",
                    fallback="Scope: {scope_note}",
                    scope_note=scope_note,
                )
            )
        metadata = {
            "strategy": getattr(signal, "strategy", None),
            "strategy_label": strategy,
            "plugin": getattr(signal, "plugin", None),
            "mode": getattr(signal, "effective_mode", None),
            "as_of": getattr(signal, "as_of", None),
            "canonical_route": getattr(signal, "canonical_route", None),
            "suggested_action": getattr(signal, "suggested_action", None),
            "would_trade_if_enabled": bool(getattr(signal, "would_trade_if_enabled", False)),
            "context_label": context or None,
            "guidance": guidance,
            "scope_note": scope_note,
            "ai_audit": getattr(signal, "payload", {}).get("ai_audit")
            if isinstance(getattr(signal, "payload", {}), Mapping)
            else None,
        }
        messages.append(
            StrategyPluginAlertMessage(
                subject=subject,
                body="\n".join(body_lines),
                alert_key=build_strategy_plugin_alert_key(
                    signal,
                    strategy_label=strategy,
                    context_label=context,
                    namespace=alert_namespace,
                ),
                metadata=metadata,
            )
        )
    return tuple(messages)


def _optional_key_part(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sanitize_key_part(value: Any) -> str:
    text = str(value or "").strip().lower()
    chars: list[str] = []
    previous_dash = False
    for char in text:
        if char.isalnum() or char in {"_", "."}:
            chars.append(char)
            previous_dash = False
        elif not previous_dash:
            chars.append("-")
            previous_dash = True
    sanitized = "".join(chars).strip("-._")
    return sanitized[:80] or "unknown"


def _materialize_artifact_path(reference: str, *, client_factory: Any = None) -> tuple[Path, dict[str, str | None]]:
    raw_reference = _required_string(reference, field_name="reference")
    if not raw_reference.startswith("gs://"):
        return Path(raw_reference).expanduser(), {"source_uri": None, "local_path": raw_reference}

    local_path = _cache_path_for_remote_artifact(raw_reference)
    _download_gcs_object(raw_reference, local_path, client_factory=client_factory)
    return local_path, {"source_uri": raw_reference, "local_path": str(local_path)}


def _download_gcs_object(uri: str, destination: Path, *, client_factory: Any = None) -> None:
    if client_factory is None:
        try:
            from google.cloud import storage  # type: ignore
        except ImportError as exc:
            raise RuntimeError("google-cloud-storage is required for GCS strategy plugin artifacts") from exc
        client_factory = storage.Client
    bucket_name, object_name = _parse_gcs_uri(uri)
    destination.parent.mkdir(parents=True, exist_ok=True)
    client = client_factory()
    client.bucket(bucket_name).blob(object_name).download_to_filename(str(destination))


def _parse_gcs_uri(uri: str) -> tuple[str, str]:
    raw_uri = str(uri or "").strip()
    if not raw_uri.startswith("gs://"):
        raise ValueError(f"Unsupported GCS URI: {raw_uri}")
    bucket_name, _, object_name = raw_uri[5:].partition("/")
    if not bucket_name or not object_name:
        raise ValueError(f"Invalid GCS URI: {raw_uri}")
    return bucket_name, object_name


def _cache_path_for_remote_artifact(reference: str) -> Path:
    digest = hashlib.sha256(reference.encode("utf-8")).hexdigest()[:16]
    leaf_name = Path(reference).name or "latest_signal.json"
    return DEFAULT_PLUGIN_ARTIFACT_CACHE_DIR / digest / leaf_name


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_strategy_plugin_field(value: str | None) -> str:
    return str(value or "").strip().lower() or "unknown"


def _translate(
    translator: Callable[..., str] | None,
    key: str,
    *,
    fallback: str,
    **kwargs: Any,
) -> str:
    if translator is None:
        return fallback.format(**kwargs)
    translated = translator(key, **kwargs)
    return translated if translated != key else fallback.format(**kwargs)


def _translate_first(
    translator: Callable[..., str] | None,
    keys: Sequence[str],
) -> str | None:
    if translator is None:
        return None
    for key in keys:
        translated = translator(key)
        if translated != key:
            text = str(translated).strip()
            if text:
                return text
    return None


def _required_string(value: Any, *, field_name: str) -> str:
    text = _optional_string(value)
    if text is None:
        raise ValueError(f"{field_name} is required")
    return text
