"""Display-only attention evidence. Never infer financial facts or run links."""
from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo


def masked_account(value: object, locale: str) -> str:
    raw = str(value or "").strip()
    label = "账户未知" if locale == "zh" else "Account unknown"
    if raw.lower() in {"", "unknown", "none", "account", "账户"}:
        return label
    # Mask all aliases too: a display mapping may itself contain a raw account ID.
    return "••" + raw[-2:] if len(raw) >= 2 else label


def _stamp(value: object, zone: str, pattern: str) -> str | None:
    try:
        stamp = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            return None
        return stamp.astimezone(ZoneInfo(zone)).strftime(pattern)
    except (ValueError, TypeError, OverflowError):
        return None


def _money(value: object, unknown: str) -> str:
    if value is None or isinstance(value, bool):
        return unknown
    try:
        number = float(value)
        return f"USD {number:,.2f}" if math.isfinite(number) else unknown
    except (TypeError, ValueError, OverflowError):
        return unknown


def attention_details(*, locale: str, daily_loss_context: Mapping | None,
                      occurred_at: object, run_url: str | None) -> list[str]:
    zh = locale == "zh"
    unknown = "未知" if zh else "Unknown"
    context = daily_loss_context if isinstance(daily_loss_context, Mapping) else {}
    lines = []
    # This field is a baseline-relative loss, not necessarily intraday trading P&L.
    if context:
        verified = context.get("daily_loss_fact_status") == "verified"
        loss = _money(context.get("daily_loss_usd") if verified else None, unknown)
        limit = _money(context.get("max_daily_loss_usd"), unknown)
        lines.append(f"基准亏损 / 上限：{loss} / {limit}" if zh else f"Baseline loss / limit: {loss} / {limit}")
        baseline = _stamp(context.get("daily_loss_baseline_as_of"), "America/New_York", "%Y-%m-%d %H:%M") if verified else None
        if baseline:
            lines.append(f"基准：{baseline}（纽约时间）的账户运行快照" if zh else f"Baseline: account runtime snapshot at {baseline} New York time")
        else:
            lines.append("基准时间和来源待核对" if zh else "Baseline time and source require review")
    stamp = _stamp(occurred_at, "Asia/Singapore", "%Y-%m-%d %H:%M:%S SGT")
    lines.append(("运行时间：" if zh else "Run time: ") + (stamp or unknown))
    safe_url = None
    try:
        parsed = urlsplit(run_url or "")
        if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password and not any(c.isspace() for c in run_url or ""):
            # Strip query credentials/fragments; never derive a link from account IDs.
            safe_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    except ValueError:
        pass
    lines.append(("运行详情：" if zh else "Run details: ") + (safe_url or ("未提供运行链接" if zh else "Run link not provided")))
    return lines
