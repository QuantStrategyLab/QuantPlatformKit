"""Shared notification rendering primitives for platform renderers.

Consolidates ~29 duplicated function definitions across IBKR, Schwab,
LongBridge, and Firstrade platform notification renderers.  Platform
renderers import from here and delete their local copies.

All functions accept either ``translator`` or ``locale`` keyword
arguments where applicable, supporting both call patterns present
across the four platforms.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

from quant_platform_kit.common.notification_localization import (
    PRICE_SOURCE_LABELS,
    localize_notification_text as _base_localize_notification_text,
    localize_price_source_label as _shared_localize_price_source_label,
    translator_uses_zh as _base_translator_uses_zh,
)

# ──────────────────────────────────────────────────────────────────────
#  Regex
# ──────────────────────────────────────────────────────────────────────

# Matches whitespace-separated key=value / key:value segments.
# Used by IBKR, Schwab, LongBridge to split detail lines.
_DETAIL_FIELD_SPLIT_RE = re.compile(r"\s+(?=[^\s=:：]+[=:：])")


# ──────────────────────────────────────────────────────────────────────
#  1. Formatting primitives (byte-identical across all 4 platforms)
# ──────────────────────────────────────────────────────────────────────


def format_percent(value: Any) -> str:
    """Format a ratio as a percentage string, e.g. 0.705 → "70.5%".

    Returns ``"n/a"`` when *value* cannot be coerced to float.
    """
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "n/a"


def format_percentile(value: Any) -> str:
    """Format a ratio as a percentile label, e.g. 0.95 → "p95".

    Returns ``"p?"`` when *value* cannot be coerced to float.
    """
    try:
        percentile = float(value) * 100
    except (TypeError, ValueError):
        return "p?"
    if float(percentile).is_integer():
        return f"p{int(percentile)}"
    return f"p{percentile:.1f}"


def format_sample_count(value: Any) -> str:
    """Format a numeric sample count, truncating to integer when whole.

    Returns ``"n/a"`` when *value* cannot be coerced to float.
    """
    try:
        count = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if float(count).is_integer():
        return str(int(count))
    return f"{count:.1f}"


def as_float_or_none(value: Any) -> float | None:
    """Coerce *value* to float, returning ``None`` on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def present(value: Any) -> bool:
    """Return ``True`` when *value* is not ``None`` and not empty-string."""
    return value not in (None, "")


def is_truthy(value: Any) -> bool:
    """Truthiness check tolerant of string representations.

    Accepts ``True``, ``"1"``, ``"true"``, ``"yes"``, ``"y"``
    (case-insensitive).
    """
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


# ──────────────────────────────────────────────────────────────────────
#  2. Text splitting utilities (identical across platforms)
# ──────────────────────────────────────────────────────────────────────


def split_detail_segment(text: str) -> list[str]:
    """Split a detail segment on whitespace-bounded key=value / key:value.

    If the segment contains no ``=``, ``:``, or ``：``, it is returned as
    a single-item list (i.e. treated as an opaque label).
    """
    value = str(text or "").strip()
    if not value:
        return []
    if "=" not in value and ":" not in value and "：" not in value:
        return [value]
    return [part.strip() for part in _DETAIL_FIELD_SPLIT_RE.split(value) if part.strip()]


def split_labeled_text(text: str) -> list[str]:
    """Split pipe-separated "|" text, expanding each segment with
    :func:`split_detail_segment`."""
    segments = [segment.strip() for segment in str(text or "").split(" | ") if segment.strip()]
    if not segments:
        return []
    lines = [segments[0]]
    for segment in segments[1:]:
        lines.extend(split_detail_segment(segment))
    return lines


# ──────────────────────────────────────────────────────────────────────
#  3. Price source & timing contract localisation
# ──────────────────────────────────────────────────────────────────────


def localize_price_source_label(
    value: object,
    *,
    translator: Callable[..., str] | None = None,
    locale: str | None = None,
) -> str:
    """Localize a price-source identifier for notification display.

    Delegates to the canonical implementation in
    :mod:`quant_platform_kit.common.notification_localization`.
    """
    return _shared_localize_price_source_label(value, translator=translator, locale=locale)


def localize_timing_contract(
    contract: str,
    *,
    translator: Callable[..., str] | None = None,
    locale: str | None = None,
) -> str:
    """Localize an execution-timing contract label.

    When *translator* is provided (Firstrade pattern), the output is
    resolved via ``translator(key)`` so platform i18n dicts can
    customise the text.  When only *locale* is provided (IBKR / Schwab /
    LongBridge pattern), hard-coded zh/en strings are used.

    Supported contract values:

    * ``"same_trading_day"``
    * ``"next_trading_day"``
    * ``"next_N_trading_days"`` (e.g. ``"next_3_trading_days"``)
    """
    value = str(contract or "").strip()
    if not value:
        return ""

    use_zh = (
        _base_translator_uses_zh(translator)
        if translator is not None
        else str(locale or "").strip().lower().startswith("zh")
    )

    # ── Firstrade pattern: use translator for output ──
    if translator is not None:
        # Firstrade uses translator keys for timing labels
        if value == "same_trading_day":
            return translator("same_trading_day")
        if value == "next_trading_day":
            return translator("next_trading_day")
        if value.startswith("next_") and value.endswith("_trading_days"):
            count_text = value.removeprefix("next_").removesuffix("_trading_days")
            if count_text.isdigit():
                return translator("next_n_trading_days", count=int(count_text))
        # Fallback: try translator, then return raw
        translated = translator(value)
        return value if translated == value else translated

    # ── Hardcoded pattern (IBKR / Schwab / LongBridge) ──
    if value == "same_trading_day":
        return "当日执行" if use_zh else "same trading day"
    if value == "next_trading_day":
        return "次一交易日执行" if use_zh else "next trading day"
    match = re.fullmatch(r"next_(\d+)_trading_days", value)
    if match:
        count = int(match.group(1))
        if use_zh:
            return f"{count}个交易日后执行"
        return f"next {count} trading days"
    return value.replace("_", " ")


def translator_uses_zh(translator: Callable[..., str]) -> bool:
    """Convenience re-export of the shared zh-detection helper."""
    return _base_translator_uses_zh(translator)


# ──────────────────────────────────────────────────────────────────────
#  4. Volatility-delever helpers (identical logic across platforms)
# ──────────────────────────────────────────────────────────────────────


def effective_volatility_delever_threshold(
    execution: Mapping[str, Any],
    *,
    prefix: str,
) -> Any:
    """Resolve the effective volatility-delever threshold.

    When the mode is ``"rolling_percentile"`` and a dynamic threshold
    value is present, return it; otherwise return the fixed threshold.
    """
    mode = str(execution.get(f"{prefix}_threshold_mode") or "").strip().lower()
    dynamic_threshold = execution.get(f"{prefix}_dynamic_threshold")
    if mode == "rolling_percentile" and present(dynamic_threshold):
        return dynamic_threshold
    return execution.get(f"{prefix}_threshold")


def format_volatility_delever_threshold_detail(
    execution: Mapping[str, Any],
    *,
    prefix: str,
    translator: Callable[..., str],
) -> str:
    """Build a human-readable volatility-delever threshold description."""
    mode = str(execution.get(f"{prefix}_threshold_mode") or "").strip().lower()
    fixed_threshold = execution.get(f"{prefix}_threshold")
    dynamic_threshold = execution.get(f"{prefix}_dynamic_threshold")

    if mode == "rolling_percentile":
        kwargs = {
            "percentile": format_percentile(execution.get(f"{prefix}_dynamic_percentile")),
            "lookback": format_sample_count(execution.get(f"{prefix}_dynamic_lookback")),
            "min_periods": format_sample_count(execution.get(f"{prefix}_dynamic_min_periods")),
            "sample_count": format_sample_count(execution.get(f"{prefix}_dynamic_sample_count")),
            "floor": format_percent(execution.get(f"{prefix}_dynamic_floor")),
            "cap": format_percent(execution.get(f"{prefix}_dynamic_cap")),
            "fixed_threshold": format_percent(fixed_threshold),
        }
        if present(dynamic_threshold):
            return translator("blend_gate_volatility_threshold_detail_dynamic", **kwargs)
        return translator("blend_gate_volatility_threshold_detail_dynamic_fallback", **kwargs)

    return translator(
        "blend_gate_volatility_threshold_detail_fixed",
        threshold=format_percent(fixed_threshold),
    )


def format_tqqq_volatility_delever_allocation_detail(
    execution: Mapping[str, Any],
    *,
    prefix: str,
    redirect_symbol: str,
    translator: Callable[..., str],
) -> str:
    """Build the allocation-detail line for a TQQQ volatility-delever action."""
    retained_ratio = as_float_or_none(execution.get(f"{prefix}_retained_ratio"))
    redirected_ratio = as_float_or_none(execution.get(f"{prefix}_redirected_ratio"))
    if retained_ratio is None:
        retained_ratio = as_float_or_none(execution.get(f"{prefix}_retention_ratio"))
    if redirected_ratio is None and retained_ratio is not None:
        redirected_ratio = max(0.0, min(1.0, 1.0 - retained_ratio))
    return translator(
        "tqqq_volatility_delever_allocation_detail",
        retained_ratio=format_percent(retained_ratio),
        redirected_ratio=format_percent(redirected_ratio),
        redirect_symbol=redirect_symbol or "QQQ",
    )


# ──────────────────────────────────────────────────────────────────────
#  5. TQQQ risk-control lines builder
# ──────────────────────────────────────────────────────────────────────


def build_tqqq_risk_control_lines(
    execution: Mapping[str, Any],
    *,
    translator: Callable[..., str],
) -> list[str]:
    """Build TQQQ volatility-delever risk-control notification lines.

    Returns an empty list when the delever gate was not applied.
    """
    prefix = "dual_drive_volatility_delever"
    if not is_truthy(execution.get(f"{prefix}_applied")):
        return []

    redirect_symbol = str(execution.get(f"{prefix}_redirect_symbol") or "QQQ").strip().upper()
    window = str(execution.get(f"{prefix}_window") or "5").strip()
    threshold = effective_volatility_delever_threshold(execution, prefix=prefix)
    threshold_detail = format_volatility_delever_threshold_detail(
        execution, prefix=prefix, translator=translator,
    )
    allocation_detail = format_tqqq_volatility_delever_allocation_detail(
        execution, prefix=prefix, redirect_symbol=redirect_symbol or "QQQ", translator=translator,
    )

    if str(execution.get(f"{prefix}_trigger_reason") or "").strip() == "hysteresis_hold":
        return [
            translator(
                "risk_control_tqqq_volatility_delever_hysteresis_dynamic",
                window=window,
                volatility=format_percent(execution.get(f"{prefix}_metric")),
                exit_threshold=format_percent(execution.get(f"{prefix}_exit_threshold")),
                threshold=format_percent(threshold),
                threshold_detail=threshold_detail,
                source_symbol="TQQQ",
                redirect_symbol=redirect_symbol or "QQQ",
                allocation_detail=allocation_detail,
            )
        ]
    return [
        translator(
            "risk_control_tqqq_volatility_delever_applied_dynamic",
            window=window,
            volatility=format_percent(execution.get(f"{prefix}_metric")),
            threshold=format_percent(threshold),
            threshold_detail=threshold_detail,
            source_symbol="TQQQ",
            redirect_symbol=redirect_symbol or "QQQ",
            allocation_detail=allocation_detail,
        )
    ]


# ──────────────────────────────────────────────────────────────────────
#  6. Timing audit & signal snapshot lines
# ──────────────────────────────────────────────────────────────────────


def build_timing_audit_lines(
    execution: Mapping[str, Any],
    *,
    translator: Callable[..., str],
    localize_timing: Callable[..., str] | None = None,
) -> list[str]:
    """Build timing audit line(s) from an execution context.

    The *execution* dict is expected to be a flat mapping with keys
    ``signal_date``, ``effective_date``, and ``execution_timing_contract``.
    For IBKR (whose data is nested under ``execution_annotations``),
    flatten via :func:`resolve_execution` before calling.

    *localize_timing* allows the caller to inject a platform-specific
    timing-contract localizer.  When omitted, :func:`localize_timing_contract`
    is called in hardcoded mode (no translator output).
    """
    signal_date = str(execution.get("signal_date") or "").strip()
    effective_date = str(execution.get("effective_date") or "").strip()
    contract = str(execution.get("execution_timing_contract") or "").strip()

    if not signal_date and not effective_date and not contract:
        return []

    label = "⏱ 执行时点" if _base_translator_uses_zh(translator) else "⏱ Timing"

    if localize_timing is not None:
        localized_contract = localize_timing(contract)
    else:
        localized_contract = localize_timing_contract(contract, locale="zh" if _base_translator_uses_zh(translator) else "en")

    if signal_date and effective_date:
        value = f"{signal_date} -> {effective_date}"
    else:
        value = signal_date or effective_date or localized_contract

    if localized_contract and localized_contract not in value:
        value = f"{value} ({localized_contract})" if value else localized_contract

    return [f"{label}: {value}"]


def format_signal_snapshot_line(
    snapshot: Any,
    *,
    translator: Callable[..., str] | None = None,
    locale: str | None = None,
    localize_text: Callable[..., str] | None = None,
) -> str:
    """Format a signal-snapshot line for notification display.

    Supports two patterns:

    * **translator-based** (IBKR / Schwab / LongBridge): pass *translator*
      and optionally *localize_text* for platform-specific localisation.
    * **locale-based** (Firstrade): pass *locale*; zh detection is
      locale-driven.
    """
    if not isinstance(snapshot, Mapping):
        return ""

    market_date = str(snapshot.get("market_date") or snapshot.get("signal_as_of") or "").strip()
    source = str(snapshot.get("latest_price_source") or "").strip()
    warning = snapshot.get("data_freshness_warning")

    if not market_date and not source and warning in (None, "", False):
        return ""

    if translator is not None:
        use_zh = _base_translator_uses_zh(translator)
    else:
        use_zh = str(locale or "").strip().lower().startswith("zh")

    if use_zh:
        parts = [
            f"日期 {market_date or '未知'}",
            f"数据源 {localize_price_source_label(source, translator=translator, locale=locale)}",
        ]
        if warning not in (None, "", False):
            if localize_text is not None:
                parts.append(f"提示 {localize_text(warning, translator=translator)}")
            elif translator is not None:
                parts.append(f"提示 {_base_localize_notification_text(warning, translator=translator)}")
            else:
                parts.append(f"提示 {warning}")
        return "🧾 信号快照: " + " | ".join(parts)

    parts = [
        f"date {market_date or 'unknown'}",
        f"source {localize_price_source_label(source, translator=translator, locale=locale)}",
    ]
    if warning not in (None, "", False):
        parts.append(f"warning {warning}")
    return "🧾 Signal snapshot: " + " | ".join(parts)


# ──────────────────────────────────────────────────────────────────────
#  7. Dashboard helpers
# ──────────────────────────────────────────────────────────────────────


def relabel_dashboard_cash_labels(
    text: str,
    *,
    cash_only_execution: bool,
    translator: Callable[..., str] | None = None,
) -> str:
    """Relabel cash/buying-power terms in a raw dashboard text block.

    When *cash_only_execution* is ``True``, "购买力"/"Buying power" are
    replaced with the translated label for "可用现金"/"Available cash".
    When ``False``, the reverse relabeling is applied.

    If *translator* is provided (Schwab / LongBridge pattern), the
    target label is resolved via ``translator("buying_power")`` or
    ``translator("buying_power_margin")``.  Otherwise the hard-coded
    IBKR labels are used.
    """
    value = str(text or "")

    if cash_only_execution:
        value = value.replace("总资产（策略净值）", "总资产（策略标的+现金，不含融资额度）")
        value = value.replace(
            "Total assets (strategy net liquidation)",
            "Total assets (strategy symbols + cash, ex-margin)",
        )
        if translator is not None:
            target = translator("buying_power")
            for source in ("Buying power", "购买力"):
                if source != target:
                    value = value.replace(source, target)
        else:
            value = value.replace("购买力", "可用现金")
            value = value.replace("Buying power", "Available cash")
        return value

    # Margin mode
    value = value.replace("总资产（策略标的+现金，不含融资额度）", "总资产（策略净值）")
    value = value.replace("总资产（策略标的+现金）", "总资产（策略净值）")
    value = value.replace(
        "Total assets (strategy symbols + cash, ex-margin)",
        "Total assets (strategy net liquidation)",
    )
    value = value.replace(
        "Total assets (strategy symbols + cash)",
        "Total assets (strategy net liquidation)",
    )
    if translator is not None:
        target = translator("buying_power_margin")
        for source in ("Available cash", "可用现金"):
            if source != target:
                value = value.replace(source, target)
    else:
        value = value.replace("可用现金", "购买力")
        value = value.replace("Available cash", "Buying power")
    return value


def is_compact_dashboard_audit_line(line: str) -> bool:
    """Return ``True`` when *line* should be stripped from compact messages.

    Matches the Schwab / LongBridge pattern.
    """
    text = str(line or "").strip()
    lowered = text.lower()
    return (
        text.startswith(("⏱", "🧾", "🧩 输入状态", "📊", "🎯", "🛡️"))
        or lowered.startswith(("signal:", "signal：", "market status:"))
        or text.startswith(("信号:", "信号：", "市场状态:", "市场状态："))
    )


def compact_dashboard_lines(dashboard_text: str) -> list[str]:
    """Filter *dashboard_text* to lines suitable for compact notifications."""
    return [
        line
        for line in str(dashboard_text or "").splitlines()
        if line.strip() and not is_compact_dashboard_audit_line(line)
    ]


# ──────────────────────────────────────────────────────────────────────
#  8. Execution context adapter (IBKR ↔ flat bridge)
# ──────────────────────────────────────────────────────────────────────


def resolve_execution(source: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten an execution context from platform-specific nesting.

    When *source* contains an ``execution_annotations`` sub-dict (IBKR
    pattern where timing/risk data lives under
    ``signal_metadata.execution_annotations``), the annotations are
    merged into the returned flat dict so downstream helpers can access
    ``signal_date``, ``effective_date``, etc. at the top level.
    """
    annotations = source.get("execution_annotations")
    if isinstance(annotations, Mapping):
        return {**source, **annotations}
    return dict(source)


# ──────────────────────────────────────────────────────────────────────
#  8.5. Structured dashboard generation (Phase 3)
# ──────────────────────────────────────────────────────────────────────


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_dashboard_from_sources(
    portfolio: Mapping[str, Any],
    execution: Mapping[str, Any],
    *,
    translator: Callable[..., str],
    format_money: Callable[[float], str] | None = None,
    format_shares: Callable[..., str] | None = None,
) -> list[str]:
    """Generate dashboard lines from structured portfolio + execution data.

    Follows the Firstrade pattern: account overview → holdings table,
    all generated from typed fields rather than raw text parsing.

    *format_money* and *format_shares* allow the caller to inject
    platform-specific formatting (e.g. ``${:,.2f}``, unit labels).
    When omitted, plain ``${:,.2f}`` / ``{} shares`` defaults are used.
    """
    _fmt_money = format_money or (lambda v: f"${v:,.2f}")
    _fmt_shares = format_shares or (lambda v, **_: f"{v} shares")

    lines = [translator("account_overview_title")]
    cash_only_execution = bool(execution.get("cash_only_execution", portfolio.get("cash_only_execution", True)))
    total_equity = _safe_float(portfolio.get("total_equity"))
    if total_equity is not None:
        total_assets_label = "total_assets" if cash_only_execution else "total_assets_margin"
        lines.append(f"  - {translator(total_assets_label)}: {_fmt_money(total_equity)}")
    buying_power = _safe_float(portfolio.get("liquid_cash"))
    if buying_power is None:
        buying_power = _safe_float(portfolio.get("buying_power"))
    if buying_power is not None:
        buying_power_label = "buying_power" if cash_only_execution else "buying_power_margin"
        lines.append(f"  - {translator(buying_power_label)}: {_fmt_money(buying_power)}")
    reserved_cash = _safe_float(execution.get("reserved_cash"))
    if reserved_cash is not None:
        lines.append(f"  - {translator('reserved_cash')}: {_fmt_money(reserved_cash)}")
    investable_cash = _safe_float(execution.get("investable_cash"))
    if investable_cash is not None:
        lines.append(f"  - {translator('investable_cash')}: {_fmt_money(investable_cash)}")

    market_values = {
        str(symbol).upper(): float(value or 0.0)
        for symbol, value in dict(portfolio.get("market_values") or {}).items()
    }
    quantities = {
        str(symbol).upper(): value
        for symbol, value in dict(portfolio.get("quantities") or {}).items()
    }
    portfolio_rows = tuple(portfolio.get("portfolio_rows") or ())
    symbols: list[str] = []
    for row in portfolio_rows:
        if isinstance(row, (list, tuple)):
            symbols.extend(str(symbol).upper() for symbol in row)
        elif row:
            symbols.append(str(row).upper())
    if not symbols:
        symbols = sorted(market_values)
    if symbols:
        lines.append(translator("holdings_title"))
        for symbol in symbols:
            lines.append(
                "  - "
                + translator(
                    "holding_line",
                    symbol=symbol,
                    market_value=_fmt_money(market_values.get(symbol, 0.0)),
                    quantity=_fmt_shares(quantities.get(symbol, 0), translator=translator),
                )
            )
    return lines


# ──────────────────────────────────────────────────────────────────────
#  i18n key aliases (Phase 2 — non-breaking key-name unification)
# ──────────────────────────────────────────────────────────────────────

_I18N_KEY_ALIASES: dict[str, str] = {
    "trade_header": "rebalance_title",
    "heartbeat_header": "heartbeat_title",
}


def resolve_i18n_key(key: str) -> str:
    """Resolve a deprecated i18n key to its canonical form.

    Platform ``build_translator()`` functions can call this when a key is
    not found in the local I18N dict, providing backward compatibility
    while allowing renderers to standardise on the canonical names.
    """
    return _I18N_KEY_ALIASES.get(key, key)


# ──────────────────────────────────────────────────────────────────────
#  Convenience re-exports
# ──────────────────────────────────────────────────────────────────────

__all__ = [
    # formatting
    "format_percent",
    "format_percentile",
    "format_sample_count",
    "as_float_or_none",
    "present",
    "is_truthy",
    # text
    "split_detail_segment",
    "split_labeled_text",
    # localisation
    "localize_price_source_label",
    "localize_timing_contract",
    "translator_uses_zh",
    # volatility / risk
    "effective_volatility_delever_threshold",
    "format_volatility_delever_threshold_detail",
    "format_tqqq_volatility_delever_allocation_detail",
    "build_tqqq_risk_control_lines",
    # timing & snapshot
    "build_timing_audit_lines",
    "format_signal_snapshot_line",
    # dashboard
    "relabel_dashboard_cash_labels",
    "is_compact_dashboard_audit_line",
    "compact_dashboard_lines",
    # adapter
    "resolve_execution",
    # dashboard generation (Phase 3)
    "format_dashboard_from_sources",
    # i18n key aliases (Phase 2)
    "resolve_i18n_key",
]
