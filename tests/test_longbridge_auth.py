from __future__ import annotations

import base64
import json
import sys
import types
import unittest
from unittest.mock import patch

from quant_platform_kit.longbridge.auth import build_contexts, fetch_token_from_secret, refresh_token_if_needed


class FakePayload:
    def __init__(self, data: str):
        self.data = data.encode("utf-8")


class FakeAccessResponse:
    def __init__(self, data: str):
        self.payload = FakePayload(data)


class FakeVersion:
    def __init__(self, name: str, state: str = "ACTIVE"):
        self.name = name
        self.state = state


class FakeSecretClient:
    def __init__(self, token: str):
        self.token = token
        self.destroyed: list[str] = []
        self.created_parent = None

    def access_secret_version(self, request):
        self.access_request = request
        return FakeAccessResponse(self.token)

    def add_secret_version(self, request):
        self.created_parent = request["parent"]
        self.created_data = request["payload"]["data"]
        return types.SimpleNamespace(name="projects/demo/secrets/token/versions/3")

    def list_secret_versions(self, request):
        return [
            FakeVersion("projects/demo/secrets/token/versions/1"),
            FakeVersion("projects/demo/secrets/token/versions/3"),
        ]

    def destroy_secret_version(self, request):
        self.destroyed.append(request["name"])


class FakeRequests:
    @staticmethod
    def get(url, headers, timeout):
        class Response:
            @staticmethod
            def json():
                return {"code": 0, "data": {"token": "new-token"}}

        return Response()


class LongBridgeAuthTests(unittest.TestCase):
    def test_fetch_token_from_secret_reads_latest_version(self) -> None:
        client = FakeSecretClient("token-abc")
        token = fetch_token_from_secret("demo", "longport_token", secret_client_factory=lambda: client)

        self.assertEqual(token, "token-abc")
        self.assertEqual(
            client.access_request["name"],
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

    def test_refresh_token_if_needed_persists_new_token(self) -> None:
        payload = {"exp": 1}
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
        token = f"aaa.{encoded}.bbb"
        client = FakeSecretClient(token)

        refreshed = refresh_token_if_needed(
            token,
            project_id="demo",
            secret_name="token",
            app_key="key",
            app_secret="secret",
            requests_module=FakeRequests,
            secret_client_factory=lambda: client,
        )

        self.assertEqual(refreshed, "new-token")
        self.assertEqual(client.created_parent, "projects/demo/secrets/token")
        self.assertEqual(client.destroyed, ["projects/demo/secrets/token/versions/1"])

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
