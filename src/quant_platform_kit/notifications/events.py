"""Notification event envelope and delivery helpers shared by platform runtimes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RenderedNotification:
    """Rendered notification payload split by sink."""

    detailed_text: str
    compact_text: str


@dataclass(frozen=True)
class NotificationPublisher:
    """Publish rendered notifications to the configured sinks."""

    log_message: Callable[[str], None]
    send_message: Callable[[str], bool | None]

    def publish(self, notification: RenderedNotification) -> bool:
        return publish_rendered_notification(
            notification,
            log_message=self.log_message,
            send_message=self.send_message,
        )


def publish_rendered_notification(
    notification: RenderedNotification,
    *,
    log_message: Callable[[str], None],
    send_message: Callable[[str], bool | None],
) -> bool:
    """Write the detailed log copy and send the compact user notification."""
    detailed = str(notification.detailed_text or "").strip()
    compact = str(notification.compact_text or "").strip()
    if detailed:
        log_message(detailed)
    if compact:
        return send_message(compact) is not False
    return True
