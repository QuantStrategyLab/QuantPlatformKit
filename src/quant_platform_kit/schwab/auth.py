from __future__ import annotations

import stat
from typing import Any, Callable

from quant_platform_kit.cloud import get_secret_store


def load_secret_payload(
    project_id: str,
    secret_id: str,
    *,
    secret_client_factory: Callable[[], Any] | None = None,
) -> str:
    return get_secret_store().get_secret(secret_id, project_id=project_id)


def build_client_from_token_payload(
    token_payload: str,
    app_key: str,
    app_secret: str,
    *,
    token_path: str = "/tmp/token.json",
    auth_module: Any | None = None,
) -> Any:
    if auth_module is None:
        from schwab import auth as auth_module

    with open(token_path, "w", encoding="utf-8") as token_file:
        token_file.write(token_payload)
    os_mode = stat.S_IRUSR | stat.S_IWUSR
    import os

    os.chmod(token_path, os_mode)
    return auth_module.client_from_token_file(token_path, app_key, app_secret)


def get_client_from_secret(
    project_id: str,
    secret_id: str,
    app_key: str,
    app_secret: str,
    *,
    token_path: str = "/tmp/token.json",
    secret_client_factory: Callable[[], Any] | None = None,
    auth_module: Any | None = None,
) -> Any:
    token_payload = load_secret_payload(
        project_id,
        secret_id,
        secret_client_factory=secret_client_factory,
    )
    return build_client_from_token_payload(
        token_payload,
        app_key,
        app_secret,
        token_path=token_path,
        auth_module=auth_module,
    )
