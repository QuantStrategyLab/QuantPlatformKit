from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable

from quant_platform_kit.common.models import ExecutionReport, OrderIntent


def _normalize_account_id(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _build_stock_contract(
    symbol: str,
    *,
    stock_factory: Callable[..., Any] | None = None,
    exchange: str = "SMART",
    currency: str = "USD",
) -> Any:
    if stock_factory is None:
        from ib_insync import Stock

        stock_factory = Stock
    return stock_factory(symbol, exchange, currency)


def _normalize_option_expiration(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        return text
    if not text:
        raise ValueError("Option OrderIntent.metadata.expiration is required.")
    if isinstance(value, datetime):
        return value.date().strftime("%Y%m%d")
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    try:
        return datetime.fromisoformat(text[:10]).date().strftime("%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"Invalid option expiration: {value!r}") from exc


def _normalize_option_right(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"CALL", "C"}:
        return "C"
    if text in {"PUT", "P"}:
        return "P"
    raise ValueError("Option OrderIntent.metadata.right must be C/call or P/put.")


def _build_option_contract(
    order_intent: OrderIntent,
    *,
    option_factory: Callable[..., Any] | None = None,
    exchange: str = "SMART",
    currency: str = "USD",
) -> Any:
    metadata = dict(order_intent.metadata or {})
    underlier = str(metadata.get("underlier") or order_intent.symbol or "").strip().upper()
    if not underlier:
        raise ValueError("Option OrderIntent requires symbol or metadata.underlier.")
    expiration = _normalize_option_expiration(metadata.get("expiration"))
    right = _normalize_option_right(metadata.get("right"))
    try:
        strike = float(metadata.get("strike"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Option OrderIntent.metadata.strike is required.") from exc
    if strike <= 0.0:
        raise ValueError("Option OrderIntent.metadata.strike must be positive.")
    if option_factory is None:
        from ib_insync import Option

        option_factory = Option
    return option_factory(
        underlier,
        expiration,
        strike,
        right,
        exchange=exchange,
        currency=currency,
    )


def _is_option_intent(order_intent: OrderIntent) -> bool:
    metadata = dict(order_intent.metadata or {})
    return (
        str(metadata.get("asset_class") or "").strip().lower() == "option"
        or str(metadata.get("security_type") or "").strip().upper() == "OPT"
        or str(metadata.get("security_type") or "").strip().upper() == "BAG"
        or str(metadata.get("intent_type") or "").strip() == "single_leg_option"
        or str(metadata.get("intent_type") or "").strip() == "multi_leg_option"
    )


def _is_combo_option_intent(order_intent: OrderIntent) -> bool:
    metadata = dict(order_intent.metadata or {})
    return (
        str(metadata.get("asset_class") or "").strip().lower() == "option"
        and str(metadata.get("intent_type") or "").strip() == "multi_leg_option"
    )


def _leg_action(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("buy"):
        return "BUY"
    if text.startswith("sell"):
        return "SELL"
    raise ValueError(f"Unsupported option combo leg action: {value!r}")


def _build_option_combo_contract(
    ib: Any,
    order_intent: OrderIntent,
    *,
    option_factory: Callable[..., Any] | None = None,
    combo_contract_factory: Callable[..., Any] | None = None,
    combo_leg_factory: Callable[..., Any] | None = None,
    exchange: str = "SMART",
    currency: str = "USD",
) -> Any:
    metadata = dict(order_intent.metadata or {})
    underlier = str(metadata.get("underlier") or order_intent.symbol or "").strip().upper()
    legs = tuple(metadata.get("legs") or ())
    if not underlier or not legs:
        raise ValueError("Multi-leg option OrderIntent requires metadata.underlier and metadata.legs.")
    if combo_contract_factory is None:
        from ib_insync import Contract

        combo_contract_factory = Contract
    if combo_leg_factory is None:
        from ib_insync import ComboLeg

        combo_leg_factory = ComboLeg

    combo_legs = []
    for leg in legs:
        if not isinstance(leg, dict):
            raise ValueError("Option combo legs must be mappings.")
        option_contract = _build_option_contract(
            OrderIntent(
                symbol=underlier,
                side=_leg_action(leg.get("action")),
                quantity=1,
                metadata={
                    "underlier": underlier,
                    "expiration": leg.get("expiration") or metadata.get("expiration"),
                    "right": leg.get("right"),
                    "strike": leg.get("strike"),
                },
            ),
            option_factory=option_factory,
            exchange=exchange,
            currency=currency,
        )
        qualified = ib.qualifyContracts(option_contract)
        qualified_contract = qualified[0] if qualified else option_contract
        con_id = getattr(qualified_contract, "conId", None)
        if con_id is None:
            raise ValueError("Qualified option combo leg did not expose conId.")
        combo_legs.append(
            combo_leg_factory(
                conId=con_id,
                ratio=int(leg.get("ratio") or 1),
                action=_leg_action(leg.get("action")),
                exchange=exchange,
            )
        )

    contract = combo_contract_factory()
    contract.symbol = underlier
    contract.secType = "BAG"
    contract.exchange = exchange
    contract.currency = currency
    contract.comboLegs = combo_legs
    return contract


def _normalize_order_side(side: str) -> str:
    text = str(side or "").strip().lower()
    if text.startswith("buy"):
        return "BUY"
    if text.startswith("sell"):
        return "SELL"
    raise ValueError(f"Unsupported order side: {side!r}")


def submit_order_intent(
    ib: Any,
    order_intent: OrderIntent,
    *,
    account_id: str | None = None,
    wait_seconds: float = 1.0,
    stock_factory: Callable[..., Any] | None = None,
    option_factory: Callable[..., Any] | None = None,
    combo_contract_factory: Callable[..., Any] | None = None,
    combo_leg_factory: Callable[..., Any] | None = None,
    market_order_factory: Callable[..., Any] | None = None,
    limit_order_factory: Callable[..., Any] | None = None,
) -> ExecutionReport:
    metadata = dict(order_intent.metadata or {})
    if _is_combo_option_intent(order_intent):
        contract = _build_option_combo_contract(
            ib,
            order_intent,
            option_factory=option_factory,
            combo_contract_factory=combo_contract_factory,
            combo_leg_factory=combo_leg_factory,
        )
    elif _is_option_intent(order_intent):
        contract = _build_option_contract(
            order_intent,
            option_factory=option_factory,
        )
    else:
        contract = _build_stock_contract(
            order_intent.symbol,
            stock_factory=stock_factory,
        )
    ib.qualifyContracts(contract)

    side = _normalize_order_side(order_intent.side)
    order_type = order_intent.order_type.lower()
    if order_type == "market":
        if market_order_factory is None:
            from ib_insync import MarketOrder

            market_order_factory = MarketOrder
        order = market_order_factory(side, order_intent.quantity)
    elif order_type == "limit":
        if order_intent.limit_price is None:
            raise ValueError("Limit orders require OrderIntent.limit_price.")
        if limit_order_factory is None:
            from ib_insync import LimitOrder

            limit_order_factory = LimitOrder
        order = limit_order_factory(side, order_intent.quantity, order_intent.limit_price)
        if order_intent.time_in_force:
            order.tif = order_intent.time_in_force
    else:
        raise ValueError(f"Unsupported IBKR order type: {order_intent.order_type!r}")

    intent_account_id = _normalize_account_id(order_intent.account_id)
    explicit_account_id = _normalize_account_id(account_id)
    if intent_account_id and explicit_account_id and intent_account_id != explicit_account_id:
        raise ValueError(
            "OrderIntent.account_id conflicts with submit_order_intent(account_id=...)."
        )
    resolved_account_id = intent_account_id or explicit_account_id
    if resolved_account_id:
        order.account = resolved_account_id

    trade = ib.placeOrder(contract, order)
    if wait_seconds:
        import time as time_module

        time_module.sleep(wait_seconds)

    order_status = trade.orderStatus
    return ExecutionReport(
        symbol=order_intent.symbol,
        side=order_intent.side.lower(),
        quantity=float(order_intent.quantity),
        status=order_status.status,
        filled_quantity=float(getattr(order_status, "filled", 0) or 0),
        average_fill_price=float(getattr(order_status, "avgFillPrice", 0) or 0),
        broker_order_id=str(trade.order.orderId),
        raw_payload={
            "order_type": order_type,
            "time_in_force": getattr(order, "tif", None),
            "account_id": resolved_account_id,
            "asset_class": metadata.get("asset_class"),
            "intent_type": metadata.get("intent_type"),
            "underlier": metadata.get("underlier"),
            "right": metadata.get("right"),
            "expiration": metadata.get("expiration"),
            "strike": metadata.get("strike"),
            "legs": metadata.get("legs"),
        },
    )
