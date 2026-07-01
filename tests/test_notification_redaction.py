from __future__ import annotations

import unittest

from quant_platform_kit.notifications._redaction import redact_sensitive_text
from quant_platform_kit.notifications.telegram import send_telegram_message
from scripts import gate_codex_app_review


class NotificationRedactionTests(unittest.TestCase):
    def test_redact_sensitive_text_masks_common_secret_shapes(self) -> None:
        raw = (
            "POST https://api.telegram.org/bot123456:ABC/sendMessage"
            "?access_token=test-secret-token&key=test-webhook-key "
            "Authorization: Bearer testabcdefghijklmnop token='test-another-secret'"
        )

        redacted = redact_sensitive_text(raw)

        self.assertNotIn("123456:ABC", redacted)
        self.assertNotIn("test-secret-token", redacted)
        self.assertNotIn("test-webhook-key", redacted)
        self.assertNotIn("testabcdefghijklmnop", redacted)
        self.assertNotIn("test-another-secret", redacted)
        self.assertIn("<redacted>", redacted)

    def test_telegram_exception_logs_redacted_endpoint(self) -> None:
        messages: list[str] = []

        def opener(_request, timeout):
            raise RuntimeError(
                "failed https://api.telegram.org/bot123456:ABC/sendMessage?access_token=test-secret-token"
            )

        sent = send_telegram_message(
            bot_token="123456:ABC",
            chat_ids=("123",),
            text="hello",
            opener=opener,
            printer=lambda *args, **_kwargs: messages.append(" ".join(str(arg) for arg in args)),
        )

        self.assertFalse(sent)
        self.assertEqual(len(messages), 1)
        self.assertNotIn("123456:ABC", messages[0])
        self.assertNotIn("test-secret-token", messages[0])
        self.assertIn("<redacted>", messages[0])

    def test_codex_gate_secret_diff_violation_does_not_echo_value(self) -> None:
        secret_value = "super-" + "secret-token-value"
        diff = "\n".join(
            [
                "diff --git a/example.py b/example.py",
                "+++ b/example.py",
                "+token = '" + secret_value + "'",
            ]
        )

        violations = gate_codex_app_review.scan_diff(diff, [])

        self.assertEqual(len(violations), 1)
        self.assertNotIn(secret_value, violations[0])
        self.assertIn("sensitive assignment pattern detected", violations[0])


if __name__ == "__main__":
    unittest.main()
