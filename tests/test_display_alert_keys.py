import json
from types import SimpleNamespace
from unittest.mock import patch

from quant_platform_kit.common.strategy_plugins import build_strategy_plugin_alert_messages


def test_names_change_message_without_changing_alert_key_or_signal():
    signal = SimpleNamespace(
        strategy="crypto_live_pool_rotation", plugin="market_regime_control",
        effective_mode="shadow", as_of="2026-10-16", canonical_route="opportunity_watch",
        suggested_action="notify_manual_review", would_trade_if_enabled=False,
        execution_controls={"notification_profile": "shadow_only"},
    )
    before = dict(vars(signal))
    original = build_strategy_plugin_alert_messages((signal,))[0]
    with patch.dict("os.environ", {"QSL_DISPLAY_NAMES_JSON": json.dumps({
        "strategies": {signal.strategy: {"en": "Crypto-Rotation-202609"}},
    })}):
        renamed = build_strategy_plugin_alert_messages((signal,))[0]
    assert "Crypto-Rotation-202609" in renamed.body
    assert renamed.alert_key == original.alert_key
    assert renamed.metadata["strategy"] == original.metadata["strategy"] == signal.strategy
    assert dict(vars(signal)) == before
