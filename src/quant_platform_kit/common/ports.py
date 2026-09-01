from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .models import ExecutionReport, OrderIntent, PortfolioSnapshot, PriceSeries, QuoteSnapshot


class MarketDataPort(Protocol):
    """Legacy mixed market-data interface kept for adapter compatibility."""

    def get_price_series(self, symbol: str, *, start: datetime | None = None, end: datetime | None = None) -> PriceSeries:
        """Return historical close series for one symbol."""

    def get_quote(self, symbol: str) -> QuoteSnapshot:
        """Return the latest quote snapshot for one symbol."""


class DecisionDataArtifactPort(Protocol):
    """Load a verified, immutable strategy decision-data artifact.

    The binding identifier and digest are public-safe evidence.  Providers,
    paths, credentials, and transport belong to the implementing adapter.
    """

    def load_verified_price_series(
        self,
        symbol: str,
        *,
        binding_id: str,
        binding_sha256: str,
    ) -> PriceSeries:
        """Return a price series only when it matches the expected binding."""


class ExecutionQuotePort(Protocol):
    """Return a short-lived quote used only for execution safeguards."""

    def get_execution_quote(self, symbol: str) -> QuoteSnapshot:
        """Return the latest broker/execution quote for one symbol."""


class PortfolioPort(Protocol):
    def get_portfolio_snapshot(self) -> PortfolioSnapshot:
        """Return current account equity, buying power, cash, and positions."""


class ExecutionPort(Protocol):
    def submit_order(self, order: OrderIntent) -> ExecutionReport:
        """Submit one order intent and return the execution result."""


class NotificationPort(Protocol):
    def send_text(self, message: str) -> bool | None:
        """Send a plain-text notification."""


class StatePort(Protocol):
    def load(self, key: str) -> str | None:
        """Load one small serialized value."""

    def save(self, key: str, value: str) -> None:
        """Persist one small serialized value."""
