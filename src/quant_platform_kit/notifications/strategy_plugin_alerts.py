"""Channel dispatcher for strategy plugin alerts."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .email import send_smtp_email
from .push import send_strategy_plugin_push
from .sms import send_twilio_sms
from .telegram import send_strategy_plugin_telegram
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

_DEFAULT_ALERT_STATE_DIR = "/tmp/quant_strategy_plugin_alerts"
_CHANNEL_EMAIL = "email"
_CHANNEL_SMS = "sms"
_CHANNEL_PUSH = "push"
_CHANNEL_TELEGRAM = "telegram"
_SUPPORTED_CHANNELS = frozenset({_CHANNEL_EMAIL, _CHANNEL_SMS, _CHANNEL_PUSH, _CHANNEL_TELEGRAM})


@dataclass(frozen=True)
class StrategyPluginAlertChannelStores:
    """Marker stores used by each alert channel."""

    email: StrategyPluginEmailAlertMarkerStore | object | None = None
    sms: StrategyPluginSmsAlertMarkerStore | object | None = None
    push: StrategyPluginPushAlertMarkerStore | object | None = None
    telegram: StrategyPluginTelegramAlertMarkerStore | object | None = None

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
        )


@dataclass(frozen=True)
class StrategyPluginAlertStateSettings:
    """Shared marker-store location for strategy plugin alert channels."""

    local_dir: str | Path | None = _DEFAULT_ALERT_STATE_DIR
    gcs_prefix_uri: str | None = None
    gcp_project_id: str | None = None
    client_factory: Any = None

    @classmethod
    def from_env(
        cls,
        *,
        env_reader: Callable[[str, str | None], str | None] = os.getenv,
        gcp_project_id: str | None = None,
        fallback_gcs_prefix_uri: str | None = None,
        default_local_dir: str | Path | None = _DEFAULT_ALERT_STATE_DIR,
    ) -> "StrategyPluginAlertStateSettings":
        explicit_gcs_uri = env_reader("STRATEGY_PLUGIN_ALERT_STATE_GCS_URI", None)
        report_gcs_uri = env_reader("EXECUTION_REPORT_GCS_URI", None)
        local_dir = env_reader("STRATEGY_PLUGIN_ALERT_STATE_DIR", None)
        return cls(
            local_dir=local_dir or default_local_dir,
            gcs_prefix_uri=explicit_gcs_uri or report_gcs_uri or fallback_gcs_prefix_uri,
            gcp_project_id=gcp_project_id,
        )

    def build_channel_stores(self) -> StrategyPluginAlertChannelStores:
        return StrategyPluginAlertChannelStores(
            email=StrategyPluginEmailAlertMarkerStore(
                local_dir=self.local_dir,
                gcs_prefix_uri=self.gcs_prefix_uri,
                gcp_project_id=self.gcp_project_id,
                client_factory=self.client_factory,
            ),
            sms=StrategyPluginSmsAlertMarkerStore(
                local_dir=self.local_dir,
                gcs_prefix_uri=self.gcs_prefix_uri,
                gcp_project_id=self.gcp_project_id,
                client_factory=self.client_factory,
            ),
            push=StrategyPluginPushAlertMarkerStore(
                local_dir=self.local_dir,
                gcs_prefix_uri=self.gcs_prefix_uri,
                gcp_project_id=self.gcp_project_id,
                client_factory=self.client_factory,
            ),
            telegram=StrategyPluginTelegramAlertMarkerStore(
                local_dir=self.local_dir,
                gcs_prefix_uri=self.gcs_prefix_uri,
                gcp_project_id=self.gcp_project_id,
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
        | StrategyPluginTelegramAlertPublishResult,
        ...,
    ]:
        return tuple(
            result
            for result in (
                self.email_result,
                self.sms_result,
                self.push_result,
                self.telegram_result,
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
    log_message: Callable[..., Any] = print,
) -> StrategyPluginAlertPublishResult:
    """Publish strategy plugin alerts through the configured notification channels."""

    selected_channels = _resolve_channels(channels, notification_settings=notification_settings)
    stores = _resolve_alert_stores(alert_stores=alert_stores, state_settings=state_settings)
    email_result = None
    sms_result = None
    push_result = None
    telegram_result = None
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
    return StrategyPluginAlertPublishResult(
        email_result=email_result,
        sms_result=sms_result,
        push_result=push_result,
        telegram_result=telegram_result,
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
        raw_channels = _get_value(notification_settings, "crisis_alert_channels", None)
    if raw_channels in (None, "", (), []):
        raw_channels = (_CHANNEL_EMAIL, _CHANNEL_SMS, _CHANNEL_PUSH, _CHANNEL_TELEGRAM)
    return _normalize_channels(raw_channels)


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
]
