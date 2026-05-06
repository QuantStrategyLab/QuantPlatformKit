from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_DOWN


def normalize_quantity_step(quantity_step: float | int | str | None) -> Decimal:
    try:
        step = Decimal(str(quantity_step if quantity_step is not None else "1"))
    except (InvalidOperation, ValueError):
        step = Decimal("1")
    if step <= 0:
        return Decimal("1")
    return step


def floor_to_quantity_step(
    quantity: float | int | str | Decimal,
    quantity_step: float | int | str | Decimal | None,
) -> float:
    step = normalize_quantity_step(quantity_step)
    try:
        value = Decimal(str(quantity))
    except (InvalidOperation, ValueError):
        return 0.0
    if value <= 0:
        return 0.0
    units = (value / step).to_integral_value(rounding=ROUND_DOWN)
    return float(units * step)


def normalize_order_quantity(quantity: float | int | str | Decimal) -> int | float:
    value = float(quantity or 0.0)
    if value.is_integer():
        return int(value)
    return value


def format_quantity(quantity: float | int | str | Decimal) -> str:
    value = normalize_order_quantity(quantity)
    if isinstance(value, int):
        return str(value)
    return f"{value:g}"
