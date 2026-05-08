from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from .feature_snapshot import load_feature_snapshot_guarded
from .strategy_contracts import (
    StrategyContext,
    StrategyDecision,
    StrategyEntrypoint,
    StrategyRuntimeAdapter,
    apply_runtime_policy_to_runtime_config,
    build_strategy_context_from_available_inputs,
)


FEATURE_SNAPSHOT_INPUT = "feature_snapshot"


@dataclass(frozen=True)
class FeatureSnapshotRuntimeSettings:
    feature_snapshot_path: str | None
    feature_snapshot_manifest_path: str | None = None
    strategy_config_path: str | None = None
    strategy_config_source: str | None = None
    dry_run_only: bool = False


@dataclass(frozen=True)
class FeatureSnapshotContextRequest:
    entrypoint: StrategyEntrypoint
    runtime_adapter: StrategyRuntimeAdapter
    as_of: Any
    available_inputs: Mapping[str, Any]
    runtime_config: Mapping[str, Any]


@dataclass(frozen=True)
class FeatureSnapshotEvaluationResult:
    decision: StrategyDecision
    metadata: Mapping[str, Any] = field(default_factory=dict)


ContextBuilder = Callable[[FeatureSnapshotContextRequest], StrategyContext]
SnapshotLoader = Callable[..., Any]


def default_feature_snapshot_context_builder(
    request: FeatureSnapshotContextRequest,
) -> StrategyContext:
    return build_strategy_context_from_available_inputs(
        entrypoint=request.entrypoint,
        runtime_adapter=request.runtime_adapter,
        as_of=request.as_of,
        available_inputs=request.available_inputs,
        runtime_config=request.runtime_config,
    )


def evaluate_feature_snapshot_strategy(
    *,
    entrypoint: StrategyEntrypoint,
    runtime_adapter: StrategyRuntimeAdapter,
    runtime_settings: FeatureSnapshotRuntimeSettings,
    runtime_config: Mapping[str, Any],
    merged_runtime_config: Mapping[str, Any],
    available_inputs: Mapping[str, Any] | None = None,
    as_of: Any | None = None,
    base_managed_symbols: tuple[str, ...] = (),
    status_icon: str | None = None,
    include_strategy_display_name: bool = False,
    include_safe_haven_metadata: bool = True,
    set_run_as_of: bool = False,
    default_benchmark_symbol: str = "QQQ",
    default_safe_haven_symbol: str | None = "BOXX",
    build_available_inputs: Callable[[Any], Mapping[str, Any]] | None = None,
    context_builder: ContextBuilder = default_feature_snapshot_context_builder,
    snapshot_loader: SnapshotLoader = load_feature_snapshot_guarded,
    on_guard_metadata: Callable[[Mapping[str, Any]], None] | None = None,
    extra_success_metadata: Callable[
        [Any, tuple[str, ...], StrategyDecision],
        Mapping[str, Any],
    ]
    | None = None,
    catch_evaluation_errors: bool = False,
) -> FeatureSnapshotEvaluationResult:
    profile = entrypoint.manifest.profile
    evaluation_as_of = as_of if as_of is not None else datetime.now(timezone.utc)
    runtime_config = dict(runtime_config)
    run_as_of = runtime_config.get("run_as_of", evaluation_as_of)
    if getattr(run_as_of, "tzinfo", None) is not None:
        run_as_of = run_as_of.replace(tzinfo=None)
    if set_run_as_of:
        runtime_config.setdefault("run_as_of", run_as_of)
    _apply_runtime_policy(runtime_config, runtime_adapter)

    runtime_config_name = str(
        merged_runtime_config.get("runtime_config_name") or profile
    )
    runtime_config_path = (
        merged_runtime_config.get("runtime_config_path")
        or runtime_settings.strategy_config_path
    )
    runtime_config_source = (
        merged_runtime_config.get("runtime_config_source")
        or runtime_settings.strategy_config_source
    )
    benchmark_symbol = _resolve_symbol(
        merged_runtime_config.get("benchmark_symbol"),
        default=default_benchmark_symbol,
    )
    safe_haven_symbol = _resolve_symbol(
        merged_runtime_config.get("safe_haven"),
        default=default_safe_haven_symbol,
    )

    if not runtime_settings.feature_snapshot_path:
        return _fail_closed_result(
            profile=profile,
            display_name=entrypoint.manifest.display_name,
            include_strategy_display_name=include_strategy_display_name,
            feature_snapshot_path=None,
            runtime_config_path=runtime_config_path,
            runtime_config_source=runtime_config_source,
            dry_run_only=runtime_settings.dry_run_only,
            managed_symbols=base_managed_symbols,
            safe_haven_symbol=safe_haven_symbol,
            include_safe_haven_metadata=include_safe_haven_metadata,
            signal_description="feature snapshot required",
            decision_text="fail_closed",
            reason="feature_snapshot_path_missing",
            metadata={
                "snapshot_guard_decision": "fail_closed",
                "fail_reason": "feature_snapshot_path_missing",
            },
        )

    guard_result = snapshot_loader(
        runtime_settings.feature_snapshot_path,
        run_as_of=run_as_of,
        required_columns=runtime_adapter.required_feature_columns,
        snapshot_date_columns=tuple(runtime_adapter.snapshot_date_columns),
        max_snapshot_month_lag=int(runtime_adapter.max_snapshot_month_lag),
        manifest_path=runtime_settings.feature_snapshot_manifest_path,
        require_manifest=bool(runtime_adapter.require_snapshot_manifest),
        expected_strategy_profile=profile,
        expected_config_name=runtime_config_name,
        expected_config_path=runtime_config_path,
        expected_contract_version=runtime_adapter.snapshot_contract_version,
    )
    guard_metadata = dict(guard_result.metadata)
    if on_guard_metadata is not None:
        on_guard_metadata(guard_metadata)

    if guard_metadata.get("snapshot_guard_decision") != "proceed":
        decision_text = str(guard_metadata.get("snapshot_guard_decision") or "fail_closed")
        reason = guard_metadata.get("fail_reason") or guard_metadata.get("no_op_reason")
        return _fail_closed_result(
            profile=profile,
            display_name=entrypoint.manifest.display_name,
            include_strategy_display_name=include_strategy_display_name,
            feature_snapshot_path=runtime_settings.feature_snapshot_path,
            runtime_config_path=runtime_config_path,
            runtime_config_source=runtime_config_source,
            dry_run_only=runtime_settings.dry_run_only,
            managed_symbols=base_managed_symbols,
            safe_haven_symbol=safe_haven_symbol,
            include_safe_haven_metadata=include_safe_haven_metadata,
            signal_description="feature snapshot guard blocked execution",
            decision_text=decision_text,
            reason=reason,
            metadata=guard_metadata,
        )

    feature_snapshot = guard_result.frame
    evaluation_inputs = dict(available_inputs or {})
    if build_available_inputs is None:
        evaluation_inputs[FEATURE_SNAPSHOT_INPUT] = feature_snapshot
    else:
        evaluation_inputs.update(build_available_inputs(feature_snapshot))

    ctx = context_builder(
        FeatureSnapshotContextRequest(
            entrypoint=entrypoint,
            runtime_adapter=runtime_adapter,
            as_of=evaluation_as_of,
            available_inputs=evaluation_inputs,
            runtime_config=runtime_config,
        )
    )
    try:
        decision = entrypoint.evaluate(ctx)
    except Exception as exc:
        if not catch_evaluation_errors:
            raise
        fail_reason = f"feature_snapshot_compute_failed:{type(exc).__name__}:{exc}"
        metadata = {
            **guard_metadata,
            "snapshot_guard_decision": "fail_closed",
            "fail_reason": fail_reason,
        }
        return _fail_closed_result(
            profile=profile,
            display_name=entrypoint.manifest.display_name,
            include_strategy_display_name=include_strategy_display_name,
            feature_snapshot_path=runtime_settings.feature_snapshot_path,
            runtime_config_path=runtime_config_path,
            runtime_config_source=runtime_config_source,
            dry_run_only=runtime_settings.dry_run_only,
            managed_symbols=(),
            safe_haven_symbol=safe_haven_symbol,
            include_safe_haven_metadata=include_safe_haven_metadata,
            signal_description="feature snapshot compute failed",
            decision_text="fail_closed",
            reason=fail_reason,
            metadata=metadata,
        )

    managed_symbols = extract_feature_snapshot_managed_symbols(
        runtime_adapter=runtime_adapter,
        feature_snapshot=feature_snapshot,
        benchmark_symbol=benchmark_symbol,
        safe_haven_symbol=safe_haven_symbol,
        fallback_symbols=base_managed_symbols,
    )
    metadata = _base_metadata(
        profile=profile,
        display_name=entrypoint.manifest.display_name,
        include_strategy_display_name=include_strategy_display_name,
        runtime_config_path=runtime_config_path,
        runtime_config_source=runtime_config_source,
        dry_run_only=runtime_settings.dry_run_only,
        managed_symbols=managed_symbols,
        safe_haven_symbol=safe_haven_symbol,
        include_safe_haven_metadata=include_safe_haven_metadata,
        status_icon=status_icon or runtime_adapter.status_icon,
    )
    metadata.update(
        {
            "feature_snapshot_path": runtime_settings.feature_snapshot_path,
            **guard_metadata,
        }
    )
    if extra_success_metadata is not None:
        metadata.update(extra_success_metadata(feature_snapshot, managed_symbols, decision))
    return FeatureSnapshotEvaluationResult(decision=decision, metadata=metadata)


def extract_feature_snapshot_managed_symbols(
    *,
    runtime_adapter: StrategyRuntimeAdapter,
    feature_snapshot: Any,
    benchmark_symbol: str,
    safe_haven_symbol: str | None,
    fallback_symbols: tuple[str, ...] = (),
) -> tuple[str, ...]:
    extractor = runtime_adapter.managed_symbols_extractor
    if callable(extractor):
        return tuple(
            extractor(
                feature_snapshot,
                benchmark_symbol=benchmark_symbol,
                safe_haven=safe_haven_symbol,
            )
        )
    if safe_haven_symbol:
        return (safe_haven_symbol,)
    return fallback_symbols


def _apply_runtime_policy(
    runtime_config: dict[str, Any],
    runtime_adapter: StrategyRuntimeAdapter,
) -> None:
    apply_runtime_policy_to_runtime_config(runtime_config, runtime_adapter)


def _resolve_symbol(raw_value: Any, *, default: str | None) -> str | None:
    value = str(raw_value or default or "").strip().upper()
    return value or None


def _fail_closed_result(
    *,
    profile: str,
    display_name: str,
    include_strategy_display_name: bool,
    feature_snapshot_path: str | None,
    runtime_config_path: Any,
    runtime_config_source: Any,
    dry_run_only: bool,
    managed_symbols: tuple[str, ...],
    safe_haven_symbol: str | None,
    include_safe_haven_metadata: bool,
    signal_description: str,
    decision_text: str,
    reason: Any,
    metadata: Mapping[str, Any],
) -> FeatureSnapshotEvaluationResult:
    result_metadata = _base_metadata(
        profile=profile,
        display_name=display_name,
        include_strategy_display_name=include_strategy_display_name,
        runtime_config_path=runtime_config_path,
        runtime_config_source=runtime_config_source,
        dry_run_only=dry_run_only,
        managed_symbols=managed_symbols,
        safe_haven_symbol=safe_haven_symbol,
        include_safe_haven_metadata=include_safe_haven_metadata,
        status_icon="🛑",
    )
    result_metadata["feature_snapshot_path"] = feature_snapshot_path
    result_metadata.update(metadata)
    decision = StrategyDecision(
        risk_flags=("no_execute",),
        diagnostics={
            "signal_description": signal_description,
            "status_description": f"{decision_text} | reason={reason}",
            "actionable": False,
            "snapshot_guard_decision": decision_text,
            "fail_reason": metadata.get("fail_reason"),
            "no_op_reason": metadata.get("no_op_reason"),
        },
    )
    return FeatureSnapshotEvaluationResult(decision=decision, metadata=result_metadata)


def _base_metadata(
    *,
    profile: str,
    display_name: str,
    include_strategy_display_name: bool,
    runtime_config_path: Any,
    runtime_config_source: Any,
    dry_run_only: bool,
    managed_symbols: tuple[str, ...],
    safe_haven_symbol: str | None,
    include_safe_haven_metadata: bool,
    status_icon: str,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "strategy_profile": profile,
        "strategy_config_path": runtime_config_path,
        "strategy_config_source": runtime_config_source,
        "dry_run_only": dry_run_only,
        "managed_symbols": managed_symbols,
        "status_icon": status_icon,
    }
    if include_strategy_display_name:
        metadata["strategy_display_name"] = str(display_name)
    if include_safe_haven_metadata:
        metadata["safe_haven_symbol"] = safe_haven_symbol
    return metadata
