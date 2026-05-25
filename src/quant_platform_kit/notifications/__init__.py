"""Notification integrations."""

from .email import parse_email_recipients, send_smtp_email
from .events import NotificationPublisher, RenderedNotification, publish_rendered_notification
from .push import parse_push_recipients, send_ntfy_push, send_pushover_push, send_strategy_plugin_push
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
from .strategy_plugin_push import (
    StrategyPluginPushAlertDelivery,
    StrategyPluginPushAlertMarkerStore,
    StrategyPluginPushAlertPublishResult,
    StrategyPluginPushSettings,
    publish_strategy_plugin_push_alerts,
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
    "StrategyPluginPushAlertDelivery",
    "StrategyPluginPushAlertMarkerStore",
    "StrategyPluginPushAlertPublishResult",
    "StrategyPluginPushSettings",
    "StrategyPluginSmsAlertDelivery",
    "StrategyPluginSmsAlertMarkerStore",
    "StrategyPluginSmsAlertPublishResult",
    "StrategyPluginSmsSettings",
    "build_strategy_plugin_alert_context_label",
    "normalize_sms_recipient",
    "parse_email_recipients",
    "parse_push_recipients",
    "parse_sms_recipients",
    "publish_rendered_notification",
    "publish_strategy_plugin_alerts",
    "publish_strategy_plugin_email_alerts",
    "publish_strategy_plugin_push_alerts",
    "publish_strategy_plugin_sms_alerts",
    "send_ntfy_push",
    "send_pushover_push",
    "send_smtp_email",
    "send_strategy_plugin_push",
    "send_twilio_sms",
]
