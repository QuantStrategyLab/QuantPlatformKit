"""Backward-compatibility shim — delegates to _email to avoid stdlib collision.

The SMTP helpers live in ``_email.py`` because ``email.py`` shadows
Python's stdlib ``email`` package, breaking ``smtplib`` imports in some
environments (e.g. when pytest's plugin loader runs alongside this package).

Prefer importing from the package root::

    from quant_platform_kit.notifications import parse_email_recipients, send_smtp_email
"""

from ._email import parse_email_recipients, send_smtp_email

__all__ = ["parse_email_recipients", "send_smtp_email"]
