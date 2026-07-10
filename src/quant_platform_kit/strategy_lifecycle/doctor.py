"""Lifecycle health doctor for repo/workflow preflight checks."""

from __future__ import annotations

import argparse
import json
from typing import Any, Sequence

from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore
from quant_platform_kit.strategy_lifecycle.return_collector import ReturnCollector


def doctor_lifecycle(
    domain: str,
    *,
    require_snapshot: bool = True,
    require_backtest: bool = False,
    require_drift: bool = False,
    max_freshness_days: int | None = None,
    store: PerformanceStore | None = None,
    collector: ReturnCollector | None = None,
) -> dict[str, Any]:
    lifecycle_store = store or PerformanceStore.from_env()
    return_collector = collector or ReturnCollector(store=lifecycle_store)
    profiles = sorted(return_collector.collect(domain))
    if not profiles:
        return {
            "ok": False,
            "domain": domain,
            "profiles_discovered": 0,
            "issues": [f"No strategy return series discovered for domain={domain!r}."],
            "profiles": [],
        }

    issues: list[str] = []
    profile_rows: list[dict[str, Any]] = []
    for profile in profiles:
        snapshot = lifecycle_store.load_latest_snapshot(domain, profile)
        backtest = lifecycle_store.load_latest_backtest(domain, profile)
        drift = lifecycle_store.load_latest_drift(domain, profile)
        row = {
            "strategy_profile": profile,
            "snapshot": snapshot is not None,
            "backtest": backtest is not None,
            "drift": drift is not None,
            "data_freshness_days": snapshot.data_freshness_days if snapshot is not None else None,
        }
        profile_rows.append(row)

        if require_snapshot and snapshot is None:
            issues.append(f"{profile}: missing lifecycle snapshot")
        if require_backtest and backtest is None:
            issues.append(f"{profile}: missing lifecycle backtest")
        if require_drift and drift is None:
            issues.append(f"{profile}: missing lifecycle drift result")
        if max_freshness_days is not None and snapshot is not None and snapshot.data_freshness_days > max_freshness_days:
            issues.append(
                f"{profile}: snapshot freshness {snapshot.data_freshness_days}d exceeds max {max_freshness_days}d"
            )

    return {
        "ok": not issues,
        "domain": domain,
        "profiles_discovered": len(profiles),
        "issues": issues,
        "profiles": profile_rows,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quant-lifecycle-doctor")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--require-snapshot", action="store_true")
    parser.add_argument("--require-backtest", action="store_true")
    parser.add_argument("--require-drift", action="store_true")
    parser.add_argument("--max-freshness-days", type=int, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = doctor_lifecycle(
        args.domain,
        require_snapshot=args.require_snapshot,
        require_backtest=args.require_backtest,
        require_drift=args.require_drift,
        max_freshness_days=args.max_freshness_days,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
