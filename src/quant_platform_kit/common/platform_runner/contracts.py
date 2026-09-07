"""Platform broker adapter protocol and common type definitions."""

from __future__ import annotations

import warnings
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PlatformBrokerAdapter(Protocol):
    """Deprecated optional sketch — not consumed by CS/IBKR/LB runtimes.

    Kept for reference only. Do not add isinstance checks or new platform
    implementations against this Protocol until a real shared consumer exists.
    Prefer concrete platform composers and QPK broker SDK helpers instead.
    """

    platform: str
    deploy_target: str = "cloud_run"

    def get_project_id(self) -> str: ...

    def load_settings(self) -> Any: ...

    def build_composer(self, settings: Any) -> Any: ...

    def run_strategy_cycle(self, composer: Any, dry_run: bool = False) -> dict: ...


def warn_platform_broker_adapter_unused() -> None:
    """Emit a one-line deprecation notice for docs/tests; no runtime side effects."""
    warnings.warn(
        "PlatformBrokerAdapter is unused by production platforms; treat as deprecated sketch.",
        DeprecationWarning,
        stacklevel=2,
    )
