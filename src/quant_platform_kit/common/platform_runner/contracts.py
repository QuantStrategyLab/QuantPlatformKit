"""Platform broker adapter protocol and common type definitions."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PlatformBrokerAdapter(Protocol):
    """每个平台必须实现的 broker 适配器接口。"""

    platform: str
    deploy_target: str = "cloud_run"

    def get_project_id(self) -> str: ...

    def load_settings(self) -> Any: ...

    def build_composer(self, settings: Any) -> Any: ...

    def run_strategy_cycle(self, composer: Any, dry_run: bool = False) -> dict: ...
