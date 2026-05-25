"""Google Voice notification helpers for strategy plugin alerts."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quant_platform_kit.common.strategy_plugins import (
    StrategyPluginAlertMessage,
    build_strategy_plugin_alert_messages,
)

from .email import parse_email_recipients, send_smtp_email


_GOOGLE_VOICE_SMTP_HOST = "smtp.gmail.com"
_GOOGLE_VOICE_SMTP_PORT = 465
_GOOGLE_VOICE_SMTP_STARTTLS = False
_GOOGLE_VOICE_SMTP_SSL = True


@dataclass(frozen=True)
class StrategyPluginGoogleVoiceSettings:
    recipients: tuple[str, ...] = ()
    gmail_user: str | None = None
    gmail_app_password: str | None = field(default=None, repr=False)
    timeout: float = 10.0

    @classmethod
    def from_object(cls, value: object) -> "StrategyPluginGoogleVoiceSettings":
        if isinstance(value, cls):
            return value
        return cls(
            recipients=tuple(
                parse_email_recipients(_get_value(value, "crisis_alert_google_voice_recipients", ()))
            ),
            gmail_user=_first_non_empty(_get_value(value, "crisis_alert_google_voice_gmail_user")),
            gmail_app_password=_get_value(value, "crisis_alert_google_voice_gmail_app_password"),
        )

    def missing_fields(self) -> tuple[str, ...]:
        missing: list[str] = []
        if not parse_email_recipients(self.recipients):
            missing.append("CRISIS_ALERT_GOOGLE_VOICE_RECIPIENTS")
        if not str(self.gmail_user or "").strip():
            missing.append("CRISIS_ALERT_GOOGLE_VOICE_GMAIL_USER")
        if not str(self.gmail_app_password or "").strip():
            missing.append("CRISIS_ALERT_GOOGLE_VOICE_GMAIL_APP_PASSWORD")
        return tuple(missing)

    @property
    def is_configured(self) -> bool:
        return not self.missing_fields()


@dataclass(frozen=True)
class StrategyPluginGoogleVoiceAlertDelivery:
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
class StrategyPluginGoogleVoiceAlertPublishResult:
    deliveries: tuple[StrategyPluginGoogleVoiceAlertDelivery, ...] = ()

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

    def to_report_fields(self, *, prefix: str = "strategy_plugin_alert_google_voice") -> dict[str, Any]:
        return {
            f"{prefix}_attempted_count": self.attempted_count,
            f"{prefix}_sent_count": self.sent_count,
            f"{prefix}_skipped_count": self.skipped_count,
            f"{prefix}_failed_count": self.failed_count,
            f"{prefix}_deliveries": [delivery.to_dict() for delivery in self.deliveries],
        }


@dataclass(frozen=True)
class StrategyPluginGoogleVoiceAlertMarkerStore:
    local_dir: str | Path | None = None
    gcs_prefix_uri: str | None = None
    gcp_project_id: str | None = None
    namespace: str = "strategy_plugin_google_voice_alerts"
    client_factory: Any = None

    def has_alert(self, alert_key: str) -> bool:
        if self.gcs_prefix_uri and self._gcs_blob(alert_key, namespace=self.namespace).exists():
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
            "schema_version": "strategy_plugin_google_voice_alert_marker.v1",
            "alert_key": str(alert_key),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "metadata": dict(metadata or {}),
        }
        encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        if self.gcs_prefix_uri:
            self._gcs_blob(alert_key, namespace=self.namespace).upload_from_string(
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

    def _gcs_blob(self, alert_key: str, *, namespace: str):
        bucket_name, prefix = _parse_gcs_uri(str(self.gcs_prefix_uri or ""))
        object_name = "/".join(
            part.strip("/")
            for part in (prefix, namespace, f"{_clean_relative_key(alert_key)}.json")
            if part and part.strip("/")
        )
        if self.client_factory is None:
            try:
                from google.cloud import storage  # type: ignore
            except ImportError as exc:
                raise RuntimeError("google-cloud-storage is required for GCS alert markers") from exc
            client_factory = storage.Client
        else:
            client_factory = self.client_factory
        client = client_factory(project=self.gcp_project_id) if self.gcp_project_id else client_factory()
        return client.bucket(bucket_name).blob(object_name)


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


def publish_strategy_plugin_google_voice_alerts(
    signals: Sequence[object],
    *,
    google_voice_settings: StrategyPluginGoogleVoiceSettings | object,
    translator: Callable[..., str] | None = None,
    strategy_label: str | None = None,
    context_label: str | None = None,
    alert_store: StrategyPluginGoogleVoiceAlertMarkerStore | object | None = None,
    send_notification: Callable[..., bool] = send_smtp_email,
    log_message: Callable[..., Any] = print,
) -> StrategyPluginGoogleVoiceAlertPublishResult:
    settings = StrategyPluginGoogleVoiceSettings.from_object(google_voice_settings)
    messages = build_strategy_plugin_alert_messages(
        signals,
        translator=translator,
        strategy_label=strategy_label,
        context_label=context_label,
        alert_namespace="strategy_plugin_google_voice_alert",
    )
    deliveries: list[StrategyPluginGoogleVoiceAlertDelivery] = []
    missing_fields = settings.missing_fields()
    if missing_fields:
        for message in messages:
            deliveries.append(
                _delivery(
                    message,
                    status="skipped",
                    reason="missing_google_voice_config",
                    error=",".join(missing_fields),
                )
            )
        result = StrategyPluginGoogleVoiceAlertPublishResult(tuple(deliveries))
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
    result = StrategyPluginGoogleVoiceAlertPublishResult(tuple(deliveries))
    _log_publish_result(result, log_message=log_message)
    return result


def _delivery(
    message: StrategyPluginAlertMessage,
    *,
    status: str,
    reason: str | None = None,
    error: str | None = None,
) -> StrategyPluginGoogleVoiceAlertDelivery:
    return StrategyPluginGoogleVoiceAlertDelivery(
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
    settings: StrategyPluginGoogleVoiceSettings,
) -> tuple[bool, str | None]:
    try:
        sent = send_notification(
            subject=message.subject,
            body=message.body,
            smtp_host=_GOOGLE_VOICE_SMTP_HOST,
            smtp_port=_GOOGLE_VOICE_SMTP_PORT,
            sender=settings.gmail_user,
            recipients=settings.recipients,
            username=settings.gmail_user,
            password=settings.gmail_app_password,
            use_starttls=_GOOGLE_VOICE_SMTP_STARTTLS,
            use_ssl=_GOOGLE_VOICE_SMTP_SSL,
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
    result: StrategyPluginGoogleVoiceAlertPublishResult,
    *,
    log_message: Callable[..., Any],
) -> None:
    if result.attempted_count <= 0:
        return
    _call_log_message(
        log_message,
        (
            "strategy_plugin_alert_google_voice_result "
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


def _fallback_alert_key(message: StrategyPluginAlertMessage) -> str:
    return "strategy_plugin_google_voice_alert/" + _clean_relative_key(message.subject or "unknown")


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
