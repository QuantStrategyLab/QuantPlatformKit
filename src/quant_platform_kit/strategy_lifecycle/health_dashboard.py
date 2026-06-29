"""Unified health dashboard — cross-market, cross-strategy aggregated view."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quant_platform_kit.strategy_lifecycle.contracts import StrategyHealthScore
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore
from quant_platform_kit.strategy_lifecycle.strategy_health_score import compute_health_score


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_dashboard(
    *,
    output_dir: str | None = None,
    output_format: str = "all",
    domains: Sequence[str] | None = None,
    store: PerformanceStore | None = None,
) -> dict[str, Any]:
    """Build the unified strategy health dashboard.

    Args:
        output_dir: Directory for output artifacts.
        output_format: "html", "telegram", "markdown", "email", or "all".
        domains: Domains to include; defaults to all.
        store: PerformanceStore instance.

    Returns:
        Dict with dashboard summary including strategy_count and output paths.
    """
    store = store or PerformanceStore.from_env()
    domains = list(domains) if domains else ["us_equity", "crypto", "hk_equity", "cn_equity"]

    # 1. Collect health scores
    all_scores: list[StrategyHealthScore] = []
    for domain in domains:
        try:
            snapshots = _collect_domain_snapshots(domain, store)
            drift_results = _collect_domain_drifts(domain, store)
            for profile, snapshot in snapshots.items():
                drift = drift_results.get(profile)
                score = compute_health_score(snapshot, drift=drift)
                all_scores.append(score)
        except Exception:
            continue

    # Sort by score (worst first)
    all_scores.sort(key=lambda s: s.overall_score)

    # 2. Persist
    store.save_dashboard(all_scores)

    # 3. Render outputs
    outputs: dict[str, str] = {}
    out_dir = Path(output_dir) if output_dir else Path.cwd() / "dashboard_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    if output_format in ("markdown", "all"):
        md_path = out_dir / "strategy_health_dashboard.md"
        md_path.write_text(_render_markdown(all_scores), encoding="utf-8")
        outputs["markdown"] = str(md_path)

    if output_format in ("telegram", "all"):
        tg_path = out_dir / "strategy_health_telegram.txt"
        tg_path.write_text(_render_telegram(all_scores), encoding="utf-8")
        outputs["telegram"] = str(tg_path)

    if output_format in ("json", "all"):
        json_path = out_dir / "strategy_health_dashboard.json"
        json_path.write_text(
            json.dumps(
                {
                    "computed_at": _now_iso(),
                    "strategy_count": len(all_scores),
                    "strategies": [s.to_dict() for s in all_scores],
                    "summary": _build_summary(all_scores),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        outputs["json"] = str(json_path)

    return {
        "strategy_count": len(all_scores),
        **{k: v for k, v in _build_summary(all_scores).items()},
        "outputs": outputs,
    }


def _build_summary(scores: list[StrategyHealthScore]) -> dict[str, int]:
    healthy = sum(1 for s in scores if s.status == "healthy")
    watch = sum(1 for s in scores if s.status == "watch")
    review = sum(1 for s in scores if s.status == "review")
    critical = sum(1 for s in scores if s.status == "critical")
    return {"healthy": healthy, "watch": watch, "review": review, "critical": critical}


# ── Renderers ───────────────────────────────────────────────────────


def _render_markdown(scores: list[StrategyHealthScore]) -> str:
    lines = [
        "# Strategy Health Dashboard",
        "",
        f"Generated: {_now_iso()}",
        "",
        "## Summary",
        "",
        "| Status | Count |",
        "| --- | ---: |",
    ]
    summary = _build_summary(scores)
    for status, emoji in [("healthy", "✅"), ("watch", "⚠️"), ("review", "🔴"), ("critical", "🚨")]:
        if summary[status]:
            lines.append(f"| {emoji} {status.title()} | {summary[status]} |")

    # Group by domain
    lines.extend(["", "## Strategies by Domain", ""])
    domains: dict[str, list[StrategyHealthScore]] = {}
    for s in scores:
        domains.setdefault(s.domain, []).append(s)

    for domain, domain_scores in domains.items():
        lines.extend(
            [
                f"### {domain.replace('_', ' ').title()}",
                "",
                "| Strategy | Score | Perf | Risk | Decay | Stable | Ops | Status |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for s in domain_scores:
            status_emoji = _status_emoji(s.status)
            lines.append(
                f"| {s.strategy_profile} | {s.overall_score:.0f} | {s.performance_score:.0f} | {s.risk_score:.0f} | "
                f"{s.decay_score:.0f} | {s.stability_score:.0f} | {s.operational_score:.0f} | {status_emoji} {s.status} |"
            )
        lines.append("")

    return "\n".join(lines)


def _render_telegram(scores: list[StrategyHealthScore]) -> str:
    """Render a compact Telegram message (fits in a single notification)."""
    summary = _build_summary(scores)
    lines = [
        "📊 Strategy Health Dashboard",
        f"🕐 {_now_iso()[:19]}",
        "",
        f"✅ Healthy: {summary['healthy']}  ⚠️ Watch: {summary['watch']}  🔴 Review: {summary['review']}  🚨 Critical: {summary['critical']}",
        "",
    ]

    # Show non-healthy strategies
    alerts = [s for s in scores if s.status != "healthy"]
    if alerts:
        lines.append("⚠️ Alerts:")
        for s in alerts[:10]:  # Telegram message length limit
            emoji = _status_emoji(s.status)
            lines.append(f"  {emoji} [{s.domain}] {s.strategy_profile}: score={s.overall_score:.0f}")
    else:
        lines.append("✅ All strategies healthy")

    return "\n".join(lines)


def _status_emoji(status: str) -> str:
    return {"healthy": "✅", "watch": "⚠️", "review": "🔴", "critical": "🚨"}.get(status, "❓")


# ── Collectors ──────────────────────────────────────────────────────


def _collect_domain_snapshots(domain: str, store: PerformanceStore) -> Mapping[str, Any]:
    """Collect latest snapshots for all strategies in a domain."""
    # Use the return collector to discover what strategies exist
    from quant_platform_kit.strategy_lifecycle.return_collector import ReturnCollector

    collector = ReturnCollector()
    all_returns = collector.collect(domain)
    result: dict[str, Any] = {}
    for profile in all_returns:
        snap = store.load_latest_snapshot(domain, profile)
        if snap is not None:
            result[profile] = snap
    return result


def _collect_domain_drifts(domain: str, store: PerformanceStore) -> Mapping[str, Any]:
    """Collect latest drift results for all strategies in a domain."""
    from quant_platform_kit.strategy_lifecycle.return_collector import ReturnCollector

    collector = ReturnCollector()
    all_returns = collector.collect(domain)
    result: dict[str, Any] = {}
    for profile in all_returns:
        drift = store.load_latest_drift(domain, profile)
        if drift is not None:
            result[profile] = drift
    return result
