#!/usr/bin/env python3
"""Universal QSL watchdog — ping health endpoints and alert on failure.

Works with any deployment type:
  Cloud Run:  qsl_watchdog.py --url https://my-service.run.app
  VPS:        qsl_watchdog.py --file /var/run/qsl/heartbeat.json
  Firestore:  qsl_watchdog.py --firestore health/alive

Exit code 0 = alive, 1 = dead (integrates with cron / GitHub Actions).
"""
from __future__ import annotations

import argparse
import os
import sys


def send_telegram(message: str) -> bool:
    token = (os.environ.get("TELEGRAM_TOKEN") or os.environ.get("TG_TOKEN") or "").strip()
    chat_id = (os.environ.get("GLOBAL_TELEGRAM_CHAT_ID") or os.environ.get("TG_CHAT_ID") or "").strip()
    if not token or not chat_id:
        print("No Telegram config; cannot send alert.", file=sys.stderr)
        return False
    import json, urllib.request
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps({"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def main() -> int:
    p = argparse.ArgumentParser(description="QSL health watchdog")
    p.add_argument("--url", help="HTTP health endpoint URL")
    p.add_argument("--file", help="Local heartbeat file path")
    p.add_argument("--firestore", help="Firestore collection/document (e.g. health/alive)")
    p.add_argument("--name", default="QSL Platform", help="Service name for alert messages")
    p.add_argument("--max-age", type=int, default=300, help="Max heartbeat age in seconds")
    p.add_argument("--alert", action="store_true", help="Send Telegram alert on failure")
    args = p.parse_args()

    from quant_platform_kit.common.health import check_service_alive, FileHeartbeat, FirestoreHeartbeat

    reader = None
    if args.file:
        reader = FileHeartbeat(args.file)
    elif args.firestore:
        parts = args.firestore.split("/")
        reader = FirestoreHeartbeat(parts[0], parts[1] if len(parts) > 1 else "alive")

    alive, detail = check_service_alive(
        heartbeat_url=args.url,
        heartbeat_reader=reader,
        max_age_seconds=args.max_age,
    )

    if alive:
        print(f"✅ {args.name}: {detail}")
        return 0

    msg = f"🚨 *{args.name}* health check FAILED: `{detail}`"
    print(f"❌ {args.name}: {detail}")
    if args.alert:
        send_telegram(msg)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
