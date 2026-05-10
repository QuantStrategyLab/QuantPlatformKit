from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class PricePoint:
    as_of: datetime
    close: float
    volume: float | None = None


@dataclass(frozen=True)
class PriceSeries:
    symbol: str
    currency: str
    points: tuple[PricePoint, ...]

    @property
    def latest(self) -> PricePoint:
        if not self.points:
            raise ValueError("PriceSeries.points must not be empty.")
        return self.points[-1]


@dataclass(frozen=True)
class QuoteSnapshot:
    symbol: str
    as_of: datetime
    last_price: float
    bid_price: float | None = None
    ask_price: float | None = None
    currency: str = "USD"


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: float
    market_value: float
    average_cost: float | None = None
    currency: str = "USD"
    account_id: str | None = None


@dataclass(frozen=True)
class PortfolioSnapshot:
    as_of: datetime
    total_equity: float
    buying_power: float | None = None
    cash_balance: float | None = None
    positions: tuple[Position, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    side: str
    quantity: float
    order_type: str = "market"
    limit_price: float | None = None
    time_in_force: str | None = None
    account_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionReport:
    symbol: str
    side: str
    quantity: float
    status: str
    filled_quantity: float | None = None
    average_fill_price: float | None = None
    broker_order_id: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyDecision:
    as_of_date: date
    summary: str
    target_weights: dict[str, float]
    order_intents: tuple[OrderIntent, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
