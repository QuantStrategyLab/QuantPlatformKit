from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .models import ExecutionReport, OrderIntent, PortfolioSnapshot, PriceSeries, QuoteSnapshot
from .ports import ExecutionPort, MarketDataPort, NotificationPort, PortfolioPort


@dataclass(frozen=True)
class CallableNotificationPort(NotificationPort):
    sender: Callable[[str], None]

    def send_text(self, message: str) -> None:
        self.sender(message)


@dataclass(frozen=True)
class CallablePortfolioPort(PortfolioPort):
    loader: Callable[[], PortfolioSnapshot]

    def get_portfolio_snapshot(self) -> PortfolioSnapshot:
        return self.loader()


@dataclass(frozen=True)
class CallableExecutionPort(ExecutionPort):
    submitter: Callable[[OrderIntent], ExecutionReport]

    def submit_order(self, order: OrderIntent) -> ExecutionReport:
        return self.submitter(order)


@dataclass(frozen=True)
class CallableMarketDataPort(MarketDataPort):
    quote_loader: Callable[[str], QuoteSnapshot]
    price_series_loader: Callable[[str], PriceSeries] | None = None

    def get_price_series(self, symbol: str, *, start=None, end=None) -> PriceSeries:
        del start, end
        if self.price_series_loader is None:
            raise NotImplementedError("This CallableMarketDataPort does not provide historical price series.")
        return self.price_series_loader(symbol)

    def get_quote(self, symbol: str) -> QuoteSnapshot:
        return self.quote_loader(symbol)
