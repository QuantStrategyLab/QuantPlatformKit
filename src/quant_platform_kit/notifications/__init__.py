"""Notification integrations."""

from .email import parse_email_recipients, send_smtp_email
from .events import NotificationPublisher, RenderedNotification, publish_rendered_notification
from .sms import normalize_sms_recipient, parse_sms_recipients, send_twilio_sms
from .strategy_plugin_alerts import (
    StrategyPluginAlertChannelStores,
    StrategyPluginAlertPublishResult,
    StrategyPluginAlertStateSettings,
    publish_strategy_plugin_alerts,
)
from .strategy_plugin_email import (
    StrategyPluginEmailAlertDelivery,
    StrategyPluginEmailAlertMarkerStore,
    StrategyPluginEmailAlertPublishResult,
    StrategyPluginEmailSettings,
    build_strategy_plugin_alert_context_label,
    publish_strategy_plugin_email_alerts,
)
from .strategy_plugin_sms import (
    StrategyPluginSmsAlertDelivery,
    StrategyPluginSmsAlertMarkerStore,
    StrategyPluginSmsAlertPublishResult,
    StrategyPluginSmsSettings,
    publish_strategy_plugin_sms_alerts,
)

__all__ = [
    "NotificationPublisher",
    "RenderedNotification",
    "StrategyPluginAlertChannelStores",
    "StrategyPluginAlertPublishResult",
    "StrategyPluginAlertStateSettings",
    "StrategyPluginEmailAlertDelivery",
    "StrategyPluginEmailAlertMarkerStore",
    "StrategyPluginEmailAlertPublishResult",
    "StrategyPluginEmailSettings",
    "StrategyPluginSmsAlertDelivery",
    "StrategyPluginSmsAlertMarkerStore",
    "StrategyPluginSmsAlertPublishResult",
    "StrategyPluginSmsSettings",
    "build_strategy_plugin_alert_context_label",
    "normalize_sms_recipient",
    "parse_email_recipients",
    "parse_sms_recipients",
    "publish_rendered_notification",
    "publish_strategy_plugin_alerts",
    "publish_strategy_plugin_email_alerts",
    "publish_strategy_plugin_sms_alerts",
    "send_smtp_email",
    "send_twilio_sms",
]
