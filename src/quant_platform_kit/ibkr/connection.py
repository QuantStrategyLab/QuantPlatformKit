from __future__ import annotations

import asyncio
import socket
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


def probe_tcp_endpoint(
    host: str,
    port: int,
    *,
    timeout: float,
    socket_create_connection: Callable[..., Any] | None = None,
) -> None:
    if socket_create_connection is None:
        socket_create_connection = socket.create_connection

    try:
        connection = socket_create_connection((host, port), timeout)
    except TimeoutError as exc:
        raise TimeoutError(f"TCP preflight timed out for {host}:{port}") from exc
    except OSError as exc:
        raise ConnectionError(f"TCP preflight failed for {host}:{port}: {exc}") from exc

    close = getattr(connection, "close", None)
    if callable(close):
        close()


def _disconnect_quietly(ib: Any) -> None:
    disconnect = getattr(ib, "disconnect", None)
    if callable(disconnect):
        try:
            disconnect()
        except Exception:
            pass


def connect_ib(
    host: str,
    port: int,
    client_id: int,
    *,
    timeout: int = 20,
    tcp_preflight_timeout: float | None = 3.0,
    socket_create_connection: Callable[..., Any] | None = None,
    ib_factory: Callable[[], Any] | None = None,
) -> Any:
    ensure_event_loop()
    if tcp_preflight_timeout is not None and tcp_preflight_timeout > 0:
        probe_tcp_endpoint(
            host,
            port,
            timeout=min(float(timeout), float(tcp_preflight_timeout)),
            socket_create_connection=socket_create_connection,
        )
    if ib_factory is None:
        from ib_insync import IB

        ib_factory = IB

    ib = ib_factory()
    try:
        ib.connect(host, port, clientId=client_id, timeout=timeout)
    except TimeoutError as exc:
        _disconnect_quietly(ib)
        raise TimeoutError(
            "IBKR API handshake timed out after TCP preflight succeeded "
            f"for {host}:{port} clientId={client_id}. "
            "Check that IB Gateway/TWS is fully logged in, API access is enabled, "
            "the paper/live port matches the session, no login/API prompt is blocking, "
            "and the client ID is not already stuck in another session."
        ) from exc
    except Exception:
        _disconnect_quietly(ib)
        raise
    return ib
