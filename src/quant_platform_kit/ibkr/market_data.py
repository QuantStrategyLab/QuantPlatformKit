from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from math import ceil
from math import isfinite, isnan
import re
from typing import Any, Callable, Sequence

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


def _coerce_expiration(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return datetime.fromisoformat(text[:10]).date()
    except ValueError:
        return None


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


def _build_option_contract(
    symbol: str,
    expiration: str,
    strike: float,
    right: str,
    *,
    exchange: str,
    currency: str,
    option_factory: Callable[..., Any] | None,
) -> Any:
    if option_factory is None:
        from ib_insync import Option

        option_factory = Option
    return option_factory(
        symbol,
        expiration,
        float(strike),
        str(right).strip().upper(),
        exchange=exchange,
        currency=currency,
    )


def _normalize_duration_for_ibkr(duration: str) -> str:
    text = str(duration or "").strip()
    match = re.fullmatch(r"(\d+)\s*([A-Za-z]+)", text)
    if not match:
        return text

    quantity = int(match.group(1))
    unit = match.group(2).upper()
    if unit == "D" and quantity > 365:
        return f"{ceil(quantity / 365)} Y"
    return f"{quantity} {unit}"


class StrictAdjustedHistoryError(RuntimeError):
    """A strict adjusted-history request or response violated its contract."""


@dataclass(frozen=True)
class AdjustedHistoricalCandle:
    session: date
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class StrictAdjustedHistoryProvenance:
    symbol: str
    exchange: str
    currency: str
    end_datetime: str
    duration: str
    bar_size: str
    what_to_show: str
    use_rth: bool
    format_date: int
    keep_up_to_date: bool
    returned_row_count: int


@dataclass(frozen=True)
class StrictAdjustedHistoryResult:
    candles: tuple[AdjustedHistoricalCandle, ...]
    provenance: StrictAdjustedHistoryProvenance


def _strict_history_request_inputs(
    symbol: str,
    *,
    end_datetime: datetime,
    duration: str,
    expected_sessions: Sequence[date],
) -> tuple[str, datetime, str, tuple[date, ...]]:
    if not isinstance(symbol, str) or re.fullmatch(r"[A-Z][A-Z0-9.-]*", symbol) is None:
        raise StrictAdjustedHistoryError("strict_adjusted_history:invalid_symbol")
    if (
        not isinstance(end_datetime, datetime)
        or end_datetime.tzinfo is None
        or end_datetime.utcoffset() is None
        or end_datetime.utcoffset().total_seconds() != 0
        or end_datetime.microsecond != 0
    ):
        raise StrictAdjustedHistoryError("strict_adjusted_history:invalid_end_datetime")
    if not isinstance(duration, str) or re.fullmatch(r"[1-9][0-9]* [DWMY]", duration) is None:
        raise StrictAdjustedHistoryError("strict_adjusted_history:invalid_duration")

    sessions = tuple(expected_sessions)
    if (
        not sessions
        or any(not isinstance(session, date) or isinstance(session, datetime) for session in sessions)
        or sessions != tuple(sorted(set(sessions)))
    ):
        raise StrictAdjustedHistoryError("strict_adjusted_history:invalid_expected_sessions")
    return symbol, end_datetime, duration, sessions


def _strict_history_number(bar: Any, field: str, *, allow_zero: bool = False) -> float:
    value = getattr(bar, field, None)
    if isinstance(value, bool):
        raise StrictAdjustedHistoryError("strict_adjusted_history:invalid_bar_field")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise StrictAdjustedHistoryError("strict_adjusted_history:invalid_bar_field") from exc
    if not isfinite(numeric) or numeric < 0 or (not allow_zero and numeric == 0):
        raise StrictAdjustedHistoryError("strict_adjusted_history:invalid_bar_field")
    return numeric


def _strict_history_candle(bar: Any) -> AdjustedHistoricalCandle:
    try:
        session = _coerce_as_of(getattr(bar, "date")).date()
    except (AttributeError, TypeError, ValueError) as exc:
        raise StrictAdjustedHistoryError("strict_adjusted_history:invalid_bar_session") from exc
    open_price = _strict_history_number(bar, "open")
    high_price = _strict_history_number(bar, "high")
    low_price = _strict_history_number(bar, "low")
    close_price = _strict_history_number(bar, "close")
    volume = _strict_history_number(bar, "volume", allow_zero=True)
    if high_price < max(open_price, low_price, close_price) or low_price > min(
        open_price,
        high_price,
        close_price,
    ):
        raise StrictAdjustedHistoryError("strict_adjusted_history:invalid_ohlc")
    return AdjustedHistoricalCandle(
        session=session,
        open=open_price,
        high=high_price,
        low=low_price,
        close=close_price,
        volume=volume,
    )


def fetch_strict_adjusted_historical_price_candles(
    ib: Any,
    symbol: str,
    *,
    end_datetime: datetime,
    duration: str,
    expected_sessions: Sequence[date],
    stock_factory: Callable[..., Any] | None = None,
) -> StrictAdjustedHistoryResult:
    """Fetch one exact ADJUSTED_LAST daily series without any provider fallback."""

    symbol, end_datetime, duration, sessions = _strict_history_request_inputs(
        symbol,
        end_datetime=end_datetime,
        duration=duration,
        expected_sessions=expected_sessions,
    )
    contract = _build_stock_contract(
        symbol,
        exchange="SMART",
        currency="USD",
        stock_factory=stock_factory,
    )
    try:
        qualified = tuple(ib.qualifyContracts(contract) or ())
    except Exception:
        raise StrictAdjustedHistoryError(
            "strict_adjusted_history:contract_qualification_failed"
        ) from None
    if len(qualified) != 1:
        raise StrictAdjustedHistoryError(
            "strict_adjusted_history:contract_qualification_failed"
        )
    qualified_contract = qualified[0]
    if (
        getattr(qualified_contract, "symbol", None) != symbol
        or getattr(qualified_contract, "exchange", None) != "SMART"
        or getattr(qualified_contract, "currency", None) != "USD"
    ):
        raise StrictAdjustedHistoryError(
            "strict_adjusted_history:qualified_contract_mismatch"
        )

    try:
        bars = ib.reqHistoricalData(
            qualified_contract,
            endDateTime=end_datetime,
            durationStr=duration,
            barSizeSetting="1 day",
            whatToShow="ADJUSTED_LAST",
            useRTH=True,
            formatDate=1,
            keepUpToDate=False,
        )
    except Exception:
        raise StrictAdjustedHistoryError("strict_adjusted_history:request_failed") from None
    if not bars:
        raise StrictAdjustedHistoryError("strict_adjusted_history:empty_response")

    candles = tuple(_strict_history_candle(bar) for bar in bars)
    if tuple(candle.session for candle in candles) != sessions:
        raise StrictAdjustedHistoryError("strict_adjusted_history:session_contract_mismatch")

    provenance = StrictAdjustedHistoryProvenance(
        symbol=symbol,
        exchange="SMART",
        currency="USD",
        end_datetime=end_datetime.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        duration=duration,
        bar_size="1 day",
        what_to_show="ADJUSTED_LAST",
        use_rth=True,
        format_date=1,
        keep_up_to_date=False,
        returned_row_count=len(candles),
    )
    return StrictAdjustedHistoryResult(candles=candles, provenance=provenance)


def _request_historical_bars(
    ib: Any,
    contract: Any,
    *,
    duration: str,
    bar_size: str,
) -> Any:
    normalized_duration = _normalize_duration_for_ibkr(duration)
    last_error: Exception | None = None
    for what_to_show in ("ADJUSTED_LAST", "TRADES"):
        try:
            bars = ib.reqHistoricalData(
                contract,
                endDateTime="",
                durationStr=normalized_duration,
                barSizeSetting=bar_size,
                whatToShow=what_to_show,
                useRTH=True,
                formatDate=1,
            )
        except Exception as exc:  # pragma: no cover - exercised by live broker adapters.
            last_error = exc
            continue
        if bars:
            return bars
    if last_error is not None:
        raise last_error
    return ()


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
    bars = _request_historical_bars(
        ib,
        contract,
        duration=duration,
        bar_size=bar_size,
    )
    points = tuple(
        PricePoint(as_of=_coerce_as_of(bar.date), close=float(bar.close))
        for bar in bars or ()
    )
    return PriceSeries(symbol=symbol, currency=currency, points=points)


def fetch_historical_price_candles(
    ib: Any,
    symbol: str,
    *,
    duration: str = "2 Y",
    bar_size: str = "1 day",
    exchange: str = "SMART",
    currency: str = "USD",
    stock_factory: Callable[..., Any] | None = None,
) -> list[dict[str, Any]]:
    contract = _build_stock_contract(
        symbol,
        exchange=exchange,
        currency=currency,
        stock_factory=stock_factory,
    )
    ib.qualifyContracts(contract)
    bars = _request_historical_bars(
        ib,
        contract,
        duration=duration,
        bar_size=bar_size,
    )
    return [
        {
            "as_of": _coerce_as_of(bar.date),
            "open": float(getattr(bar, "open", bar.close)),
            "high": float(getattr(bar, "high", bar.close)),
            "low": float(getattr(bar, "low", bar.close)),
            "close": float(bar.close),
            "volume": float(getattr(bar, "volume", 0.0) or 0.0),
        }
        for bar in bars or ()
    ]


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


def _wait_for_market_data(ib: Any, wait_seconds: float) -> None:
    if not wait_seconds:
        return
    sleeper = getattr(ib, "sleep", None)
    if callable(sleeper):
        sleeper(wait_seconds)
        return
    import time as time_module

    time_module.sleep(wait_seconds)


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
    _wait_for_market_data(ib, wait_seconds)

    as_of = datetime.now(timezone.utc)
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
    retry_wait_seconds: float = 1.5,
    attempts_per_data_type: int = 2,
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

    snapshots: dict[str, QuoteSnapshot] = {}
    missing_contracts = list(contracts)
    attempts_per_data_type = max(int(attempts_per_data_type or 1), 1)

    setter = getattr(ib, "reqMarketDataType", None)
    # Prefer delayed data before live data so accounts without live subscriptions do
    # not emit noisy IBKR 10089 permission errors before falling back.
    market_data_types = (3, 4, 1, 2) if callable(setter) else (1,)

    try:
        for market_data_type in market_data_types:
            if callable(setter):
                _set_market_data_type(ib, market_data_type)

            for attempt_index in range(attempts_per_data_type):
                wait_for_attempt = wait_seconds if attempt_index == 0 else retry_wait_seconds
                recovered = _collect_quote_snapshots(
                    ib,
                    missing_contracts,
                    wait_seconds=wait_for_attempt,
                    currency=currency,
                )
                snapshots.update(recovered)
                missing_contracts = [
                    (symbol, contract)
                    for symbol, contract in missing_contracts
                    if symbol not in snapshots
                ]
                if not missing_contracts:
                    break

            if not missing_contracts:
                break
    finally:
        if callable(setter):
            _set_market_data_type(ib, 1)

    return snapshots


def _select_option_chain_params(chains: Any) -> Any | None:
    candidates = list(chains or ())
    if not candidates:
        return None
    for chain in candidates:
        if str(getattr(chain, "exchange", "") or "").strip().upper() == "SMART":
            return chain
    return candidates[0]


def _ticker_delta(ticker: Any) -> float | None:
    for greeks_name in ("modelGreeks", "bidGreeks", "askGreeks", "lastGreeks"):
        greeks = getattr(ticker, greeks_name, None)
        delta = _coerce_positive_price(abs(getattr(greeks, "delta", 0.0))) if greeks is not None else None
        if delta is not None:
            return float(delta)
    return None


def fetch_option_chain_snapshot(
    ib: Any,
    underlier: str,
    *,
    rights: tuple[str, ...] = ("C", "P"),
    min_dte: int = 25,
    max_dte: int = 930,
    target_dte: int | None = None,
    max_expirations: int = 3,
    strike_range_pct: tuple[float, float] = (0.50, 1.35),
    max_contracts: int = 80,
    wait_seconds: float = 3.0,
    exchange: str = "SMART",
    currency: str = "USD",
    stock_factory: Callable[..., Any] | None = None,
    option_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Fetch a bounded option-chain snapshot suitable for strategy-side contract selection."""

    symbol = str(underlier or "").strip().upper()
    if not symbol:
        raise ValueError("underlier is required.")

    stock_contract = _build_stock_contract(
        symbol,
        exchange=exchange,
        currency=currency,
        stock_factory=stock_factory,
    )
    qualified = ib.qualifyContracts(stock_contract)
    qualified_stock = qualified[0] if qualified else stock_contract
    con_id = getattr(qualified_stock, "conId", None)
    if con_id is None:
        raise ValueError(f"IBKR stock contract for {symbol} did not expose conId.")

    spot_snapshot = fetch_quote_snapshots(
        ib,
        (symbol,),
        wait_seconds=wait_seconds,
        exchange=exchange,
        currency=currency,
        stock_factory=stock_factory,
    )
    spot = float(spot_snapshot[symbol].last_price) if symbol in spot_snapshot else 0.0
    if spot <= 0.0:
        raise ValueError(f"Could not resolve underlying price for {symbol}.")

    chains = ib.reqSecDefOptParams(symbol, "", "STK", con_id)
    chain = _select_option_chain_params(chains)
    if chain is None:
        return {"underlier": symbol, "spot": spot, "contracts": ()}

    as_of = datetime.now(timezone.utc).date()
    target_dte = int(target_dte if target_dte is not None else (min_dte + max_dte) / 2)
    expirations = []
    for raw_expiration in getattr(chain, "expirations", ()) or ():
        expiration_date = _coerce_expiration(raw_expiration)
        if expiration_date is None:
            continue
        dte = (expiration_date - as_of).days
        if int(min_dte) <= dte <= int(max_dte):
            expirations.append((abs(dte - target_dte), raw_expiration, expiration_date, dte))
    expirations = sorted(expirations)[: max(1, int(max_expirations or 1))]

    low_ratio, high_ratio = strike_range_pct
    min_strike = spot * max(0.01, float(low_ratio))
    max_strike = spot * max(float(high_ratio), float(low_ratio))
    strikes = [
        float(strike)
        for strike in getattr(chain, "strikes", ()) or ()
        if min_strike <= float(strike) <= max_strike
    ]
    if max_contracts > 0 and expirations and rights:
        max_strikes = max(1, int(max_contracts // (len(expirations) * len(rights)) or 1))
        if len(strikes) > max_strikes:
            if max_strikes == 1:
                strikes = [min(strikes, key=lambda strike: abs(strike - spot))]
            else:
                last_index = len(strikes) - 1
                indices = {
                    round(index * last_index / (max_strikes - 1))
                    for index in range(max_strikes)
                }
                strikes = [strikes[index] for index in sorted(indices)]

    requested: list[tuple[Any, str, float, str, date, int, Any]] = []
    for _dte_gap, raw_expiration, expiration_date, dte in expirations:
        expiration_text = str(raw_expiration).replace("-", "")
        for right in rights:
            normalized_right = str(right or "").strip().upper()[0]
            for strike in strikes:
                contract = _build_option_contract(
                    symbol,
                    expiration_text,
                    strike,
                    normalized_right,
                    exchange=exchange,
                    currency=currency,
                    option_factory=option_factory,
                )
                ib.qualifyContracts(contract)
                ticker = ib.reqMktData(contract, "", False, False)
                requested.append((contract, normalized_right, strike, expiration_text, expiration_date, dte, ticker))

    _wait_for_market_data(ib, wait_seconds)
    rows = []
    for contract, right, strike, _expiration_text, expiration_date, dte, ticker in requested:
        ib.cancelMktData(contract)
        bid = _coerce_positive_price(getattr(ticker, "bid", None))
        ask = _coerce_positive_price(getattr(ticker, "ask", None))
        last = _coerce_positive_price(getattr(ticker, "last", None))
        rows.append(
            {
                "underlier": symbol,
                "right": right,
                "expiration": expiration_date.isoformat(),
                "dte": dte,
                "strike": float(strike),
                "bid": bid,
                "ask": ask,
                "last": last,
                "mid": ((bid + ask) / 2.0) if bid is not None and ask is not None else last,
                "delta": _ticker_delta(ticker),
            }
        )
    return {
        "underlier": symbol,
        "spot": spot,
        "contracts": tuple(rows),
    }
