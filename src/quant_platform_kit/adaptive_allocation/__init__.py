"""Read-only adaptive allocation contracts and Shadow selector.

This package deliberately has no broker, platform mutation, or order-routing
dependency.  It is the common decision-record layer used before any future
allocation automation is considered.
"""

from quant_platform_kit.adaptive_allocation.contracts import (
    AdaptiveSelectionPolicy,
    MarketContextSnapshot,
    PlatformHealthSnapshot,
    PluginRiskAdjustment,
    SelectionDecision,
    StrategyCandidate,
)
from quant_platform_kit.adaptive_allocation.selector import select_shadow

__all__ = [
    "AdaptiveSelectionPolicy",
    "MarketContextSnapshot",
    "PlatformHealthSnapshot",
    "PluginRiskAdjustment",
    "SelectionDecision",
    "StrategyCandidate",
    "select_shadow",
]
