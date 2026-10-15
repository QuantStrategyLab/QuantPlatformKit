"""Export legacy v2, or an isolated coverage envelope pending paired readers.

Coverage-bearing records must not be fed to an old optimization watcher as
ordinary v2. Their inner v2 metadata retains supplied effective/requested/source
windows and machine-checkable comparison qualification; it is not native archive
proof or exact TWR. Strict sanitized P3 artifacts are a separate contract.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from quant_platform_kit.strategy_lifecycle.contracts import (
    BacktestResult, StrategyPerformanceSnapshot, WindowPerformance,
    interval_return_coverage_comparison_reason, normalize_interval_return_coverage,
)
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore

PERFORMANCE_SCHEMA_VERSION = "strategy_performance.v2"
COVERAGE_EXPORT_SCHEMA_VERSION = "strategy_performance.coverage_envelope.v1"
METRICS_KIND = "performance"
DEFAULT_WINDOWS: tuple[int, ...] = (126, 252, 63, 21)
REQUIRED_METRICS = ("sharpe", "cagr", "calmar", "win_rate", "max_dd")
PROVENANCE_SENTINELS = {"", "unavailable", "not_available", "legacy_missing", "unknown", "none", "null"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _window_for_snapshot(snapshot: StrategyPerformanceSnapshot, preferred_windows: Sequence[int]) -> WindowPerformance:
    for window in preferred_windows:
        candidate = snapshot.windows.get(int(window))
        if candidate is not None:
            return candidate
    if snapshot.windows:
        return sorted(snapshot.windows.items(), key=lambda item: item[0], reverse=True)[0][1]
    raise ValueError(f"snapshot has no window metrics for profile={snapshot.strategy_profile!r}")


def _current_metrics(window: WindowPerformance, snapshot: StrategyPerformanceSnapshot) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "sharpe": window.sharpe_ratio,
        "cagr": window.cagr,
        "calmar": window.calmar_ratio,
        "win_rate": window.win_rate,
        "max_dd": window.max_drawdown,
        "volatility": window.volatility,
        "total_return": window.total_return,
        "observation_count": window.observation_count,
        "benchmark_symbol": window.benchmark_symbol or snapshot.benchmark_symbol,
        "benchmark_return": window.benchmark_return,
        "benchmark_cagr": window.benchmark_cagr,
        "benchmark_max_dd": window.benchmark_max_drawdown,
        "excess_cagr": window.excess_cagr,
        "alpha": window.alpha,
        "information_ratio": window.information_ratio,
        "latest_return": snapshot.latest_return,
        "drift_score": snapshot.drift_score,
        "data_freshness_days": snapshot.data_freshness_days,
    }
    _assert_required_metrics(metrics, label=f"snapshot:{snapshot.strategy_profile}")
    return metrics


def _baseline_metrics(backtest: BacktestResult) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "sharpe": backtest.sharpe_ratio,
        "cagr": backtest.cagr,
        "calmar": backtest.calmar_ratio,
        "win_rate": backtest.win_rate,
        "max_dd": backtest.max_drawdown,
        "volatility": backtest.volatility,
        "total_return": backtest.total_return,
        "observation_count": backtest.observation_count,
        "benchmark_symbol": backtest.benchmark_symbol,
        "benchmark_cagr": backtest.benchmark_cagr,
        "benchmark_max_dd": backtest.benchmark_max_drawdown,
        "excess_cagr": backtest.excess_cagr,
        "param_version": backtest.param_version,
        "oos_sharpe": backtest.oos_sharpe,
        "oos_calmar": backtest.oos_calmar,
        "oos_max_dd": backtest.oos_max_drawdown,
        "walk_forward_stability": backtest.walk_forward_stability,
    }
    _assert_required_metrics(metrics, label=f"backtest:{backtest.strategy_profile}")
    return metrics


def _assert_required_metrics(metrics: Mapping[str, Any], *, label: str) -> None:
    missing = [name for name in REQUIRED_METRICS if metrics.get(name) is None]
    if missing:
        raise ValueError(f"{label} missing required metrics: {', '.join(missing)}")


def _date_timestamp(value: date | None) -> str:
    if value is None:
        return "unavailable"
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _usable_provenance(value: str) -> bool:
    return isinstance(value, str) and value.strip().lower() not in PROVENANCE_SENTINELS


def export_strategy_performance(
    domain: str,
    *,
    repo: str,
    strategy_profiles: Sequence[str] | None = None,
    preferred_windows: Sequence[int] = DEFAULT_WINDOWS,
    store: PerformanceStore | None = None,
    output_path: str | Path | None = None,
    baseline_coverage_by_profile: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    lifecycle_store = store or PerformanceStore.from_env()
    profiles = list(strategy_profiles or lifecycle_store.list_snapshot_profiles(domain))
    if not profiles:
        raise ValueError(
            f"No lifecycle snapshots found for domain={domain!r}; set LIFECYCLE_LOCAL_ROOT/LIFECYCLE_PERFORMANCE_BUCKET first."
        )

    generated_at = _now_iso()
    snapshots: list[dict[str, Any]] = []
    for profile in sorted({str(profile).strip() for profile in profiles if str(profile).strip()}):
        snapshot = lifecycle_store.load_latest_snapshot(domain, profile)
        if snapshot is None:
            raise ValueError(f"Missing latest lifecycle snapshot for domain={domain!r}, profile={profile!r}")
        if snapshot.as_of is None:
            raise ValueError("observation_date_unavailable")
        backtest = lifecycle_store.load_latest_backtest(domain, profile)
        if backtest is None:
            raise ValueError(f"Missing latest lifecycle backtest for domain={domain!r}, profile={profile!r}")

        window = _window_for_snapshot(snapshot, preferred_windows)
        snapshot_timestamp = _date_timestamp(snapshot.as_of)
        snapshots.append(
            {
                "repo": repo,
                "strategy_profile": profile,
                "schema_version": PERFORMANCE_SCHEMA_VERSION,
                "metrics_kind": METRICS_KIND,
                "current_metrics": _current_metrics(window, snapshot),
                "baseline_metrics": _baseline_metrics(backtest),
                "source": snapshot.source_artifact_path or "performance_store",
                "generated_at": generated_at,
                "metadata": {
                    "domain": domain,
                    "as_of": snapshot.as_of.isoformat(),
                    "window_days": window.window_days,
                    "window_start": window.start_date.isoformat(),
                    "window_end": window.end_date.isoformat(),
                    "snapshot_computed_at": snapshot.computed_at,
                    "backtest_computed_at": backtest.computed_at,
                    "snapshot_source_revision": snapshot.source_revision,
                    "backtest_source_revision": backtest.source_revision,
                    "snapshot_cost_model": snapshot.cost_model,
                    "backtest_cost_model": backtest.cost_model,
                    "provenance": {
                        "snapshot": {
                            "source_revision": snapshot.source_revision or "legacy_missing",
                            "cost_model": snapshot.cost_model or "legacy_missing",
                            "data_timestamp": snapshot_timestamp,
                            "status": "verified" if snapshot.as_of and _usable_provenance(snapshot.source_revision) and _usable_provenance(snapshot.cost_model) else "legacy_missing",
                        },
                        "backtest": {
                            "source_revision": backtest.source_revision or "legacy_missing",
                            "cost_model": backtest.cost_model or "legacy_missing",
                            "data_timestamp": _date_timestamp(backtest.end_date),
                            "status": "verified" if _usable_provenance(backtest.source_revision) and _usable_provenance(backtest.cost_model) and backtest.end_date else "legacy_missing",
                        },
                    },
                    "snapshot_data_timestamp": snapshot_timestamp,
                    "backtest_data_timestamp": _date_timestamp(backtest.end_date),
                },
            }
        )
        coverage = snapshot.interval_return_coverage
        if coverage is not None:
            coverage = normalize_interval_return_coverage(coverage)
            reference_coverage = None
            try:
                reference_coverage = normalize_interval_return_coverage(
                    (baseline_coverage_by_profile or {}).get(profile))
            except (TypeError, ValueError):
                pass
            reason = interval_return_coverage_comparison_reason(
                coverage, (baseline_coverage_by_profile or {}).get(profile),
                current_window=window, reference_metrics=backtest,
            )
            metadata = snapshots[-1]["metadata"]
            # Account scope is internal source identity, not a public sanitized
            # P3 field. Window/method metadata is enough to disclose this view.
            metadata["interval_return_coverage"] = {k: v for k, v in coverage.items()
                                                    if k != "account_scope_sha256"}
            metadata["snapshot_data_timestamp"] = coverage["return_end_at"]
            metadata["provenance"]["snapshot"]["data_timestamp"] = coverage["return_end_at"]
            metadata["interval_comparison"] = {
                "comparable": not bool(reason), "reason": reason,
                "actual_start_date": window.start_date.isoformat(),
                "actual_end_date": window.end_date.isoformat(),
                "actual_observation_count": window.observation_count,
                "calendar_id": window.calendar_id, "periods_per_year": window.periods_per_year,
                "reference_coverage": ({k: v for k, v in reference_coverage.items()
                                        if k != "account_scope_sha256"} if reference_coverage is not None else None),
                "reference_start_date": backtest.start_date.isoformat() if backtest.start_date else None,
                "reference_end_date": backtest.end_date.isoformat() if backtest.end_date else None,
                "reference_observation_count": backtest.observation_count,
                "reference_calendar_id": backtest.calendar_id,
                "reference_periods_per_year": backtest.periods_per_year,
                "scope": "supplied_checkpoint_window",
            }

    payload: dict[str, Any] = {
        "schema_version": PERFORMANCE_SCHEMA_VERSION,
        "metrics_kind": METRICS_KIND,
        "repo": repo,
        "domain": domain,
        "generated_at": generated_at,
        "source": "strategy_lifecycle_performance_store",
        "snapshots": snapshots,
    }
    if any("interval_return_coverage" in item["metadata"] for item in snapshots):
        # Both container and each item use a new schema. Old AAB projection
        # cannot find ordinary current/baseline metrics at its expected level.
        payload["schema_version"] = COVERAGE_EXPORT_SCHEMA_VERSION
        payload["snapshots"] = [
            {"schema_version": COVERAGE_EXPORT_SCHEMA_VERSION, "metrics_kind": METRICS_KIND,
             "payload": item} for item in snapshots
        ]
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="strategy_performance_export")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--profile", action="append", dest="profiles", default=None)
    parser.add_argument("--output", required=True)
    parser.add_argument("--window", action="append", dest="windows", type=int, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    payload = export_strategy_performance(
        args.domain,
        repo=args.repo,
        strategy_profiles=args.profiles,
        preferred_windows=tuple(args.windows or DEFAULT_WINDOWS),
        output_path=args.output,
    )
    print(json.dumps({"status": "ok", "snapshots": len(payload["snapshots"]), "output": args.output}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
