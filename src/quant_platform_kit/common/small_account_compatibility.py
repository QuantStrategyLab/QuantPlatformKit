"""Helpers for whole-share execution on small accounts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


__all__ = [
    "SmallAccountCashCompatibilityResult",
    "apply_small_account_cash_compatibility",
    "build_small_account_allocation_drift_notes",
    "format_small_account_allocation_drift_notes",
    "format_small_account_cash_substitution_notes",
    "project_unbuyable_value_targets_to_cash",
]


@dataclass(frozen=True)
class SmallAccountCashCompatibilityResult:
    targets: dict[str, float]
    whole_share_substituted_symbols: tuple[str, ...]
    safe_haven_cash_substituted_symbols: tuple[str, ...]
    cash_substitution_notes: tuple[dict[str, object], ...]


def _normalize_symbol(value: object) -> str:
    return str(value or "").strip().upper()


def _normalize_trade_symbol(value: object, *, symbol_suffix: str = ".US") -> str:
    symbol = _normalize_symbol(value)
    suffix = str(symbol_suffix or "").strip().upper()
    if suffix and symbol.endswith(suffix):
        return symbol[: -len(suffix)]
    return symbol


def _positive_target_total(targets: Mapping[str, object]) -> float:
    total = 0.0
    for value in dict(targets or {}).values():
        try:
            total += max(0.0, float(value or 0.0))
        except (TypeError, ValueError):
            continue
    return total


def _normalize_prices(prices: Mapping[str, object]) -> dict[str, float]:
    return {
        _normalize_symbol(symbol): float(price or 0.0)
        for symbol, price in dict(prices or {}).items()
    }


def _format_symbol(symbol: str, *, suffix: str) -> str:
    normalized = _normalize_symbol(symbol)
    normalized_suffix = str(suffix or "").strip()
    if normalized_suffix and not normalized.endswith(normalized_suffix.upper()):
        return f"{normalized}{normalized_suffix}"
    return normalized


def _coerce_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return default


def _coerce_order_price(order: Mapping[str, object], prices: Mapping[str, float], symbol: str) -> float:
    for key in ("average_fill_price", "filled_price", "limit_price", "price", "submitted_price"):
        price = _coerce_float(order.get(key), 0.0)
        if price > 0.0:
            return price
    return max(0.0, float(prices.get(symbol, 0.0) or 0.0))


def _format_weight(value: float) -> str:
    return f"{float(value or 0.0):.1%}"


def _format_weight_drift(value: float) -> str:
    return f"{float(value or 0.0) * 100:+.1f}pp"


def build_small_account_allocation_drift_notes(
    *,
    target_values: Mapping[str, object] | None = None,
    target_weights: Mapping[str, object] | None = None,
    current_values: Mapping[str, object] | None = None,
    current_quantities: Mapping[str, object] | None = None,
    prices: Mapping[str, object] | None = None,
    submitted_orders: Iterable[Mapping[str, object]] = (),
    total_value: float | None = None,
    cash_value: float = 0.0,
    symbol_suffix: str = ".US",
    min_abs_weight_drift: float = 0.005,
    small_account_max_total_value: float = 5000.0,
    max_notes: int = 5,
) -> tuple[dict[str, object], ...]:
    """Estimate target drift after whole-share orders fully fill.

    The estimate is intentionally simple and side-effect free: it uses current
    values/quantities, order quantities, and reference prices to explain the
    integer-share gap a small account may see if the submitted orders all fill.
    """

    normalized_prices = {
        _normalize_trade_symbol(symbol, symbol_suffix=symbol_suffix): _coerce_float(price)
        for symbol, price in dict(prices or {}).items()
    }
    normalized_current_values = {
        _normalize_trade_symbol(symbol, symbol_suffix=symbol_suffix): _coerce_float(value)
        for symbol, value in dict(current_values or {}).items()
    }
    normalized_current_quantities = {
        _normalize_trade_symbol(symbol, symbol_suffix=symbol_suffix): _coerce_float(quantity)
        for symbol, quantity in dict(current_quantities or {}).items()
    }
    for symbol, quantity in normalized_current_quantities.items():
        if symbol not in normalized_current_values:
            normalized_current_values[symbol] = quantity * max(0.0, normalized_prices.get(symbol, 0.0))

    denominator = _coerce_float(total_value, 0.0)
    if denominator <= 0.0:
        denominator = sum(max(0.0, value) for value in normalized_current_values.values()) + max(
            0.0,
            _coerce_float(cash_value, 0.0),
        )
    if denominator <= 0.0:
        return ()
    if denominator > max(0.0, _coerce_float(small_account_max_total_value, 0.0)):
        return ()

    normalized_target_values: dict[str, float] = {}
    if target_values:
        normalized_target_values.update(
            {
                _normalize_trade_symbol(symbol, symbol_suffix=symbol_suffix): _coerce_float(value)
                for symbol, value in dict(target_values or {}).items()
            }
        )
    if target_weights:
        for symbol, weight in dict(target_weights or {}).items():
            normalized_target_values[_normalize_trade_symbol(symbol, symbol_suffix=symbol_suffix)] = (
                denominator * _coerce_float(weight)
            )

    if not normalized_target_values:
        return ()

    projected_values = dict(normalized_current_values)
    projected_quantities = dict(normalized_current_quantities)
    for raw_order in tuple(submitted_orders or ()):
        if not isinstance(raw_order, Mapping):
            continue
        symbol = _normalize_trade_symbol(raw_order.get("symbol"), symbol_suffix=symbol_suffix)
        if not symbol:
            continue
        side = str(raw_order.get("side") or "").strip().lower()
        quantity = _coerce_float(raw_order.get("quantity"), 0.0)
        if quantity <= 0.0 or side not in {"buy", "sell"}:
            continue
        price = _coerce_order_price(raw_order, normalized_prices, symbol)
        if price <= 0.0:
            continue
        signed_quantity = quantity if side == "buy" else -quantity
        projected_quantities[symbol] = projected_quantities.get(symbol, 0.0) + signed_quantity
        projected_values[symbol] = max(0.0, projected_values.get(symbol, 0.0) + signed_quantity * price)
        normalized_prices.setdefault(symbol, price)

    notes: list[dict[str, object]] = []
    symbols = sorted(set(normalized_target_values))
    for symbol in symbols:
        target_value = max(0.0, normalized_target_values.get(symbol, 0.0))
        projected_value = max(0.0, projected_values.get(symbol, 0.0))
        if target_value <= 0.0 and projected_value <= 0.0:
            continue
        target_weight = target_value / denominator
        projected_weight = projected_value / denominator
        drift_weight = projected_weight - target_weight
        if abs(drift_weight) < max(0.0, _coerce_float(min_abs_weight_drift, 0.0)):
            continue
        notes.append(
            {
                "kind": "small_account_allocation_drift",
                "symbol": symbol,
                "target_value": round(target_value, 2),
                "projected_value": round(projected_value, 2),
                "target_weight": target_weight,
                "projected_weight": projected_weight,
                "drift_weight": drift_weight,
                "drift_value": round(projected_value - target_value, 2),
                "projected_quantity": projected_quantities.get(symbol),
            }
        )

    notes.sort(key=lambda note: abs(float(note.get("drift_weight") or 0.0)), reverse=True)
    return tuple(notes[: max(0, int(max_notes or 0))])


def format_small_account_allocation_drift_notes(
    notes: Iterable[Mapping[str, object]],
    *,
    translator,
    wrapper_key: str = "small_account_allocation_drift",
    detail_key: str = "small_account_allocation_drift_detail",
    symbol_suffix: str = ".US",
) -> tuple[str, ...]:
    """Render small-account projected allocation drift notes."""

    details: list[str] = []
    seen_symbols: set[str] = set()
    for note in tuple(notes or ()):
        if not isinstance(note, Mapping):
            continue
        if str(note.get("kind") or "") != "small_account_allocation_drift":
            continue
        symbol = _normalize_symbol(note.get("symbol"))
        if not symbol or symbol in seen_symbols:
            continue
        seen_symbols.add(symbol)
        detail = translator(
            detail_key,
            symbol=_format_symbol(symbol, suffix=symbol_suffix),
            projected_weight=_format_weight(_coerce_float(note.get("projected_weight"))),
            target_weight=_format_weight(_coerce_float(note.get("target_weight"))),
            drift_weight=_format_weight_drift(_coerce_float(note.get("drift_weight"))),
        )
        if not detail or detail == detail_key:
            detail = (
                f"{_format_symbol(symbol, suffix=symbol_suffix)} projected "
                f"{_format_weight(_coerce_float(note.get('projected_weight')))} vs target "
                f"{_format_weight(_coerce_float(note.get('target_weight')))} "
                f"({_format_weight_drift(_coerce_float(note.get('drift_weight')))})"
            )
        details.append(str(detail))
    if not details:
        return ()
    message = translator(wrapper_key, details="; ".join(details))
    if not message or message == wrapper_key:
        message = f"Small-account integer-share drift: {'; '.join(details)}"
    return (message,)


def project_unbuyable_value_targets_to_cash(
    target_values: Mapping[str, object],
    prices: Mapping[str, object],
    *,
    symbols: Iterable[str] | None = None,
    quantity_step: float = 1.0,
) -> tuple[dict[str, float], tuple[str, ...]]:
    """Zero value targets that cannot buy one execution quantity step.

    This keeps strategy output intact while letting whole-share execution layers
    avoid preserving a single oversized share for a sleeve whose target is less
    than one tradable unit.
    """

    adjusted = {
        _normalize_symbol(symbol): float(value or 0.0)
        for symbol, value in dict(target_values or {}).items()
    }
    step = max(0.0, float(quantity_step or 0.0))
    if step <= 0.0:
        return adjusted, ()

    if symbols is None:
        candidate_symbols = tuple(adjusted)
    else:
        candidate_symbols = tuple(dict.fromkeys(_normalize_symbol(symbol) for symbol in symbols))

    substituted: list[str] = []
    normalized_prices = _normalize_prices(prices)
    for symbol in candidate_symbols:
        if not symbol:
            continue
        target_value = max(0.0, float(adjusted.get(symbol, 0.0) or 0.0))
        price = max(0.0, float(normalized_prices.get(symbol, 0.0) or 0.0))
        if price <= 0.0:
            continue
        if 0.0 < target_value < (price * step):
            adjusted[symbol] = 0.0
            substituted.append(symbol)

    return adjusted, tuple(dict.fromkeys(substituted))


def apply_small_account_cash_compatibility(
    target_values: Mapping[str, object],
    prices: Mapping[str, object],
    *,
    candidate_symbols: Iterable[str] | None = None,
    safe_haven_cash_symbols: Iterable[str] = (),
    quantity_step: float = 1.0,
    cash_substitute_limit_usd: float = 2000.0,
) -> SmallAccountCashCompatibilityResult:
    """Apply whole-share small-account projection and cash-safe-haven fallback.

    If every risk/income target that remains positive is below one tradable unit,
    and the remaining positive safe-haven/cash-sweep sleeve is still small, the
    safe-haven target is also projected to cash. The returned notes preserve the
    original target and price so platform notifications can explain why no risk
    or safe-haven rebuy was submitted.
    """

    adjusted_targets, substituted = project_unbuyable_value_targets_to_cash(
        target_values,
        prices,
        symbols=candidate_symbols,
        quantity_step=quantity_step,
    )
    normalized_candidates = (
        tuple(adjusted_targets)
        if candidate_symbols is None
        else tuple(dict.fromkeys(_normalize_symbol(symbol) for symbol in candidate_symbols))
    )
    remaining_non_safe_targets = [
        symbol
        for symbol in normalized_candidates
        if float(adjusted_targets.get(_normalize_symbol(symbol), 0.0) or 0.0) > 0.0
    ]
    safe_haven_symbols = tuple(
        dict.fromkeys(
            _normalize_symbol(symbol)
            for symbol in safe_haven_cash_symbols
            if _normalize_symbol(symbol)
        )
    )
    safe_haven_substituted: list[str] = []
    if (
        substituted
        and not remaining_non_safe_targets
        and _positive_target_total(adjusted_targets) <= max(0.0, float(cash_substitute_limit_usd or 0.0))
    ):
        for symbol in safe_haven_symbols:
            if float(adjusted_targets.get(symbol, 0.0) or 0.0) > 0.0:
                adjusted_targets[symbol] = 0.0
                safe_haven_substituted.append(symbol)

    notes: list[dict[str, object]] = []
    if substituted:
        normalized_targets = {
            _normalize_symbol(symbol): float(value or 0.0)
            for symbol, value in dict(target_values or {}).items()
        }
        normalized_prices = _normalize_prices(prices)
        for symbol in substituted:
            target_value = max(0.0, float(normalized_targets.get(symbol, 0.0) or 0.0))
            price = max(0.0, float(normalized_prices.get(symbol, 0.0) or 0.0))
            if target_value <= 0.0 or price <= 0.0:
                continue
            notes.append(
                {
                    "symbol": symbol,
                    "target_value": target_value,
                    "price": price,
                    "cash_symbols": tuple(safe_haven_substituted),
                }
            )

    return SmallAccountCashCompatibilityResult(
        targets=adjusted_targets,
        whole_share_substituted_symbols=substituted,
        safe_haven_cash_substituted_symbols=tuple(safe_haven_substituted),
        cash_substitution_notes=tuple(notes),
    )


def format_small_account_cash_substitution_notes(
    notes: Iterable[Mapping[str, object]],
    *,
    translator,
    wrapper_key: str = "buy_deferred",
    detail_key: str = "buy_deferred_small_account_cash_substitution",
    cash_label_key: str = "cash_label",
    symbol_suffix: str = ".US",
) -> tuple[str, ...]:
    """Render small-account cash substitution notes through platform i18n."""

    messages: list[str] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for note in tuple(notes or ()):
        if not isinstance(note, Mapping):
            continue
        symbol = _normalize_symbol(note.get("symbol"))
        if not symbol:
            continue
        target_value = max(0.0, float(note.get("target_value") or 0.0))
        price = max(0.0, float(note.get("price") or 0.0))
        if target_value <= 0.0 or price <= 0.0:
            continue
        cash_symbols = tuple(
            dict.fromkeys(
                _normalize_symbol(cash_symbol)
                for cash_symbol in tuple(note.get("cash_symbols") or ())
                if _normalize_symbol(cash_symbol)
            )
        )
        cash_symbols_text = ", ".join(
            _format_symbol(cash_symbol, suffix=symbol_suffix)
            for cash_symbol in cash_symbols
        )
        if not cash_symbols_text:
            cash_symbols_text = str(translator(cash_label_key)).strip()
            if not cash_symbols_text or cash_symbols_text == cash_label_key:
                cash_symbols_text = "cash"
        note_key = (symbol, f"{target_value:.2f}", cash_symbols_text)
        if note_key in seen_keys:
            continue
        seen_keys.add(note_key)
        detail = translator(
            detail_key,
            symbol=_format_symbol(symbol, suffix=symbol_suffix),
            diff=f"{target_value:.2f}",
            price=f"{price:.2f}",
            cash_symbols=cash_symbols_text,
        )
        message = translator(wrapper_key, detail=detail)
        if not message or message == wrapper_key:
            message = detail
        messages.append(message)
    return tuple(messages)
