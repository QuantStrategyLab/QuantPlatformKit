from quant_platform_kit.notifications.events import (
    NotificationPublisher,
    RenderedNotification,
    publish_rendered_notification,
)


def test_publish_rendered_notification_splits_log_and_send_sinks():
    logs = []
    sends = []

    publish_rendered_notification(
        RenderedNotification(detailed_text=" detailed ", compact_text=" compact "),
        log_message=logs.append,
        send_message=sends.append,
    )

    assert logs == ["detailed"]
    assert sends == ["compact"]


def test_publish_rendered_notification_skips_empty_sinks():
    logs = []
    sends = []

    publish_rendered_notification(
        RenderedNotification(detailed_text="  ", compact_text=""),
        log_message=logs.append,
        send_message=sends.append,
    )

    assert logs == []
    assert sends == []


def test_notification_publisher_uses_configured_sinks():
    logs = []
    sends = []
    publisher = NotificationPublisher(log_message=logs.append, send_message=sends.append)

    publisher.publish(RenderedNotification(detailed_text="log", compact_text="send"))

    assert logs == ["log"]
    assert sends == ["send"]
