"""Notification integrations."""

from .email import parse_email_recipients, send_smtp_email
from .events import NotificationPublisher, RenderedNotification, publish_rendered_notification
from .strategy_plugin_google_voice import (
    StrategyPluginGoogleVoiceAlertDelivery,
    StrategyPluginGoogleVoiceAlertMarkerStore,
    StrategyPluginGoogleVoiceAlertPublishResult,
    StrategyPluginGoogleVoiceSettings,
    build_strategy_plugin_alert_context_label,
    publish_strategy_plugin_google_voice_alerts,
)

__all__ = [
    "NotificationPublisher",
    "RenderedNotification",
    "StrategyPluginGoogleVoiceAlertDelivery",
    "StrategyPluginGoogleVoiceAlertMarkerStore",
    "StrategyPluginGoogleVoiceAlertPublishResult",
    "StrategyPluginGoogleVoiceSettings",
    "build_strategy_plugin_alert_context_label",
    "parse_email_recipients",
    "publish_rendered_notification",
    "publish_strategy_plugin_google_voice_alerts",
    "send_smtp_email",
]
