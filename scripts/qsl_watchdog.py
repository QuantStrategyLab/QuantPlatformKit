#!/usr/bin/env python3
"""Universal QSL Watchdog — ping health endpoints, alert on failure.

Works for ANY deployment — Cloud Run, VPS, bare metal, self-hosted.

  Cloud Run:  qsl_watchdog.py --url https://my-service.run.app
  VPS HTTP:   qsl_watchdog.py --url http://my-vps:8080
  File-based: qsl_watchdog.py --file /tmp/qsl.heartbeat

Exit 0 = alive, 1 = dead.  Can be used with cron, GitHub Actions, or any scheduler.

Optional Telegram alert: set TELEGRAM_TOKEN + GLOBAL_TELEGRAM_CHAT_ID env vars.
"""
from __future__ import annotations

import argparse
import os
import sys


def _telegram_alert(message: str) -> bool:
    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    chat_id = os.environ.get("GLOBAL_TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False
    import json
    import urllib.request
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": chat_id, "text": message}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> int:
    p = argparse.ArgumentParser(description="Universal QSL health watchdog")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--url", help="HTTP health endpoint URL (e.g. https://svc.run.app or http://vps:8080)")
    g.add_argument("--file", help="Local heartbeat file path (e.g. /tmp/qsl.heartbeat)")
    p.add_argument("--name", default="QSL Platform", help="Service name for alerts")
    p.add_argument("--max-age", type=int, default=300, help="Max heartbeat age in seconds (default 300)")
    p.add_argument("--alert", action="store_true", help="Send Telegram alert on failure")
    args = p.parse_args()

    from quant_platform_kit.common.health import check_alive

    alive, detail = check_alive(url=args.url or "", file_path=args.file or "", max_age_seconds=args.max_age)

    if alive:
        print(f"✅ {args.name}: {detail}")
        return 0

    msg = f"🚨 *{args.name}* DOWN: {detail}"
    print(f"❌ {msg}")
    if args.alert:
        _telegram_alert(msg)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
