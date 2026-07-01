"""Unified health monitor — one API for every deployment type.

    from quant_platform_kit.common.health import HealthMonitor

    # Cloud Run / Flask
    monitor = HealthMonitor(app=flask_app, cycle_callback=get_report)
    monitor.start()

    # VPS CLI — HTTP endpoint on port 8080
    monitor = HealthMonitor(http_port=8080)
    monitor.start()
    monitor.beat(status="ok")  # call each cycle

    # Self-hosted — file-based (no cloud deps)
    monitor = HealthMonitor(file_path="/tmp/qsl.heartbeat")
    monitor.beat(status="ok")

    # Binance — Firestore (auto-detected if GOOGLE_APPLICATION_CREDENTIALS set)
    monitor = HealthMonitor()  # auto: Firestore > file fallback
    monitor.beat(status="ok", error="", cycle_count=1)

    # Watchdog — run anywhere (cron / GitHub Actions / UptimeRobot):
    qsl_watchdog.py --url https://my-service/health
    qsl_watchdog.py --file /tmp/qsl.heartbeat
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Heartbeat:
    status: str = "ok"
    timestamp: str = ""
    uptime_seconds: int = 0
    cycle_count: int = 0
    last_error: str = ""
    version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "timestamp": self.timestamp or datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": self.uptime_seconds,
            "cycle_count": self.cycle_count,
            "last_error": self.last_error,
            "version": self.version,
        }


# ---------------------------------------------------------------------------
# Pluggable backends
# ---------------------------------------------------------------------------

class HealthBackend(Protocol):
    def write(self, hb: Heartbeat) -> None: ...
    def read(self) -> Heartbeat | None: ...


class _FileBackend:
    """Zero-dependency file heartbeat — works on any OS."""
    def __init__(self, path: str = "/tmp/qsl.heartbeat"):
        self.path = Path(path)

    def write(self, hb: Heartbeat) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(hb.to_dict(), ensure_ascii=False))

    def read(self) -> Heartbeat | None:
        if not self.path.exists():
            return None
        d = json.loads(self.path.read_text())
        return Heartbeat(**{k: d.get(k, "") for k in Heartbeat.__dataclass_fields__})


class _FirestoreBackend:
    """Firestore heartbeat — for GCP-connected deployments."""
    def __init__(self, collection: str = "health", document: str = "alive"):
        self.collection = collection
        self.document = document

    def _client(self):
        from google.cloud import firestore
        return firestore.Client()

    def write(self, hb: Heartbeat) -> None:
        try:
            self._client().collection(self.collection).document(self.document).set(hb.to_dict(), merge=True)
        except Exception:
            pass

    def read(self) -> Heartbeat | None:
        try:
            doc = self._client().collection(self.collection).document(self.document).get()
            if not doc.exists:
                return None
            d = doc.to_dict() or {}
            return Heartbeat(**{k: d.get(k, "") for k in Heartbeat.__dataclass_fields__})
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Unified monitor
# ---------------------------------------------------------------------------

class HealthMonitor:
    """One API for all platforms.

    Call `monitor.beat()` each cycle. The right backend is selected automatically
    or explicitly via constructor args.
    """

    def __init__(
        self,
        *,
        app=None,                # Flask app → adds /health endpoint
        http_port: int = 0,      # Start standalone HTTP server on this port
        file_path: str = "",     # Use file backend at this path
        backend: HealthBackend | None = None,  # Explicit backend (overrides auto-detect)
    ):
        self._app = app
        self._http_port = http_port
        self._file_path = file_path
        self._backend = backend or self._auto_backend()
        self._start_time = datetime.now(timezone.utc)
        self._cycle_count = 0
        self._last_error = ""

    def _auto_backend(self) -> HealthBackend:
        if self._file_path:
            return _FileBackend(self._file_path)
        # Auto-detect: try Firestore if GCP creds are set, otherwise file
        try:
            import os
            if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or os.environ.get("FIRESTORE_EMULATOR_HOST"):
                return _FirestoreBackend()
        except Exception:
            pass
        return _FileBackend()

    # -- lifecycle --

    def start(self) -> HealthMonitor:
        """Start HTTP health endpoint. Must be called exactly once."""
        if self._app is not None:
            self._register_flask()
        elif self._http_port > 0:
            self._start_http_server()
        return self

    def beat(self, *, status: str = "ok", error: str = "", cycle_count: int | None = None) -> None:
        """Write a heartbeat. Call this once per cycle."""
        if cycle_count is not None:
            self._cycle_count = cycle_count
        if error:
            self._last_error = error
        uptime = int((datetime.now(timezone.utc) - self._start_time).total_seconds())
        self._backend.write(Heartbeat(
            status=status,
            uptime_seconds=uptime,
            cycle_count=self._cycle_count,
            last_error=self._last_error,
        ))

    def read(self) -> Heartbeat | None:
        return self._backend.read()

    # -- HTTP endpoints --

    def _register_flask(self) -> None:
        from flask import jsonify

        def qpk_health():
            return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})

        existing_rules = {getattr(rule, "rule", "") for rule in self._app.url_map.iter_rules()}
        if "/health" not in existing_rules:
            self._app.add_url_rule(
                "/health",
                endpoint="qpk_health",
                view_func=qpk_health,
                methods=["GET"],
            )
        if "/healthz" not in existing_rules:
            self._app.add_url_rule(
                "/healthz",
                endpoint="qpk_healthz",
                view_func=qpk_health,
                methods=["GET"],
            )

    def _start_http_server(self) -> None:
        import http.server
        port = self._http_port

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in ("/health", "/healthz"):
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"status":"ok"}')
                else:
                    self.send_response(404)
                    self.end_headers()
            def log_message(self, fmt, *args):
                pass

        server = http.server.HTTPServer(("0.0.0.0", port), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()


# ---------------------------------------------------------------------------
# Flask convenience (backward compat)
# ---------------------------------------------------------------------------

def register_health_endpoint(app) -> None:
    """Add GET /health to a Flask app. Legacy shim — prefer HealthMonitor(app=app).start()."""
    HealthMonitor(app=app).start()


# ---------------------------------------------------------------------------
# CLI watchdog helpers
# ---------------------------------------------------------------------------

def is_heartbeat_fresh(hb: Heartbeat | None, max_age_seconds: int = 300) -> bool:
    if hb is None or not hb.timestamp:
        return False
    try:
        ts = datetime.fromisoformat(hb.timestamp.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - ts).total_seconds() <= max_age_seconds
    except (ValueError, TypeError):
        return False


def check_alive(
    *,
    url: str = "",
    file_path: str = "",
    max_age_seconds: int = 300,
) -> tuple[bool, str]:
    """Check service health — HTTP endpoint or file heartbeat."""
    # HTTP check
    if url:
        import urllib.request
        try:
            with urllib.request.urlopen(f"{url.rstrip('/')}/health", timeout=10) as r:
                return (True, "OK") if r.status == 200 else (False, f"HTTP {r.status}")
        except Exception as e:
            return (False, f"{type(e).__name__}")

    # File check
    if file_path:
        backend = _FileBackend(file_path)
        hb = backend.read()
        return (True, "OK") if is_heartbeat_fresh(hb, max_age_seconds) else (False, "stale")

    return (False, "no check method")


# Backward-compat re-exports
FileHeartbeat = _FileBackend
FirestoreHeartbeat = _FirestoreBackend
check_service_alive = check_alive
