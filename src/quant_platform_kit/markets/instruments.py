"""Instrument specifications across equities, ETFs, futures, and crypto."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum


class AssetClass(str, Enum):
    """Supported tradable asset classes."""

    EQUITY = "equity"
    ETF = "etf"
    FUTURE = "future"
    CRYPTO = "crypto"
    OPTION = "option"


class MarginMode(str, Enum):
    """Account/contract margin valuation model."""

    CASH = "cash"
    REG_T_MARGIN = "reg_t_margin"
    PORTFOLIO_MARGIN = "portfolio_margin"
    FUTURES_SPAN = "futures_span"


def _to_decimal(value: Decimal | int | str, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric, not bool")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, (int, str)):
        try:
            result = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"Invalid {field_name}: {value!r}") from exc
    else:
        raise ValueError(f"{field_name} must be Decimal, int, or str")
    if not result.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return result


@dataclass(frozen=True)
class InstrumentSpec:
    """Contract-level execution specification for multi-market order sizing and risk."""

    symbol: str
    market: str
    asset_class: AssetClass
    currency: str
    lot_size: Decimal = Decimal("1")
    multiplier: Decimal = Decimal("1")
    tick_size: Decimal = Decimal("0.01")
    margin_mode: MarginMode = MarginMode.CASH
    allow_short: bool = False
    expiry_date: date | None = None
    roll_days_before_expiry: int = 5

    def __post_init__(self) -> None:
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol must be non-empty")
        if not self.market or not self.market.strip():
            raise ValueError("market must be non-empty")
        if not self.currency or not self.currency.strip():
            raise ValueError("currency must be non-empty")

        lot = _to_decimal(self.lot_size, "lot_size")
        mult = _to_decimal(self.multiplier, "multiplier")
        tick = _to_decimal(self.tick_size, "tick_size")
        if lot <= 0:
            raise ValueError("lot_size must be positive")
        if mult <= 0:
            raise ValueError("multiplier must be positive")
        if tick <= 0:
            raise ValueError("tick_size must be positive")
        object.__setattr__(self, "lot_size", lot)
        object.__setattr__(self, "multiplier", mult)
        object.__setattr__(self, "tick_size", tick)

        if self.roll_days_before_expiry < 0:
            raise ValueError("roll_days_before_expiry must be non-negative")
        if self.asset_class == AssetClass.FUTURE and self.expiry_date is None:
            raise ValueError("expiry_date is required for FUTURE instruments")

    def round_quantity_to_lot(self, raw_quantity: Decimal | int | str) -> Decimal:
        """Floor a non-negative quantity down to the nearest multiple of lot_size."""
        qty = _to_decimal(raw_quantity, "raw_quantity")
        if qty < 0:
            raise ValueError("raw_quantity must be non-negative")
        return (qty // self.lot_size) * self.lot_size

    def validate_order_quantity(
        self,
        quantity: Decimal | int | str,
        *,
        allow_odd_lot: bool = False,
    ) -> Decimal:
        """Validate a positive order quantity against lot_size constraints."""
        qty = _to_decimal(quantity, "quantity")
        if qty <= 0:
            raise ValueError("order quantity must be positive")
        if not allow_odd_lot and (qty % self.lot_size) != 0:
            raise ValueError(
                f"quantity {qty} for {self.symbol} must be a multiple of lot_size {self.lot_size}"
            )
        return qty

    def notional_value(
        self,
        quantity: Decimal | int | str,
        price: Decimal | int | str,
    ) -> Decimal:
        """Compute contract notional value using abs(quantity) * price * multiplier."""
        qty = _to_decimal(quantity, "quantity")
        px = _to_decimal(price, "price")
        if px < 0:
            raise ValueError("price must be non-negative")
        return abs(qty) * px * self.multiplier

    def should_roll(self, as_of: date) -> bool:
        """Return True when an expiring contract is inside its roll window."""
        if self.expiry_date is None:
            return False
        return (self.expiry_date - as_of).days <= self.roll_days_before_expiry
