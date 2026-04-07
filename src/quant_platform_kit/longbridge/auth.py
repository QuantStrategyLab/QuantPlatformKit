from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any, Callable


def fetch_token_from_secret(
    project_id: str,
    secret_name: str,
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
    resource_name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": resource_name})
    return response.payload.data.decode("UTF-8").strip()


def _longport_sign(method: str, uri: str, headers: dict[str, str], params: str, body: str, secret: str) -> str:
    canonical_request = (
        f"{method.upper()}|{uri}|{params}|"
        f"authorization:{headers['Authorization']}\n"
        f"x-api-key:{headers['X-Api-Key']}\n"
        f"x-timestamp:{headers['X-Timestamp']}\n|authorization;x-api-key;x-timestamp|"
    )
    if body:
        canonical_request += hashlib.sha1(body.encode("utf-8")).hexdigest()
    sign_str = "HMAC-SHA256|" + hashlib.sha1(canonical_request.encode("utf-8")).hexdigest()
    signature = hmac.new(secret.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"HMAC-SHA256 SignedHeaders=authorization;x-api-key;x-timestamp, Signature={signature}"


def _decode_token_expiry(token: str) -> float | None:
    try:
        parts = token.split(".")
        if len(parts) <= 1:
            return None
        payload_b64 = parts[1]
        padded_payload = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded_payload).decode("utf-8"))
        expiry = payload.get("exp")
        if expiry is None:
            return None
        return float(expiry)
    except Exception:
        return None


def _format_expiry(expiry_timestamp: float) -> str:
    return datetime.fromtimestamp(expiry_timestamp, timezone.utc).isoformat()


def refresh_token_if_needed(
    current_token: str,
    *,
    project_id: str,
    secret_name: str,
    app_key: str | None,
    app_secret: str | None,
    refresh_threshold_days: int = 30,
    requests_module: Any | None = None,
    secret_client_factory: Callable[[], Any] | None = None,
) -> str:
    expiry_timestamp = _decode_token_expiry(current_token)
    now = time.time()

    if not app_key or not app_secret:
        if expiry_timestamp is not None and expiry_timestamp <= now:
            raise RuntimeError(
                "LongPort token in secret "
                f"'{secret_name}' expired at {_format_expiry(expiry_timestamp)} "
                "and cannot be refreshed because LONGPORT_APP_KEY/LONGPORT_APP_SECRET is missing."
            )
        return current_token

    if expiry_timestamp is not None and (expiry_timestamp - now) / 86400 > refresh_threshold_days:
        return current_token

    if requests_module is None:
        import requests as requests_module

    headers = {
        "X-Api-Key": app_key,
        "Authorization": current_token,
        "X-Timestamp": str(int(time.time())),
        "Content-Type": "application/json; charset=utf-8",
    }
    headers["X-Api-Signature"] = _longport_sign("GET", "/v1/token/refresh", headers, "", "", app_secret)
    response = requests_module.get(
        "https://openapi.longportapp.com/v1/token/refresh",
        headers=headers,
        timeout=15,
    ).json()
    if response.get("code") != 0:
        if expiry_timestamp is not None and expiry_timestamp <= now:
            code = response.get("code")
            message = response.get("message") or "unknown error"
            raise RuntimeError(
                f"LongPort token in secret '{secret_name}' expired at {_format_expiry(expiry_timestamp)}; "
                f"refresh failed with code {code}: {message}"
            )
        return current_token

    new_token = response["data"]["token"]
    if secret_client_factory is None:
        try:
            import google.cloud.secretmanager_v1 as secret_manager
        except ImportError:
            from google.cloud import secret_manager

        secret_client_factory = secret_manager.SecretManagerServiceClient
        destroyed_state = secret_manager.SecretVersion.State.DESTROYED
    else:
        destroyed_state = getattr(getattr(secret_client_factory(), "__class__", object), "DESTROYED", None)

    client = secret_client_factory()
    parent = f"projects/{project_id}/secrets/{secret_name}"
    new_version = client.add_secret_version(
        request={"parent": parent, "payload": {"data": new_token.encode("UTF-8")}}
    )

    try:
        versions = client.list_secret_versions(request={"parent": parent})
        for version in versions:
            if version.name == new_version.name:
                continue
            version_state = getattr(version, "state", None)
            if destroyed_state is not None and version_state == destroyed_state:
                continue
            client.destroy_secret_version(request={"name": version.name})
    except Exception:
        pass

    return new_token


def build_contexts(app_key: str, app_secret: str, access_token: str) -> tuple[Any, Any]:
    from longport.openapi import Config, QuoteContext, TradeContext

    config = Config(app_key=app_key, app_secret=app_secret, access_token=access_token)
    return QuoteContext(config), TradeContext(config)
