from __future__ import annotations

from collections.abc import Callable, Sequence

NotificationTranslator = Callable[..., str]
NotificationReplacement = tuple[str, str]


PRICE_SOURCE_LABELS: dict[str, tuple[str, str]] = {
    "longbridge_candlesticks": ("LongBridge 日线K线", "LongBridge daily candlesticks"),
    "schwab_daily_history_with_live_quote_overlay": ("Schwab 日线历史", "Schwab daily history"),
    "firstrade_ohlc_with_live_quote_overlay": ("Firstrade OHLC", "Firstrade OHLC"),
    "market_quote": ("实时行情报价", "market quote"),
    "mixed_market_quote_snapshot_close": (
        "实时行情报价 + 快照收盘价回补",
        "market quote + snapshot close fallback",
    ),
    "mixed_market_quote_historical_close": (
        "实时行情报价 + 历史收盘价回补",
        "market quote + historical close fallback",
    ),
    "snapshot_close": ("快照收盘价", "snapshot close"),
    "historical_close": ("历史收盘价", "historical close"),
    "market_data": ("市场数据", "market data"),
}


COMMON_ZH_NOTIFICATION_REPLACEMENTS: tuple[NotificationReplacement, ...] = (
    ("feature snapshot guard blocked execution", "特征快照校验阻止执行"),
    ("feature snapshot required", "需要特征快照"),
    ("feature snapshot compute failed", "特征快照计算失败"),
    ("feature_snapshot_download_failed", "特征快照下载失败"),
    ("feature_snapshot_compute_failed", "特征快照计算失败"),
    ("feature_snapshot_path_missing", "缺少特征快照路径"),
    ("feature_snapshot_missing", "特征快照不存在"),
    ("feature_snapshot_stale", "特征快照过旧"),
    ("feature_snapshot_manifest_missing", "缺少快照清单"),
    ("feature_snapshot_profile_mismatch", "快照策略名不匹配"),
    ("feature_snapshot_config_name_mismatch", "快照配置名不匹配"),
    ("feature_snapshot_config_path_mismatch", "快照配置路径不匹配"),
    ("feature_snapshot_contract_version_mismatch", "快照契约版本不匹配"),
    ("soxl_soxx_trend_income", "SOXL/SOXX 半导体趋势收益"),
    ("tqqq_growth_income", "TQQQ 增长收益"),
    ("global_etf_rotation", "全球 ETF 轮动"),
    ("russell_1000_multi_factor_defensive", "罗素1000多因子"),
    ("tech_communication_pullback_enhancement", "科技通信回调增强"),
    ("qqq_tech_enhancement", "科技通信回调增强"),
    ("mega_cap_leader_rotation_top50_balanced", "Mega Cap Top50 平衡龙头轮动"),
    ("outside_monthly_execution_window", "当前不在月度执行窗口"),
    ("no_execution_window_after_snapshot", "快照后没有可用执行窗口"),
    ("no-op", "不执行"),
    ("monthly snapshot cadence", "月度快照节奏"),
    ("waiting inside execution window", "等待进入执行窗口"),
    ("small_account_warning=true", "小账户提示=是"),
    ("portfolio_equity=", "净值="),
    ("min_recommended_equity=", "建议最低净值="),
    (
        "integer_shares_min_position_value_may_prevent_backtest_replication",
        "整数股和最小仓位限制可能导致实盘无法完全复现回测",
    ),
    (
        "integer-share minimum position sizing may prevent backtest replication",
        "整数股和最小仓位限制可能导致实盘无法完全复现回测",
    ),
    ("small account warning: portfolio equity", "小账户提示：净值"),
    ("small account warning", "小账户提示"),
    ("is below the recommended", "低于建议"),
    ("is below recommended", "低于建议"),
    ("snapshot_as_of=", "快照日期="),
    ("snapshot=", "快照日期="),
    ("allowed=", "允许日期="),
    ("<unknown>", "未知"),
    ("<none>", "无"),
    ("RISK-ON", "风险开启"),
    ("DE-LEVER", "降杠杆"),
    ("regime=hard_defense", "市场阶段=强防御"),
    ("regime=soft_defense", "市场阶段=软防御"),
    ("regime=risk_on", "市场阶段=进攻"),
    ("benchmark_trend=down", "基准趋势=向下"),
    ("benchmark_trend=up", "基准趋势=向上"),
    ("benchmark=down", "基准趋势=向下"),
    ("benchmark=up", "基准趋势=向上"),
    ("breadth=", "市场宽度="),
    ("target_stock=", "目标股票仓位="),
    ("realized_stock=", "实际股票仓位="),
    ("stock_exposure=", "股票目标仓位="),
    ("safe_haven=", "避险仓位="),
    ("selected=", "入选标的数="),
    ("top=", "前排标的="),
    ("no_selection", "无入选标的"),
    ("outside_execution_window", "当前不在执行窗口"),
    ("insufficient_buying_power", "购买力不足"),
    ("missing_price", "缺少报价"),
    ("no_equity", "无净值"),
    ("fail_closed", "关闭执行"),
    ("reason=", "原因="),
)


def translator_uses_zh(translator: NotificationTranslator) -> bool:
    sample = str(translator("no_trades"))
    return any("\u4e00" <= ch <= "\u9fff" for ch in sample)


def locale_uses_zh(locale: str | None) -> bool:
    return str(locale or "").strip().lower().startswith("zh")


def localize_price_source_label(
    value: object,
    *,
    translator: NotificationTranslator | None = None,
    locale: str | None = None,
) -> str:
    source = str(value or "").strip()
    use_zh = translator_uses_zh(translator) if translator is not None else locale_uses_zh(locale)
    unknown = "未知" if use_zh else "unknown"
    if not source:
        return unknown
    label = PRICE_SOURCE_LABELS.get(source)
    if label is not None:
        return label[0] if use_zh else label[1]
    return source.replace("_", " ")


def localize_notification_text(
    text: object,
    *,
    translator: NotificationTranslator,
    extra_replacements: Sequence[NotificationReplacement] = (),
) -> str:
    value = str(text or "").strip()
    if not value or not translator_uses_zh(translator):
        return value
    localized = value
    for source, target in (*tuple(extra_replacements), *COMMON_ZH_NOTIFICATION_REPLACEMENTS):
        localized = localized.replace(source, target)
    return localized
