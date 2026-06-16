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

STRATEGY_PLUGIN_I18N: dict[str, dict[str, str]] = {
    "zh": {
        "strategy_plugin_alert_locale": "zh-CN",
        "strategy_plugin_alert_reason_joiner": "、",
        "strategy_plugin_alert_reason_none": "未提供明确原因",
        "strategy_plugin_line": "🧩 插件：{plugin} | 状态：{route} | 提醒：{action}",
        "strategy_plugin_alert_subject": "策略插件提醒：{plugin} | {route}",
        "strategy_plugin_alert_title": "【策略插件提醒】",
        "strategy_plugin_alert_context": "发布来源：{context}",
        "strategy_plugin_alert_context_strategy_plugin_publish": "插件发布 / {target}",
        "strategy_plugin_alert_target": "{target_name}：{target}",
        "strategy_plugin_alert_target_name_strategy": "策略",
        "strategy_plugin_alert_target_name_notification_target": "通知对象",
        "strategy_plugin_alert_strategy": "策略：{strategy}",
        "strategy_plugin_alert_plugin": "插件：{plugin}",
        "strategy_plugin_alert_situation": "当前情况：{situation}",
        "strategy_plugin_alert_trigger": "触发原因：{reasons}",
        "strategy_plugin_alert_recommendation": "建议处理：{recommendation}",
        "strategy_plugin_alert_status": "插件状态：{route}",
        "strategy_plugin_alert_action": "动作边界：{action}",
        "strategy_plugin_alert_mode": "模式：{mode}",
        "strategy_plugin_alert_as_of": "信号时间：{as_of}",
        "strategy_plugin_alert_guidance": "处置建议：{guidance}",
        "strategy_plugin_alert_scope_note": "自动化边界：{scope_note}",
        "strategy_plugin_alert_scope": "这条通知只用于人工复核；插件不会自动下单，也不会直接修改仓位",
        "strategy_plugin_name_crisis_response_shadow": "危机观察通知",
        "strategy_plugin_name_macro_risk_governor": "宏观风险控制通知",
        "strategy_plugin_name_market_regime_control": "市场状态控制",
        "strategy_plugin_name_panic_reversal_shadow": "恐慌反转观察通知",
        "strategy_plugin_name_taco_rebound_shadow": "TACO 反弹观察通知",
        "strategy_plugin_notification_target_market_regime_notification": "统一市场状态通知",
        "strategy_plugin_mode_shadow": "影子观察",
        "strategy_plugin_route_blocked": "已阻断",
        "strategy_plugin_route_crisis": "危机",
        "strategy_plugin_route_delever": "降杠杆",
        "strategy_plugin_route_no_action": "未触发",
        "strategy_plugin_route_opportunity_watch": "机会观察",
        "strategy_plugin_route_panic_reversal": "恐慌反转",
        "strategy_plugin_route_risk_off": "风险关闭",
        "strategy_plugin_route_risk_reduced": "风险降低",
        "strategy_plugin_route_true_crisis": "真危机",
        "strategy_plugin_route_taco_rebound": "TACO 反弹确认",
        "strategy_plugin_route_unknown_route": "未知状态",
        "strategy_plugin_route_watch": "观察",
        "strategy_plugin_action_no_action": "不操作",
        "strategy_plugin_action_watch_only": "仅观察，不自动交易",
        "strategy_plugin_action_notify_manual_review": "通知人工复核",
        "strategy_plugin_action_defend": "防守",
        "strategy_plugin_action_delever": "降杠杆",
        "strategy_plugin_action_blocked": "已阻断",
        "strategy_plugin_action_monitor": "持续观察",
        "strategy_plugin_action_unknown_action": "未知提醒",
        "strategy_plugin_situation_watch_watch_only": "观察状态：插件检测到市场进入观察区。",
        "strategy_plugin_situation_market_regime_control_watch_watch_only": "波动观察：市场状态控制检测到波动或宏观压力进入观察区。",
        "strategy_plugin_situation_market_regime_control_risk_reduced_delever": "自动降杠杆候选：市场压力升高，策略可按已批准的可回测规则降低杠杆。",
        "strategy_plugin_situation_market_regime_control_risk_off_defend": "防守状态：市场状态进入风险关闭区，机会类信号应先让位给风险控制。",
        "strategy_plugin_situation_market_regime_control_opportunity_watch_notify_manual_review": "机会观察：出现可能的反弹或低吸窗口，当前证据只够人工复核。",
        "strategy_plugin_situation_market_regime_control_blocked_blocked": "数据阻断：数据质量或新鲜度保护已触发，当前插件信号不能直接使用。",
        "strategy_plugin_situation_taco_rebound_shadow_taco_rebound_notify_manual_review": "TACO 反弹观察：出现可能的反弹窗口，属于人工复核机会。",
        "strategy_plugin_situation_true_crisis_defend": "危机防守：危机防守信号已触发，需要优先处理风险敞口。",
        "strategy_plugin_situation_delever_delever": "降杠杆：降杠杆信号已触发，需要按策略规则压低风险敞口。",
        "strategy_plugin_situation_notify_manual_review": "人工复核：插件发现需要人工判断的市场状态。",
        "strategy_plugin_situation_default": "状态提醒：插件发现需要关注的市场状态。",
        "strategy_plugin_recommendation_market_regime_control_watch_watch_only": "核对触发项、近几日波动和当前仓位杠杆；这类观察通知不自动改仓位，需要调仓时以策略运行结果或人工确认执行。",
        "strategy_plugin_recommendation_market_regime_control_risk_reduced_delever": "核对策略运行结果、账户约束和降杠杆阈值；若策略侧已触发自动规则，由策略通知和仓位适配器执行。",
        "strategy_plugin_recommendation_market_regime_control_risk_off_defend": "暂停机会类加仓判断，先确认防守仓位是否符合策略规则；恢复进攻前等待风险关闭状态解除。",
        "strategy_plugin_recommendation_market_regime_control_opportunity_watch_notify_manual_review": "人工核对反弹质量、成交/趋势确认和失效条件；确认前只作为低吸候选，不直接转成自动买入。",
        "strategy_plugin_recommendation_market_regime_control_blocked_blocked": "先修复数据源、产物新鲜度或校验失败项；阻断解除前不要基于这条信号调仓。",
        "strategy_plugin_recommendation_watch_only": "核对触发项、市场环境和现有仓位；观察通知不自动改仓位，需要调仓时以策略运行结果或人工确认执行。",
        "strategy_plugin_recommendation_notify_manual_review": "人工复核触发原因、新闻/宏观背景、现有仓位和失效条件；未确认前不要把这条通知当成下单指令。",
        "strategy_plugin_recommendation_defend": "优先确认策略运行结果和账户约束；如果策略已触发自动防守，由策略通知和仓位适配器执行，插件通知本身不直接下单。",
        "strategy_plugin_recommendation_delever": "优先确认策略运行结果和账户约束；如果策略已触发自动降杠杆，由策略通知和仓位适配器执行，插件通知本身不直接下单。",
        "strategy_plugin_recommendation_blocked": "先修复数据源或产物新鲜度，再决定是否人工处理；不要基于被阻断的信号调仓。",
        "strategy_plugin_recommendation_default": "先人工复核，再决定是否交给策略规则或人工流程处理；不要把插件通知直接当作交易指令。",
        "strategy_plugin_guidance_crisis_response_shadow_true_crisis_defend": "优先考虑降低杠杆或清理杠杆仓位，暂停加仓；如需保留风险敞口，先降到可承受的小仓位。",
        "strategy_plugin_guidance_crisis_response_shadow_no_action_blocked": "危机路线被风控阻断；先核对数据新鲜度和外部情境，不建议仅凭此条加仓。",
        "strategy_plugin_guidance_macro_risk_governor_delever_delever": "宏观风险控制建议降低杠杆敞口；是否执行由策略侧可回测规则和仓位适配器决定。",
        "strategy_plugin_guidance_macro_risk_governor_crisis_defend": "宏观危机信号建议风险仓位转向防守或现金类资产，直到压力缓和。",
        "strategy_plugin_guidance_market_regime_control_risk_off_defend": "市场状态控制进入风险关闭；机会类信号先不执行，风险仓位应保持防守。",
        "strategy_plugin_guidance_market_regime_control_risk_reduced_delever": "市场状态控制建议降杠杆；自动仓位调整只按策略侧已批准的可回测规则执行。",
        "strategy_plugin_guidance_market_regime_control_opportunity_watch_notify_manual_review": "仅作人工复核：市场状态允许有限机会观察，但插件本身不会下单或直接改仓位。",
        "strategy_plugin_guidance_market_regime_control_blocked_blocked": "市场状态控制被数据质量或新鲜度保护阻断；先核对数据源和产物，再决定是否人工处理。",
        "strategy_plugin_guidance_taco_rebound_shadow_taco_rebound_notify_manual_review": "TACO 仅提示可能的反弹窗口；可考虑小仓位、分批、预设止损/失效条件的人工博弈，不建议一次性满仓。",
    },
    "en": {
        "strategy_plugin_alert_locale": "en-US",
        "strategy_plugin_alert_reason_joiner": ", ",
        "strategy_plugin_alert_reason_none": "no explicit reason provided",
        "strategy_plugin_line": "🧩 Plugin: {plugin} | status: {route} | notice: {action}",
        "strategy_plugin_alert_subject": "Strategy plugin notice: {plugin} | {route}",
        "strategy_plugin_alert_title": "【Strategy Plugin Notice】",
        "strategy_plugin_alert_context": "Source: {context}",
        "strategy_plugin_alert_context_strategy_plugin_publish": "plugin publish / {target}",
        "strategy_plugin_alert_target": "{target_name}: {target}",
        "strategy_plugin_alert_target_name_strategy": "Strategy",
        "strategy_plugin_alert_target_name_notification_target": "Notification scope",
        "strategy_plugin_alert_strategy": "Strategy: {strategy}",
        "strategy_plugin_alert_plugin": "Plugin: {plugin}",
        "strategy_plugin_alert_situation": "Situation: {situation}",
        "strategy_plugin_alert_trigger": "Trigger: {reasons}",
        "strategy_plugin_alert_recommendation": "Suggested review: {recommendation}",
        "strategy_plugin_alert_status": "Plugin status: {route}",
        "strategy_plugin_alert_action": "Action boundary: {action}",
        "strategy_plugin_alert_mode": "Mode: {mode}",
        "strategy_plugin_alert_as_of": "Signal as-of: {as_of}",
        "strategy_plugin_alert_guidance": "Manual guidance: {guidance}",
        "strategy_plugin_alert_scope_note": "Automation boundary: {scope_note}",
        "strategy_plugin_alert_scope": "Manual review notice only; the plugin does not place orders or directly change allocations",
        "strategy_plugin_name_crisis_response_shadow": "Crisis Watch Notice",
        "strategy_plugin_name_macro_risk_governor": "Macro Risk Governor Notice",
        "strategy_plugin_name_market_regime_control": "Market Regime Control",
        "strategy_plugin_name_panic_reversal_shadow": "Panic Reversal Watch Notice",
        "strategy_plugin_name_taco_rebound_shadow": "TACO Rebound Watch Notice",
        "strategy_plugin_notification_target_market_regime_notification": "Unified market-regime notification",
        "strategy_plugin_mode_shadow": "shadow",
        "strategy_plugin_route_blocked": "blocked",
        "strategy_plugin_route_crisis": "crisis",
        "strategy_plugin_route_delever": "de-lever",
        "strategy_plugin_route_no_action": "no alert",
        "strategy_plugin_route_opportunity_watch": "opportunity watch",
        "strategy_plugin_route_panic_reversal": "panic reversal",
        "strategy_plugin_route_risk_off": "risk off",
        "strategy_plugin_route_risk_reduced": "risk reduced",
        "strategy_plugin_route_true_crisis": "true crisis",
        "strategy_plugin_route_taco_rebound": "TACO rebound confirmed",
        "strategy_plugin_route_unknown_route": "unknown status",
        "strategy_plugin_route_watch": "watch",
        "strategy_plugin_action_no_action": "no action",
        "strategy_plugin_action_watch_only": "notify only",
        "strategy_plugin_action_notify_manual_review": "notify manual review",
        "strategy_plugin_action_defend": "defend",
        "strategy_plugin_action_delever": "de-lever",
        "strategy_plugin_action_blocked": "blocked",
        "strategy_plugin_action_monitor": "watch",
        "strategy_plugin_action_unknown_action": "unknown notice",
        "strategy_plugin_situation_watch_watch_only": "Watch state: the plugin detected that the market has entered a watch zone.",
        "strategy_plugin_situation_market_regime_control_watch_watch_only": "Volatility watch: market-regime control detected volatility or macro pressure in the watch zone.",
        "strategy_plugin_situation_market_regime_control_risk_reduced_delever": "Automatic de-lever candidate: market stress has risen, and the strategy may reduce leverage under approved backtestable rules.",
        "strategy_plugin_situation_market_regime_control_risk_off_defend": "Defensive state: the market regime is in the risk-off zone, so opportunity signals should give way to risk control.",
        "strategy_plugin_situation_market_regime_control_opportunity_watch_notify_manual_review": "Opportunity watch: a possible rebound or dip-buy window is present, but the evidence is only strong enough for manual review.",
        "strategy_plugin_situation_market_regime_control_blocked_blocked": "Data block: data-quality or freshness guards fired, so the current plugin signal cannot be used directly.",
        "strategy_plugin_situation_taco_rebound_shadow_taco_rebound_notify_manual_review": "TACO rebound watch: a possible rebound window is present and needs manual review.",
        "strategy_plugin_situation_true_crisis_defend": "Crisis defense: a crisis-defense signal is active and risk exposure needs priority review.",
        "strategy_plugin_situation_delever_delever": "De-lever: a de-lever signal is active and risk exposure should be reduced under strategy rules.",
        "strategy_plugin_situation_notify_manual_review": "Manual review: the plugin found a market state that needs human judgment.",
        "strategy_plugin_situation_default": "State notice: the plugin found a market state that needs attention.",
        "strategy_plugin_recommendation_market_regime_control_watch_watch_only": "Check the trigger, recent volatility, and current leverage; this watch notice does not change allocations automatically, and any position change should come from the strategy run or an explicit manual decision.",
        "strategy_plugin_recommendation_market_regime_control_risk_reduced_delever": "Check the strategy run, account constraints, and de-lever thresholds; if the strategy-side automatic rule fired, execution belongs to the strategy notification and position adapter.",
        "strategy_plugin_recommendation_market_regime_control_risk_off_defend": "Pause opportunity adds and confirm whether defensive exposure matches strategy rules; wait for the risk-off state to clear before resuming offensive signals.",
        "strategy_plugin_recommendation_market_regime_control_opportunity_watch_notify_manual_review": "Manually review rebound quality, volume/trend confirmation, and the invalidation level; treat it as a dip-buy candidate only until confirmed.",
        "strategy_plugin_recommendation_market_regime_control_blocked_blocked": "Fix source data, artifact freshness, or validation failures first; do not adjust exposure from this signal until the block clears.",
        "strategy_plugin_recommendation_watch_only": "Review the trigger, market context, and current holdings; watch notices do not change allocations automatically, and any trade should come from the strategy run or an explicit manual decision.",
        "strategy_plugin_recommendation_notify_manual_review": "Review the trigger, news or macro context, current exposure, and invalidation level before acting; do not treat this notice as an order instruction.",
        "strategy_plugin_recommendation_defend": "Confirm the strategy run and account constraints first; if automatic defense is active, execution belongs to the strategy notification and position adapter, not to this plugin notice.",
        "strategy_plugin_recommendation_delever": "Confirm the strategy run and account constraints first; if automatic de-levering is active, execution belongs to the strategy notification and position adapter, not to this plugin notice.",
        "strategy_plugin_recommendation_blocked": "Fix source data or artifact freshness before acting; do not adjust exposure from a blocked signal.",
        "strategy_plugin_recommendation_default": "Review manually first, then decide whether the action belongs to strategy rules or a manual process; do not treat the plugin notice as a trade instruction.",
        "strategy_plugin_guidance_crisis_response_shadow_true_crisis_defend": "Consider reducing or clearing leveraged exposure, then pause new risk additions; if keeping exposure, resize it to a small amount you can tolerate.",
        "strategy_plugin_guidance_crisis_response_shadow_no_action_blocked": "A guard blocked the crisis route; verify data freshness and external context before acting on this alert.",
        "strategy_plugin_guidance_macro_risk_governor_delever_delever": "The macro risk governor suggests reducing leveraged exposure; execution is controlled by strategy-side backtestable rules and position adapters.",
        "strategy_plugin_guidance_macro_risk_governor_crisis_defend": "The macro crisis signal suggests moving the risk sleeve toward defensive or cash-like exposure until stress de-escalates.",
        "strategy_plugin_guidance_market_regime_control_risk_off_defend": "Market regime control is risk-off; opportunity signals should stay blocked and risk exposure should remain defensive.",
        "strategy_plugin_guidance_market_regime_control_risk_reduced_delever": "Market regime control suggests de-levering; automatic position changes only follow strategy-side approved, backtestable rules.",
        "strategy_plugin_guidance_market_regime_control_opportunity_watch_notify_manual_review": "Manual review only: the market regime allows bounded opportunity watch, but the plugin does not place orders or directly change allocations.",
        "strategy_plugin_guidance_market_regime_control_blocked_blocked": "Market regime control was blocked by data-quality or freshness guards; verify source data and artifacts before manual action.",
        "strategy_plugin_guidance_taco_rebound_shadow_taco_rebound_notify_manual_review": "TACO only flags a possible rebound window; consider a small staged manual probe with a predefined invalidation level instead of full-size exposure.",
    },
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


def merge_strategy_plugin_i18n(
    i18n: dict[str, dict[str, str]],
    *,
    shared_wins: bool = True,
) -> dict[str, dict[str, str]]:
    merged = {str(locale): dict(values) for locale, values in i18n.items()}
    for locale, shared_values in STRATEGY_PLUGIN_I18N.items():
        existing = merged.setdefault(locale, {})
        if shared_wins:
            existing.update(shared_values)
        else:
            merged[locale] = {**shared_values, **existing}
    return merged


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
