from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from quant_platform_kit.schwab.auth import build_client_from_token_payload, get_client_from_secret


class FakeSecretPayload:
    def __init__(self, data: str):
        self.data = data.encode("utf-8")


class FakeSecretResponse:
    def __init__(self, data: str):
        self.payload = FakeSecretPayload(data)


class FakeSecretClient:
    def __init__(self, data: str):
        self.data = data

    def access_secret_version(self, request):
        self.request = request
        return FakeSecretResponse(self.data)


class FakeAuthModule:
    @staticmethod
    def client_from_token_file(token_path, app_key, app_secret):
        return {
            "token_path": token_path,
            "app_key": app_key,
            "app_secret": app_secret,
            "token_contents": Path(token_path).read_text(encoding="utf-8"),
        }


class SchwabAuthTests(unittest.TestCase):
    def test_build_client_from_token_payload_writes_token_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            token_path = str(Path(tmp_dir) / "token.json")
            client = build_client_from_token_payload(
                '{"access_token":"abc"}',
                "app-key",
                "app-secret",
                token_path=token_path,
                auth_module=FakeAuthModule,
            )

        self.assertEqual(client["app_key"], "app-key")
        self.assertIn("access_token", client["token_contents"])

    def test_get_client_from_secret_loads_secret_then_builds_client(self) -> None:
        def factory():
            return FakeSecretClient('{"refresh_token":"xyz"}')

        with tempfile.TemporaryDirectory() as tmp_dir:
            token_path = str(Path(tmp_dir) / "token.json")
            client = get_client_from_secret(
                "demo-project",
                "schwab_token",
                "app-key",
                "app-secret",
                token_path=token_path,
                secret_client_factory=factory,
                auth_module=FakeAuthModule,
            )

        self.assertEqual(client["app_secret"], "app-secret")
        self.assertIn("refresh_token", client["token_contents"])


if __name__ == "__main__":
    unittest.main()
