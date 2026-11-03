"""Durable research promotion ticket storage and directory locking."""

from __future__ import annotations

import json
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path

from .models import ResearchPromotionTicket


def save_research_promotion_ticket(
    ticket: ResearchPromotionTicket,
    path: str | Path,
) -> Path:
    """Replace a complete ticket atomically; failed writes retain the old file."""
    import os
    import tempfile

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(ticket.to_dict(include_progress=True), indent=2, sort_keys=True, allow_nan=False) + "\n"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent,
            prefix=f".{target.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target


def load_research_promotion_ticket(path: str | Path) -> ResearchPromotionTicket:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("ticket file must contain a JSON object")
    ticket = ResearchPromotionTicket.from_dict(raw)
    if ticket.live_authority_granted:
        raise ValueError("refusing to load ticket with live_authority_granted=true")
    return ticket


@contextmanager
def _research_directory_lock(directory: Path):
    """One process at a time for this shared directory, never a global queue."""
    import os

    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".research.lock").open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                yield False
                return
            try:
                yield True
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
