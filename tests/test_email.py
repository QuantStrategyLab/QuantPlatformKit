from quant_platform_kit.notifications.email import parse_email_recipients, send_smtp_email


def test_parse_email_recipients_splits_and_deduplicates():
    assert parse_email_recipients("ops@example.com; risk@example.com, ops@example.com\n") == (
        "ops@example.com",
        "risk@example.com",
    )


def test_send_smtp_email_uses_configured_smtp_client():
    observed = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            observed["connect"] = (host, port, timeout)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def starttls(self):
            observed["starttls"] = True

        def login(self, username, password):
            observed["login"] = (username, password)

        def send_message(self, message):
            observed["message"] = message

    class FakeSmtpModule:
        SMTP = FakeSMTP
        SMTP_SSL = FakeSMTP

    assert send_smtp_email(
        subject="Crisis",
        body="body",
        smtp_host="smtp.example.com",
        smtp_port=587,
        sender="bot@example.com",
        recipients=("risk@example.com",),
        username="user",
        password="pass",
        smtp_module=FakeSmtpModule,
    )
    assert observed["connect"] == ("smtp.example.com", 587, 10.0)
    assert observed["starttls"] is True
    assert observed["login"] == ("user", "pass")
    assert observed["message"]["Subject"] == "Crisis"
    assert observed["message"]["To"] == "risk@example.com"
