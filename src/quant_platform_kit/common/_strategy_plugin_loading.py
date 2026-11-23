"""Config parsers, payload validators, and artifact loaders for strategy plugins."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import replace as dataclass_replace
from typing import Any

from quant_platform_kit.common._strategy_plugin_helpers import (
    _as_bool,
    _materialize_artifact_path,
    _optional_string,
    _required_string,
)
from quant_platform_kit.common._strategy_plugin_models import (
    STRATEGY_PLUGIN_NOTIFICATION_TARGETS,
    StrategyPluginDefinition,
    StrategyPluginMountConfig,
    StrategyPluginNotificationTargetConfig,
    StrategyPluginSignal,
    normalize_strategy_plugin_definitions,
    normalize_strategy_plugin_mode,
)

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


def validate_strategy_plugin_notification_target(
    *,
    notification_target: str,
    plugin: str,
    source: str = "plugin",
) -> None:
    target_name = _required_string(notification_target, field_name="notification_target")
    plugin_name = _required_string(plugin, field_name="plugin")
    allowed_targets = STRATEGY_PLUGIN_NOTIFICATION_TARGETS.get(plugin_name, frozenset())
    if target_name not in allowed_targets:
        allowed = ", ".join(sorted(allowed_targets)) or "(none)"
        raise ValueError(
            f"strategy plugin {plugin_name} does not support notification target {target_name} "
            f"in {source}; supported notification targets: {allowed}"
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


def parse_strategy_plugin_notification_targets(
    raw_config: str | Sequence[Mapping[str, Any]] | Mapping[str, Any] | None,
    *,
    plugin_definitions: Mapping[str, StrategyPluginDefinition] | Sequence[StrategyPluginDefinition] | None = None,
) -> tuple[StrategyPluginNotificationTargetConfig, ...]:
    if raw_config is None or raw_config == "":
        return ()
    definitions = normalize_strategy_plugin_definitions(plugin_definitions)
    payload: Any
    if isinstance(raw_config, str):
        payload = json.loads(raw_config)
    else:
        payload = raw_config

    if isinstance(payload, Mapping):
        payload = payload.get("notification_targets", ())
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("strategy plugin notification target config must be a JSON list or object with notification_targets")

    targets: list[StrategyPluginNotificationTargetConfig] = []
    seen: set[tuple[str, str]] = set()
    for item in payload:
        if not isinstance(item, Mapping):
            raise ValueError("each strategy plugin notification target must be an object")
        if "mode" in item:
            raise ValueError("notification target config must not set mode; read mode from the plugin artifact")
        notification_target = _required_string(item.get("notification_target"), field_name="notification_target")
        plugin = _required_string(item.get("plugin"), field_name="plugin")
        signal_path = _required_string(
            item.get("signal_path") or item.get("latest_signal_path") or item.get("path"),
            field_name="signal_path",
        )
        key = (notification_target, plugin)
        if key in seen:
            raise ValueError(
                f"duplicate strategy plugin notification target: notification_target={notification_target} plugin={plugin}"
            )
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
            source="notification_target",
        )
        validate_strategy_plugin_notification_target(
            notification_target=notification_target,
            plugin=plugin,
            source="notification_target",
        )
        targets.append(
            StrategyPluginNotificationTargetConfig(
                notification_target=notification_target,
                plugin=plugin,
                signal_path=signal_path,
                enabled=_as_bool(item.get("enabled"), default=True),
                expected_mode=normalized_expected_mode,
                expected_schema_version=expected_schema_version,
            )
        )
    return tuple(targets)


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


def load_configured_strategy_plugin_notification_target_signals(
    targets: Sequence[StrategyPluginNotificationTargetConfig],
    *,
    notification_target: str | None = None,
    client_factory: Any = None,
    plugin_definitions: Mapping[str, StrategyPluginDefinition] | Sequence[StrategyPluginDefinition] | None = None,
) -> tuple[StrategyPluginSignal, ...]:
    selected_target = _optional_string(notification_target)
    definitions = normalize_strategy_plugin_definitions(plugin_definitions)
    signals: list[StrategyPluginSignal] = []
    for target in targets:
        if not target.enabled:
            continue
        if selected_target is not None and target.notification_target != selected_target:
            continue
        validate_strategy_plugin_notification_target(
            notification_target=target.notification_target,
            plugin=target.plugin,
            source="notification_target",
        )
        signals.append(
            load_strategy_plugin_signal(
                target.signal_path,
                expected_notification_target=target.notification_target,
                expected_plugin=target.plugin,
                expected_mode=target.expected_mode,
                expected_schema_version=target.expected_schema_version,
                client_factory=client_factory,
                plugin_definitions=definitions,
            )
        )
    return tuple(signals)


def load_strategy_plugin_signal(
    reference: str,
    *,
    expected_strategy: str | None = None,
    expected_notification_target: str | None = None,
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
        expected_notification_target=expected_notification_target,
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
    expected_notification_target: str | None = None,
    expected_plugin: str | None = None,
    expected_mode: str | None = None,
    expected_schema_version: str | None = None,
    source_uri: str | None = None,
    local_path: str | None = None,
    plugin_definitions: Mapping[str, StrategyPluginDefinition] | Sequence[StrategyPluginDefinition] | None = None,
) -> StrategyPluginSignal:
    target_type = _optional_string(payload.get("target_type")) or (
        "notification_target" if _optional_string(payload.get("notification_target")) else "strategy"
    )
    if target_type not in {"strategy", "notification_target"}:
        raise ValueError(f"strategy plugin signal target_type must be strategy or notification_target; got {target_type!r}")
    if target_type == "notification_target":
        notification_target = _required_string(payload.get("notification_target"), field_name="notification_target")
        strategy = _optional_string(payload.get("strategy")) or ""
    else:
        strategy = _required_string(payload.get("strategy"), field_name="strategy")
        notification_target = _optional_string(payload.get("notification_target")) or ""
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
    expected_notification_target = _optional_string(expected_notification_target)
    expected_plugin = _optional_string(expected_plugin)
    if expected_strategy is not None and target_type != "strategy":
        raise ValueError(
            "strategy plugin artifact target mismatch: "
            f"expected strategy {expected_strategy}, got notification target {notification_target}"
        )
    if expected_strategy is not None and strategy != expected_strategy:
        raise ValueError(f"strategy plugin artifact strategy mismatch: expected {expected_strategy}, got {strategy}")
    if expected_notification_target is not None and target_type != "notification_target":
        raise ValueError(
            "strategy plugin artifact target mismatch: "
            f"expected notification target {expected_notification_target}, got strategy {strategy}"
        )
    if expected_notification_target is not None and notification_target != expected_notification_target:
        raise ValueError(
            "strategy plugin artifact notification_target mismatch: "
            f"expected {expected_notification_target}, got {notification_target}"
        )
    if expected_plugin is not None and plugin != expected_plugin:
        raise ValueError(f"strategy plugin artifact plugin mismatch: expected {expected_plugin}, got {plugin}")
    if expected_mode is not None:
        normalized_expected_mode = normalize_strategy_plugin_mode(expected_mode, field_name="expected_mode")
        if effective_mode != normalized_expected_mode:
            raise ValueError(
                "strategy plugin artifact mode mismatch: "
                f"expected {normalized_expected_mode}, got {effective_mode}"
            )
    if target_type == "strategy":
        validate_strategy_plugin_compatibility(
            strategy=strategy,
            plugin=plugin,
            mode=effective_mode,
            plugin_definitions=plugin_definitions,
            source="artifact",
        )
    else:
        validate_strategy_plugin_notification_target(
            notification_target=notification_target,
            plugin=plugin,
            source="artifact",
        )
    schema_version = _optional_string(payload.get("schema_version")) or ""
    definitions = normalize_strategy_plugin_definitions(plugin_definitions)
    definition = definitions.get(plugin)
    if definition is not None and definition.supported_schema_versions and not schema_version:
        raise ValueError(f"strategy plugin {plugin} artifact schema_version is required")
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
        target_type=target_type,
        notification_target=notification_target,
    )


def _coerce_strategy_plugin_signal(signal: Any) -> StrategyPluginSignal:
    """Normalize a StrategyPluginSignal, Mapping, or duck-typed object at public boundaries."""
    if isinstance(signal, StrategyPluginSignal):
        return signal
    if isinstance(signal, Mapping):
        def _read(key: str, default: Any = None) -> Any:
            return signal.get(key, default)
    else:
        def _read(key: str, default: Any = None) -> Any:
            return getattr(signal, key, default)
    effective_mode = _optional_string(_read("effective_mode")) or ""
    mode = _optional_string(_read("mode")) or effective_mode
    configured_mode = _optional_string(_read("configured_mode")) or mode
    return StrategyPluginSignal(
        strategy=_read("strategy") or "",
        plugin=_read("plugin") or "",
        mode=mode,
        configured_mode=configured_mode,
        effective_mode=effective_mode or mode,
        schema_version=_read("schema_version") or "",
        as_of=_read("as_of") or "",
        canonical_route=_read("canonical_route"),
        suggested_action=_read("suggested_action"),
        would_trade_if_enabled=_as_bool(_read("would_trade_if_enabled", False), default=False),
        execution_controls=_read("execution_controls") or {},
        payload=_read("payload") or {},
        source_uri=_read("source_uri"),
        local_path=_read("local_path"),
        deprecated_plugin=bool(_read("deprecated_plugin", False)),
        successor_plugin=_read("successor_plugin"),
        supported_schema_versions=_read("supported_schema_versions") or (),
        target_type=_read("target_type") or "strategy",
        notification_target=_read("notification_target") or "",
        enabled=_as_bool(_read("enabled", True), default=True),
    )


def build_strategy_plugin_report_payload(
    signals: Sequence[StrategyPluginSignal | Any],
) -> dict[str, Any]:
    summaries: list[dict[str, Any]] = []
    for raw_signal in signals:
        if isinstance(raw_signal, StrategyPluginSignal):
            summaries.append(raw_signal.report_summary())
        elif not isinstance(raw_signal, Mapping) and callable(getattr(raw_signal, "report_summary", None)):
            summaries.append(raw_signal.report_summary())
        else:
            summaries.append(_coerce_strategy_plugin_signal(raw_signal).report_summary())
    return {
        "strategy_plugins": summaries,
    }


def build_strategy_plugin_metadata(
    signals: Sequence[StrategyPluginSignal | Any],
) -> dict[str, Any]:
    """Build portfolio-snapshot metadata consumed by deterministic strategies."""
    plugin_payloads: dict[str, Any] = {}
    summaries: dict[str, Any] = {}
    for raw_signal in signals:
        signal = _coerce_strategy_plugin_signal(raw_signal)
        if not _as_bool(
            signal.execution_controls.get("strategy_runtime_metadata_allowed"),
            default=False,
        ):
            continue
        if not signal.plugin:
            continue
        plugin_payloads[signal.plugin] = _build_non_authoritative_runtime_plugin_payload(signal.payload)
        custom_summary = (
            getattr(raw_signal, "report_summary", None)
            if not isinstance(raw_signal, (StrategyPluginSignal, Mapping))
            else None
        )
        summaries[signal.plugin] = custom_summary() if callable(custom_summary) else signal.report_summary()
    if not plugin_payloads:
        return {}
    metadata: dict[str, Any] = {
        "strategy_plugins": plugin_payloads,
        "strategy_plugin_summaries": summaries,
    }
    metadata.update(plugin_payloads)
    return metadata


def _build_non_authoritative_runtime_plugin_payload(payload: Mapping[str, Any] | object) -> dict[str, Any]:
    """Copy a sidecar payload for strategy metadata without delegation rights.

    The V2 plugin contract permits strategy metadata for deterministic
    observability and research. It does not permit a plugin artifact to grant
    itself allocation or broker authority. Preserve the original artifact on
    ``StrategyPluginSignal.payload`` for audit, while making this injected copy
    explicitly non-authoritative for every strategy consumer.
    """

    if not isinstance(payload, Mapping):
        return {"strategy_runtime_metadata_non_authoritative": True}
    normalized = dict(payload)
    for control_key in ("execution_controls", "consumption_policy"):
        source = payload.get(control_key)
        if not isinstance(source, Mapping):
            continue
        controls = dict(source)
        controls.update(
            {
                "broker_order_allowed": False,
                "live_allocation_mutation_allowed": False,
                "repository_broker_write_allowed": False,
                "repository_allocation_mutation_allowed": False,
                "position_control_allowed": False,
                "consumption_evidence_status": "shadow_only",
            }
        )
        normalized[control_key] = controls
    normalized["strategy_runtime_metadata_non_authoritative"] = True
    return normalized


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

