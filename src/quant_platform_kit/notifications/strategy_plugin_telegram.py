"""Telegram notification helpers for strategy plugin alerts."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from quant_platform_kit.common.strategy_plugins import (
    StrategyPluginAlertMessage,
    build_strategy_plugin_alert_messages,
)

from .alert_marker import CloudAlertMarkerStore, _clean_relative_key
from ._redaction import redact_sensitive_text
from .telegram import (
    DEFAULT_TELEGRAM_BOT_API_BASE_URL,
    parse_telegram_chat_ids,
    send_strategy_plugin_telegram,
)

_DEFAULT_TELEGRAM_BODY_MAX_CHARS = 3900
_MARKET_REGIME_CONTROL_PLUGIN = "market_regime_control"
_ZH_MARKET_REGIME_ROUTE_LABELS = {
    "true_crisis": "黑天鹅",
    "crisis": "黑天鹅",
    "risk_off": "黑天鹅",
    "opportunity_watch": "抄底机会",
    "panic_reversal": "抄底机会",
    "taco_rebound": "抄底机会",
    "risk_reduced": "机会被否决",
    "delever": "机会被否决",
    "blocked": "数据阻断",
    "watch": "观察",
}
_EN_MARKET_REGIME_ROUTE_LABELS = {
    "true_crisis": "black swan risk",
    "crisis": "black swan risk",
    "risk_off": "black swan risk",
    "opportunity_watch": "dip-buy opportunity",
    "panic_reversal": "dip-buy opportunity",
    "taco_rebound": "dip-buy opportunity",
    "risk_reduced": "opportunity vetoed",
    "delever": "opportunity vetoed",
    "blocked": "data blocked",
    "watch": "watch",
}


@dataclass(frozen=True)
class StrategyPluginTelegramSettings:
    chat_ids: tuple[str, ...] = ()
    bot_token: str | None = field(default=None, repr=False)
    api_base_url: str = DEFAULT_TELEGRAM_BOT_API_BASE_URL
    parse_mode: str | None = None
    disable_web_page_preview: bool = True
    body_max_chars: int = _DEFAULT_TELEGRAM_BODY_MAX_CHARS
    timeout: float = 10.0

    @classmethod
    def from_object(cls, value: object) -> "StrategyPluginTelegramSettings":
        if isinstance(value, cls):
            return value
        return cls(
            chat_ids=tuple(
                parse_telegram_chat_ids(_get_value(value, "strategy_plugin_alert_telegram_chat_ids", ()))
            ),
            bot_token=_first_non_empty(_get_value(value, "strategy_plugin_alert_telegram_bot_token")),
            api_base_url=(
                _first_non_empty(_get_value(value, "strategy_plugin_alert_telegram_api_base_url"))
                or DEFAULT_TELEGRAM_BOT_API_BASE_URL
            ),
            parse_mode=_first_non_empty(_get_value(value, "strategy_plugin_alert_telegram_parse_mode")),
            disable_web_page_preview=_coerce_bool(
                _get_value(value, "strategy_plugin_alert_telegram_disable_web_page_preview"),
                default=True,
            ),
            body_max_chars=_coerce_int(
                _get_value(value, "strategy_plugin_alert_telegram_body_max_chars"),
                _DEFAULT_TELEGRAM_BODY_MAX_CHARS,
            ),
        )

    def missing_fields(self) -> tuple[str, ...]:
        missing: list[str] = []
        if not parse_telegram_chat_ids(self.chat_ids):
            missing.append("STRATEGY_PLUGIN_ALERT_TELEGRAM_CHAT_IDS")
        if not str(self.bot_token or "").strip():
            missing.append("STRATEGY_PLUGIN_ALERT_TELEGRAM_BOT_TOKEN")
        return tuple(missing)

    @property
    def is_configured(self) -> bool:
        return not self.missing_fields()


@dataclass(frozen=True)
class StrategyPluginTelegramAlertDelivery:
    alert_key: str
    subject: str
    status: str
    reason: str | None = None
    error: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "alert_key": self.alert_key,
            "subject": self.subject,
            "status": self.status,
            "reason": self.reason,
            "error": self.error,
            **dict(self.metadata or {}),
        }
        return {key: value for key, value in payload.items() if value not in (None, "", (), [])}


@dataclass(frozen=True)
class StrategyPluginTelegramAlertPublishResult:
    deliveries: tuple[StrategyPluginTelegramAlertDelivery, ...] = ()

    @property
    def attempted_count(self) -> int:
        return len(self.deliveries)

    @property
    def sent_count(self) -> int:
        return sum(1 for delivery in self.deliveries if delivery.status == "sent")

    @property
    def skipped_count(self) -> int:
        return sum(1 for delivery in self.deliveries if delivery.status == "skipped")

    @property
    def failed_count(self) -> int:
        return sum(1 for delivery in self.deliveries if delivery.status == "failed")

    def to_report_fields(self, *, prefix: str = "strategy_plugin_alert_telegram") -> dict[str, Any]:
        return {
            f"{prefix}_attempted_count": self.attempted_count,
            f"{prefix}_sent_count": self.sent_count,
            f"{prefix}_skipped_count": self.skipped_count,
            f"{prefix}_failed_count": self.failed_count,
            f"{prefix}_deliveries": [delivery.to_dict() for delivery in self.deliveries],
        }


@dataclass(frozen=True)
class StrategyPluginTelegramAlertMarkerStore(CloudAlertMarkerStore):
    """Telegram-specific alert marker store — thin wrapper around shared base."""
    namespace: str = "strategy_plugin_telegram_alerts"
    schema_version: str = "strategy_plugin_telegram_alert_marker.v1"


def publish_strategy_plugin_telegram_alerts(
    signals: Sequence[object],
    *,
    telegram_settings: StrategyPluginTelegramSettings | object,
    translator: Callable[..., str] | None = None,
    strategy_label: str | None = None,
    context_label: str | None = None,
    alert_store: StrategyPluginTelegramAlertMarkerStore | object | None = None,
    send_notification: Callable[..., bool] = send_strategy_plugin_telegram,
    log_message: Callable[..., Any] = print,
) -> StrategyPluginTelegramAlertPublishResult:
    settings = StrategyPluginTelegramSettings.from_object(telegram_settings)
    messages = build_strategy_plugin_alert_messages(
        signals,
        translator=translator,
        strategy_label=strategy_label,
        context_label=context_label,
        alert_namespace="strategy_plugin_telegram_alert",
    )
    deliveries: list[StrategyPluginTelegramAlertDelivery] = []
    missing_fields = settings.missing_fields()
    if missing_fields:
        for message in messages:
            deliveries.append(
                _delivery(
                    message,
                    status="skipped",
                    reason="missing_telegram_config",
                    error=",".join(missing_fields),
                )
            )
        result = StrategyPluginTelegramAlertPublishResult(tuple(deliveries))
        _log_publish_result(result, log_message=log_message)
        return result

    for message in messages:
        alert_key = message.alert_key or _fallback_alert_key(message)
        try:
            duplicate = _store_has_alert(alert_store, alert_key)
            store_error = None
        except Exception as exc:
            duplicate = False
            store_error = f"alert_store_check_failed:{type(exc).__name__}: {redact_sensitive_text(exc)}"
        if duplicate:
            deliveries.append(_delivery(message, status="skipped", reason="duplicate_alert"))
            continue
        sent, send_error = _send_message(send_notification, message, settings)
        if not sent:
            deliveries.append(_delivery(message, status="failed", reason="send_failed", error=send_error))
            continue
        record_error = _store_record_error(alert_store, alert_key, message)
        combined_error = "; ".join(error for error in (store_error, record_error) if error)
        deliveries.append(_delivery(message, status="sent", error=combined_error or None))
    result = StrategyPluginTelegramAlertPublishResult(tuple(deliveries))
    _log_publish_result(result, log_message=log_message)
    return result


def _delivery(
    message: StrategyPluginAlertMessage,
    *,
    status: str,
    reason: str | None = None,
    error: str | None = None,
) -> StrategyPluginTelegramAlertDelivery:
    return StrategyPluginTelegramAlertDelivery(
        alert_key=message.alert_key or _fallback_alert_key(message),
        subject=message.subject,
        status=status,
        reason=reason,
        error=error,
        metadata=message.metadata,
    )


def _send_message(
    send_notification: Callable[..., bool],
    message: StrategyPluginAlertMessage,
    settings: StrategyPluginTelegramSettings,
) -> tuple[bool, str | None]:
    title, body = _build_telegram_message_parts(message, max_chars=settings.body_max_chars)
    try:
        sent = send_notification(
            title=title,
            body=body,
            chat_ids=settings.chat_ids,
            bot_token=settings.bot_token,
            api_base_url=settings.api_base_url,
            parse_mode=settings.parse_mode,
            disable_web_page_preview=settings.disable_web_page_preview,
            timeout=settings.timeout,
        )
    except Exception as exc:
        return False, f"{type(exc).__name__}: {redact_sensitive_text(exc)}"
    return bool(sent), None


def _build_telegram_message_parts(
    message: StrategyPluginAlertMessage,
    *,
    max_chars: int,
) -> tuple[str, str]:
    compact_body = _build_compact_market_regime_body(message)
    if compact_body:
        return "", _truncate_telegram_body(compact_body, max_chars=max_chars)
    return message.subject, _build_telegram_body(message, max_chars=max_chars)


def _build_compact_market_regime_body(message: StrategyPluginAlertMessage) -> str | None:
    metadata = message.metadata
    if not isinstance(metadata, Mapping):
        return None
    plugin = str(metadata.get("plugin") or "").strip().lower()
    if plugin != _MARKET_REGIME_CONTROL_PLUGIN:
        return None
    background = _first_non_empty(metadata.get("situation"))
    recommendation = _first_non_empty(metadata.get("recommendation"))
    if not background or not recommendation:
        return None
    use_zh = _message_uses_zh(message)
    route = str(metadata.get("canonical_route") or "").strip().lower()
    as_of = _first_non_empty(metadata.get("as_of")) or ("未知" if use_zh else "unknown")
    if use_zh:
        return "\n".join(
            (
                f"日期：{as_of}",
                f"市场状态：{_market_regime_route_label(route, use_zh=True)}",
                f"背景情况：{background}",
                f"建议操作：{recommendation}",
            )
        )
    return "\n".join(
        (
            f"Date: {as_of}",
            f"Market state: {_market_regime_route_label(route, use_zh=False)}",
            f"Background: {background}",
            f"Suggested action: {recommendation}",
        )
    )


def _message_uses_zh(message: StrategyPluginAlertMessage) -> bool:
    metadata = message.metadata if isinstance(message.metadata, Mapping) else {}
    text = "\n".join(
        str(value or "")
        for value in (
            message.subject,
            message.body,
            metadata.get("situation"),
            metadata.get("recommendation"),
            metadata.get("reason_summary"),
        )
    )
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _market_regime_route_label(route: str, *, use_zh: bool) -> str:
    labels = _ZH_MARKET_REGIME_ROUTE_LABELS if use_zh else _EN_MARKET_REGIME_ROUTE_LABELS
    return labels.get(route, "需要复核" if use_zh else "manual review")


def _build_telegram_body(message: StrategyPluginAlertMessage, *, max_chars: int) -> str:
    body = str(message.body or "").strip() or str(message.subject or "").strip()
    return _truncate_telegram_body(body, max_chars=max_chars)


def _truncate_telegram_body(body: str, *, max_chars: int) -> str:
    limit = max(80, min(4096, int(max_chars or _DEFAULT_TELEGRAM_BODY_MAX_CHARS)))
    if len(body) <= limit:
        return body
    return body[: max(0, limit - 3)].rstrip() + "..."


def _store_has_alert(alert_store: object | None, alert_key: str) -> bool:
    if alert_store is None:
        return False
    checker = getattr(alert_store, "has_alert", None)
    if checker is None:
        return False
    return bool(checker(alert_key))


def _store_record_error(
    alert_store: object | None,
    alert_key: str,
    message: StrategyPluginAlertMessage,
) -> str | None:
    if alert_store is None:
        return None
    recorder = getattr(alert_store, "record_alert", None)
    if recorder is None:
        return None
    try:
        recorder(
            alert_key,
            metadata={
                "subject": message.subject,
                **dict(message.metadata or {}),
            },
        )
    except Exception as exc:
        return f"alert_store_record_failed:{type(exc).__name__}: {redact_sensitive_text(exc)}"
    return None


def _log_publish_result(
    result: StrategyPluginTelegramAlertPublishResult,
    *,
    log_message: Callable[..., Any],
) -> None:
    if result.attempted_count <= 0:
        return
    _call_log_message(
        log_message,
        (
            "strategy_plugin_alert_telegram_result "
            f"attempted={result.attempted_count} "
            f"sent={result.sent_count} "
            f"skipped={result.skipped_count} "
            f"failed={result.failed_count}"
        ),
    )


def _call_log_message(log_message: Callable[..., Any], text: str) -> None:
    try:
        log_message(text, flush=True)
    except TypeError:
        log_message(text)


def _get_value(value: object, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value in (None, ""):
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _coerce_int(value: Any, default: int) -> int:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return int(text)
    except (TypeError, ValueError):
        return default


def _fallback_alert_key(message: StrategyPluginAlertMessage) -> str:
    return "strategy_plugin_telegram_alert/" + _clean_relative_key(message.subject or "unknown")


