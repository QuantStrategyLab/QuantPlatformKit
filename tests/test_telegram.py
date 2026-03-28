from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from quant_platform_kit.notifications.telegram import send_telegram_message


class TelegramTests(unittest.TestCase):
    def test_send_telegram_message_rejects_empty_values(self) -> None:
        with self.assertRaises(ValueError):
            send_telegram_message("", "1", "hello")
        with self.assertRaises(ValueError):
            send_telegram_message("token", "", "hello")
        with self.assertRaises(ValueError):
            send_telegram_message("token", "1", "")

    def test_send_telegram_message_calls_telegram_api(self) -> None:
        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps({"ok": True}).encode("utf-8")
        fake_context = MagicMock()
        fake_context.__enter__.return_value = fake_response
        fake_context.__exit__.return_value = None

        with patch("urllib.request.urlopen", return_value=fake_context) as urlopen:
            send_telegram_message("token", "123", "hello world")

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.telegram.org/bottoken/sendMessage")
        self.assertEqual(request.method, "POST")


if __name__ == "__main__":
    unittest.main()
