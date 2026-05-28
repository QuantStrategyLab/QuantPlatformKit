"""QuantPlatformKit package.

Keep the package import lightweight while preserving compatibility exports
used by older strategy repositories.
"""

__version__ = "0.7.35"

from .common.models import (
    ExecutionReport,
    OrderIntent,
    PortfolioSnapshot,
    Position,
    PricePoint,
    PriceSeries,
    QuoteSnapshot,
    StrategyDecision,
)
from .common.runtime_inputs import (
    build_semiconductor_rotation_indicators_from_history,
    build_semiconductor_rotation_inputs_from_history,
    build_strategy_evaluation_inputs,
)

__all__ = [
    "__version__",
    "ExecutionReport",
    "OrderIntent",
    "PortfolioSnapshot",
    "Position",
    "PricePoint",
    "PriceSeries",
    "QuoteSnapshot",
    "StrategyDecision",
    "build_semiconductor_rotation_indicators_from_history",
    "build_semiconductor_rotation_inputs_from_history",
    "build_strategy_evaluation_inputs",
]
