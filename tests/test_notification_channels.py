from quant_platform_kit.notifications import telegram
from quant_platform_kit.notifications.channel import TelegramChatChannel


def test_telegram_chat_channel_uses_current_sender_contract(monkeypatch):
    observed = {}

    def fake_send(**kwargs):
        observed.update(kwargs)
        return False

    monkeypatch.setattr(telegram, "send_telegram_message", fake_send)

    sent = TelegramChatChannel().send_message(
        "chat",
        "message",
        token="token",
    )

    assert sent is False
    assert observed["bot_token"] == "token"
    assert observed["chat_ids"] == "chat"
