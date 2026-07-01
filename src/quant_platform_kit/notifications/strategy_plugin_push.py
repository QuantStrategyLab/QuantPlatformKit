"""Push notification helpers for strategy plugin alerts."""

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
from .push import (
    DEFAULT_NTFY_API_BASE_URL,
    DEFAULT_PUSHOVER_API_BASE_URL,
    PUSH_PROVIDER_NTFY,
    PUSH_PROVIDER_PUSHOVER,
    parse_push_recipients,
    send_strategy_plugin_push,
)

_DEFAULT_PUSH_PROVIDER = PUSH_PROVIDER_PUSHOVER
_SUPPORTED_PUSH_PROVIDERS = frozenset({PUSH_PROVIDER_PUSHOVER, PUSH_PROVIDER_NTFY})
_DEFAULT_PUSH_BODY_MAX_CHARS = 1800


@dataclass(frozen=True)
class StrategyPluginPushSettings:
    recipients: tuple[str, ...] = ()
    provider: str = _DEFAULT_PUSH_PROVIDER
    app_token: str | None = field(default=None, repr=False)
    access_token: str | None = field(default=None, repr=False)
    api_base_url: str | None = None
    device: str | None = None
    priority: str | None = None
    tags: str | None = None
    body_max_chars: int = _DEFAULT_PUSH_BODY_MAX_CHARS
    timeout: float = 10.0

    @classmethod
    def from_object(cls, value: object) -> "StrategyPluginPushSettings":
        if isinstance(value, cls):
            return value
        provider = (
            _first_non_empty(_get_value(value, "strategy_plugin_alert_push_provider"))
            or _DEFAULT_PUSH_PROVIDER
        ).lower()
        return cls(
            recipients=tuple(
                parse_push_recipients(_get_value(value, "strategy_plugin_alert_push_recipients", ()))
            ),
            provider=provider,
            app_token=_first_non_empty(_get_value(value, "strategy_plugin_alert_push_app_token")),
            access_token=_first_non_empty(_get_value(value, "strategy_plugin_alert_push_access_token")),
            api_base_url=(
                _first_non_empty(_get_value(value, "strategy_plugin_alert_push_api_base_url"))
                or _default_api_base_url(provider)
            ),
            device=_first_non_empty(_get_value(value, "strategy_plugin_alert_push_device")),
            priority=_first_non_empty(_get_value(value, "strategy_plugin_alert_push_priority")),
            tags=_first_non_empty(_get_value(value, "strategy_plugin_alert_push_tags")),
            body_max_chars=_coerce_int(
                _get_value(value, "strategy_plugin_alert_push_body_max_chars"),
                _DEFAULT_PUSH_BODY_MAX_CHARS,
            ),
        )

    def missing_fields(self) -> tuple[str, ...]:
        missing: list[str] = []
        if self.provider not in _SUPPORTED_PUSH_PROVIDERS:
            missing.append("STRATEGY_PLUGIN_ALERT_PUSH_PROVIDER=pushover or ntfy")
        if not parse_push_recipients(self.recipients):
            missing.append("STRATEGY_PLUGIN_ALERT_PUSH_RECIPIENTS")
        if self.provider == PUSH_PROVIDER_PUSHOVER and not str(self.app_token or "").strip():
            missing.append("STRATEGY_PLUGIN_ALERT_PUSH_APP_TOKEN")
        return tuple(missing)

    @property
    def is_configured(self) -> bool:
        return not self.missing_fields()


@dataclass(frozen=True)
class StrategyPluginPushAlertDelivery:
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
class StrategyPluginPushAlertPublishResult:
    deliveries: tuple[StrategyPluginPushAlertDelivery, ...] = ()

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

    def to_report_fields(self, *, prefix: str = "strategy_plugin_alert_push") -> dict[str, Any]:
        return {
            f"{prefix}_attempted_count": self.attempted_count,
            f"{prefix}_sent_count": self.sent_count,
            f"{prefix}_skipped_count": self.skipped_count,
            f"{prefix}_failed_count": self.failed_count,
            f"{prefix}_deliveries": [delivery.to_dict() for delivery in self.deliveries],
        }


@dataclass(frozen=True)
class StrategyPluginPushAlertMarkerStore(CloudAlertMarkerStore):
    """Push-specific alert marker store — thin wrapper around shared base."""
    namespace: str = "strategy_plugin_push_alerts"
    schema_version: str = "strategy_plugin_push_alert_marker.v1"


def publish_strategy_plugin_push_alerts(
    signals: Sequence[object],
    *,
    push_settings: StrategyPluginPushSettings | object,
    translator: Callable[..., str] | None = None,
    strategy_label: str | None = None,
    context_label: str | None = None,
    alert_store: StrategyPluginPushAlertMarkerStore | object | None = None,
    send_notification: Callable[..., bool] = send_strategy_plugin_push,
    log_message: Callable[..., Any] = print,
) -> StrategyPluginPushAlertPublishResult:
    settings = StrategyPluginPushSettings.from_object(push_settings)
    messages = build_strategy_plugin_alert_messages(
        signals,
        translator=translator,
        strategy_label=strategy_label,
        context_label=context_label,
        alert_namespace="strategy_plugin_push_alert",
    )
    deliveries: list[StrategyPluginPushAlertDelivery] = []
    missing_fields = settings.missing_fields()
    if missing_fields:
        for message in messages:
            deliveries.append(
                _delivery(
                    message,
                    status="skipped",
                    reason="missing_push_config",
                    error=",".join(missing_fields),
                )
            )
        result = StrategyPluginPushAlertPublishResult(tuple(deliveries))
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
    result = StrategyPluginPushAlertPublishResult(tuple(deliveries))
    _log_publish_result(result, log_message=log_message)
    return result


def _delivery(
    message: StrategyPluginAlertMessage,
    *,
    status: str,
    reason: str | None = None,
    error: str | None = None,
) -> StrategyPluginPushAlertDelivery:
    return StrategyPluginPushAlertDelivery(
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
    settings: StrategyPluginPushSettings,
) -> tuple[bool, str | None]:
    try:
        sent = send_notification(
            provider=settings.provider,
            title=message.subject,
            body=_build_push_body(message, max_chars=settings.body_max_chars),
            recipients=settings.recipients,
            app_token=settings.app_token,
            access_token=settings.access_token,
            api_base_url=settings.api_base_url,
            device=settings.device,
            priority=settings.priority,
            tags=settings.tags,
            timeout=settings.timeout,
        )
    except Exception as exc:
        return False, f"{type(exc).__name__}: {redact_sensitive_text(exc)}"
    return bool(sent), None


def _build_push_body(message: StrategyPluginAlertMessage, *, max_chars: int) -> str:
    body = str(message.body or "").strip() or str(message.subject or "").strip()
    limit = max(80, int(max_chars or _DEFAULT_PUSH_BODY_MAX_CHARS))
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
    result: StrategyPluginPushAlertPublishResult,
    *,
    log_message: Callable[..., Any],
) -> None:
    if result.attempted_count <= 0:
        return
    _call_log_message(
        log_message,
        (
            "strategy_plugin_alert_push_result "
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


def _coerce_int(value: Any, default: int) -> int:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return int(text)
    except (TypeError, ValueError):
        return default


def _default_api_base_url(provider: str) -> str:
    if provider == PUSH_PROVIDER_NTFY:
        return DEFAULT_NTFY_API_BASE_URL
    return DEFAULT_PUSHOVER_API_BASE_URL


def _fallback_alert_key(message: StrategyPluginAlertMessage) -> str:
    return "strategy_plugin_push_alert/" + _clean_relative_key(message.subject or "unknown")



