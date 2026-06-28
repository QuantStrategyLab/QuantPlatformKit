"""SMTP email notification helpers."""

from __future__ import annotations

import smtplib
from collections.abc import Sequence
from email.message import EmailMessage


def parse_email_recipients(raw_value: str | Sequence[str] | None) -> tuple[str, ...]:
    if raw_value is None:
        return ()
    if isinstance(raw_value, str):
        values = raw_value.replace(";", ",").replace("\n", ",").split(",")
    else:
        values = raw_value
    recipients = []
    seen = set()
    for value in values:
        recipient = str(value or "").strip()
        if not recipient or recipient in seen:
            continue
        recipients.append(recipient)
        seen.add(recipient)
    return tuple(recipients)


def send_smtp_email(
    *,
    subject: str,
    body: str,
    smtp_host: str | None,
    smtp_port: int,
    sender: str | None,
    recipients: Sequence[str],
    username: str | None = None,
    password: str | None = None,
    use_starttls: bool = True,
    use_ssl: bool = False,
    timeout: float = 10.0,
    smtp_module=smtplib,
    printer=print,
) -> bool:
    resolved_recipients = parse_email_recipients(recipients)
    host = str(smtp_host or "").strip()
    from_addr = str(sender or "").strip()
    if not host or not from_addr or not resolved_recipients:
        return False

    message = EmailMessage()
    message["From"] = from_addr
    message["To"] = ", ".join(resolved_recipients)
    message["Subject"] = str(subject or "").strip() or "strategy alert"
    message.set_content(str(body or "").strip())

    try:
        smtp_cls = smtp_module.SMTP_SSL if use_ssl else smtp_module.SMTP
        with smtp_cls(host, int(smtp_port), timeout=timeout) as smtp:
            if use_starttls and not use_ssl:
                smtp.starttls()
            if username:
                smtp.login(str(username), str(password or ""))
            smtp.send_message(message)
        return True
    except Exception as exc:
        printer(f"Email send failed: {exc}", flush=True)
        return False
