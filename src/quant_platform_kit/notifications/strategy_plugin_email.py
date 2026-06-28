"""Email notification helpers for strategy plugin alerts."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quant_platform_kit.cloud import get_object_store
from quant_platform_kit.common.strategy_plugins import (
    StrategyPluginAlertMessage,
    build_strategy_plugin_alert_messages,
)

from .email import parse_email_recipients, send_smtp_email


_DEFAULT_EMAIL_SMTP_HOST = "smtp.gmail.com"
_DEFAULT_EMAIL_SMTP_PORT = 465
_DEFAULT_EMAIL_SMTP_SECURITY = "ssl"
_SMTP_SECURITY_NONE = "none"
_SMTP_SECURITY_SSL = "ssl"
_SMTP_SECURITY_STARTTLS = "starttls"
_SMTP_SECURITY_VALUES = {
    _SMTP_SECURITY_NONE,
    _SMTP_SECURITY_SSL,
    _SMTP_SECURITY_STARTTLS,
}


@dataclass(frozen=True)
class StrategyPluginEmailSettings:
    recipients: tuple[str, ...] = ()
    sender_email: str | None = None
    sender_password: str | None = field(default=None, repr=False)
    smtp_host: str = _DEFAULT_EMAIL_SMTP_HOST
    smtp_port: int = _DEFAULT_EMAIL_SMTP_PORT
    smtp_security: str = _DEFAULT_EMAIL_SMTP_SECURITY
    timeout: float = 10.0

    @classmethod
    def from_object(cls, value: object) -> "StrategyPluginEmailSettings":
        if isinstance(value, cls):
            return value
        return cls(
            recipients=tuple(
                parse_email_recipients(_get_value(value, "strategy_plugin_alert_email_recipients", ()))
            ),
            sender_email=_first_non_empty(_get_value(value, "strategy_plugin_alert_email_sender_email")),
            sender_password=_get_value(value, "strategy_plugin_alert_email_sender_password"),
            smtp_host=_first_non_empty(
                _get_value(value, "strategy_plugin_alert_email_smtp_host")
            )
            or _DEFAULT_EMAIL_SMTP_HOST,
            smtp_port=_coerce_int(
                _get_value(value, "strategy_plugin_alert_email_smtp_port"),
                _DEFAULT_EMAIL_SMTP_PORT,
            ),
            smtp_security=_coerce_smtp_security(
                _get_value(value, "strategy_plugin_alert_email_smtp_security")
            ),
        )

    def missing_fields(self) -> tuple[str, ...]:
        missing: list[str] = []
        if not parse_email_recipients(self.recipients):
            missing.append("STRATEGY_PLUGIN_ALERT_EMAIL_RECIPIENTS")
        if not str(self.sender_email or "").strip():
            missing.append("STRATEGY_PLUGIN_ALERT_EMAIL_SENDER_EMAIL")
        if not str(self.sender_password or "").strip():
            missing.append("STRATEGY_PLUGIN_ALERT_EMAIL_SENDER_PASSWORD")
        return tuple(missing)

    @property
    def is_configured(self) -> bool:
        return not self.missing_fields()


@dataclass(frozen=True)
class StrategyPluginEmailAlertDelivery:
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
class StrategyPluginEmailAlertPublishResult:
    deliveries: tuple[StrategyPluginEmailAlertDelivery, ...] = ()

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

    def to_report_fields(self, *, prefix: str = "strategy_plugin_alert_email") -> dict[str, Any]:
        return {
            f"{prefix}_attempted_count": self.attempted_count,
            f"{prefix}_sent_count": self.sent_count,
            f"{prefix}_skipped_count": self.skipped_count,
            f"{prefix}_failed_count": self.failed_count,
            f"{prefix}_deliveries": [delivery.to_dict() for delivery in self.deliveries],
        }


@dataclass(frozen=True)
class StrategyPluginEmailAlertMarkerStore:
    local_dir: str | Path | None = None
    gcs_prefix_uri: str | None = None
    gcp_project_id: str | None = None
    namespace: str = "strategy_plugin_email_alerts"
    client_factory: Any = None

    def _object_store(self):
        return get_object_store(project_id=self.gcp_project_id)

    def has_alert(self, alert_key: str) -> bool:
        if self.gcs_prefix_uri and self._object_store().exists(self._gcs_uri(alert_key, namespace=self.namespace)):
            return True
        if self.local_dir and self._local_path(alert_key, namespace=self.namespace).exists():
            return True
        return False

    def record_alert(
        self,
        alert_key: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        payload = {
            "schema_version": "strategy_plugin_email_alert_marker.v1",
            "alert_key": str(alert_key),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "metadata": dict(metadata or {}),
        }
        encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        if self.gcs_prefix_uri:
            self._object_store().write_text(
                self._gcs_uri(alert_key, namespace=self.namespace),
                encoded,
                content_type="application/json",
            )
            return
        if self.local_dir:
            path = self._local_path(alert_key, namespace=self.namespace)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(encoded, encoding="utf-8")

    def _local_path(self, alert_key: str, *, namespace: str) -> Path:
        root = Path(self.local_dir or tempfile.gettempdir()).expanduser()
        return root / namespace / f"{_clean_relative_key(alert_key)}.json"

    def _gcs_uri(self, alert_key: str, *, namespace: str) -> str:
        bucket_name, prefix = _parse_gcs_uri(str(self.gcs_prefix_uri or ""))
        object_name = "/".join(
            part.strip("/")
            for part in (prefix, namespace, f"{_clean_relative_key(alert_key)}.json")
            if part and part.strip("/")
        )
        return f"gs://{bucket_name}/{object_name}"


def build_strategy_plugin_alert_context_label(
    *,
    platform_id: str | None = None,
    strategy_profile: str | None = None,
    account_scope: str | None = None,
    deployment_selector: str | None = None,
    service_name: str | None = None,
    runtime_target: Any = None,
) -> str:
    target = runtime_target
    resolved_platform = platform_id or getattr(target, "platform_id", None)
    resolved_strategy = strategy_profile or getattr(target, "strategy_profile", None)
    resolved_account = account_scope or getattr(target, "account_scope", None)
    resolved_deployment = deployment_selector or getattr(target, "deployment_selector", None)
    resolved_service = service_name or getattr(target, "service_name", None)
    parts = [
        resolved_platform,
        resolved_account or resolved_deployment or resolved_service,
        resolved_strategy,
    ]
    return " / ".join(str(part).strip() for part in parts if str(part or "").strip())


def publish_strategy_plugin_email_alerts(
    signals: Sequence[object],
    *,
    email_settings: StrategyPluginEmailSettings | object,
    translator: Callable[..., str] | None = None,
    strategy_label: str | None = None,
    context_label: str | None = None,
    alert_store: StrategyPluginEmailAlertMarkerStore | object | None = None,
    send_notification: Callable[..., bool] = send_smtp_email,
    log_message: Callable[..., Any] = print,
) -> StrategyPluginEmailAlertPublishResult:
    settings = StrategyPluginEmailSettings.from_object(email_settings)
    messages = build_strategy_plugin_alert_messages(
        signals,
        translator=translator,
        strategy_label=strategy_label,
        context_label=context_label,
        alert_namespace="strategy_plugin_email_alert",
    )
    deliveries: list[StrategyPluginEmailAlertDelivery] = []
    missing_fields = settings.missing_fields()
    if missing_fields:
        for message in messages:
            deliveries.append(
                _delivery(
                    message,
                    status="skipped",
                    reason="missing_email_config",
                    error=",".join(missing_fields),
                )
            )
        result = StrategyPluginEmailAlertPublishResult(tuple(deliveries))
        _log_publish_result(result, log_message=log_message)
        return result

    for message in messages:
        alert_key = message.alert_key or _fallback_alert_key(message)
        try:
            duplicate = _store_has_alert(alert_store, alert_key)
            store_error = None
        except Exception as exc:
            duplicate = False
            store_error = f"alert_store_check_failed:{type(exc).__name__}: {exc}"
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
    result = StrategyPluginEmailAlertPublishResult(tuple(deliveries))
    _log_publish_result(result, log_message=log_message)
    return result


def _delivery(
    message: StrategyPluginAlertMessage,
    *,
    status: str,
    reason: str | None = None,
    error: str | None = None,
) -> StrategyPluginEmailAlertDelivery:
    return StrategyPluginEmailAlertDelivery(
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
    settings: StrategyPluginEmailSettings,
) -> tuple[bool, str | None]:
    try:
        sent = send_notification(
            subject=message.subject,
            body=message.body,
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            sender=settings.sender_email,
            recipients=settings.recipients,
            username=settings.sender_email,
            password=settings.sender_password,
            use_starttls=settings.smtp_security == _SMTP_SECURITY_STARTTLS,
            use_ssl=settings.smtp_security == _SMTP_SECURITY_SSL,
            timeout=settings.timeout,
        )
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return bool(sent), None


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
        return f"alert_store_record_failed:{type(exc).__name__}: {exc}"
    return None


def _log_publish_result(
    result: StrategyPluginEmailAlertPublishResult,
    *,
    log_message: Callable[..., Any],
) -> None:
    if result.attempted_count <= 0:
        return
    _call_log_message(
        log_message,
        (
            "strategy_plugin_alert_email_result "
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


def _coerce_smtp_security(value: Any) -> str:
    security = str(value or "").strip().lower()
    if security in _SMTP_SECURITY_VALUES:
        return security
    return _DEFAULT_EMAIL_SMTP_SECURITY


def _fallback_alert_key(message: StrategyPluginAlertMessage) -> str:
    return "strategy_plugin_email_alert/" + _clean_relative_key(message.subject or "unknown")


def _clean_relative_key(value: str) -> str:
    parts = []
    for raw_part in str(value or "").replace("\\", "/").split("/"):
        cleaned = "".join(
            char if char.isalnum() or char in {"-", "_", "."} else "-"
            for char in raw_part.strip()
        ).strip("-._")
        if cleaned:
            parts.append(cleaned[:100])
    return "/".join(parts) or "unknown"


def _parse_gcs_uri(uri: str) -> tuple[str, str]:
    raw_uri = str(uri or "").strip()
    if not raw_uri.startswith("gs://"):
        raise ValueError(f"gcs uri must start with gs://, got: {uri!r}")
    remainder = raw_uri[5:]
    bucket_name, _, object_prefix = remainder.partition("/")
    if not bucket_name:
        raise ValueError(f"gcs uri must include a bucket name, got: {uri!r}")
    return bucket_name, object_prefix.strip("/")
