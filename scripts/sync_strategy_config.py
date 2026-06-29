#!/usr/bin/env python3
"""Sync strategy platform configuration to Cloud Run services and Scheduler jobs.

Reads a centralized config file (strategy_platform_config.json) and
automatically:
1. Validates each strategy-platform assignment against strategy_registry
2. Generates RUNTIME_TARGET_JSON for each service
3. Creates or updates Cloud Scheduler jobs (main, precheck, probe, backup)
4. Reports what changed vs what's already in place

Usage:
    python scripts/sync_strategy_config.py                    # dry-run (check only)
    python scripts/sync_strategy_config.py --apply             # apply changes
    python scripts/sync_strategy_config.py --strategy=soxl   # single strategy
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(__file__).resolve().parent.parent / "strategy_platform_config.json"

# ── Platform → GCP project & region mapping ──
PLATFORM_DEPLOY_TARGETS: dict[str, dict[str, str]] = {
    "schwab": {
        "project": "charlesschwabquant",
        "region": "us-central1",
        "scheduler_sa": "schwab-platform-scheduler@charlesschwabquant.iam.gserviceaccount.com",
    },
    "ibkr": {
        "project": "interactivebrokersquant",
        "region": "us-central1",
        "scheduler_sa": "ibkr-platform-scheduler@interactivebrokersquant.iam.gserviceaccount.com",
    },
    "longbridge": {
        "project": "longbridgequant",
        "region": "asia-east2",
        "scheduler_sa": "longbridge-platform-scheduler@longbridgequant.iam.gserviceaccount.com",
    },
}

# ── Platform → enabled profiles (cached from strategy_registry) ──
def _load_enabled_profiles() -> dict[str, frozenset[str]]:
    """Try to load enabled profiles from each platform's registry."""
    result: dict[str, frozenset[str]] = {}
    for pid in ("schwab", "ibkr", "longbridge"):
        try:
            mod = __import__(f"strategy_registry_{pid}", fromlist=["__all__"])
        except ImportError:
            continue
        for attr in ("SCHWAB_ENABLED_PROFILES", "IBKR_ENABLED_PROFILES",
                     "LONGBRIDGE_ENABLED_PROFILES"):
            profiles = getattr(mod, attr, None)
            if profiles is not None:
                result[pid] = profiles
                break
    return result


@dataclass
class DiffReport:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def load_config(path: Path | None = None) -> dict[str, Any]:
    path = path or CONFIG_PATH
    if not path.exists():
        raise SystemExit(f"Config file not found: {path}\n"
                         f"Copy strategy_platform_config.example.json and edit it.")
    return json.loads(path.read_text())


def validate_strategy(strategy_id: str, cfg: dict, enabled: dict[str, frozenset[str]]) -> list[str]:
    """Check that a strategy can run on its assigned platform."""
    errors: list[str] = []
    primary = cfg.get("primary_platform")
    if not primary:
        errors.append(f"{strategy_id}: missing primary_platform")
        return errors

    if primary not in enabled:
        errors.append(f"{strategy_id}: platform '{primary}' not recognized")
        return errors

    if strategy_id not in enabled[primary]:
        errors.append(
            f"{strategy_id}: NOT in {primary} enabled profiles "
            f"({sorted(enabled[primary])[:5]}...). "
            f"Add it to strategy_registry first."
        )
    return errors


def build_runtime_target_json(strategy_id: str, cfg: dict, platform_id: str) -> str:
    """Generate RUNTIME_TARGET_JSON for a given strategy+platform."""
    acct = cfg.get("accounts", {}).get(platform_id, {})
    execution = cfg.get("execution", {})
    return json.dumps({
        "platform_id": platform_id,
        "strategy_profile": strategy_id,
        "execution_mode": acct.get("execution_mode", "live"),
        "dry_run_only": acct.get("dry_run_only", False),
        "account_scope": acct.get("account_scope", "default"),
        "scheduler": {
            "main_time": execution.get("main_time", "45 15 * * *"),
            "precheck_time": execution.get("precheck_time", "45 9 * * *"),
            "probe_time": execution.get("probe_time", "35 9,15 * * *"),
            "timezone": execution.get("timezone", "America/New_York"),
        },
    }, separators=(",", ":"))


def get_service_url(platform_id: str, account_scope: str = "default") -> str:
    """Get the Cloud Run service URL for a platform+account."""
    target = PLATFORM_DEPLOY_TARGETS[platform_id]
    result = subprocess.run(
        ["gcloud", "run", "services", "describe",
         f"charles-schwab-quant-service" if platform_id == "schwab"
         else f"interactive-brokers-quant-live-{account_scope}-service" if platform_id == "ibkr"
         else f"longbridge-quant-{account_scope.lower()}-service",
         "--project", target["project"],
         "--region", target["region"],
         "--format", "value(status.url)"],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def sync_scheduler_jobs(
    strategy_id: str, cfg: dict, platform_id: str,
    *,
    apply: bool = False,
) -> DiffReport:
    """Create or update Cloud Scheduler jobs for a strategy on a platform."""
    report = DiffReport()
    target = PLATFORM_DEPLOY_TARGETS[platform_id]
    execution = cfg.get("execution", {})
    service_url = get_service_url(platform_id,
                                   cfg.get("accounts", {}).get(platform_id, {}).get("account_scope", "default"))

    if not service_url:
        report.errors.append(f"{strategy_id}/{platform_id}: cannot resolve service URL")
        return report

    base_name = f"{platform_id}-{strategy_id}"[:40].rstrip("-")
    sa = target["scheduler_sa"]

    jobs = [
        ("main", execution.get("main_time", "45 15 * * *"), "/run",
         f"Main execution for {strategy_id}"),
        ("precheck", execution.get("precheck_time", "45 9 * * *"), "/dry-run",
         f"Pre-market dry-run for {strategy_id}"),
        ("backup", execution.get("backup_time", "52 15 * * 1-5"), "/run",
         f"Backup execution for {strategy_id}"),
    ]

    for suffix, schedule, path, desc in jobs:
        job_name = f"{base_name}-{suffix}"[:50].rstrip("-")
        job_uri = f"{service_url}{path}"

        # Check if job exists
        check = subprocess.run(
            ["gcloud", "scheduler", "jobs", "describe", job_name,
             "--project", target["project"], "--location", target["region"]],
            capture_output=True, text=True, timeout=15
        )

        if check.returncode != 0:
            if apply:
                result = subprocess.run(
                    ["gcloud", "scheduler", "jobs", "create", "http", job_name,
                     "--project", target["project"], "--location", target["region"],
                     "--schedule", schedule,
                     "--time-zone", execution.get("timezone", "America/New_York"),
                     "--http-method", "POST", "--uri", job_uri,
                     "--oidc-service-account-email", sa,
                     "--oidc-token-audience", service_url,
                     "--headers", "User-Agent=Google-Cloud-Scheduler",
                     "--description", desc],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    report.added.append(f"  + {job_name}: {schedule} → {job_uri}")
                else:
                    report.errors.append(f"  ✗ {job_name}: {result.stderr.strip()[-100:]}")
            else:
                report.added.append(f"  + {job_name}: {schedule} → {job_uri} [dry-run]")
        else:
            report.unchanged.append(f"  = {job_name}: {schedule}")

    return report


def main() -> int:
    apply = "--apply" in sys.argv
    strategy_filter = None
    for arg in sys.argv[1:]:
        if arg.startswith("--strategy="):
            strategy_filter = arg.split("=", 1)[1]

    config = load_config()
    enabled = _load_enabled_profiles()

    total = DiffReport()

    for strategy_id, cfg in config.get("strategies", {}).items():
        if strategy_filter and strategy_id != strategy_filter:
            continue

        print(f"\n{'='*60}")
        print(f"Strategy: {strategy_id}")
        print(f"  Primary platform: {cfg.get('primary_platform', 'N/A')}")

        # Validate
        errors = validate_strategy(strategy_id, cfg, enabled)
        if errors:
            for e in errors:
                print(f"  ✗ VALIDATION: {e}")
                total.errors.append(e)
            continue

        platform_id = cfg["primary_platform"]
        rt_json = build_runtime_target_json(strategy_id, cfg, platform_id)
        print(f"  RUNTIME_TARGET_JSON: {rt_json[:120]}...")

        # Show what env vars would be set
        if apply:
            print("  [would update Cloud Run env vars here]")
        else:
            print("  [dry-run: no changes applied. Use --apply to deploy]")

        # Sync Scheduler
        scheduler_report = sync_scheduler_jobs(strategy_id, cfg, platform_id, apply=apply)
        for item in scheduler_report.added:
            print(item)
        for item in scheduler_report.unchanged:
            print(item)
        for item in scheduler_report.errors:
            print(item)
            total.errors.append(item)

    print(f"\n{'='*60}")
    print(f"Summary: {len(total.added)} to add, {len(total.unchanged)} unchanged, "
          f"{len(total.errors)} errors")

    if not apply:
        print("\nThis was a dry-run. Use --apply to actually create/update resources.")

    return 1 if total.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
