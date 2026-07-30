from quant_platform_kit.notifications import cycle_channel
from quant_platform_kit.notifications import telegram


def test_telegram_cycle_sender_propagates_transport_failure(monkeypatch):
    monkeypatch.setattr(
        telegram,
        "send_telegram_message",
        lambda **_kwargs: False,
    )
    sender = cycle_channel.build_cycle_sender(
        telegram_token="token",
        telegram_chat_id="chat",
    )

    assert sender("rebalance") is False


def test_telegram_cycle_sender_fails_when_credentials_are_missing():
    sender = cycle_channel.build_cycle_sender()

    assert sender("rebalance") is False
