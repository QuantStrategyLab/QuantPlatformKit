"""Channel dispatcher for strategy plugin alerts."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._email import send_smtp_email
from .push import send_strategy_plugin_push
from .sms import send_twilio_sms
from .telegram import send_strategy_plugin_telegram
from .webhook import send_strategy_plugin_webhook
from .strategy_plugin_email import (
    StrategyPluginEmailAlertMarkerStore,
    StrategyPluginEmailAlertPublishResult,
    StrategyPluginEmailSettings,
    build_strategy_plugin_alert_context_label,
    publish_strategy_plugin_email_alerts,
)
from .strategy_plugin_sms import (
    StrategyPluginSmsAlertMarkerStore,
    StrategyPluginSmsAlertPublishResult,
    StrategyPluginSmsSettings,
    publish_strategy_plugin_sms_alerts,
)
from .strategy_plugin_push import (
    StrategyPluginPushAlertMarkerStore,
    StrategyPluginPushAlertPublishResult,
    StrategyPluginPushSettings,
    publish_strategy_plugin_push_alerts,
)
from .strategy_plugin_telegram import (
    StrategyPluginTelegramAlertMarkerStore,
    StrategyPluginTelegramAlertPublishResult,
    StrategyPluginTelegramSettings,
    publish_strategy_plugin_telegram_alerts,
)
from .strategy_plugin_webhook import (
    StrategyPluginWebhookAlertMarkerStore,
    StrategyPluginWebhookAlertPublishResult,
    publish_strategy_plugin_webhook_alerts,
)

_DEFAULT_ALERT_STATE_DIR = "/tmp/quant_strategy_plugin_alerts"
_CHANNEL_EMAIL = "email"
_CHANNEL_SMS = "sms"
_CHANNEL_PUSH = "push"
_CHANNEL_TELEGRAM = "telegram"
_CHANNEL_WEBHOOK = "webhook"
_SUPPORTED_CHANNELS = frozenset({_CHANNEL_EMAIL, _CHANNEL_SMS, _CHANNEL_PUSH, _CHANNEL_TELEGRAM, _CHANNEL_WEBHOOK})


def _read_cloud_env(
    env_reader: Callable[[str, str | None], str | None],
    *,
    new_key: str,
    old_key: str,
) -> str | None:
    """Read new env var name first, fall back to old name with deprecation warning."""
    val = env_reader(new_key, None)
    if val is not None:
        return val
    val = env_reader(old_key, None)
    if val is not None:
        import warnings
        warnings.warn(
            f"Env var '{old_key}' is deprecated, use '{new_key}'",
            DeprecationWarning,
            stacklevel=3,
        )
    return val


@dataclass(frozen=True)
class StrategyPluginAlertChannelStores:
    """Marker stores used by each alert channel."""

    email: StrategyPluginEmailAlertMarkerStore | object | None = None
    sms: StrategyPluginSmsAlertMarkerStore | object | None = None
    push: StrategyPluginPushAlertMarkerStore | object | None = None
    telegram: StrategyPluginTelegramAlertMarkerStore | object | None = None
    webhook: StrategyPluginWebhookAlertMarkerStore | object | None = None

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, object | None] | None,
    ) -> "StrategyPluginAlertChannelStores":
        if value is None:
            return cls()
        return cls(
            email=value.get(_CHANNEL_EMAIL),
            sms=value.get(_CHANNEL_SMS),
            push=value.get(_CHANNEL_PUSH),
            telegram=value.get(_CHANNEL_TELEGRAM),
            webhook=value.get(_CHANNEL_WEBHOOK),
        )


@dataclass(frozen=True)
class StrategyPluginAlertStateSettings:
    """Shared marker-store location for strategy plugin alert channels."""

    local_dir: str | Path | None = _DEFAULT_ALERT_STATE_DIR
    cloud_prefix_uri: str | None = None
    project_id: str | None = None
    client_factory: Any = None

    @classmethod
    def from_env(
        cls,
        *,
        env_reader: Callable[[str, str | None], str | None] = os.getenv,
        project_id: str | None = None,
        fallback_cloud_prefix_uri: str | None = None,
        default_local_dir: str | Path | None = _DEFAULT_ALERT_STATE_DIR,
    ) -> "StrategyPluginAlertStateSettings":
        explicit_cloud_uri = _read_cloud_env(
            env_reader,
            new_key="STRATEGY_PLUGIN_ALERT_STATE_CLOUD_URI",
            old_key="STRATEGY_PLUGIN_ALERT_STATE_GCS_URI",
        )
        report_cloud_uri = _read_cloud_env(
            env_reader,
            new_key="EXECUTION_REPORT_CLOUD_URI",
            old_key="EXECUTION_REPORT_GCS_URI",
        )
        local_dir = env_reader("STRATEGY_PLUGIN_ALERT_STATE_DIR", None)
        return cls(
            local_dir=local_dir or default_local_dir,
            cloud_prefix_uri=explicit_cloud_uri or report_cloud_uri or fallback_cloud_prefix_uri,
            project_id=project_id,
        )

    def build_channel_stores(self) -> StrategyPluginAlertChannelStores:
        return StrategyPluginAlertChannelStores(
            email=StrategyPluginEmailAlertMarkerStore(
                local_dir=self.local_dir,
                cloud_prefix_uri=self.cloud_prefix_uri,
                project_id=self.project_id,
                client_factory=self.client_factory,
            ),
            sms=StrategyPluginSmsAlertMarkerStore(
                local_dir=self.local_dir,
                cloud_prefix_uri=self.cloud_prefix_uri,
                project_id=self.project_id,
                client_factory=self.client_factory,
            ),
            push=StrategyPluginPushAlertMarkerStore(
                local_dir=self.local_dir,
                cloud_prefix_uri=self.cloud_prefix_uri,
                project_id=self.project_id,
                client_factory=self.client_factory,
            ),
            telegram=StrategyPluginTelegramAlertMarkerStore(
                local_dir=self.local_dir,
                cloud_prefix_uri=self.cloud_prefix_uri,
                project_id=self.project_id,
                client_factory=self.client_factory,
            ),
            webhook=StrategyPluginWebhookAlertMarkerStore(
                local_dir=self.local_dir,
                cloud_prefix_uri=self.cloud_prefix_uri,
                project_id=self.project_id,
                client_factory=self.client_factory,
            ),
        )


@dataclass(frozen=True)
class StrategyPluginAlertPublishResult:
    """Combined delivery result across strategy plugin alert channels."""

    email_result: StrategyPluginEmailAlertPublishResult | None = None
    sms_result: StrategyPluginSmsAlertPublishResult | None = None
    push_result: StrategyPluginPushAlertPublishResult | None = None
    telegram_result: StrategyPluginTelegramAlertPublishResult | None = None
    webhook_result: StrategyPluginWebhookAlertPublishResult | None = None

    @property
    def attempted_count(self) -> int:
        return sum(result.attempted_count for result in self._results())

    @property
    def sent_count(self) -> int:
        return sum(result.sent_count for result in self._results())

    @property
    def skipped_count(self) -> int:
        return sum(result.skipped_count for result in self._results())

    @property
    def failed_count(self) -> int:
        return sum(result.failed_count for result in self._results())

    def to_report_fields(self) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "strategy_plugin_alert_attempted_count": self.attempted_count,
            "strategy_plugin_alert_sent_count": self.sent_count,
            "strategy_plugin_alert_skipped_count": self.skipped_count,
            "strategy_plugin_alert_failed_count": self.failed_count,
        }
        if self.email_result is not None:
            fields.update(self.email_result.to_report_fields())
        if self.sms_result is not None:
            fields.update(self.sms_result.to_report_fields())
        if self.push_result is not None:
            fields.update(self.push_result.to_report_fields())
        if self.telegram_result is not None:
            fields.update(self.telegram_result.to_report_fields())
        if self.webhook_result is not None:
            fields.update(self.webhook_result.to_report_fields())
        return fields

    def to_summary_fields(self) -> dict[str, int]:
        fields = {
            "strategy_plugin_alert_sent_count": self.sent_count,
        }
        if self.email_result is not None:
            fields["strategy_plugin_alert_email_sent_count"] = self.email_result.sent_count
        if self.sms_result is not None:
            fields["strategy_plugin_alert_sms_sent_count"] = self.sms_result.sent_count
        if self.push_result is not None:
            fields["strategy_plugin_alert_push_sent_count"] = self.push_result.sent_count
        if self.telegram_result is not None:
            fields["strategy_plugin_alert_telegram_sent_count"] = self.telegram_result.sent_count
        if self.webhook_result is not None:
            fields["strategy_plugin_alert_webhook_sent_count"] = self.webhook_result.sent_count
        return fields

    def attach_to_report(self, report: dict[str, Any]) -> None:
        report.setdefault("summary", {}).update(self.to_summary_fields())
        report.setdefault("diagnostics", {}).update(self.to_report_fields())

    def _results(
        self,
    ) -> tuple[
        StrategyPluginEmailAlertPublishResult
        | StrategyPluginSmsAlertPublishResult
        | StrategyPluginPushAlertPublishResult
        | StrategyPluginTelegramAlertPublishResult
        | StrategyPluginWebhookAlertPublishResult,
        ...,
    ]:
        return tuple(
            result
            for result in (
                self.email_result,
                self.sms_result,
                self.push_result,
                self.telegram_result,
                self.webhook_result,
            )
            if result is not None
        )


def publish_strategy_plugin_alerts(
    signals: Sequence[object],
    *,
    notification_settings: (
        StrategyPluginEmailSettings
        | StrategyPluginSmsSettings
        | StrategyPluginPushSettings
        | StrategyPluginTelegramSettings
        | object
    ),
    translator: Callable[..., str] | None = None,
    strategy_label: str | None = None,
    context_label: str | None = None,
    channels: Sequence[str] | str | None = None,
    state_settings: StrategyPluginAlertStateSettings | None = None,
    alert_stores: StrategyPluginAlertChannelStores | Mapping[str, object | None] | None = None,
    send_email_notification: Callable[..., bool] = send_smtp_email,
    send_sms_notification: Callable[..., bool] = send_twilio_sms,
    send_push_notification: Callable[..., bool] = send_strategy_plugin_push,
    send_telegram_notification: Callable[..., bool] = send_strategy_plugin_telegram,
    send_webhook_notification: Callable[..., bool] = send_strategy_plugin_webhook,
    log_message: Callable[..., Any] = print,
) -> StrategyPluginAlertPublishResult:
    """Publish strategy plugin alerts through the configured notification channels."""

    selected_channels = _resolve_channels(channels, notification_settings=notification_settings)
    stores = _resolve_alert_stores(alert_stores=alert_stores, state_settings=state_settings)
    email_result = None
    sms_result = None
    push_result = None
    telegram_result = None
    webhook_result = None
    if _CHANNEL_EMAIL in selected_channels:
        email_result = publish_strategy_plugin_email_alerts(
            signals,
            email_settings=notification_settings,
            translator=translator,
            strategy_label=strategy_label,
            context_label=context_label,
            alert_store=stores.email,
            send_notification=send_email_notification,
            log_message=log_message,
        )
    if _CHANNEL_SMS in selected_channels:
        sms_result = publish_strategy_plugin_sms_alerts(
            signals,
            sms_settings=notification_settings,
            translator=translator,
            strategy_label=strategy_label,
            context_label=context_label,
            alert_store=stores.sms,
            send_notification=send_sms_notification,
            log_message=log_message,
        )
    if _CHANNEL_PUSH in selected_channels:
        push_result = publish_strategy_plugin_push_alerts(
            signals,
            push_settings=notification_settings,
            translator=translator,
            strategy_label=strategy_label,
            context_label=context_label,
            alert_store=stores.push,
            send_notification=send_push_notification,
            log_message=log_message,
        )
    if _CHANNEL_TELEGRAM in selected_channels:
        telegram_result = publish_strategy_plugin_telegram_alerts(
            signals,
            telegram_settings=notification_settings,
            translator=translator,
            strategy_label=strategy_label,
            context_label=context_label,
            alert_store=stores.telegram,
            send_notification=send_telegram_notification,
            log_message=log_message,
        )
    if _CHANNEL_WEBHOOK in selected_channels:
        webhook_result = publish_strategy_plugin_webhook_alerts(
            signals,
            webhook_settings=notification_settings,
            translator=translator,
            strategy_label=strategy_label,
            context_label=context_label,
            alert_store=stores.webhook,
            send_notification=send_webhook_notification,
            log_message=log_message,
        )
    return StrategyPluginAlertPublishResult(
        email_result=email_result,
        sms_result=sms_result,
        push_result=push_result,
        telegram_result=telegram_result,
        webhook_result=webhook_result,
    )


def _resolve_alert_stores(
    *,
    alert_stores: StrategyPluginAlertChannelStores | Mapping[str, object | None] | None,
    state_settings: StrategyPluginAlertStateSettings | None,
) -> StrategyPluginAlertChannelStores:
    if isinstance(alert_stores, StrategyPluginAlertChannelStores):
        return alert_stores
    if isinstance(alert_stores, Mapping):
        return StrategyPluginAlertChannelStores.from_mapping(alert_stores)
    return (state_settings or StrategyPluginAlertStateSettings.from_env()).build_channel_stores()


def _normalize_channels(channels: Sequence[str] | str) -> tuple[str, ...]:
    raw_channels = (
        channels.replace(";", ",").replace("\n", ",").split(",")
        if isinstance(channels, str)
        else tuple(channels)
    )
    normalized: list[str] = []
    for channel in raw_channels:
        name = str(channel or "").strip().lower()
        if not name:
            continue
        if name not in _SUPPORTED_CHANNELS:
            supported = ", ".join(sorted(_SUPPORTED_CHANNELS))
            raise ValueError(f"unsupported strategy plugin alert channel {name!r}; expected one of: {supported}")
        if name not in normalized:
            normalized.append(name)
    return tuple(normalized)


def _resolve_channels(
    channels: Sequence[str] | str | None,
    *,
    notification_settings: object,
) -> tuple[str, ...]:
    raw_channels = channels
    if raw_channels is None:
        raw_channels = _get_value(notification_settings, "strategy_plugin_alert_channels", None)
    if raw_channels in (None, "", (), []):
        raw_channels = (_CHANNEL_EMAIL, _CHANNEL_SMS, _CHANNEL_PUSH, _CHANNEL_TELEGRAM)
    resolved = _normalize_channels(raw_channels)
    # Auto-add webhook if any webhook URL is configured
    if _CHANNEL_WEBHOOK not in resolved and _has_any_webhook_url(notification_settings):
        resolved = (*resolved, _CHANNEL_WEBHOOK)
    return resolved


def _has_any_webhook_url(settings: object) -> bool:
    """Check if any webhook provider URL is configured."""
    url_keys = (
        "strategy_plugin_alert_webhook_wecom_url",
        "strategy_plugin_alert_webhook_dingtalk_url",
        "strategy_plugin_alert_webhook_feishu_url",
        "strategy_plugin_alert_webhook_serverchan_url",
    )
    for key in url_keys:
        url = _get_value(settings, key, None)
        if url and str(url).strip():
            return True
    return False


def _get_value(value: object, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


__all__ = [
    "StrategyPluginAlertChannelStores",
    "StrategyPluginAlertPublishResult",
    "StrategyPluginAlertStateSettings",
    "build_strategy_plugin_alert_context_label",
    "publish_strategy_plugin_alerts",
    "publish_strategy_plugin_webhook_alerts",
]
