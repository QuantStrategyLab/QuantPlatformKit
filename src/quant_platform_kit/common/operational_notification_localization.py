"""Locale-aware rendering helpers for human-facing operational alerts.

Runtime and workflow logs deliberately remain structured and machine-friendly.
This module is only for the short messages delivered to an operator through
Telegram, email, or another notification channel.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from quant_platform_kit.common.notification_localization import resolve_notification_locale


OperationalLocale = str


_TEXTS: dict[str, dict[str, str]] = {
    "zh": {
        "runtime_guard_title": "[运行守卫] {name}",
        "execution_report_heartbeat_title": "[执行回执心跳] {name}",
        "runtime_workflow_heartbeat_title": "[运行工作流心跳] {name}",
        "project": "项目：{value}",
        "lookback_minutes": "检查范围：过去 {value} 分钟",
        "lookback_hours": "检查范围：过去 {value} 小时",
        "issues": "问题：",
        "technical_details": "技术详情（原文）：",
        "recent_reports": "最近检查的回执（原文）：",
        "latest_runtime_run": "最近一次运行：",
        "workflow": "工作流：{value}",
        "status_normal": "状态：正常",
        "runtime_guard_service_configuration_error": "服务配置读取失败",
        "runtime_guard_cloud_run_log_query_failed": "Cloud Run 日志查询失败：{service}",
        "runtime_guard_cloud_run_failure_logs": "{count} 条 Cloud Run 失败日志：{service}",
        "runtime_guard_no_successful_request": "过去 {lookback_minutes} 分钟内未发现成功请求：{service}",
        "runtime_guard_scheduler_failure_logs": "发现 {count} 条 Cloud Scheduler 失败日志",
        "runtime_guard_scheduler_log_query_failed": "Cloud Scheduler 日志查询失败",
        "heartbeat_scheduler_policy_error": "运行目标调度策略读取失败",
        "heartbeat_list_failed": "执行回执列表读取失败",
        "heartbeat_no_recent_report": "过去 {lookback_hours} 小时内没有新的执行回执",
        "heartbeat_missing_acceptable_report": "缺少可接受的执行回执：{targets}",
        "heartbeat_no_acceptable_report": "最近 {count} 份执行回执均不符合要求",
        "heartbeat_runtime_target_disabled": "运行目标已停用；未提交订单。",
        "heartbeat_no_enabled_target": "没有与当前心跳匹配的可执行运行目标；未提交订单。",
        "heartbeat_no_scheduled_window_due": "当前没有应执行的交易窗口；未提交订单。",
        "heartbeat_no_scheduler_run_due": "当前没有应执行的调度任务；未提交订单。",
        "heartbeat_accepted_report": "已收到合格执行回执：{detail}",
        "activity_no_trade": "无交易",
        "activity_rebalance_recorded": "已记录调仓操作",
        "workflow_heartbeat_latest_failed": "最近一次运行未成功完成（结论：{conclusion}）",
        "workflow_heartbeat_no_success": "GitHub Actions 查询未返回成功的运行记录",
        "workflow_heartbeat_query_failed": "GitHub Actions 运行记录查询失败",
        "workflow_heartbeat_missing_dispatches": "已连续 {count} 个预期周期未发现运行（频率：{threshold}）",
        "attention_title": "{platform} · {account} · {strategy}",
        "attention_result_ok": "结果：运行正常",
        "attention_result_watch": "结果：观察中（无需立即处理）",
        "attention_result_action": "结果：需确认（已限制新风险或偏离待审）",
        "attention_result_halt": "结果：硬停 / 运行异常，需人工恢复",
        "attention_result_new_risk_prohibited": "结果：已禁止新增风险",
        "attention_reason": "原因：{code}",
        "attention_reason_none": "无",
        "attention_reason_unknown": "无法解释此原因码，请查看该次运行的风控记录",
        "attention_reason_new_risk_prohibited": "风控已拦截；调用方未提供具体原因码",
        "attention_reason_DAILY_LOSS_LIMIT_EXCEEDED": "当日亏损达到配置上限，已拦截新增风险",
        "attention_reason_DAILY_LOSS_UNKNOWN_FAIL_CLOSED": "当日亏损或上限无法核实，暂不允许新增风险",
        "attention_reason_OBSERVATION_NOT_COMPLETE": "账户快照不完整",
        "attention_reason_RECONCILIATION_NOT_VERIFIED": "账户对账尚未核实",
        "attention_reason_CIRCUIT_BREAKER_OPEN": "熔断保护已开启",
        "attention_reason_EQUITY_UNKNOWN_FAIL_CLOSED": "账户净值无法核实",
        "attention_reason_SNAPSHOT_VALIDATION_FAIL_CLOSED": "账户快照未通过校验",
        "attention_reason_CAPITAL_ENVELOPE_NEW_RISK_PROHIBITED": "资金风险约束不允许新增风险",
        "attention_reason_broker_outcome_unknown": "券商订单结果未知，禁止重复提交",
        "attention_reason_RECONCILE_ONLY": "账户处于仅对账状态",
        "attention_reason_drift_critical": "生产偏离严重（CRITICAL）",
        "attention_reason_drift_review": "生产偏离待审（REVIEW）",
        "attention_reason_drift_watch": "生产偏离观察（WATCH）",
        "attention_reason_drift_status_unknown": "生产偏离状态未知",
        "attention_reason_operational_uncertain": "运行状态不确定 / 故障",
        "attention_reason_hard_park": "硬停（需授权恢复）",
        "attention_reason_mandate_dd_exhausted": "授权回撤额度已用尽",
        "attention_reason_mandate_dd_elevated": "授权回撤接近上限",
        "attention_reason_PRODUCTION_DRIFT_CRITICAL": "生产偏离严重（CRITICAL）",
        "attention_reason_PRODUCTION_DRIFT_REVIEW": "生产偏离待审（REVIEW）",
        "attention_reason_PRODUCTION_DRIFT_WATCH": "生产偏离观察（WATCH）",
        "attention_reason_PRODUCTION_DRIFT_STATUS_INVALID_FAIL_CLOSED": "生产偏离状态非法（失败关闭）",
        "attention_next_none": "下一步：无需操作",
        "attention_next_console_optional": "下一步：可在管理站查看详情",
        "attention_next_open_console_confirm": "下一步：打开管理站确认意图（确认意图不等于放行实盘）",
        "attention_next_open_console_resume": "下一步：打开管理站处理恢复 / 复位（需授权）",
        "attention_next_review_daily_loss": "下一步：在管理站核对当日净值、资金进出和亏损上限；保持禁止新增风险，确认意图不会解除保护",
        "attention_next_inspect_guard_reason": "下一步：在管理站查看该次运行的风控原因码和账户状态；保持保护，确认意图不会解除保护",
    },
    "en": {
        "runtime_guard_title": "[Runtime Guard] {name}",
        "execution_report_heartbeat_title": "[Execution Report Heartbeat] {name}",
        "runtime_workflow_heartbeat_title": "[Runtime Workflow Heartbeat] {name}",
        "project": "Project: {value}",
        "lookback_minutes": "Lookback: {value} minutes",
        "lookback_hours": "Lookback: {value} hours",
        "issues": "Issues:",
        "technical_details": "Technical details (original):",
        "recent_reports": "Recent reports (original):",
        "latest_runtime_run": "Latest runtime run:",
        "workflow": "Workflow: {value}",
        "status_normal": "Status: normal",
        "runtime_guard_service_configuration_error": "Service configuration could not be read",
        "runtime_guard_cloud_run_log_query_failed": "Cloud Run log query failed: {service}",
        "runtime_guard_cloud_run_failure_logs": "{count} Cloud Run failure log(s): {service}",
        "runtime_guard_no_successful_request": "No successful request for {service} in the last {lookback_minutes} minutes",
        "runtime_guard_scheduler_failure_logs": "{count} Cloud Scheduler failure log(s) found",
        "runtime_guard_scheduler_log_query_failed": "Cloud Scheduler log query failed",
        "heartbeat_scheduler_policy_error": "Runtime-target scheduler policy could not be read",
        "heartbeat_list_failed": "Execution-report listing failed",
        "heartbeat_no_recent_report": "No new execution report in the last {lookback_hours} hours",
        "heartbeat_missing_acceptable_report": "Missing acceptable execution report: {targets}",
        "heartbeat_no_acceptable_report": "None of the most recent {count} execution reports was acceptable",
        "heartbeat_runtime_target_disabled": "Runtime target is disabled; no order was submitted.",
        "heartbeat_no_enabled_target": "No enabled runtime target matches this heartbeat; no order was submitted.",
        "heartbeat_no_scheduled_window_due": "No scheduled trading window was due; no order was submitted.",
        "heartbeat_no_scheduler_run_due": "No scheduler-backed run was due; no order was submitted.",
        "heartbeat_accepted_report": "An acceptable execution report was received: {detail}",
        "activity_no_trade": "no trade",
        "activity_rebalance_recorded": "rebalance action recorded",
        "workflow_heartbeat_latest_failed": "The latest runtime run did not complete successfully (conclusion: {conclusion})",
        "workflow_heartbeat_no_success": "The GitHub Actions query returned no successful runtime run",
        "workflow_heartbeat_query_failed": "The GitHub Actions runtime-run query failed",
        "workflow_heartbeat_missing_dispatches": "No runtime dispatch was found for {count} expected interval(s) (threshold: {threshold})",
        "attention_title": "{platform} · {account} · {strategy}",
        "attention_result_ok": "Result: normal",
        "attention_result_watch": "Result: watch (no immediate action)",
        "attention_result_action": "Result: action needed (new risk limited or drift review)",
        "attention_result_halt": "Result: halt / operational fault — human recovery required",
        "attention_result_new_risk_prohibited": "Result: new risk additions prohibited",
        "attention_reason": "Reason: {code}",
        "attention_reason_none": "none",
        "attention_reason_unknown": "unrecognized reason code; inspect this run's guard record",
        "attention_reason_new_risk_prohibited": "a risk guard blocked additions; the caller did not provide the specific reason code",
        "attention_reason_DAILY_LOSS_LIMIT_EXCEEDED": "daily loss reached the configured limit; new risk additions were blocked",
        "attention_reason_DAILY_LOSS_UNKNOWN_FAIL_CLOSED": "daily loss or its limit could not be verified; new risk remains blocked",
        "attention_reason_OBSERVATION_NOT_COMPLETE": "account snapshot is incomplete",
        "attention_reason_RECONCILIATION_NOT_VERIFIED": "account reconciliation is not verified",
        "attention_reason_CIRCUIT_BREAKER_OPEN": "the circuit breaker is open",
        "attention_reason_EQUITY_UNKNOWN_FAIL_CLOSED": "account equity could not be verified",
        "attention_reason_SNAPSHOT_VALIDATION_FAIL_CLOSED": "account snapshot validation failed",
        "attention_reason_CAPITAL_ENVELOPE_NEW_RISK_PROHIBITED": "capital risk limits prohibit new risk additions",
        "attention_reason_broker_outcome_unknown": "broker order outcome is unknown; do not resubmit",
        "attention_reason_RECONCILE_ONLY": "the account is in reconcile-only mode",
        "attention_reason_drift_critical": "production drift critical",
        "attention_reason_drift_review": "production drift review",
        "attention_reason_drift_watch": "production drift watch",
        "attention_reason_drift_status_unknown": "production drift status unknown",
        "attention_reason_operational_uncertain": "operational uncertainty / fault",
        "attention_reason_hard_park": "hard park (authorized recovery required)",
        "attention_reason_mandate_dd_exhausted": "mandate drawdown budget exhausted",
        "attention_reason_mandate_dd_elevated": "mandate drawdown elevated",
        "attention_reason_PRODUCTION_DRIFT_CRITICAL": "production drift critical",
        "attention_reason_PRODUCTION_DRIFT_REVIEW": "production drift review",
        "attention_reason_PRODUCTION_DRIFT_WATCH": "production drift watch",
        "attention_reason_PRODUCTION_DRIFT_STATUS_INVALID_FAIL_CLOSED": "production drift status invalid (fail closed)",
        "attention_next_none": "Next: none",
        "attention_next_console_optional": "Next: review details in the management console if needed",
        "attention_next_open_console_confirm": "Next: open the management console to confirm intent (confirming intent does not enable live)",
        "attention_next_open_console_resume": "Next: open the management console for recovery / reset (authorization required)",
        "attention_next_review_daily_loss": "Next: review today's equity, cash flows and daily-loss limit in the console; keep new risk blocked. Confirming intent does not release the guard",
        "attention_next_inspect_guard_reason": "Next: inspect this run's guard reason codes and account state; keep protections active. Confirming intent does not release the guard",
    },
}


def resolve_operational_notification_locale(value: object | None) -> OperationalLocale:
    """Normalize the operator's configured notification locale.

    Chinese locale variants intentionally share the concise ``zh`` templates;
    unknown values fall back to English to preserve the previous behavior.
    """

    return resolve_notification_locale(value)


def operational_notification_text(
    locale: object | None,
    key: str,
    /,
    **values: object,
) -> str:
    """Render one stable operational-message key in the requested locale."""

    normalized = resolve_operational_notification_locale(locale)
    template = _TEXTS[normalized].get(key) or _TEXTS["en"].get(key) or key
    return template.format(**values)


def localize_attention_reason_code(locale: object | None, code: object) -> str:
    """Translate a known attention / production-drift reason code for operators.

    Unknown codes stay as the original machine token so diagnostics remain intact.
    """

    raw = str(code or "").strip() or "none"
    key = f"attention_reason_{raw}"
    normalized = resolve_operational_notification_locale(locale)
    template = _TEXTS[normalized].get(key) or _TEXTS["en"].get(key)
    return template if template is not None else raw


def localize_operational_activity(locale: object | None, detail: object) -> str:
    """Translate known activity labels while keeping diagnostic values intact."""

    value = str(detail or "").strip()
    known = {
        "no trade": "activity_no_trade",
        "rebalance action recorded": "activity_rebalance_recorded",
    }
    key = known.get(value.lower())
    return operational_notification_text(locale, key) if key else value


def format_operational_alert(
    *,
    locale: object | None,
    alert_type: str,
    name: object,
    context: Mapping[str, object] | None = None,
    issues: Sequence[str] = (),
    recent_reports: Sequence[str] = (),
    technical_details: Sequence[str] = (),
    latest_runtime_run: Sequence[str] = (),
    workflow_url: object | None = None,
) -> str:
    """Build a concise localized operator notification.

    ``recent_reports`` and ``technical_details`` are expressly labelled as
    original diagnostic text.  They may contain broker or cloud-provider
    wording and therefore must not be presented as localized summaries.
    """

    title_key = f"{str(alert_type).strip()}_title"
    lines = [operational_notification_text(locale, title_key, name=str(name or "runtime"))]
    for key, value in (context or {}).items():
        lines.append(operational_notification_text(locale, str(key), value=value))
    if issues:
        lines.extend([operational_notification_text(locale, "issues"), *(f"- {item}" for item in issues)])
    if recent_reports:
        lines.extend(
            [
                operational_notification_text(locale, "recent_reports"),
                *(str(item) for item in recent_reports),
            ]
        )
    if latest_runtime_run:
        lines.extend(
            [
                operational_notification_text(locale, "latest_runtime_run"),
                *(str(item) for item in latest_runtime_run),
            ]
        )
    if technical_details:
        lines.extend(
            [
                operational_notification_text(locale, "technical_details"),
                *(str(item) for item in technical_details),
            ]
        )
    if workflow_url:
        lines.append(operational_notification_text(locale, "workflow", value=str(workflow_url)))
    return "\n".join(line for line in lines if line)


def format_operational_heartbeat_status(
    *,
    locale: object | None,
    name: object,
    detail: object,
) -> str:
    """Render the opt-in normal execution-heartbeat summary."""

    return "\n".join(
        (
            operational_notification_text(
                locale,
                "execution_report_heartbeat_title",
                name=str(name or "runtime"),
            ),
            operational_notification_text(locale, "status_normal"),
            str(detail or ""),
        )
    )


# A separate opt-in renderer: legacy entrypoints above retain their exact output.
_RECEIPT_TEXTS = {
    "zh": {
        "title": "[执行回执检查]",
        "observed_at": "检查时间：{value}",
        "due_at": "最近应执行时间：{value}",
        "orders": "本轮提交订单：{value}",
        "unknown": "未知",
        "run": "运行记录：{value}",
        "category": "{label}：{count} 份",
        "accepted": "回执符合既有验收要求",
        "blocked_run": "已运行但执行被阻断",
        "strategy_risk_rejected": "本轮已运行但被风控拦截",
        "skipped_before_due": "早于最近应执行时间，已跳过",
        "skipped_outside_window": "不在检查窗口内，已跳过",
        "receipt_missing": "缺少执行回执",
        "receipt_stale": "执行回执已过期",
        "receipt_unacceptable": "执行回执不符合既有验收要求",
        "auth_failure": "认证失败",
        "unknown_category": "回执分类未知",
    },
    "en": {
        "title": "[Execution receipt check]",
        "observed_at": "Checked at: {value}",
        "due_at": "Latest execution due: {value}",
        "orders": "Orders submitted this run: {value}",
        "unknown": "Unknown",
        "run": "Run record: {value}",
        "category": "{label}: {count} report(s)",
        "accepted": "Receipt meets existing acceptance rules",
        "blocked_run": "Run observed but execution blocked",
        "strategy_risk_rejected": "Run observed but blocked by strategy risk checks",
        "skipped_before_due": "Skipped before latest execution due",
        "skipped_outside_window": "Skipped outside the check window",
        "receipt_missing": "Execution receipt missing",
        "receipt_stale": "Execution receipt stale",
        "receipt_unacceptable": "Execution receipt fails existing acceptance rules",
        "auth_failure": "Authentication failed",
        "unknown_category": "Receipt category unknown",
    },
}


def format_sgt_time(value: datetime | None, *, locale: object | None = None) -> str:
    """Format an aware datetime without silently assigning a missing timezone."""
    from zoneinfo import ZoneInfo

    normalized = resolve_operational_notification_locale(locale)
    if value is None:
        return _RECEIPT_TEXTS[normalized]["unknown"]
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("notification_time_timezone_missing")
    stamp = value.astimezone(ZoneInfo("Asia/Singapore")).strftime("%Y-%m-%d %H:%M:%S")
    return stamp + ("（新加坡时间）" if normalized == "zh" else " SGT")


def format_receipt_alert(
    *, locale: object | None, categories: Mapping[str, int | None],
    observed_at: datetime | None = None, due_at: datetime | None = None,
    orders_submitted_count: int | None = None,
    run_url: str | None = None,
) -> str:
    """Render caller-proven receipt categories only; never infer acceptance.

    Raw report URIs, account names and diagnostic text are not accepted fields.
    Unknown category tokens are not echoed. Counts refer to inspected reports;
    orders_submitted_count refers only to the caller's single proven run.
    """
    from urllib.parse import urlsplit, urlunsplit

    normalized = resolve_operational_notification_locale(locale)
    text = _RECEIPT_TEXTS[normalized]
    lines = [text["title"], text["observed_at"].format(value=format_sgt_time(observed_at, locale=normalized)),
             text["due_at"].format(value=format_sgt_time(due_at, locale=normalized))]
    known_categories = {"accepted", "blocked_run", "strategy_risk_rejected", "skipped_before_due",
                        "skipped_outside_window", "receipt_missing", "receipt_stale",
                        "receipt_unacceptable", "auth_failure"}
    for category, count in categories.items():
        if count is not None and (type(count) is not int or count < 0):
            raise ValueError("notification_receipt_count_invalid")
        if count == 0:
            continue
        label = text[category] if category in known_categories else text["unknown_category"]
        lines.append(text["category"].format(label=label, count=text["unknown"] if count is None else count))
    if orders_submitted_count is not None and (type(orders_submitted_count) is not int or orders_submitted_count < 0):
        raise ValueError("notification_order_count_invalid")
    lines.append(text["orders"].format(value=text["unknown"] if orders_submitted_count is None else orders_submitted_count))
    if run_url:
        parsed = urlsplit(run_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("notification_run_url_invalid")
        # Links are supplied by the caller, never reconstructed from account IDs.
        safe_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        lines.append(text["run"].format(value=safe_url))
    return "\n".join(lines)
