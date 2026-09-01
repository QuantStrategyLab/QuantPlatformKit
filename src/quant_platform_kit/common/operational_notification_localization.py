"""Locale-aware rendering helpers for human-facing operational alerts.

Runtime and workflow logs deliberately remain structured and machine-friendly.
This module is only for the short messages delivered to an operator through
Telegram, email, or another notification channel.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


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
        "workflow_heartbeat_missing_dispatches": "已连续 {count} 个预期周期未发现运行（阈值：{threshold}）",
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
        "workflow_heartbeat_missing_dispatches": "No runtime dispatch was found for {count} expected interval(s) (threshold: {threshold})",
    },
}


def resolve_operational_notification_locale(value: object | None) -> OperationalLocale:
    """Normalize the operator's configured notification locale.

    Chinese locale variants intentionally share the concise ``zh`` templates;
    unknown values fall back to English to preserve the previous behavior.
    """

    return "zh" if str(value or "").strip().lower().replace("_", "-").startswith("zh") else "en"


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
