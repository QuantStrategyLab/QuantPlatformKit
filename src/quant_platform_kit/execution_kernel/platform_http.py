"""Platform HTTP composition helpers (template for execution runtimes).

Downstream platform repositories (CharlesSchwabPlatform, BinancePlatform,
InteractiveBrokersPlatform, LongBridgePlatform, …) historically kept Flask
route tables, runtime wiring and notification fallbacks in a single
``main.py``. Wave2 platform redos follow this thin-main + explicit re-export
layout (CharlesSchwabPlatform is the reference):

Module split
------------
- ``http_routes.py`` — Flask app + HTTP handlers (``/run``, ``/dry-run``, …)
- ``runtime_wiring.py`` — composer / broker / strategy assembly
- ``notifications_runtime.py`` — channel adapters and failure notifications
- ``strategy_plugins_runtime.py`` — plugin signal presentation
- ``platform_entry.py`` — late-bound entry lookup for monkeypatch-friendly tests
- ``main.py`` — thin process entry: named imports + ``__all__`` + ``app.run``

Thin ``main.py`` contract (explicit re-exports; no ``import *`` as the API)
---------------------------------------------------------------------------
Prefer named imports that re-export the public surface, then list the same
names in ``__all__``:

.. code-block:: python

    from runtime_wiring import build_composer, validate_config, ...
    from notifications_runtime import publish_notification, ...
    from strategy_plugins_runtime import load_strategy_plugin_signals, ...
    from http_routes import app, handle_schwab, health, ...

    import platform_entry as _platform_entry
    _platform_entry.bind(__import__("sys").modules[__name__])

    __all__ = [
        "app",
        "build_composer",
        "handle_schwab",
        "health",
        # …every symbol tests or Gunicorn may patch/import from main
    ]

    if __name__ == "__main__":
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

Do not use ``from http_routes import *`` (or similar) as the sole public API:
patch targets and review diffs must stay name-stable. Keep implementation in
the split modules; ``main`` only binds and re-exports.

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
        "main": (
            "Thin process entry: explicit named re-exports + __all__; "
            "bind host/port only (no import * as the public API)."
        ),
        "http_routes": "Flask/FastAPI app factory and route handlers.",
        "runtime_wiring": "Build composer, broker adapters, strategy adapters.",
        "notifications_runtime": "Notification publish and runtime-error fallback.",
        "strategy_plugins_runtime": "Plugin signal lines and alert fan-out.",
        "platform_entry": "Late-bound entry module for monkeypatch-friendly tests.",
    }


def describe_platform_thin_main_rules() -> Mapping[str, str]:
    """Return the Wave2 thin-main re-export rules platforms should follow."""
    return {
        "explicit_reexports": "Use named imports from split modules into main.",
        "all_list": "Mirror every re-exported public name in main.__all__.",
        "no_star_api": "Do not use import * as the sole public surface.",
        "entry_bind": "Bind platform_entry to the process main module for patches.",
        "behavior": "Preserve route and execute_cycle behavior while splitting.",
    }
