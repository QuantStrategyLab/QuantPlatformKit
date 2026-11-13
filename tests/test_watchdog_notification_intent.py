import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch


spec = importlib.util.spec_from_file_location('watchdog_under_test', Path(__file__).parents[1] / 'scripts/qsl_watchdog.py')
watchdog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watchdog)


def test_watchdog_sends_intent_and_rejects_unacknowledged_delivery():
    token = str(123456789) + ':' + 'A' * 35
    for acknowledged in (True, False):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = json.dumps({'ok': acknowledged}).encode()
        with patch.dict(os.environ, {'TELEGRAM_TOKEN': token, 'GLOBAL_TELEGRAM_CHAT_ID': 'synthetic-chat'}, clear=True), patch(
            'urllib.request.urlopen', return_value=response,
        ) as send:
            assert watchdog._telegram_alert('Health check failed') is acknowledged
        payload = json.loads(send.call_args.args[0].data)
        assert payload['chat_id'] == 'synthetic-chat'
        assert 'token' not in payload


def test_report_serialization_has_no_secrets():
    token = str(123456789) + ':' + 'A' * 35
    captured = []
    from quant_platform_kit.notifications import send_notification_intent

    def sender(intent, **kwargs):
        receipt = send_notification_intent(intent, **kwargs)
        captured.append(receipt)
        return receipt

    with patch.dict(os.environ, {'TELEGRAM_TOKEN': token, 'GLOBAL_TELEGRAM_CHAT_ID': 'synthetic-chat'}, clear=True), patch(
        'urllib.request.urlopen', side_effect=RuntimeError(token),
    ), patch('quant_platform_kit.notifications.send_notification_intent', side_effect=sender):
        assert watchdog._telegram_alert('Health check failed') is False
    serialized = json.dumps(captured)
    import re
    assert re.search(r'\d{6,12}:A[\w-]{34}', serialized) is None
    assert token not in serialized
    assert 'synthetic-chat' not in serialized
    for receipt in captured:
        for key, value in receipt.items():
            if key.lower() in {'token', 'secret', 'password', 'api_key'}:
                assert not value
