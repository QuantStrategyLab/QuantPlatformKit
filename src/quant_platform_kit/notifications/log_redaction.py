"""Opt-in redaction for configured logging handlers and text streams."""

from __future__ import annotations

import logging
import sys
from threading import RLock
from typing import Any

from ._redaction import redact_exception, redact_sensitive_data, redact_sensitive_text


class SensitiveDataFilter(logging.Filter):
    """Remove credential fields, formatted secrets and exception URL credentials."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_sensitive_data(record.msg)
        record.args = redact_sensitive_data(record.args)
        record.msg = redact_sensitive_text(record.getMessage())
        record.args = ()
        if record.exc_info and record.exc_info[1] is not None:
            record.exc_text = redact_exception(record.exc_info[1])
            record.exc_info = None
        elif record.exc_text:
            record.exc_text = redact_sensitive_text(record.exc_text)
        if record.stack_info:
            record.stack_info = redact_sensitive_text(record.stack_info)
        return True


class _RedactingStream:
    """Buffer text through newline so split writes are redacted together."""

    def __init__(self, stream: Any) -> None:
        self._stream = stream
        self._pending = ""
        self._lock = RLock()

    def write(self, text: str) -> int:
        with self._lock:
            self._pending += text
            while "\n" in self._pending:
                line, self._pending = self._pending.split("\n", 1)
                self._stream.write(redact_sensitive_text(line) + "\n")
        return len(text)

    def writelines(self, lines: Any) -> None:
        for line in lines:
            self.write(line)

    def flush(self) -> None:
        with self._lock:
            if self._pending:
                self._stream.write(redact_sensitive_text(self._pending))
                self._pending = ""
            self._stream.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


def install_log_redaction(*, wrap_streams: bool = False) -> None:
    """Idempotently filter root/current handlers; optionally wrap stdout/stderr.

    Call after logging configuration, and again after adding handlers. Root
    logger filters alone do not cover records propagated from child loggers.
    Streams cover text writes through newline or flush, not binary writes.
    """
    root = logging.getLogger()
    loggers = [root] + [
        logger for logger in logging.Logger.manager.loggerDict.values()
        if isinstance(logger, logging.Logger)
    ]
    targets = [root] + [handler for logger in loggers for handler in logger.handlers]
    for target in targets:
        if not any(isinstance(item, SensitiveDataFilter) for item in target.filters):
            target.addFilter(SensitiveDataFilter())
    if wrap_streams:
        for name in ("stdout", "stderr"):
            stream = getattr(sys, name)
            if not isinstance(stream, _RedactingStream):
                setattr(sys, name, _RedactingStream(stream))
