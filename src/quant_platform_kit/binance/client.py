from __future__ import annotations


def connect_client(api_key: str, api_secret: str, *, timeout: int = 30, client_factory=None):
    if client_factory is None:
        from binance.client import Client as client_factory  # type: ignore

    client = client_factory(api_key, api_secret, {"timeout": timeout})
    client.ping()
    return client
