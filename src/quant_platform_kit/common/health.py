"""Platform-agnostic health check and watchdog framework.

Supports multiple backends so open-source users can self-host with whatever
infrastructure they have — VPS, Cloud Run, GCP, AWS, or bare metal.

Usage per deployment type
-------------------------
Cloud Run / Flask:
    from quant_platform_kit.common.health import register_health_endpoint
    register_health_endpoint(app)  # adds GET /health

VPS / CLI (file-based):
    from quant_platform_kit.common.health import FileHeartbeat
    hb = FileHeartbeat("/var/run/qsl/heartbeat.json")
    hb.beat(status="ok")

Firestore (for Binance):
    from quant_platform_kit.common.health import FirestoreHeartbeat
    hb = FirestoreHeartbeat(collection="health", document="alive")
    hb.beat(status="ok")

Watchdog (GitHub Actions):
    curl -f https://myservice.run.app/health || send_telegram("DOWN")

Watchdog (cron on VPS):
    */5 * * * * curl -f http://localhost:8080/health || notify_error
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol


# ---------------------------------------------------------------------------
# Heartbeat data model
# ---------------------------------------------------------------------------

@dataclass
class Heartbeat:
    status: str = "ok"
    timestamp: str = ""
    uptime_seconds: int = 0
    cycle_count: int = 0
    last_error: str = ""
    version: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "timestamp": self.timestamp or datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": self.uptime_seconds,
            "cycle_count": self.cycle_count,
            "last_error": self.last_error,
            "version": self.version,
            **dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# Backend protocols
# ---------------------------------------------------------------------------

class HeartbeatWriter(Protocol):
    def write(self, heartbeat: Heartbeat) -> None:
        ...


class HeartbeatReader(Protocol):
    def read(self) -> Heartbeat | None:
        ...


# ---------------------------------------------------------------------------
# File-based heartbeat (for VPS / bare-metal / self-hosted)
# ---------------------------------------------------------------------------

class FileHeartbeat:
    """Write heartbeat to a local JSON file.  Suitable for VPS / bare-metal."""

    def __init__(self, path: str | Path):
        self._path = Path(path)

    def write(self, heartbeat: Heartbeat) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(heartbeat.to_dict(), ensure_ascii=False))

    def read(self) -> Heartbeat | None:
        if not self._path.exists():
            return None
        data = json.loads(self._path.read_text())
        return Heartbeat(
            status=str(data.get("status", "ok")),
            timestamp=str(data.get("timestamp", "")),
            uptime_seconds=int(data.get("uptime_seconds", 0)),
            cycle_count=int(data.get("cycle_count", 0)),
            last_error=str(data.get("last_error", "")),
            version=str(data.get("version", "")),
            metadata={k: v for k, v in data.items() if k not in Heartbeat.__dataclass_fields__},
        )


# ---------------------------------------------------------------------------
# Firestore heartbeat (for Binance VPS)
# ---------------------------------------------------------------------------

class FirestoreHeartbeat:
    """Write heartbeat to Google Firestore."""

    def __init__(self, collection: str = "health", document: str = "alive"):
        self._collection = collection
        self._document = document
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google.cloud import firestore  # lazy import
            self._client = firestore.Client()
        return self._client

    def write(self, heartbeat: Heartbeat) -> None:
        try:
            self._get_client().collection(self._collection).document(self._document).set(
                heartbeat.to_dict(), merge=True
            )
        except Exception:
            pass  # Firestore is best-effort; don't crash the main loop

    def read(self) -> Heartbeat | None:
        try:
            doc = self._get_client().collection(self._collection).document(self._document).get()
            if not doc.exists:
                return None
            data = doc.to_dict() or {}
            return Heartbeat(
                status=str(data.get("status", "ok")),
                timestamp=str(data.get("timestamp", "")),
                uptime_seconds=int(data.get("uptime_seconds", 0)),
                cycle_count=int(data.get("cycle_count", 0)),
                last_error=str(data.get("last_error", "")),
                version=str(data.get("version", "")),
            )
        except Exception:
            return None


# ---------------------------------------------------------------------------
# GCS heartbeat (for Cloud Run / GCP)
# ---------------------------------------------------------------------------

class GcsHeartbeat:
    """Write heartbeat to Google Cloud Storage."""

    def __init__(self, bucket: str, path: str = "health/heartbeat.json"):
        self._bucket = bucket
        self._path = path

    def write(self, heartbeat: Heartbeat) -> None:
        try:
            from google.cloud import storage  # lazy import
            client = storage.Client()
            bucket = client.bucket(self._bucket)
            blob = bucket.blob(self._path)
            blob.upload_from_string(json.dumps(heartbeat.to_dict()), content_type="application/json")
        except Exception:
            pass

    def read(self) -> Heartbeat | None:
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(self._bucket)
            blob = bucket.blob(self._path)
            if not blob.exists():
                return None
            data = json.loads(blob.download_as_text())
            return Heartbeat(**{k: data.get(k, "") for k in Heartbeat.__dataclass_fields__})
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Flask /health endpoint (for Cloud Run platforms)
# ---------------------------------------------------------------------------

def register_health_endpoint(app) -> None:
    """Add GET /health and GET /healthz to a Flask app."""
    from flask import jsonify

    @app.route("/health", methods=["GET"])
    @app.route("/healthz", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})


# ---------------------------------------------------------------------------
# HTTP health server for CLI apps (no Flask dependency)
# ---------------------------------------------------------------------------

def start_health_server(port: int = 8080, *, daemon: bool = True):
    """Start a minimal HTTP health server in a background thread.

    Suitable for CLI-based platforms that don't use Flask.
    """
    import http.server
    import threading

    class HealthHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/health", "/healthz"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode())
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # silent

    server = http.server.HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=daemon)
    thread.start()
    return server


# ---------------------------------------------------------------------------
# Watchdog helper (for external ping services)
# ---------------------------------------------------------------------------

def is_heartbeat_fresh(heartbeat: Heartbeat | None, max_age_seconds: int = 300) -> bool:
    """Return True if the heartbeat is recent enough to consider the service alive."""
    if heartbeat is None or not heartbeat.timestamp:
        return False
    try:
        ts = datetime.fromisoformat(heartbeat.timestamp.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        return age <= max_age_seconds
    except (ValueError, TypeError):
        return False


def check_service_alive(
    *,
    heartbeat_url: str = "",
    heartbeat_reader: HeartbeatReader | None = None,
    max_age_seconds: int = 300,
) -> tuple[bool, str]:
    """Check if a service is alive via HTTP endpoint or heartbeat reader.

    Returns (is_alive, detail_message).
    """
    # Try HTTP first
    if heartbeat_url:
        import urllib.request
        try:
            with urllib.request.urlopen(heartbeat_url + "/health", timeout=10) as resp:
                if resp.status == 200:
                    return True, "OK"
                return False, f"HTTP {resp.status}"
        except Exception as exc:
            return False, f"unreachable: {exc}"

    # Try heartbeat reader
    if heartbeat_reader is not None:
        hb = heartbeat_reader.read()
        if is_heartbeat_fresh(hb, max_age_seconds):
            return True, "OK"
        return False, "stale" if hb else "no heartbeat"

    return False, "no check method configured"
