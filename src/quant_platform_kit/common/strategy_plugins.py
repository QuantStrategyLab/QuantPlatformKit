"""Shared runtime helpers for sidecar strategy plugin artifacts."""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

PLUGIN_MODE_SHADOW = "shadow"
SUPPORTED_STRATEGY_PLUGIN_MODES = frozenset({PLUGIN_MODE_SHADOW})
DEFAULT_PLUGIN_ARTIFACT_CACHE_DIR = Path(tempfile.gettempdir()) / "quant_strategy_plugin_artifacts"
STRATEGY_PLUGIN_NON_ALERT_ROUTES = frozenset({"no_action"})
STRATEGY_PLUGIN_ALERT_ACTIONS = frozenset({"defend", "blocked"})


@dataclass(frozen=True)
class StrategyPluginMountConfig:
    strategy: str
    plugin: str
    signal_path: str
    enabled: bool = True
    expected_mode: str | None = None


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

    def report_summary(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "plugin": self.plugin,
            "mode": self.mode,
            "configured_mode": self.configured_mode,
            "effective_mode": self.effective_mode,
            "schema_version": self.schema_version,
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


def normalize_strategy_plugin_mode(value: Any, *, field_name: str = "mode") -> str:
    mode = str(value or "").strip().lower()
    if mode not in SUPPORTED_STRATEGY_PLUGIN_MODES:
        modes = ", ".join(sorted(SUPPORTED_STRATEGY_PLUGIN_MODES))
        raise ValueError(f"{field_name} must be one of {modes}; got {value!r}")
    return mode


def parse_strategy_plugin_mounts(
    raw_config: str | Sequence[Mapping[str, Any]] | Mapping[str, Any] | None,
) -> tuple[StrategyPluginMountConfig, ...]:
    if raw_config is None or raw_config == "":
        return ()
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
        mounts.append(
            StrategyPluginMountConfig(
                strategy=strategy,
                plugin=plugin,
                signal_path=signal_path,
                enabled=_as_bool(item.get("enabled"), default=True),
                expected_mode=(
                    normalize_strategy_plugin_mode(expected_mode, field_name="expected_mode")
                    if expected_mode is not None
                    else None
                ),
            )
        )
    return tuple(mounts)


def load_configured_strategy_plugin_signals(
    mounts: Sequence[StrategyPluginMountConfig],
    *,
    strategy_profile: str | None = None,
    client_factory: Any = None,
) -> tuple[StrategyPluginSignal, ...]:
    selected_strategy = _optional_string(strategy_profile)
    signals: list[StrategyPluginSignal] = []
    for mount in mounts:
        if not mount.enabled:
            continue
        if selected_strategy is not None and mount.strategy != selected_strategy:
            continue
        signals.append(
            load_strategy_plugin_signal(
                mount.signal_path,
                expected_strategy=mount.strategy,
                expected_plugin=mount.plugin,
                expected_mode=mount.expected_mode,
                client_factory=client_factory,
            )
        )
    return tuple(signals)


def load_strategy_plugin_signal(
    reference: str,
    *,
    expected_strategy: str | None = None,
    expected_plugin: str | None = None,
    expected_mode: str | None = None,
    client_factory: Any = None,
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
        source_uri=metadata.get("source_uri"),
        local_path=str(local_path),
    )


def validate_strategy_plugin_signal_payload(
    payload: Mapping[str, Any],
    *,
    expected_strategy: str | None = None,
    expected_plugin: str | None = None,
    expected_mode: str | None = None,
    source_uri: str | None = None,
    local_path: str | None = None,
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

    execution_controls = payload.get("execution_controls") or {}
    if not isinstance(execution_controls, Mapping):
        raise ValueError("strategy plugin signal execution_controls must be an object")

    return StrategyPluginSignal(
        strategy=strategy,
        plugin=plugin,
        mode=mode,
        configured_mode=configured_mode,
        effective_mode=effective_mode,
        schema_version=_optional_string(payload.get("schema_version")) or "",
        as_of=_optional_string(payload.get("as_of")) or "",
        canonical_route=_optional_string(payload.get("canonical_route")),
        suggested_action=_optional_string(payload.get("suggested_action")),
        would_trade_if_enabled=_as_bool(payload.get("would_trade_if_enabled"), default=False),
        execution_controls=execution_controls,
        payload=dict(payload),
        source_uri=_optional_string(source_uri),
        local_path=_optional_string(local_path),
    )


def build_strategy_plugin_report_payload(signals: Sequence[StrategyPluginSignal]) -> dict[str, Any]:
    return {
        "strategy_plugins": [signal.report_summary() for signal in signals],
    }


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


def build_strategy_plugin_notification_lines(
    signals: Sequence[StrategyPluginSignal],
    *,
    translator: Callable[..., str] | None = None,
) -> tuple[str, ...]:
    lines: list[str] = []
    for signal in signals:
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


def build_strategy_plugin_alert_messages(
    signals: Sequence[StrategyPluginSignal],
    *,
    translator: Callable[..., str] | None = None,
    strategy_label: str | None = None,
) -> tuple[StrategyPluginAlertMessage, ...]:
    messages: list[StrategyPluginAlertMessage] = []
    for signal in signals:
        if not should_alert_strategy_plugin_signal(signal):
            continue
        route = getattr(signal, "canonical_route", None) or "unknown_route"
        action = getattr(signal, "suggested_action", None) or "unknown_action"
        plugin = translate_strategy_plugin_value("name", getattr(signal, "plugin", None), translator=translator)
        translated_route = translate_strategy_plugin_value("route", route, translator=translator)
        translated_action = translate_strategy_plugin_value("action", action, translator=translator)
        strategy = str(strategy_label or getattr(signal, "strategy", None) or "").strip() or "unknown"
        subject = _translate(
            translator,
            "strategy_plugin_alert_subject",
            fallback="Strategy plugin alert: {plugin} | {route}",
            strategy=strategy,
            plugin=plugin,
            route=translated_route,
        )
        body_lines = [
            _translate(translator, "strategy_plugin_alert_title", fallback="Strategy Plugin Alert"),
            _translate(
                translator,
                "strategy_plugin_line",
                fallback="Plugin: {plugin} | status: {route} | notice: {action}",
                plugin=plugin,
                mode=translate_strategy_plugin_value("mode", getattr(signal, "effective_mode", None), translator=translator),
                route=translated_route,
                action=translated_action,
            ),
            _translate(
                translator,
                "strategy_plugin_alert_strategy",
                fallback="Strategy: {strategy}",
                strategy=strategy,
            ),
            _translate(
                translator,
                "strategy_plugin_alert_as_of",
                fallback="Signal as-of: {as_of}",
                as_of=getattr(signal, "as_of", None) or "unknown",
            ),
            _translate(
                translator,
                "strategy_plugin_alert_would_trade",
                fallback="Would trade if enabled: {value}",
                value=str(bool(getattr(signal, "would_trade_if_enabled", False))).lower(),
            ),
        ]
        source = getattr(signal, "source_uri", None) or getattr(signal, "local_path", None)
        if source:
            body_lines.append(
                _translate(
                    translator,
                    "strategy_plugin_alert_source",
                    fallback="Source: {source}",
                    source=source,
                )
            )
        messages.append(StrategyPluginAlertMessage(subject=subject, body="\n".join(body_lines)))
    return tuple(messages)


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


def _required_string(value: Any, *, field_name: str) -> str:
    text = _optional_string(value)
    if text is None:
        raise ValueError(f"{field_name} is required")
    return text
