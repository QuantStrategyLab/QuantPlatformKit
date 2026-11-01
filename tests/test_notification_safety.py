"""Regression coverage for report-safe notification and logging boundaries."""

import io
import json
import logging
import sys
from dataclasses import FrozenInstanceError, fields
from hashlib import sha256
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest
from requests.exceptions import ConnectionError

from quant_platform_kit import notifications
from quant_platform_kit.notifications import (
    NotificationIntent,
    SensitiveDataFilter,
    install_log_redaction,
    redact_exception,
    redact_sensitive_data,
    redact_sensitive_text,
    send_notification_intent,
)


@pytest.fixture
def fake_token():
    # Construct obvious synthetic data at runtime, never a scanner-shaped literal.
    return "123456789:" + "A" * 35


@pytest.fixture(autouse=True)
def restore_logging_and_streams():
    loggers = [logging.getLogger()] + [
        item for item in logging.Logger.manager.loggerDict.values()
        if isinstance(item, logging.Logger)
    ]
    targets = loggers + [handler for logger in loggers for handler in logger.handlers]
    saved = [(target, list(target.filters)) for target in targets]
    stdout, stderr = sys.stdout, sys.stderr
    yield
    for target, filters in saved:
        target.filters[:] = filters
    sys.stdout, sys.stderr = stdout, stderr


def response(status=200, payload=None):
    context = MagicMock()
    context.__enter__.return_value.status = status
    context.__enter__.return_value.read.return_value = json.dumps(
        {"ok": True} if payload is None else payload
    ).encode()
    return context


def test_intent_is_credential_free_immutable_and_serializable(fake_token):
    metadata = {"source": "worker", "details": [{"attempt": 1}]}
    intent = NotificationIntent("hello", "run-1", ("chat-1",), metadata=metadata)
    metadata["details"][0]["token"] = fake_token
    assert "token" not in intent.metadata["details"][0]
    with pytest.raises(FrozenInstanceError):
        intent.text = fake_token
    with pytest.raises(TypeError):
        intent.metadata["token"] = fake_token
    with pytest.raises(TypeError):
        intent.metadata["details"][0]["token"] = fake_token
    assert {field.name for field in fields(intent)} == {
        "text", "run_id", "chat_ids", "channel", "dry_run", "metadata",
    }
    encoded = json.dumps(intent.to_dict())
    assert fake_token not in encoded + repr(intent)
    assert json.loads(encoded)["metadata"] == {"source": "worker", "details": [{"attempt": 1}]}


@pytest.mark.parametrize("key", [
    "token", "bot_token", "SECRET", "password", "api_key", "apiKey",
    "Authorization", "private-key", "clientSecret", "credentials", "access_key",
])
def test_intent_rejects_credential_keys_and_data_redacts_them(key, fake_token):
    with pytest.raises(ValueError) as error:
        NotificationIntent("hello", "run-1", metadata={"nested": [{key: fake_token}]})
    assert fake_token not in str(error.value)
    original = {key: "fake", "text": "hello", "run_id": "run-1", "dry_run": False}
    redacted = redact_sensitive_data(original)
    assert redacted == {**original, key: "<redacted>"}
    assert original[key] == "fake"


@pytest.mark.parametrize("field", ["text", "run_id", "chat_ids", "channel", "metadata"])
def test_intent_rejects_token_literals_anywhere(field, fake_token):
    values = {"text": "hello", "run_id": "run-1"}
    values[field] = ((fake_token,) if field == "chat_ids" else
                     {"note": fake_token} if field == "metadata" else fake_token)
    with pytest.raises(ValueError) as error:
        NotificationIntent(**values)
    assert fake_token not in str(error.value)


def test_structured_and_json_redaction_is_recursive_and_non_mutating(fake_token):
    original = {"token": "fake", "text": "preserve", "items": [
        {"url": "https://api.telegram.org/bot" + fake_token + "/sendMessage"},
        "bare " + fake_token, {"password": "short"},
    ], "run_id": "run-1", "chat_ids": ["chat-1"], "dry_run": True, "count": 2}
    before = json.dumps(original)
    result = redact_sensitive_data(original)
    assert fake_token not in json.dumps(result)
    assert json.dumps(original) == before
    assert result["text"] == "preserve"
    assert result["chat_ids"] == ["chat-1"]
    assert result["dry_run"] is True and result["count"] == 2
    result["items"][0]["url"] = "changed"
    assert original["items"][0]["url"] != "changed"
    encoded = redact_sensitive_text(before)
    assert fake_token not in encoded
    assert json.loads(encoded)["token"] == "<redacted>"
    assert redact_sensitive_text("bare " + fake_token) == "bare <redacted>"
    assert redact_sensitive_text("no credentials here") == "no credentials here"


def test_exception_chains_and_requests_urls_are_redacted(fake_token):
    url = "https://api.telegram.org/bot" + fake_token + "/sendMessage"
    try:
        try:
            raise URLError("failed at " + url)
        except URLError as cause:
            raise ConnectionError("request " + url) from cause
    except ConnectionError as exc:
        rendered = redact_exception(exc)
    assert fake_token not in rendered
    assert "URLError" in rendered and "ConnectionError" in rendered
    assert "direct cause" in rendered


def test_logging_filter_handles_requests_exception_args_and_cached_traceback(fake_token):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(SensitiveDataFilter())
    logger = logging.getLogger("qpk.notification-safety")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        try:
            raise ConnectionError("https://api.telegram.org/bot" + fake_token + "/sendMessage")
        except ConnectionError:
            logger.exception("request failed for %s", fake_token)
        logger.info("structured %s", {"token": "fake", "run_id": "run-1"})
        logger.info("mapping %(token)s %(run_id)s", {"token": "fake", "run_id": "run-1"})
        record = logging.LogRecord("qpk", logging.ERROR, __file__, 1, "cached", (), None)
        record.exc_text = "old traceback " + fake_token
        record.stack_info = "stack " + fake_token
        handler.handle(record)
    finally:
        logger.removeHandler(handler)
    output = stream.getvalue()
    assert fake_token not in output
    assert "'fake'" not in output and "mapping fake " not in output
    assert "ConnectionError" in output and "run-1" in output
    assert "<redacted>" in output


def test_install_is_idempotent_and_covers_propagation_and_local_handlers(fake_token):
    root = logging.getLogger()
    root_stream, child_stream = io.StringIO(), io.StringIO()
    root_handler, child_handler = logging.StreamHandler(root_stream), logging.StreamHandler(child_stream)
    logger = logging.getLogger("qpk.install-safety")
    logger.setLevel(logging.WARNING)
    root.addHandler(root_handler)
    logger.addHandler(child_handler)
    try:
        install_log_redaction()
        install_log_redaction()
        for target in (root, root_handler, child_handler):
            assert sum(isinstance(item, SensitiveDataFilter) for item in target.filters) == 1
        logger.warning("token literal %s", fake_token)
        root.warning("token literal %s", fake_token)
    finally:
        root.removeHandler(root_handler)
        logger.removeHandler(child_handler)
    assert fake_token not in root_stream.getvalue() + child_stream.getvalue()
    assert "<redacted>" in root_stream.getvalue() and "<redacted>" in child_stream.getvalue()


def test_optional_stream_wrapper_redacts_split_writes_and_flush(fake_token):
    stdout, stderr = io.StringIO(), io.StringIO()
    sys.stdout, sys.stderr = stdout, stderr
    install_log_redaction(wrap_streams=True)
    first_stdout, first_stderr = sys.stdout, sys.stderr
    install_log_redaction(wrap_streams=True)
    assert (sys.stdout, sys.stderr) == (first_stdout, first_stderr)
    assert sys.stdout.write(fake_token[:10]) == 10
    sys.stdout.write(fake_token[10:] + "\n")
    sys.stderr.write(json.dumps({"token": "fake", "run_id": "run-1"}))
    sys.stderr.flush()
    sys.stdout.writelines([fake_token, "\n"])
    assert fake_token not in stdout.getvalue()
    assert "<redacted>" in stdout.getvalue()
    assert json.loads(stderr.getvalue()) == {"token": "<redacted>", "run_id": "run-1"}


def test_sender_resolves_env_at_send_time_and_returns_only_receipt(fake_token):
    intent = NotificationIntent("hello", "run-1", ("chat-1",))
    opener = MagicMock(return_value=response())
    with patch.dict("os.environ", {"TELEGRAM_TOKEN": fake_token}):
        receipt = send_notification_intent(intent, opener=opener)
    assert receipt == {
        "status": "sent", "http_status": 200, "sha256": sha256(b"hello").hexdigest(),
        "length": 5, "run_id": "run-1", "ok": True,
    }
    assert fake_token not in json.dumps([intent.to_dict(), receipt]) + repr(receipt)
    assert opener.call_count == 1
    assert opener.call_args.args[0].full_url.endswith("/bot" + fake_token + "/sendMessage")


def test_sender_supports_existing_env_and_cloud_secret_store_names(fake_token):
    intent = NotificationIntent("hello", "run-1", ("chat-1",))
    with patch.dict("os.environ", {"STRATEGY_PLUGIN_ALERT_TELEGRAM_BOT_TOKEN": fake_token}):
        assert send_notification_intent(
            intent, bot_token_env="STRATEGY_PLUGIN_ALERT_TELEGRAM_BOT_TOKEN",
            opener=lambda *_args, **_kwargs: response(),
        )["ok"]
    with patch("quant_platform_kit.cloud.get_secret_store") as factory:
        factory.return_value.get_secret.return_value = fake_token
        receipt = send_notification_intent(
            intent, secret_name="synthetic-telegram-token", project_id="synthetic-project",
            opener=lambda *_args, **_kwargs: response(),
        )
    factory.return_value.get_secret.assert_called_once_with(
        "synthetic-telegram-token", project_id="synthetic-project",
    )
    assert receipt["ok"]


def test_dry_run_reads_no_credentials_and_sends_nothing():
    with patch("os.environ.get", side_effect=AssertionError("must not read env")), patch(
        "quant_platform_kit.cloud.get_secret_store", side_effect=AssertionError("must not read secrets")
    ), patch("urllib.request.urlopen", side_effect=AssertionError("must not send")):
        receipt = send_notification_intent(
            NotificationIntent("hello", "run-1", ("chat-1",), dry_run=True),
            secret_name="synthetic-telegram-token",
        )
    assert receipt["status"] == "dry_run" and receipt["ok"]
    assert receipt["http_status"] is None


@pytest.mark.parametrize("case,code", [("http", 403), ("ack", 200), ("network", None), ("secret", None)])
def test_sender_failure_receipts_do_not_retain_provider_errors(case, code, fake_token):
    intent = NotificationIntent("hello", "run-1", ("chat-1",))
    url = "https://api.telegram.org/bot" + fake_token + "/sendMessage"
    opener = MagicMock(return_value=response(payload={"ok": False, "description": fake_token}))
    if case == "http":
        opener.side_effect = HTTPError(url, 403, fake_token, {}, None)
    elif case == "network":
        opener.side_effect = ConnectionError(url)
    with patch.dict("os.environ", {"TELEGRAM_TOKEN": fake_token}), patch(
        "quant_platform_kit.cloud.get_secret_store"
    ) as factory:
        factory.side_effect = RuntimeError(fake_token)
        receipt = send_notification_intent(
            intent, opener=opener,
            secret_name="synthetic-telegram-token" if case == "secret" else None,
        )
    assert receipt["status"] == "failed" and not receipt["ok"]
    assert receipt["http_status"] == code
    assert fake_token not in json.dumps(receipt) + repr(receipt)


def test_mixed_recipient_outcomes_fail_with_unknown_aggregate_status(fake_token):
    with patch.dict("os.environ", {"TELEGRAM_TOKEN": fake_token}):
        receipt = send_notification_intent(
            NotificationIntent("hello", "run-1", ("chat-1", "chat-2")),
            opener=MagicMock(side_effect=[response(), response(503, {"ok": False})]),
        )
    assert not receipt["ok"] and receipt["http_status"] is None


def test_new_public_api_is_exported_from_notifications_package():
    for name in (
        "NotificationIntent", "NotificationReceipt", "SensitiveDataFilter", "install_log_redaction",
        "redact_exception", "redact_sensitive_data", "redact_sensitive_text", "send_notification_intent",
    ):
        assert name in notifications.__all__
        assert getattr(notifications, name) is not None


@pytest.mark.parametrize("text", [
    "prefix {\"token\": \"fake\"}", "prefix {'password': 'fake with spaces'}",
    "bot_token=fake", "authorization=short", "api_key=short",
])
def test_formatted_credential_assignments_are_redacted(text):
    result = redact_sensitive_text(text)
    assert "fake" not in result and "short" not in result
    assert "<redacted>" in result


def test_missing_configuration_and_invalid_channel_return_failed_receipt():
    with patch.dict("os.environ", {}, clear=True), patch("urllib.request.urlopen") as opener:
        for intent in (
            NotificationIntent("hello", "run-1", ("chat-1",)),
            NotificationIntent("hello", "run-1", ("chat-1",), channel="unsupported"),
        ):
            receipt = send_notification_intent(intent)
            assert receipt["status"] == "failed" and not receipt["ok"]
            assert receipt["http_status"] is None
        opener.assert_not_called()



def test_redacted_json_preserves_escaping_and_url_boundaries(fake_token):
    original = {
        "text": 'password="fake with spaces"',
        "url": "https://api.telegram.org/bot" + fake_token,
        "nested_json": json.dumps({"token": "fake"}),
    }
    result = json.loads(redact_sensitive_text(json.dumps(original)))
    assert result["text"] == 'password="<redacted>"'
    assert result["url"] == "https://api.telegram.org/bot<redacted>"
    assert json.loads(result["nested_json"])["token"] == "<redacted>"


def test_logging_filter_keeps_percent_placeholders_after_sensitive_names(fake_token):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(SensitiveDataFilter())
    logger = logging.getLogger("qpk.placeholder-safety")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        logger.info("token=%s", "plain-secret-value")
        logger.info("password: %s user=%s", "plain-secret-value", "run-1")
        logger.info("%(api_key)s %(run_id)s", {"api_key": "plain-secret-value", "run_id": "run-1"})
    finally:
        logger.removeHandler(handler)
    output = stream.getvalue()
    assert "plain-secret-value" not in output
    assert "run-1" in output and "Logging error" not in output


def test_telegram_token_ending_in_separator_is_redacted():
    token = "123456789:A" + "b" * 33 + "-"
    assert token not in redact_sensitive_text("value " + token)
    assert token not in redact_sensitive_text(token + " tail")


def test_redaction_is_linear_on_long_hyphenated_text():
    import time

    started = time.perf_counter()
    redact_sensitive_text("a-" * 20000)
    assert time.perf_counter() - started < 2
