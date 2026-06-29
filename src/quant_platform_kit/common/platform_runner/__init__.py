"""Platform runner — 平台服务通用框架。

Provides shared templates for strategy loading, monitoring dispatch,
and platform boilerplate that was previously duplicated across
IBKR, LongBridge, Schwab, and Firstrade platforms.
"""
from .loader import (
    load_strategy_definition,
    load_strategy_entrypoint_for_profile,
    load_strategy_runtime_adapter_for_profile,
)
from .monitor import dispatch_due_monitors, load_monitor_targets
