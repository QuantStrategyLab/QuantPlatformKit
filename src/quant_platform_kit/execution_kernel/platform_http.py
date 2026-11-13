"""Platform HTTP composition helpers (template for execution runtimes).

Downstream platform repositories (CharlesSchwabPlatform, BinancePlatform, …)
historically kept Flask route tables, runtime wiring and notification fallbacks
in a single ``main.py``. Prefer the local split pattern already applied in
CharlesSchwabPlatform:

- ``http_routes.py`` — Flask app + HTTP handlers
- ``runtime_wiring.py`` — composer / broker / strategy assembly
- ``notifications_runtime.py`` — channel adapters and failure notifications
- ``strategy_plugins_runtime.py`` — plugin signal presentation
- ``main.py`` — thin entry (``app.run`` / ASGI)

This module intentionally stays documentation-oriented until a coordinated
QPK pin upgrades all platforms to share one Flask factory. Do not import it
from live order paths yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class PlatformHttpSurface:
    """Named callables a platform HTTP layer should expose.

    Matches the organization route contract: ``/run``, ``/dry-run``,
    ``/health``, ``/probe``, ``/monitor-dispatch``.
    """

    run: Callable[..., Any]
    dry_run: Callable[..., Any]
    health: Callable[..., Any]
    probe: Callable[..., Any] | None = None
    monitor_dispatch: Callable[..., Any] | None = None


def describe_platform_http_modules() -> Mapping[str, str]:
    """Return the recommended module layout for a platform repository."""
    return {
        "main": "Thin process entry; bind host/port only.",
        "http_routes": "Flask/FastAPI app factory and route handlers.",
        "runtime_wiring": "Build composer, broker adapters, strategy adapters.",
        "notifications_runtime": "Notification publish and runtime-error fallback.",
        "strategy_plugins_runtime": "Plugin signal lines and alert fan-out.",
    }
