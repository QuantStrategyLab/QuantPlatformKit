"""Webhook notification helpers for strategy plugin alerts.

Supports multiple Chinese chat platforms via webhook — WeCom (企业微信),
DingTalk (钉钉), Feishu (飞书), and ServerChan (Server酱).

Each provider is configured with its own webhook URL.  When multiple
providers are enabled, the alert is delivered to all of them and each
delivery is recorded independently.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from quant_platform_kit.common.strategy_plugins import (
    StrategyPluginAlertMessage,
    build_strategy_plugin_alert_messages,
)

from .alert_marker import CloudAlertMarkerStore, _clean_relative_key
from .webhook import (
    WEBHOOK_PROVIDER_WECOM,
    WEBHOOK_PROVIDER_DINGTALK,
    WEBHOOK_PROVIDER_FEISHU,
    WEBHOOK_PROVIDER_SERVERCHAN,
    parse_webhook_providers,
    send_strategy_plugin_webhook,
)

_DEFAULT_WEBHOOK_BODY_MAX_CHARS = 4000

# Map provider name → URL field on settings
_PROVIDER_URL_FIELDS: dict[str, str] = {
    WEBHOOK_PROVIDER_WECOM: "wecom_webhook_url",
    WEBHOOK_PROVIDER_DINGTALK: "dingtalk_webhook_url",
    WEBHOOK_PROVIDER_FEISHU: "feishu_webhook_url",
    WEBHOOK_PROVIDER_SERVERCHAN: "serverchan_webhook_url",
}


# ──────────────────────────────────────────────────────────────────────
#  Settings
# ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StrategyPluginWebhookSettings:
    """Configuration for webhook-based alert delivery.

    Set ``providers`` to a tuple of provider names (e.g. ``("wecom", "dingtalk")``)
    and supply the corresponding webhook URL for each enabled provider.

    All URL fields are hidden from repr to avoid leaking credentials in logs.
    """

    providers: tuple[str, ...] = ()
    wecom_webhook_url: str | None = field(default=None, repr=False)
    dingtalk_webhook_url: str | None = field(default=None, repr=False)
    feishu_webhook_url: str | None = field(default=None, repr=False)
    serverchan_webhook_url: str | None = field(default=None, repr=False)
    body_max_chars: int = _DEFAULT_WEBHOOK_BODY_MAX_CHARS
    timeout: float = 10.0

    @classmethod
    def from_object(cls, value: object) -> "StrategyPluginWebhookSettings":
        if isinstance(value, cls):
            return value
        # Read per-platform URLs
        wecom_url = _first_non_empty(
            _get_value(value, "strategy_plugin_alert_webhook_wecom_url")
        )
        dingtalk_url = _first_non_empty(
            _get_value(value, "strategy_plugin_alert_webhook_dingtalk_url")
        )
        feishu_url = _first_non_empty(
            _get_value(value, "strategy_plugin_alert_webhook_feishu_url")
        )
        serverchan_url = _first_non_empty(
            _get_value(value, "strategy_plugin_alert_webhook_serverchan_url")
        )
        # Providers: explicit config takes priority, otherwise auto-detect from URLs
        explicit_providers = parse_webhook_providers(
            _get_value(value, "strategy_plugin_alert_webhook_providers", ())
        )
        if explicit_providers:
            providers = explicit_providers
        else:
            providers = _auto_detect_providers(
                wecom_url=wecom_url,
                dingtalk_url=dingtalk_url,
                feishu_url=feishu_url,
                serverchan_url=serverchan_url,
            )
        return cls(
            providers=providers,
            wecom_webhook_url=wecom_url,
            dingtalk_webhook_url=dingtalk_url,
            feishu_webhook_url=feishu_url,
            serverchan_webhook_url=serverchan_url,
            body_max_chars=_coerce_int(
                _get_value(value, "strategy_plugin_alert_webhook_body_max_chars"),
                _DEFAULT_WEBHOOK_BODY_MAX_CHARS,
            ),
            timeout=_coerce_float(
                _get_value(value, "strategy_plugin_alert_webhook_timeout"),
                10.0,
            ),
        )

    def missing_fields(self) -> tuple[str, ...]:
        """Return env var names that must be set for the selected providers."""
        missing: list[str] = []
        resolved = parse_webhook_providers(self.providers)
        if not resolved:
            missing.append("STRATEGY_PLUGIN_ALERT_WEBHOOK_PROVIDERS")
        for provider in resolved:
            url = _get_provider_url(self, provider)
            if not url:
                missing.append(f"STRATEGY_PLUGIN_ALERT_WEBHOOK_{provider.upper()}_URL")
        return tuple(missing)

    @property
    def is_configured(self) -> bool:
        return not self.missing_fields()


# ──────────────────────────────────────────────────────────────────────
#  Delivery & PublishResult
# ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StrategyPluginWebhookAlertDelivery:
    """Record of a single webhook alert delivery attempt."""

    alert_key: str
    subject: str
    status: str  # "sent", "skipped", "failed"
    reason: str | None = None
    error: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    provider: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "alert_key": self.alert_key,
            "subject": self.subject,
            "status": self.status,
            "reason": self.reason,
            "error": self.error,
            **dict(self.metadata or {}),
        }
        if self.provider:
            payload["provider"] = self.provider
        return {key: value for key, value in payload.items() if value not in (None, "", (), [])}


@dataclass(frozen=True)
class StrategyPluginWebhookAlertPublishResult:
    """Aggregated result of publishing webhook alerts across all providers."""

    deliveries: tuple[StrategyPluginWebhookAlertDelivery, ...] = ()

    @property
    def attempted_count(self) -> int:
        return len(self.deliveries)

    @property
    def sent_count(self) -> int:
        return sum(1 for d in self.deliveries if d.status == "sent")

    @property
    def skipped_count(self) -> int:
        return sum(1 for d in self.deliveries if d.status == "skipped")

    @property
    def failed_count(self) -> int:
        return sum(1 for d in self.deliveries if d.status == "failed")

    def to_report_fields(
        self, *, prefix: str = "strategy_plugin_alert_webhook"
    ) -> dict[str, Any]:
        return {
            f"{prefix}_attempted_count": self.attempted_count,
            f"{prefix}_sent_count": self.sent_count,
            f"{prefix}_skipped_count": self.skipped_count,
            f"{prefix}_failed_count": self.failed_count,
            f"{prefix}_deliveries": [d.to_dict() for d in self.deliveries],
        }


# ──────────────────────────────────────────────────────────────────────
#  MarkerStore
# ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StrategyPluginWebhookAlertMarkerStore(CloudAlertMarkerStore):
    """Webhook-specific alert marker store — thin wrapper around shared base."""

    namespace: str = "strategy_plugin_webhook_alerts"
    schema_version: str = "strategy_plugin_webhook_alert_marker.v1"


# ──────────────────────────────────────────────────────────────────────
#  Main publish function
# ──────────────────────────────────────────────────────────────────────

def publish_strategy_plugin_webhook_alerts(
    signals: Sequence[object],
    *,
    webhook_settings: StrategyPluginWebhookSettings | object,
    translator: Callable[..., str] | None = None,
    strategy_label: str | None = None,
    context_label: str | None = None,
    alert_store: StrategyPluginWebhookAlertMarkerStore | object | None = None,
    send_notification: Callable[..., bool] = send_strategy_plugin_webhook,
    log_message: Callable[..., Any] = print,
) -> StrategyPluginWebhookAlertPublishResult:
    """Publish strategy plugin alerts to configured webhook providers.

    For each alert message, the function iterates over all enabled providers
    and sends the message to each.  A single alert may produce multiple
    deliveries (one per provider).
    """
    settings = StrategyPluginWebhookSettings.from_object(webhook_settings)
    messages = build_strategy_plugin_alert_messages(
        signals,
        translator=translator,
        strategy_label=strategy_label,
        context_label=context_label,
        alert_namespace="strategy_plugin_webhook_alert",
    )
    deliveries: list[StrategyPluginWebhookAlertDelivery] = []
    missing_fields = settings.missing_fields()
    if missing_fields:
        for message in messages:
            deliveries.append(
                _delivery(
                    message,
                    status="skipped",
                    reason="missing_webhook_config",
                    error=",".join(missing_fields),
                )
            )
        result = StrategyPluginWebhookAlertPublishResult(tuple(deliveries))
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
            deliveries.append(
                _delivery(message, status="skipped", reason="duplicate_alert")
            )
            continue

        # Send to each enabled provider
        any_sent = False
        for provider in settings.providers:
            url = _get_provider_url(settings, provider)
            if not url:
                deliveries.append(
                    _delivery(
                        message,
                        status="skipped",
                        reason="missing_url",
                        error=f"no webhook URL configured for {provider}",
                        provider=provider,
                    )
                )
                continue
            sent, send_error = _send_message(
                send_notification, message, provider, url, settings
            )
            if sent:
                any_sent = True
                deliveries.append(
                    _delivery(message, status="sent", provider=provider)
                )
            else:
                deliveries.append(
                    _delivery(
                        message,
                        status="failed",
                        reason="send_failed",
                        error=send_error,
                        provider=provider,
                    )
                )

        # Record alert marker if at least one provider succeeded
        if any_sent:
            record_error = _store_record_error(alert_store, alert_key, message)
            if record_error and store_error:
                store_error = "; ".join([store_error, record_error])
            elif record_error:
                store_error = record_error

    result = StrategyPluginWebhookAlertPublishResult(tuple(deliveries))
    _log_publish_result(result, log_message=log_message)
    return result


# ──────────────────────────────────────────────────────────────────────
#  Internal helpers
# ──────────────────────────────────────────────────────────────────────

def _get_provider_url(settings: StrategyPluginWebhookSettings, provider: str) -> str | None:
    """Look up the webhook URL for a provider from settings."""
    field_name = _PROVIDER_URL_FIELDS.get(provider)
    if field_name is None:
        return None
    url = getattr(settings, field_name, None)
    return str(url or "").strip() or None


def _delivery(
    message: StrategyPluginAlertMessage,
    *,
    status: str,
    reason: str | None = None,
    error: str | None = None,
    provider: str = "",
) -> StrategyPluginWebhookAlertDelivery:
    return StrategyPluginWebhookAlertDelivery(
        alert_key=message.alert_key or _fallback_alert_key(message),
        subject=message.subject,
        status=status,
        reason=reason,
        error=error,
        metadata=message.metadata,
        provider=provider,
    )


def _send_message(
    send_notification: Callable[..., bool],
    message: StrategyPluginAlertMessage,
    provider: str,
    webhook_url: str,
    settings: StrategyPluginWebhookSettings,
) -> tuple[bool, str | None]:
    """Send a single alert message to one webhook provider."""
    try:
        sent = send_notification(
            provider=provider,
            title=message.subject,
            body=_build_webhook_body(message, max_chars=settings.body_max_chars),
            webhook_url=webhook_url,
            timeout=settings.timeout,
        )
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return bool(sent), None


def _build_webhook_body(message: StrategyPluginAlertMessage, *, max_chars: int) -> str:
    body = str(message.body or "").strip() or str(message.subject or "").strip()
    limit = max(80, min(4096, int(max_chars or _DEFAULT_WEBHOOK_BODY_MAX_CHARS)))
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
        return f"alert_store_record_failed:{type(exc).__name__}: {exc}"
    return None


def _log_publish_result(
    result: StrategyPluginWebhookAlertPublishResult,
    *,
    log_message: Callable[..., Any],
) -> None:
    if result.attempted_count <= 0:
        return
    _call_log_message(
        log_message,
        (
            "strategy_plugin_alert_webhook_result "
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


def _auto_detect_providers(
    *,
    wecom_url: str | None,
    dingtalk_url: str | None,
    feishu_url: str | None,
    serverchan_url: str | None,
) -> tuple[str, ...]:
    """Auto-detect webhook providers from configured URLs.

    Returns a deduplicated tuple of provider names for each URL that is set.
    """
    providers: list[str] = []
    if wecom_url:
        providers.append(WEBHOOK_PROVIDER_WECOM)
    if dingtalk_url:
        providers.append(WEBHOOK_PROVIDER_DINGTALK)
    if feishu_url:
        providers.append(WEBHOOK_PROVIDER_FEISHU)
    if serverchan_url:
        providers.append(WEBHOOK_PROVIDER_SERVERCHAN)
    return tuple(providers)


def _coerce_int(value: Any, default: int) -> int:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return int(text)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def _fallback_alert_key(message: StrategyPluginAlertMessage) -> str:
    return "strategy_plugin_webhook_alert/" + _clean_relative_key(
        message.subject or "unknown"
    )
