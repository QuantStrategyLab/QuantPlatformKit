from __future__ import annotations

import json
import urllib.parse
import urllib.request


def send_telegram_message(token: str, chat_id: str, message: str, *, timeout: int = 15) -> None:
    if not token.strip():
        raise ValueError("token must not be empty.")
    if not chat_id.strip():
        raise ValueError("chat_id must not be empty.")
    if not message.strip():
        raise ValueError("message must not be empty.")

    body = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode("utf-8")
    request = urllib.request.Request(
        url=f"https://api.telegram.org/bot{token}/sendMessage",
        data=body,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("ok"):
        raise RuntimeError(f"telegram api returned not ok: {payload}")
