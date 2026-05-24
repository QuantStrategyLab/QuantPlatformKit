"""Backward-compatible aliases for strategy plugin Google Voice alerts."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from .email import send_smtp_email
from .strategy_plugin_google_voice import (
    StrategyPluginGoogleVoiceAlertDelivery,
    StrategyPluginGoogleVoiceAlertMarkerStore,
    StrategyPluginGoogleVoiceAlertPublishResult,
    StrategyPluginGoogleVoiceSettings,
    build_strategy_plugin_alert_context_label,
    publish_strategy_plugin_google_voice_alerts,
)

StrategyPluginEmailSettings = StrategyPluginGoogleVoiceSettings
StrategyPluginEmailAlertDelivery = StrategyPluginGoogleVoiceAlertDelivery
StrategyPluginEmailAlertPublishResult = StrategyPluginGoogleVoiceAlertPublishResult
StrategyPluginEmailAlertMarkerStore = StrategyPluginGoogleVoiceAlertMarkerStore


def publish_strategy_plugin_email_alerts(
    signals: Sequence[object],
    *,
    email_settings: StrategyPluginEmailSettings | object,
    translator: Callable[..., str] | None = None,
    strategy_label: str | None = None,
    context_label: str | None = None,
    alert_store: StrategyPluginEmailAlertMarkerStore | object | None = None,
    send_email: Callable[..., bool] = send_smtp_email,
    log_message: Callable[..., Any] = print,
) -> StrategyPluginEmailAlertPublishResult:
    return publish_strategy_plugin_google_voice_alerts(
        signals,
        google_voice_settings=email_settings,
        translator=translator,
        strategy_label=strategy_label,
        context_label=context_label,
        alert_store=alert_store,
        send_notification=send_email,
        log_message=log_message,
    )

