"""Continuous Performance Monitor — main orchestration.

Collects daily strategy returns, computes rolling metrics for all configured windows,
and persists StrategyPerformanceSnapshot records to the performance store.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

logger = logging.getLogger(__name__)

from quant_platform_kit.strategy_lifecycle.contracts import StrategyPerformanceSnapshot
from quant_platform_kit.strategy_lifecycle.performance_metrics import (
    DEFAULT_WINDOWS,
    compare_with_backtest,
    compute_window_metrics,
    normalize_return_series,
)
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore
from quant_platform_kit.strategy_lifecycle.return_collector import (
    ReturnCollector,
    resolve_strategy_benchmark,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_valid_series(series: object, *, min_observations: int = 10) -> bool:
    if not isinstance(series, pd.Series):
        return False
    return len(series.dropna()) >= min_observations


def run_monitor(
    domain: str,
    *,
    strategy_profile: str | None = None,
    output_dir: str | None = None,
    windows: Sequence[int] = DEFAULT_WINDOWS,
    min_observations: int = 10,
    store: PerformanceStore | None = None,
    collector: ReturnCollector | None = None,
) -> list[StrategyPerformanceSnapshot]:
    """Run the performance monitor for the given domain.

    Args:
        domain: Market domain (us_equity, crypto, hk_equity, cn_equity)
        strategy_profile: Limit to a single strategy. If None, monitors all.
        output_dir: Optional local directory to write snapshot JSON files.
        windows: Trading-day windows to compute (default: 21, 63, 126, 252, 756).
        min_observations: Minimum observations required for a valid series.
        store: PerformanceStore instance; auto-created from env if None.
        collector: ReturnCollector instance; auto-created if None.

    Returns:
        List of StrategyPerformanceSnapshot objects generated.
    """
    store = store or PerformanceStore.from_env()
    collector = collector or ReturnCollector()

    # 1. Collect returns
    all_returns = collector.collect(domain)
    if not all_returns:
        return []

    profiles = [strategy_profile] if strategy_profile else sorted(all_returns.keys())
    snapshots: list[StrategyPerformanceSnapshot] = []

    for profile in profiles:
        returns = all_returns.get(profile)
        if not _is_valid_series(returns, min_observations=min_observations):
            continue

        series = normalize_return_series(returns)

        # Resolve benchmark
        benchmark_symbol = resolve_strategy_benchmark(profile, domain)
        benchmark_series = collector.collect_benchmark(domain, benchmark_symbol)
        benchmark_returns = normalize_return_series(benchmark_series) if benchmark_series is not None else None

        # Load backtest reference for comparison
        latest_backtest = store.load_latest_backtest(domain, profile)

        # Build snapshot
        snapshot = StrategyPerformanceSnapshot(
            strategy_profile=profile,
            domain=domain,
            platform="",
            as_of=date.today(),
            benchmark_symbol=benchmark_symbol,
            computed_at=_now_iso(),
        )

        # Compute each window
        windows_dict = dict(snapshot.windows)
        for w in windows:
            sliced = series if w >= len(series) else series.iloc[-w:]
            bench_sliced = benchmark_returns.iloc[-w:] if benchmark_returns is not None and len(benchmark_returns) >= w else None
            wp = compute_window_metrics(
                sliced,
                benchmark_returns=bench_sliced,
                benchmark_symbol=benchmark_symbol,
                window_days=w,
            )
            windows_dict[w] = wp

        # Latest return
        if len(series) > 0:
            snapshot = StrategyPerformanceSnapshot(
                strategy_profile=snapshot.strategy_profile,
                domain=snapshot.domain,
                platform=snapshot.platform,
                as_of=snapshot.as_of,
                windows=windows_dict,
                latest_return=float(series.iloc[-1]),
                benchmark_symbol=snapshot.benchmark_symbol,
                data_freshness_days=(date.today() - series.index[-1].date()).days if hasattr(series.index[-1], "date") else 0,
                source_artifact_path="",
                computed_at=snapshot.computed_at,
            )
        else:
            snapshot = StrategyPerformanceSnapshot(
                strategy_profile=snapshot.strategy_profile,
                domain=snapshot.domain,
                platform=snapshot.platform,
                as_of=snapshot.as_of,
                windows=windows_dict,
                benchmark_symbol=snapshot.benchmark_symbol,
                computed_at=snapshot.computed_at,
            )

        # Attach drift reference: use 126-day window to compare against backtest
        ref_window = windows_dict.get(126) or windows_dict.get(252)
        if ref_window is not None and latest_backtest is not None:
            deviations = compare_with_backtest(ref_window, latest_backtest)
            if deviations:
                max_dev = max(deviations.values())
                snapshot = StrategyPerformanceSnapshot(
                    strategy_profile=snapshot.strategy_profile,
                    domain=snapshot.domain,
                    platform=snapshot.platform,
                    as_of=snapshot.as_of,
                    windows=snapshot.windows,
                    latest_return=snapshot.latest_return,
                    benchmark_symbol=snapshot.benchmark_symbol,
                    drift_score=min(max_dev, 1.0),
                    data_freshness_days=snapshot.data_freshness_days,
                    source_artifact_path=snapshot.source_artifact_path,
                    computed_at=snapshot.computed_at,
                )

        # Persist
        store.save_snapshot(snapshot)

        # Optional local output
        if output_dir:
            out_path = Path(output_dir) / domain / profile / f"{snapshot.as_of.isoformat()}.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            import json
            out_path.write_text(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        snapshots.append(snapshot)

    return snapshots


def _serialize_decision(decision: Any) -> dict[str, Any]:
    positions = getattr(decision, "positions", ()) or ()
    serialized_positions: list[dict[str, Any]] = []
    for position in positions:
        serialized_positions.append(
            {
                "symbol": str(getattr(position, "symbol", "") or ""),
                "target_weight": float(getattr(position, "target_weight", 0.0) or 0.0),
                "role": str(getattr(position, "role", "") or ""),
            }
        )
    return {
        "positions": serialized_positions,
        "risk_flags": list(getattr(decision, "risk_flags", ()) or ()),
        "diagnostics": dict(getattr(decision, "diagnostics", {}) or {}),
    }


class PerformanceMonitor:
    """Per-run performance / decision recorder for live strategy entrypoints."""

    def __init__(self, store: PerformanceStore | None = None) -> None:
        self._store = store or PerformanceStore.from_env()

    def record(
        self,
        profile_id: str,
        decision: Any,
        execution_result: Mapping[str, Any] | None = None,
        *,
        domain: str = "",
    ) -> dict[str, Any]:
        profile = str(profile_id or "").strip()
        if not profile:
            return {"ok": False, "skipped": "empty_profile"}

        payload = {
            "strategy_profile": profile,
            "domain": str(domain or "").strip(),
            "recorded_at": _now_iso(),
            "decision": _serialize_decision(decision),
            "execution_result": dict(execution_result or {}),
        }
        self._store.save_live_run_record(profile, str(domain or "").strip(), payload)
        return {"ok": True, "profile": profile, "domain": str(domain or "").strip()}

    def record_execution(
        self,
        profile_id: str,
        execution_result: Mapping[str, Any],
        *,
        domain: str = "",
        decision: Any | None = None,
    ) -> dict[str, Any]:
        """Persist platform-layer execution telemetry after order routing."""
        profile = str(profile_id or "").strip()
        if not profile:
            return {"ok": False, "skipped": "empty_profile"}
        if not execution_result:
            return {"ok": False, "skipped": "empty_execution_result"}

        payload: dict[str, Any] = {
            "strategy_profile": profile,
            "domain": str(domain or "").strip(),
            "recorded_at": _now_iso(),
            "record_kind": "execution",
            "execution_result": dict(execution_result),
        }
        if decision is not None:
            payload["decision"] = _serialize_decision(decision)
        self._store.save_live_run_record(profile, str(domain or "").strip(), payload)
        return {"ok": True, "profile": profile, "domain": str(domain or "").strip()}


def infer_strategy_domain(profile_id: str, *, explicit_domain: str = "") -> str:
    domain = str(explicit_domain or "").strip()
    if domain:
        return domain
    profile = str(profile_id or "").strip().lower()
    if profile.startswith("cn_"):
        return "cn_equity"
    if profile.startswith("hk_"):
        return "hk_equity"
    if profile.startswith("crypto_"):
        return "crypto"
    return "us_equity"


def try_record_platform_execution(
    profile_id: str,
    execution_result: Mapping[str, Any] | None,
    *,
    domain: str = "",
    decision: Any | None = None,
) -> None:
    """Best-effort execution recorder for platform runtimes; never raises."""
    try:
        if not execution_result:
            return
        monitor = PerformanceMonitor()
        monitor.record_execution(
            profile_id,
            execution_result,
            domain=infer_strategy_domain(profile_id, explicit_domain=domain),
            decision=decision,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("PerformanceMonitor.record_execution failed: %s", exc)
