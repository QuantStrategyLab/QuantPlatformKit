"""Command-line entrypoint for strategy lifecycle operations."""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import Any


def _load_callable(module_name: str, function_name: str) -> Callable[..., Any]:
    module = importlib.import_module(module_name)
    return getattr(module, function_name)


def _print(message: str) -> None:
    print(message)


def _run_monitor(args: argparse.Namespace) -> int:
    _print(f"[monitor] Running performance monitor for domain={args.domain}")
    run_monitor = _load_callable(
        "quant_platform_kit.strategy_lifecycle.performance_monitor",
        "run_monitor",
    )
    snapshots = run_monitor(
        domain=args.domain,
        strategy_profile=args.strategy,
        output_dir=args.output_dir,
    )
    _print(f"[monitor] Generated {len(snapshots)} performance snapshots")
    return 0


def _run_drift(args: argparse.Namespace) -> int:
    _print(f"[drift] Running drift detection for domain={args.domain}")
    run_drift_detection = _load_callable(
        "quant_platform_kit.strategy_lifecycle.drift_detector",
        "run_drift_detection",
    )
    baseline_store = None
    if getattr(args, "baseline_local_root", None):
        from pathlib import Path
        from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore

        baseline_store = replace(
            PerformanceStore.from_env(),
            local_root=Path(args.baseline_local_root),
        )
    baseline_lineage_policy = "migration" if getattr(args, "allow_legacy_baseline_history", False) else (
        "strict" if getattr(args, "strict_baseline_lineage", False) else "auto"
    )
    results = run_drift_detection(
        domain=args.domain,
        strategy_profile=args.strategy,
        baseline_store=baseline_store,
        baseline_lineage_policy=baseline_lineage_policy,
    )
    critical_count = sum(1 for item in results if getattr(getattr(item, "status", None), "value", None) == "critical")
    review_count = sum(1 for item in results if getattr(getattr(item, "status", None), "value", None) == "review")
    _print(f"[drift] {len(results)} strategies checked, {critical_count} critical, {review_count} review")
    if not getattr(args, "no_alerts", False):
        build_drift_alert = _load_callable(
            "quant_platform_kit.strategy_lifecycle.drift_alerts",
            "build_drift_alert",
        )
        publish_drift_alerts = _load_callable(
            "quant_platform_kit.strategy_lifecycle.drift_alerts",
            "publish_drift_alerts",
        )
        events = [event for event in (build_drift_alert(result) for result in results) if event is not None]
        counts = publish_drift_alerts(events, dry_run=getattr(args, "dry_run_alerts", False))
        _print(f"[drift] Alerts published: {sum(counts.values())}")
    return 0


def _run_optimize(args: argparse.Namespace) -> int:
    _print(f"[optimize] Optimizing {args.strategy} with method={args.method}")
    run_optimization = _load_callable(
        "quant_platform_kit.strategy_lifecycle.param_optimizer",
        "run_optimization",
    )
    proposal = run_optimization(strategy_profile=args.strategy, method=args.method)
    _print(f"[optimize] Recommendation: {getattr(proposal, 'recommendation', '')}")
    improvement_score = getattr(proposal, "improvement_score", None)
    if improvement_score is not None:
        _print(f"[optimize] Improvement score: {improvement_score:.3f}")
    return 0


def _run_update(args: argparse.Namespace) -> int:
    _print(f"[update] Processing proposal: {args.proposal}")
    process_update = _load_callable(
        "quant_platform_kit.strategy_lifecycle.update_orchestrator",
        "process_update",
    )
    result = process_update(proposal_path=args.proposal, auto_approve=args.auto_approve)
    _print(f"[update] Result: stage={result.get('stage')}, reason={result.get('reason', '')}")
    return 1 if result.get("stage") == "error" else 0


def _run_dashboard(args: argparse.Namespace) -> int:
    _print(f"[dashboard] Building health dashboard (format={args.output_format})")
    build_dashboard = _load_callable(
        "quant_platform_kit.strategy_lifecycle.health_dashboard",
        "build_dashboard",
    )
    result = build_dashboard(output_dir=args.output_dir, output_format=args.output_format)
    _print(f"[dashboard] Dashboard built with {result.get('strategy_count', 0)} strategies")
    return 0


def _run_autopilot(args: argparse.Namespace) -> int:
    _print(f"[autopilot] Running auto-pilot cycle for domain={args.domain} (dry_run={args.dry_run})")
    run_auto_pilot_cycle = _load_callable(
        "quant_platform_kit.strategy_lifecycle.codex_integration",
        "run_auto_pilot_cycle",
    )
    summary = run_auto_pilot_cycle(
        args.domain,
        dry_run=args.dry_run,
        create_issues=not args.no_issues,
        trigger_optimization=True,
    )
    _print(f"[autopilot] Snapshots: {summary.get('snapshots_count', 0)}")
    _print(f"[autopilot] Drifts checked: {summary.get('drifts_checked', 0)}")
    _print(f"[autopilot] Drifts alerting: {summary.get('drifts_alerting', 0)}")
    _print(f"[autopilot] Issues created: {summary.get('issues_created', 0)}")
    _print(f"[autopilot] Actions: {len(summary.get('actions', []))}")
    for action in summary.get("actions", []):
        decision = action.get("ai_decision", {})
        _print(
            f"  - {action['strategy']}: drift={action['drift_status']}, "
            f"optimize={decision.get('optimization_needed')}, "
            f"method={decision.get('recommended_method', 'none')}"
        )
    return 0


def _run_lifecycle(args: argparse.Namespace) -> int:
    _print(f"[lifecycle] Running full lifecycle for domain={args.domain}")
    _print("[lifecycle] Step: monitor")
    monitor_status = _run_monitor(argparse.Namespace(domain=args.domain, strategy=None, output_dir=None))
    if monitor_status != 0:
        return monitor_status

    _print("[lifecycle] Step: drift")
    drift_status = _run_drift(
        argparse.Namespace(
            domain=args.domain,
            strategy=None,
            no_alerts=args.no_alerts,
            dry_run_alerts=args.dry_run_alerts,
        )
    )
    if drift_status != 0:
        return drift_status

    if not args.skip_optimization:
        if args.strategy:
            _print("[lifecycle] Step: optimize")
            optimize_status = _run_optimize(argparse.Namespace(strategy=args.strategy, method=args.method))
            if optimize_status != 0:
                return optimize_status
        else:
            _print("[lifecycle] Step: optimize skipped (no --strategy provided)")

    _print("[lifecycle] Step: dashboard")
    dashboard_status = _run_dashboard(argparse.Namespace(output_dir=None, output_format=args.output_format))
    if dashboard_status != 0:
        return dashboard_status

    _print("[lifecycle] Full lifecycle complete")
    return 0


def _run_evidence(args: argparse.Namespace) -> int:
    _print(f"[evidence] Validating package file={args.file}")
    validate_evidence_package_file = _load_callable(
        "quant_platform_kit.strategy_lifecycle.evidence_gate",
        "validate_evidence_package_file",
    )
    result = validate_evidence_package_file(args.file)
    if getattr(args, "json", False):
        import json

        _print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        status = "valid" if result.valid else "invalid"
        _print(f"[evidence] status={status} issues={len(result.issues)} warnings={len(result.warnings)}")
        for item in result.issues:
            _print(f"  - issue: {item}")
        for item in result.warnings:
            _print(f"  - warning: {item}")
    return 0 if result.valid else 1


def _run_export_performance(args: argparse.Namespace) -> int:
    _print(f"[export-performance] Exporting strategy_performance.v2 for domain={args.domain}")
    export_strategy_performance = _load_callable(
        "quant_platform_kit.strategy_lifecycle.performance_export",
        "export_strategy_performance",
    )
    payload = export_strategy_performance(
        args.domain,
        repo=args.repo,
        strategy_profiles=args.profile,
        output_path=args.output,
    )
    _print(f"[export-performance] Exported {len(payload.get('snapshots', []))} snapshots")
    return 0


def _run_doctor(args: argparse.Namespace) -> int:
    _print(f"[doctor] Checking lifecycle health for domain={args.domain}")
    doctor_lifecycle = _load_callable(
        "quant_platform_kit.strategy_lifecycle.doctor",
        "doctor_lifecycle",
    )
    result = doctor_lifecycle(
        args.domain,
        require_snapshot=args.require_snapshot,
        require_backtest=args.require_backtest,
        require_drift=args.require_drift,
        max_freshness_days=args.max_freshness_days,
    )
    _print(
        f"[doctor] profiles={result.get('profiles_discovered', 0)} "
        f"issues={len(result.get('issues', []))} ok={result.get('ok', False)}"
    )
    for issue in result.get("issues", []):
        _print(f"  - issue: {issue}")
    return 0 if result.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quant-lifecycle", description="Quant strategy lifecycle CLI.")
    parser.add_argument("--version", action="version", version="quant-lifecycle 0.10.0")
    subparsers = parser.add_subparsers(dest="command", required=True)

    monitor = subparsers.add_parser("monitor", help="Run the continuous performance monitor for one domain.")
    monitor.add_argument("--domain", default="us_equity")
    monitor.add_argument("--strategy", default=None)
    monitor.add_argument("--output-dir", default=None)
    monitor.set_defaults(func=_run_monitor)

    drift = subparsers.add_parser("drift", help="Run drift detection and publish drift alerts.")
    drift.add_argument("--domain", default="us_equity")
    drift.add_argument("--strategy", default=None)
    drift.add_argument("--no-alerts", action="store_true")
    drift.add_argument("--dry-run-alerts", action="store_true")
    drift.add_argument("--baseline-local-root", default=None)
    drift.add_argument("--strict-baseline-lineage", action="store_true")
    drift.add_argument(
        "--allow-legacy-baseline-history",
        action="store_true",
        help="One-time migration: reuse untagged prior drift status with an external accepted baseline.",
    )
    drift.set_defaults(func=_run_drift)

    optimize = subparsers.add_parser("optimize", help="Run parameter optimization for one strategy.")
    optimize.add_argument("--strategy", required=True)
    optimize.add_argument("--method", default="grid_search")
    optimize.set_defaults(func=_run_optimize)

    update = subparsers.add_parser("update", help="Process a parameter update proposal.")
    update.add_argument("--proposal", required=True)
    update.add_argument("--auto-approve", action="store_true")
    update.set_defaults(func=_run_update)

    dashboard = subparsers.add_parser("dashboard", help="Build the unified strategy health dashboard.")
    dashboard.add_argument("--output-dir", default=None)
    dashboard.add_argument("--format", dest="output_format", default="all")
    dashboard.set_defaults(func=_run_dashboard)

    autopilot = subparsers.add_parser("autopilot", help="Run a full auto-pilot cycle.")
    autopilot.add_argument("--domain", default="us_equity")
    autopilot.add_argument("--dry-run", action="store_true")
    autopilot.add_argument("--no-issues", action="store_true")
    autopilot.set_defaults(func=_run_autopilot)

    evidence = subparsers.add_parser("evidence", help="Validate a strategy promotion evidence package.")
    evidence.add_argument("--file", required=True)
    evidence.add_argument("--json", action="store_true")
    evidence.set_defaults(func=_run_evidence)

    export_performance = subparsers.add_parser("export-performance", help="Export canonical strategy_performance.v2 payload.")
    export_performance.add_argument("--domain", required=True)
    export_performance.add_argument("--repo", required=True)
    export_performance.add_argument("--profile", action="append", default=None)
    export_performance.add_argument("--output", required=True)
    export_performance.set_defaults(func=_run_export_performance)

    doctor = subparsers.add_parser("doctor", help="Validate lifecycle data prerequisites for a domain.")
    doctor.add_argument("--domain", required=True)
    doctor.add_argument("--require-snapshot", action="store_true")
    doctor.add_argument("--require-backtest", action="store_true")
    doctor.add_argument("--require-drift", action="store_true")
    doctor.add_argument("--max-freshness-days", type=int, default=None)
    doctor.set_defaults(func=_run_doctor)

    lifecycle = subparsers.add_parser("lifecycle", help="Run the full lifecycle pipeline.")
    lifecycle.add_argument("--domain", default="us_equity")
    lifecycle.add_argument("--strategy", default=None)
    lifecycle.add_argument("--method", default="grid_search")
    lifecycle.add_argument("--format", dest="output_format", default="all")
    lifecycle.add_argument("--skip-optimization", action="store_true")
    lifecycle.add_argument("--no-alerts", action="store_true")
    lifecycle.add_argument("--dry-run-alerts", action="store_true")
    lifecycle.set_defaults(func=_run_lifecycle)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:  # noqa: BLE001
        print(f"[{args.command}] Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
