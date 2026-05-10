"""Shared domain models, ports, strategy contracts, and plugin helpers."""

from .notification_localization import (
    COMMON_ZH_NOTIFICATION_REPLACEMENTS,
    localize_notification_text,
    translator_uses_zh,
)
from .runtime_logging import (
    RuntimeLogContext,
    build_run_id,
    emit_runtime_log,
    extract_cloud_trace,
)
from .runtime_assembly import RuntimeAssembly, build_runtime_assembly
from .runtime_target import (
    build_runtime_context_fields,
    RuntimeTarget,
    ResolvedRuntimeIdentity,
    build_runtime_target,
    resolve_runtime_identity_from_env,
    resolve_runtime_target_from_env,
    resolve_runtime_target_strategy_profile_from_env,
)
from .strategy_plugins import (
    PLUGIN_MODE_SHADOW,
    SUPPORTED_STRATEGY_PLUGIN_MODES,
    StrategyPluginMountConfig,
    StrategyPluginSignal,
    build_strategy_plugin_report_payload,
    load_configured_strategy_plugin_signals,
    load_strategy_plugin_signal,
    normalize_strategy_plugin_mode,
    parse_strategy_plugin_mounts,
    validate_strategy_plugin_signal_payload,
)

__all__ = [
    "COMMON_ZH_NOTIFICATION_REPLACEMENTS",
    "PLUGIN_MODE_SHADOW",
    "SUPPORTED_STRATEGY_PLUGIN_MODES",
    "localize_notification_text",
    "RuntimeTarget",
    "ResolvedRuntimeIdentity",
    "build_runtime_context_fields",
    "build_run_id",
    "emit_runtime_log",
    "extract_cloud_trace",
    "RuntimeLogContext",
    "RuntimeAssembly",
    "build_runtime_assembly",
    "StrategyPluginMountConfig",
    "StrategyPluginSignal",
    "build_strategy_plugin_report_payload",
    "build_runtime_target",
    "load_configured_strategy_plugin_signals",
    "load_strategy_plugin_signal",
    "normalize_strategy_plugin_mode",
    "parse_strategy_plugin_mounts",
    "resolve_runtime_identity_from_env",
    "resolve_runtime_target_from_env",
    "resolve_runtime_target_strategy_profile_from_env",
    "translator_uses_zh",
    "validate_strategy_plugin_signal_payload",
]
