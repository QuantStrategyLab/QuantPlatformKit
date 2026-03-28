from __future__ import annotations

import stat
from typing import Any, Callable


def load_secret_payload(
    project_id: str,
    secret_id: str,
    *,
    secret_client_factory: Callable[[], Any] | None = None,
) -> str:
    if secret_client_factory is None:
        try:
            import google.cloud.secretmanager_v1 as secret_manager
        except ImportError:
            from google.cloud import secret_manager

        secret_client_factory = secret_manager.SecretManagerServiceClient

    client = secret_client_factory()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


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
