"""SMS notification helpers."""

from __future__ import annotations

import base64
import urllib.parse
import urllib.request
from collections.abc import Sequence
from typing import Any


def normalize_sms_recipient(value: str) -> str:
    """Normalize common US phone-number formatting to E.164.

    Non-phone identifiers are returned trimmed so tests and future providers can
    still pass explicit values through unchanged.
    """

    text = str(value or "").strip()
    if not text:
        return ""
    digits = "".join(char for char in text if char.isdigit())
    if text.startswith("+") and digits:
        return f"+{digits}"
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return text


def parse_sms_recipients(raw_value: str | Sequence[str] | None) -> tuple[str, ...]:
    if raw_value is None:
        return ()
    if isinstance(raw_value, str):
        values = raw_value.replace(";", ",").replace("\n", ",").split(",")
    else:
        values = raw_value
    recipients = []
    seen = set()
    for value in values:
        recipient = normalize_sms_recipient(str(value or ""))
        if not recipient or recipient in seen:
            continue
        recipients.append(recipient)
        seen.add(recipient)
    return tuple(recipients)


def send_twilio_sms(
    *,
    body: str,
    recipients: Sequence[str],
    account_sid: str | None,
    auth_token: str | None,
    from_number: str | None = None,
    messaging_service_sid: str | None = None,
    api_base_url: str = "https://api.twilio.com",
    timeout: float = 10.0,
    opener: Any = None,
    printer=print,
) -> bool:
    resolved_recipients = parse_sms_recipients(recipients)
    sid = str(account_sid or "").strip()
    token = str(auth_token or "").strip()
    sender = normalize_sms_recipient(str(from_number or ""))
    service_sid = str(messaging_service_sid or "").strip()
    text = str(body or "").strip()
    if not resolved_recipients or not sid or not token or not text:
        return False
    if not sender and not service_sid:
        return False

    request_opener = opener or urllib.request.urlopen
    base_url = str(api_base_url or "https://api.twilio.com").rstrip("/")
    endpoint = f"{base_url}/2010-04-01/Accounts/{urllib.parse.quote(sid)}/Messages.json"
    auth_header = base64.b64encode(f"{sid}:{token}".encode("utf-8")).decode("ascii")
    all_sent = True
    for recipient in resolved_recipients:
        payload = {
            "To": recipient,
            "Body": text,
        }
        if service_sid:
            payload["MessagingServiceSid"] = service_sid
        else:
            payload["From"] = sender
        data = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=data,
            headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with request_opener(request, timeout=timeout) as response:
                status = getattr(response, "status", None)
                if status is None:
                    status = response.getcode()
                status = int(status)
        except Exception as exc:
            printer(f"SMS send failed for {recipient}: {exc}", flush=True)
            all_sent = False
            continue
        if status < 200 or status >= 300:
            printer(f"SMS send failed for {recipient}: HTTP {status}", flush=True)
            all_sent = False
    return all_sent
