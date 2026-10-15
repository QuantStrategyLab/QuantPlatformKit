from __future__ import annotations

import base64
import json
import sys
import time
import types
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from quant_platform_kit.longbridge.auth import (
    DEFAULT_REFRESHED_TOKEN_LIFETIME_DAYS,
    build_contexts,
    fetch_token_from_secret,
    refresh_token_if_needed,
)


class FakeSecretStore:
    """Mocks quant_platform_kit.cloud.SecretStore for read-only tests."""

    def __init__(self, token: str):
        self.token = token
        self.access_name = None

    def get_secret(self, secret_name: str, *, project_id: str | None = None) -> str:
        self.access_name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        return self.token


class FakeSecretStoreReadWrite:
    """Mocks SecretStoreReadWrite for read+write tests."""

    def __init__(self, token: str):
        self.token = token
        self.created_parent = None
        self.created_data = None
        self.destroyed: list[str] = []

    def get_secret(self, secret_name: str, *, project_id: str | None = None) -> str:
        return self.token

    def create_secret(self, secret_name: str, payload: str, *, project_id: str | None = None) -> str:
        self.created_parent = f"projects/{project_id}/secrets/{secret_name}"
        self.created_data = payload.encode("utf-8")
        return "projects/demo/secrets/token/versions/3"

    def update_secret(self, secret_name: str, payload: str, *, project_id: str | None = None) -> str:
        self.created_parent = f"projects/{project_id}/secrets/{secret_name}"
        self.created_data = payload.encode("utf-8")
        return "projects/demo/secrets/token/versions/3"

    def destroy_latest_secret(self, secret_name: str, *, project_id: str | None = None) -> None:
        self.destroyed.append(f"projects/{project_id}/secrets/{secret_name}/versions/1")
        self.destroyed.append(f"projects/{project_id}/secrets/{secret_name}/versions/3")


class RecordingRequests:
    """Captures the refresh GET URL/headers and returns a successful body."""

    last_url: str | None = None
    last_headers: dict | None = None

    @classmethod
    def reset(cls) -> None:
        cls.last_url = None
        cls.last_headers = None

    @classmethod
    def get(cls, url, headers, timeout):
        cls.last_url = url
        cls.last_headers = dict(headers)

        class Response:
            @staticmethod
            def json():
                return {"code": 0, "data": {"token": "new-token"}}

        return Response()


class FakeFailedRequests:
    @staticmethod
    def get(url, headers, timeout):
        class Response:
            @staticmethod
            def json():
                return {"code": 401003, "message": "token expired", "data": None}

        return Response()


class LongBridgeAuthTests(unittest.TestCase):
    @patch("quant_platform_kit.longbridge.auth.get_secret_store")
    def test_fetch_token_from_secret_reads_latest_version(self, mock_get_store) -> None:
        fake_store = FakeSecretStore("token-abc")
        mock_get_store.return_value = fake_store

        token = fetch_token_from_secret("demo", "longport_token")

        self.assertEqual(token, "token-abc")
        self.assertEqual(
            fake_store.access_name,
            "projects/demo/secrets/longport_token/versions/latest",
        )

    def test_refresh_token_if_needed_returns_same_token_when_far_from_expiry(self) -> None:
        payload = {"exp": 9999999999}
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
        token = f"aaa.{encoded}.bbb"

        refreshed = refresh_token_if_needed(
            token,
            project_id="demo",
            secret_name="token",
            app_key="key",
            app_secret="secret",
            refresh_threshold_days=30,
        )

        self.assertEqual(refreshed, token)

    @patch("quant_platform_kit.longbridge.auth.get_secret_store_rw")
    def test_refresh_token_if_needed_persists_new_token_with_expired_at(self, mock_get_store_rw) -> None:
        payload = {"exp": 1}
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
        token = f"aaa.{encoded}.bbb"
        fake_store = FakeSecretStoreReadWrite(token)
        mock_get_store_rw.return_value = fake_store
        RecordingRequests.reset()

        refreshed = refresh_token_if_needed(
            token,
            project_id="demo",
            secret_name="token",
            app_key="key",
            app_secret="secret",
            requests_module=RecordingRequests,
            refreshed_token_lifetime_days=DEFAULT_REFRESHED_TOKEN_LIFETIME_DAYS,
        )

        self.assertEqual(refreshed, "new-token")
        self.assertEqual(fake_store.created_parent, "projects/demo/secrets/token")
        self.assertIsNotNone(RecordingRequests.last_url)
        parsed = urlparse(RecordingRequests.last_url)
        self.assertEqual(parsed.path, "/v1/token/refresh")
        query = parse_qs(parsed.query)
        self.assertIn("expired_at", query)
        expired_at = query["expired_at"][0]
        self.assertTrue(expired_at.endswith("Z"))
        self.assertRegex(expired_at, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
        # Signature must cover the same encoded query string used in the URL.
        self.assertIn("Signature=", RecordingRequests.last_headers["X-Api-Signature"])

    def test_refresh_token_if_needed_raises_clear_error_when_expired_and_refresh_fails(self) -> None:
        payload = {"exp": 1}
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
        token = f"aaa.{encoded}.bbb"

        with self.assertRaises(RuntimeError) as context:
            refresh_token_if_needed(
                token,
                project_id="demo",
                secret_name="longport_token_sg",
                app_key="key",
                app_secret="secret",
                requests_module=FakeFailedRequests,
            )

        self.assertIn("longport_token_sg", str(context.exception))
        self.assertIn("refresh failed with code 401003", str(context.exception))

    def test_refresh_token_if_needed_fail_closed_when_refresh_fails_but_token_not_expired(self) -> None:
        payload = {"exp": int(time.time()) + 86400}
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
        token = f"aaa.{encoded}.bbb"

        with self.assertRaises(RuntimeError) as context:
            refresh_token_if_needed(
                token,
                project_id="demo",
                secret_name="longport_token_paper",
                app_key="key",
                app_secret="secret",
                refresh_threshold_days=30,
                requests_module=FakeFailedRequests,
            )

        message = str(context.exception)
        self.assertIn("longport_token_paper", message)
        self.assertIn("still within expiry window", message)
        self.assertIn("401003", message)

    def test_refresh_token_if_needed_raises_clear_error_when_expired_and_app_credentials_missing(self) -> None:
        payload = {"exp": 1}
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
        token = f"aaa.{encoded}.bbb"

        with self.assertRaises(RuntimeError) as context:
            refresh_token_if_needed(
                token,
                project_id="demo",
                secret_name="longport_token_sg",
                app_key="",
                app_secret="",
            )

        self.assertIn("LONGPORT_APP_KEY/LONGPORT_APP_SECRET is missing", str(context.exception))

    def test_build_contexts_uses_longport_openapi(self) -> None:
        longport_module = types.ModuleType("longport")
        openapi_module = types.ModuleType("longport.openapi")

        class FakeConfig:
            def __init__(self, app_key, app_secret, access_token):
                self.args = (app_key, app_secret, access_token)

        class FakeQuoteContext:
            def __init__(self, config):
                self.config = config

        class FakeTradeContext:
            def __init__(self, config):
                self.config = config

        openapi_module.Config = FakeConfig
        openapi_module.QuoteContext = FakeQuoteContext
        openapi_module.TradeContext = FakeTradeContext

        with patch.dict(sys.modules, {"longport": longport_module, "longport.openapi": openapi_module}):
            q_ctx, t_ctx = build_contexts("app-key", "app-secret", "token")

        self.assertEqual(q_ctx.config.args, ("app-key", "app-secret", "token"))
        self.assertEqual(t_ctx.config.args, ("app-key", "app-secret", "token"))


if __name__ == "__main__":
    unittest.main()
