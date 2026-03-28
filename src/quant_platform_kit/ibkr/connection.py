from __future__ import annotations

import asyncio
from typing import Any, Callable


def ensure_event_loop() -> asyncio.AbstractEventLoop:
    """ib_insync expects an event loop even inside worker threads."""
    try:
        loop = asyncio.get_event_loop_policy().get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop


def connect_ib(
    host: str,
    port: int,
    client_id: int,
    *,
    timeout: int = 20,
    ib_factory: Callable[[], Any] | None = None,
) -> Any:
    ensure_event_loop()
    if ib_factory is None:
        from ib_insync import IB

        ib_factory = IB

    ib = ib_factory()
    ib.connect(host, port, clientId=client_id, timeout=timeout)
    return ib
