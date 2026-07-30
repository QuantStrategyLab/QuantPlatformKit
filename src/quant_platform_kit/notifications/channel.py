"""Notification channel abstraction — pluggable senders for SMS, push, email, and chat.

Each channel type has a Protocol defining the send signature.
The default implementations wire to Twilio (SMS), Pushover/Ntfy (push),
SMTP (email), and Telegram Bot API (chat).

To replace a provider, implement the corresponding Protocol and pass it
as ``send_notification`` to the ``publish_strategy_plugin_*`` function.

Example (custom SMS provider)::

    class AliyunSmsChannel:
        def send_sms(self, recipient: str, body: str, *, sender: str | None = None) -> bool:
            # call Aliyun SMS API
            return True

    publish_strategy_plugin_sms_alerts(
        signals,
        sms_settings=settings,
        send_notification=AliyunSmsChannel().send_sms,
    )
"""

from __future__ import annotations

from typing import Protocol


# ──────────────────────────────────────────────────────────────────────
#  Channel Protocols
# ──────────────────────────────────────────────────────────────────────


class SmsChannel(Protocol):
    """Send an SMS message. Return True on success, False on failure."""

    def send_sms(self, recipient: str, body: str, *, sender: str | None = None) -> bool:
        ...


class PushChannel(Protocol):
    """Send a push notification. Return True on success, False on failure.

    ``target`` is provider-specific: Pushover user key, Ntfy topic, etc.
    ``provider`` identifies the backend (e.g. "pushover", "ntfy").
    """

    def send_push(
        self,
        title: str,
        body: str,
        *,
        target: str,
        provider: str = "pushover",
        url: str | None = None,
        url_title: str | None = None,
        priority: str = "normal",
        api_base_url: str | None = None,
    ) -> bool:
        ...


class EmailChannel(Protocol):
    """Send an email message. Return True on success, False on failure."""

    def send_email(
        self,
        subject: str,
        body: str,
        *,
        recipients: list[str],
        sender: str | None = None,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 465,
        security: str = "ssl",
        username: str | None = None,
        password: str | None = None,
    ) -> bool:
        ...


class WebhookChannel(Protocol):
    """Send a message to a webhook-based chat platform (WeCom, DingTalk, Feishu, ServerChan, etc.).

    ``webhook_url`` is the full webhook URL provided by the platform.
    ``title`` is optional and will be rendered appropriately for the platform.
    Return True on success, False on failure.
    """

    def send_webhook(
        self,
        webhook_url: str,
        text: str,
        *,
        title: str | None = None,
    ) -> bool:
        ...


class ChatChannel(Protocol):
    """Send a message to a chat platform. Return True on success, False on failure.

    ``chat_id`` and ``token`` are specific to Telegram Bot API.
    For other platforms (Slack, Discord, WeChat), wrap their API
    in this signature.
    """

    def send_message(
        self,
        chat_id: str,
        text: str,
        *,
        token: str,
        api_base_url: str = "https://api.telegram.org",
        parse_mode: str = "HTML",
    ) -> bool:
        ...


# ──────────────────────────────────────────────────────────────────────
#  Default channel implementations (thin wrappers around existing functions)
# ──────────────────────────────────────────────────────────────────────


class TwilioSmsChannel:
    """Default SMS channel — wraps send_twilio_sms()."""

    def send_sms(self, recipient: str, body: str, *, sender: str | None = None) -> bool:
        from .sms import send_twilio_sms
        return send_twilio_sms(
            recipient=recipient,
            body=body,
            account_sid=None,
            auth_token=None,
            sender=sender,
        )


class PushoverChannel:
    """Pushover push channel — wraps send_pushover_push()."""

    def send_push(
        self,
        title: str,
        body: str,
        *,
        target: str,
        provider: str = "pushover",
        url: str | None = None,
        url_title: str | None = None,
        priority: str = "normal",
        api_base_url: str | None = None,
    ) -> bool:
        from .push import send_pushover_push
        return send_pushover_push(
            user_key=target,
            message=body,
            title=title,
            url=url,
            url_title=url_title,
            priority=priority,
            api_base_url=api_base_url,
        )


class NtfyChannel:
    """Ntfy push channel — wraps send_ntfy_push()."""

    def send_push(
        self,
        title: str,
        body: str,
        *,
        target: str,
        provider: str = "ntfy",
        url: str | None = None,
        url_title: str | None = None,
        priority: str = "normal",
        api_base_url: str | None = None,
    ) -> bool:
        from .push import send_ntfy_push
        return send_ntfy_push(
            topic=target,
            message=body,
            title=title,
            url=url,
            priority=priority,
            api_base_url=api_base_url,
        )


class SmtpEmailChannel:
    """Default email channel — wraps send_smtp_email()."""

    def send_email(
        self,
        subject: str,
        body: str,
        *,
        recipients: list[str],
        sender: str | None = None,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 465,
        security: str = "ssl",
        username: str | None = None,
        password: str | None = None,
    ) -> bool:
        from .email import send_smtp_email
        return send_smtp_email(
            recipients=recipients,
            subject=subject,
            body=body,
            sender=sender,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            security=security,
            username=username,
            password=password,
        )


class TelegramChatChannel:
    """Default chat channel — wraps send_telegram_message()."""

    def send_message(
        self,
        chat_id: str,
        text: str,
        *,
        token: str,
        api_base_url: str = "https://api.telegram.org",
        parse_mode: str = "HTML",
    ) -> bool:
        from .telegram import send_telegram_message
        return send_telegram_message(
            chat_ids=chat_id,
            text=text,
            bot_token=token,
            api_base_url=api_base_url,
            parse_mode=parse_mode,
        )


class WecomWebhookChannel:
    """WeCom (企业微信) bot webhook channel — wraps send_wecom_webhook()."""

    def send_webhook(
        self,
        webhook_url: str,
        text: str,
        *,
        title: str | None = None,
    ) -> bool:
        from .webhook import send_wecom_webhook
        return send_wecom_webhook(webhook_url, text)


class DingtalkWebhookChannel:
    """DingTalk (钉钉) bot webhook channel — wraps send_dingtalk_webhook()."""

    def send_webhook(
        self,
        webhook_url: str,
        text: str,
        *,
        title: str | None = None,
    ) -> bool:
        from .webhook import send_dingtalk_webhook
        return send_dingtalk_webhook(webhook_url, text, title=title or "")


class FeishuWebhookChannel:
    """Feishu (飞书) bot webhook channel — wraps send_feishu_webhook()."""

    def send_webhook(
        self,
        webhook_url: str,
        text: str,
        *,
        title: str | None = None,
    ) -> bool:
        from .webhook import send_feishu_webhook
        return send_feishu_webhook(webhook_url, text)


class ServerchanWebhookChannel:
    """ServerChan (Server酱) webhook channel — wraps send_serverchan_webhook()."""

    def send_webhook(
        self,
        webhook_url: str,
        text: str,
        *,
        title: str | None = None,
    ) -> bool:
        from .webhook import send_serverchan_webhook
        return send_serverchan_webhook(webhook_url, title=title or "", body=text)
