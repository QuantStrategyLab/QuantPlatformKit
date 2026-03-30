"""QuantPlatformKit public package surface."""

__version__ = "0.6.0"

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
from .common.strategies import (
    CRYPTO_DOMAIN,
    US_EQUITY_DOMAIN,
    StrategyDefinition,
    get_supported_profiles_for_platform,
    resolve_strategy_definition,
)

__all__ = [
    "__version__",
    "CRYPTO_DOMAIN",
    "ExecutionReport",
    "OrderIntent",
    "PortfolioSnapshot",
    "Position",
    "PricePoint",
    "PriceSeries",
    "QuoteSnapshot",
    "StrategyDefinition",
    "StrategyDecision",
    "US_EQUITY_DOMAIN",
    "get_supported_profiles_for_platform",
    "resolve_strategy_definition",
]
