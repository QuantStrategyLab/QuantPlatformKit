"""Helpers for whole-share execution on small accounts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


__all__ = [
    "SmallAccountCashCompatibilityResult",
    "apply_small_account_cash_compatibility",
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
    if safe_haven_substituted:
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
