from __future__ import annotations

from datetime import date, datetime, time
from math import isnan
from typing import Any, Callable

from quant_platform_kit.common.models import PricePoint, PriceSeries, QuoteSnapshot


def _coerce_as_of(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    try:
        return datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"Unsupported IBKR date value: {value!r}") from exc


def _build_stock_contract(
    symbol: str,
    *,
    exchange: str,
    currency: str,
    stock_factory: Callable[..., Any] | None,
) -> Any:
    if stock_factory is None:
        from ib_insync import Stock

        stock_factory = Stock
    return stock_factory(symbol, exchange, currency)


def fetch_historical_price_series(
    ib: Any,
    symbol: str,
    *,
    duration: str = "2 Y",
    bar_size: str = "1 day",
    exchange: str = "SMART",
    currency: str = "USD",
    stock_factory: Callable[..., Any] | None = None,
) -> PriceSeries:
    contract = _build_stock_contract(
        symbol,
        exchange=exchange,
        currency=currency,
        stock_factory=stock_factory,
    )
    ib.qualifyContracts(contract)
    bars = ib.reqHistoricalData(
        contract,
        endDateTime="",
        durationStr=duration,
        barSizeSetting=bar_size,
        whatToShow="ADJUSTED_LAST",
        useRTH=True,
        formatDate=1,
    )
    points = tuple(
        PricePoint(as_of=_coerce_as_of(bar.date), close=float(bar.close))
        for bar in bars or ()
    )
    return PriceSeries(symbol=symbol, currency=currency, points=points)


def _coerce_positive_price(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and isnan(value):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if numeric > 0 else None


def _extract_market_price(ticker: Any) -> float | None:
    for candidate in (
        ticker.marketPrice(),
        getattr(ticker, "last", None),
        getattr(ticker, "close", None),
    ):
        price = _coerce_positive_price(candidate)
        if price is not None:
            return price

    bid = _coerce_positive_price(getattr(ticker, "bid", None))
    ask = _coerce_positive_price(getattr(ticker, "ask", None))
    if bid is not None and ask is not None:
        return float((bid + ask) / 2.0)
    return bid or ask


def _set_market_data_type(ib: Any, market_data_type: int) -> None:
    setter = getattr(ib, "reqMarketDataType", None)
    if callable(setter):
        setter(market_data_type)



def _collect_quote_snapshots(
    ib: Any,
    contracts: list[tuple[str, Any]],
    *,
    wait_seconds: float,
    currency: str,
) -> dict[str, QuoteSnapshot]:
    requested = {
        symbol: ib.reqMktData(contract, "", False, False)
        for symbol, contract in contracts
    }
    if wait_seconds:
        import time as time_module

        time_module.sleep(wait_seconds)

    as_of = datetime.utcnow()
    snapshots: dict[str, QuoteSnapshot] = {}
    for symbol, contract in contracts:
        ib.cancelMktData(contract)
        ticker = requested[symbol]
        last_price = _extract_market_price(ticker)
        if last_price is None:
            continue

        bid = getattr(ticker, "bid", None)
        ask = getattr(ticker, "ask", None)
        snapshots[symbol] = QuoteSnapshot(
            symbol=symbol,
            as_of=as_of,
            last_price=last_price,
            bid_price=float(bid) if bid is not None and not (isinstance(bid, float) and isnan(bid)) else None,
            ask_price=float(ask) if ask is not None and not (isinstance(ask, float) and isnan(ask)) else None,
            currency=currency,
        )
    return snapshots



def fetch_quote_snapshots(
    ib: Any,
    symbols: list[str] | tuple[str, ...] | set[str],
    *,
    wait_seconds: float = 3.0,
    exchange: str = "SMART",
    currency: str = "USD",
    stock_factory: Callable[..., Any] | None = None,
) -> dict[str, QuoteSnapshot]:
    contracts: list[tuple[str, Any]] = []
    for symbol in symbols:
        contract = _build_stock_contract(
            symbol,
            exchange=exchange,
            currency=currency,
            stock_factory=stock_factory,
        )
        ib.qualifyContracts(contract)
        contracts.append((symbol, contract))

    snapshots = _collect_quote_snapshots(
        ib,
        contracts,
        wait_seconds=wait_seconds,
        currency=currency,
    )
    missing_contracts = [(symbol, contract) for symbol, contract in contracts if symbol not in snapshots]
    if not missing_contracts:
        return snapshots

    setter = getattr(ib, "reqMarketDataType", None)
    if not callable(setter):
        return snapshots

    try:
        for market_data_type in (2, 4):
            _set_market_data_type(ib, market_data_type)
            recovered = _collect_quote_snapshots(
                ib,
                missing_contracts,
                wait_seconds=wait_seconds,
                currency=currency,
            )
            snapshots.update(recovered)
            missing_contracts = [
                (symbol, contract)
                for symbol, contract in missing_contracts
                if symbol not in recovered
            ]
            if not missing_contracts:
                break
    finally:
        _set_market_data_type(ib, 1)

    return snapshots
