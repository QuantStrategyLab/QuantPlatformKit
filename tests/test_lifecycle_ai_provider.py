"""Tests for strategy_lifecycle.ai_provider gateway fallback payloads."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from quant_platform_kit.strategy_lifecycle import ai_provider


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc_info):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class AiProviderGatewayFallbackTests(unittest.TestCase):

    def test_local_gateway_payload_defaults_to_quant_platform_kit(self) -> None:
        requests = []

        def fake_urlopen(request, timeout):
            requests.append(request)
            if request.full_url.endswith("/v1/ai/execute/jobs"):
                return _FakeResponse({"job_id": "job-1"})
            return _FakeResponse({"status": "succeeded", "output": "ok"})

        with patch.dict(
            ai_provider.os.environ,
            {"CODEX_AUDIT_SERVICE_URL": "https://gateway.example"},
            clear=True,
        ), patch.object(ai_provider, "_fetch_oidc_token", return_value="token"), patch(
            "urllib.request.urlopen", side_effect=fake_urlopen
        ), patch("time.sleep", return_value=None):
            client = ai_provider.AiServiceClient(
                ai_provider.AiServiceConfig.reliability(
                    primary=ai_provider.AiProviderConfig.codex_vps()
                )
            )
            result = client._call_local(
                ai_provider.AiProviderConfig.codex_vps(), "review this", 1.0
            )

        self.assertTrue(result.success)
        payload = json.loads(requests[0].data.decode("utf-8"))
        self.assertEqual(payload["source_repository"], "QuantStrategyLab/QuantPlatformKit")
        self.assertEqual(
            dict(requests[0].header_items()).get("User-agent"),
            "quant-platform-kit-lifecycle",
        )


if __name__ == "__main__":
    unittest.main()
