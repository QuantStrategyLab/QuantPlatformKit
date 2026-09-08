"""Tests for strategy_lifecycle.ai_provider gateway fallback payloads."""

from __future__ import annotations

import json
import io
import urllib.error
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
    def test_research_subscription_opt_in_reaches_sdk_without_api_fallback(self):
        gateway = Mock()
        gateway.execute.return_value = SimpleNamespace(provider="cursor", success=True, output="advisory", error="",
            raw={"provider": "cursor", "research_stage": "optimization", "model": "synthetic-model",
                 "reasoning_effort": "high"})
        with patch.object(ai_provider, "_HAS_GATEWAY_CLIENT", True), patch.object(ai_provider, "GatewayConfig", create=True), patch.object(
            ai_provider, "AiGatewayClient", return_value=gateway, create=True
        ), patch.dict(ai_provider.os.environ, {"AI_GATEWAY_RESEARCH_PROVIDERS": "codex,cursor"}, clear=True):
            result = ai_provider.AiServiceClient(ai_provider.AiServiceConfig.reliability(
                primary=ai_provider.AiProviderConfig.codex_vps(), fallback=[ai_provider.AiProviderConfig.gpt()]
            )).execute("synthetic", research_stage="optimization")
        self.assertTrue(result.success)
        self.assertEqual(result.provider, "cursor")
        self.assertEqual(gateway.execute.call_args.kwargs["allowed_providers"], ["codex", "cursor"])
        gateway.execute.assert_called_once()
        gateway.analyze.assert_not_called()

    def test_invalid_research_subscription_configuration_never_calls_backend(self):
        for setting in ("api", "cursor,codex", "codex,cursor,api", "codex,codex", "codex,"):
            with self.subTest(setting=setting), patch.dict(ai_provider.os.environ, {"AI_GATEWAY_RESEARCH_PROVIDERS": setting}, clear=True), patch.object(
                ai_provider.AiServiceClient, "_call_single"
            ) as backend:
                result = ai_provider.AiServiceClient(ai_provider.AiServiceConfig.reliability(
                    primary=ai_provider.AiProviderConfig.codex_vps()
                )).execute("synthetic", research_stage="optimization")
            self.assertFalse(result.success)
            backend.assert_not_called()

    def test_direct_subscription_freezes_admitted_route_and_preserves_identity(self):
        route = {"provider": "cursor", "research_stage": "optimization", "model": "synthetic-model", "reasoning_effort": "high"}
        for change in ({}, {"provider": "codex"}, {"model": "different-model"}, {"reasoning_effort": "low"}, {"job_id": "different-job"}):
            with self.subTest(change=change), patch.object(ai_provider, "_HAS_GATEWAY_CLIENT", False), patch.dict(
                ai_provider.os.environ, {"CODEX_AUDIT_SERVICE_URL": "https://gateway.invalid", "AI_GATEWAY_RESEARCH_PROVIDERS": "codex,cursor"}, clear=True
            ), patch.object(ai_provider, "_fetch_oidc_token", return_value="synthetic"), patch("urllib.request.urlopen", side_effect=[
                _FakeResponse({"subscription_research_routing": "v1"}),
                _FakeResponse({"job_id": "synthetic", **route}),
                _FakeResponse({"job_id": "synthetic", "status": "succeeded", "output": "advisory", **route, **change}),
            ]) as http, patch("time.sleep"):
                result = ai_provider.AiServiceClient(ai_provider.AiServiceConfig.reliability(
                    primary=ai_provider.AiProviderConfig.codex_vps(), fallback=[ai_provider.AiProviderConfig.gpt()]
                )).execute("synthetic", research_stage="optimization")
            self.assertEqual(result.success, not bool(change))
            self.assertEqual(http.call_count, 3)
            self.assertEqual(json.loads(http.call_args_list[1].args[0].data)["allowed_providers"], ["codex", "cursor"])
            if not change:
                self.assertEqual(result.provider, "cursor")
            else:
                self.assertEqual(result.output, "")

    def test_codex_default_rejects_unrequested_cursor_result(self):
        with patch.object(ai_provider, "_HAS_GATEWAY_CLIENT", False), patch.dict(
            ai_provider.os.environ, {"CODEX_AUDIT_SERVICE_URL": "https://gateway.invalid"}, clear=True
        ), patch.object(ai_provider, "_fetch_oidc_token", return_value="synthetic"), patch("urllib.request.urlopen", side_effect=[
            _FakeResponse({"codex_research_routing": "v1"}), _FakeResponse({"job_id": "synthetic"}),
            _FakeResponse({"status": "succeeded", "provider": "cursor", "research_stage": "optimization",
                           "model": "synthetic-model", "reasoning_effort": "high", "output": "wrong backend"}),
        ]), patch("time.sleep"):
            result = ai_provider.AiServiceClient(ai_provider.AiServiceConfig.reliability(
                primary=ai_provider.AiProviderConfig.codex_vps()
            )).execute("synthetic", research_stage="optimization")
        self.assertFalse(result.success)
        self.assertEqual(result.output, "")

    def test_subscription_rejects_missing_admission_route_without_poll(self):
        with patch.object(ai_provider, "_HAS_GATEWAY_CLIENT", False), patch.dict(
            ai_provider.os.environ, {"CODEX_AUDIT_SERVICE_URL": "https://gateway.invalid", "AI_GATEWAY_RESEARCH_PROVIDERS": "cursor"}, clear=True
        ), patch.object(ai_provider, "_fetch_oidc_token", return_value="synthetic"), patch("urllib.request.urlopen", side_effect=[
            _FakeResponse({"subscription_research_routing": "v1"}), _FakeResponse({"job_id": "synthetic"}),
        ]) as http:
            result = ai_provider.AiServiceClient(ai_provider.AiServiceConfig.reliability(
                primary=ai_provider.AiProviderConfig.codex_vps()
            )).execute("synthetic", research_stage="summary")
        self.assertFalse(result.success)
        self.assertEqual(http.call_count, 2)

    def test_subscription_old_sdk_is_unavailable_without_api_retry(self):
        gateway = Mock()
        gateway.execute.side_effect = TypeError("private provider detail")
        with patch.object(ai_provider, "_HAS_GATEWAY_CLIENT", True), patch.object(ai_provider, "GatewayConfig", create=True), patch.object(
            ai_provider, "AiGatewayClient", return_value=gateway, create=True
        ), patch.dict(ai_provider.os.environ, {"AI_GATEWAY_RESEARCH_PROVIDERS": "codex,cursor"}, clear=True):
            result = ai_provider.AiServiceClient(ai_provider.AiServiceConfig.reliability(
                primary=ai_provider.AiProviderConfig.codex_vps(), fallback=[ai_provider.AiProviderConfig.gpt()]
            )).execute("synthetic", research_stage="optimization")
        self.assertFalse(result.success)
        self.assertNotIn("private", repr(result))
        gateway.execute.assert_called_once()
        gateway.analyze.assert_not_called()

    def test_subscription_failed_job_does_not_repeat_or_leak_error(self):
        route = {"provider": "cursor", "research_stage": "optimization", "model": "synthetic-model", "reasoning_effort": "high"}
        with patch.object(ai_provider, "_HAS_GATEWAY_CLIENT", False), patch.dict(
            ai_provider.os.environ, {"CODEX_AUDIT_SERVICE_URL": "https://gateway.invalid", "AI_GATEWAY_RESEARCH_PROVIDERS": "codex,cursor"}, clear=True
        ), patch.object(ai_provider, "_fetch_oidc_token", return_value="synthetic"), patch("urllib.request.urlopen", side_effect=[
            _FakeResponse({"subscription_research_routing": "v1"}), _FakeResponse({"job_id": "synthetic", **route}),
            _FakeResponse({"job_id": "synthetic", "status": "failed", "error": "private provider detail", **route}),
        ]) as http, patch("time.sleep"):
            result = ai_provider.AiServiceClient(ai_provider.AiServiceConfig.reliability(
                primary=ai_provider.AiProviderConfig.codex_vps(), fallback=[ai_provider.AiProviderConfig.gpt()]
            )).execute("synthetic", research_stage="optimization")
        self.assertFalse(result.success)
        self.assertEqual(result.provider, "cursor")
        self.assertEqual(http.call_count, 3)
        self.assertNotIn("private", repr(result))

    def test_research_sdk_failure_does_not_expose_provider_details(self):
        for raw in ({"private": "private provider detail"}, {"status": "deferred", "retry_at": 9000, "private": "private provider detail"}):
            gateway = Mock()
            gateway.execute.return_value = SimpleNamespace(provider="cursor", success=False, output="private provider detail",
                error="private provider detail", raw=raw)
            with self.subTest(deferred=raw.get("status")), patch.object(ai_provider, "_HAS_GATEWAY_CLIENT", True), patch.object(
                ai_provider, "GatewayConfig", create=True
            ), patch.object(ai_provider, "AiGatewayClient", return_value=gateway, create=True), patch.dict(
                ai_provider.os.environ, {"AI_GATEWAY_RESEARCH_PROVIDERS": "codex,cursor"}, clear=True
            ):
                result = ai_provider.AiServiceClient(ai_provider.AiServiceConfig.reliability(
                    primary=ai_provider.AiProviderConfig.codex_vps(), fallback=[ai_provider.AiProviderConfig.gpt()]
                )).execute("synthetic", research_stage="optimization")
            self.assertFalse(result.success)
            self.assertNotIn("private", repr(result))
            gateway.execute.assert_called_once()
            gateway.analyze.assert_not_called()
            if raw.get("status") == "deferred":
                self.assertEqual(result.raw, {"status": "deferred", "retry_at": 9000})

    def test_research_stage_preserves_sdk_deferral_without_paid_fallback(self):
        gateway = Mock()
        gateway.execute.return_value = SimpleNamespace(provider="codex", success=False, output="", error="deferred",
            raw={"status": "deferred", "retry_at": 9000})
        config = ai_provider.AiServiceConfig.reliability(primary=ai_provider.AiProviderConfig.codex_vps(),
            fallback=[ai_provider.AiProviderConfig.gpt()])
        with patch.object(ai_provider, "_HAS_GATEWAY_CLIENT", True), patch.object(ai_provider, "GatewayConfig", create=True), patch.object(
            ai_provider, "AiGatewayClient", return_value=gateway, create=True
        ):
            result = ai_provider.AiServiceClient(config).execute("synthetic", research_stage="optimization")
        self.assertEqual(result.raw["status"], "deferred")
        self.assertEqual(gateway.execute.call_args.kwargs["research_stage"], "optimization")
        gateway.execute.assert_called_once()
        gateway.analyze.assert_not_called()

    def test_research_stage_direct_http_defers_without_poll_or_fallback(self):
        error = urllib.error.HTTPError("https://gateway.invalid", 429, "deferred", {}, io.BytesIO(json.dumps({
            "status": "deferred", "retry_at": 9000, "private": "must-not-propagate",
        }).encode()))
        with patch.object(ai_provider, "_HAS_GATEWAY_CLIENT", False), patch.dict(
            ai_provider.os.environ, {"CODEX_AUDIT_SERVICE_URL": "https://gateway.invalid"}, clear=True
        ), patch.object(ai_provider, "_fetch_oidc_token", return_value="synthetic"), patch("urllib.request.urlopen", side_effect=[
            _FakeResponse({"codex_research_routing": "v1"}), error
        ]) as http:
            result = ai_provider.AiServiceClient(ai_provider.AiServiceConfig.reliability(
                primary=ai_provider.AiProviderConfig.codex_vps()
            )).execute("synthetic", research_stage="optimization")
        self.assertEqual(result.raw, {"status": "deferred", "retry_at": 9000})
        self.assertNotIn("must-not-propagate", repr(result))
        self.assertEqual(http.call_count, 2)
        self.assertEqual(json.loads(http.call_args.args[0].data)["research_stage"], "optimization")

    def test_research_direct_http_rejects_old_service_and_missing_route(self):
        for replies in (
            [_FakeResponse({"status": "ok"})],
            [_FakeResponse({"codex_research_routing": "v1"}), _FakeResponse({"job_id": "synthetic"}),
             _FakeResponse({"status": "succeeded", "output": "unverified route"})],
        ):
            with self.subTest(replies=len(replies)), patch.object(ai_provider, "_HAS_GATEWAY_CLIENT", False), patch.dict(
                ai_provider.os.environ, {"CODEX_AUDIT_SERVICE_URL": "https://gateway.invalid"}, clear=True
            ), patch.object(ai_provider, "_fetch_oidc_token", return_value="synthetic"), patch(
                "urllib.request.urlopen", side_effect=replies
            ) as http, patch("time.sleep"):
                result = ai_provider.AiServiceClient(ai_provider.AiServiceConfig.reliability(
                    primary=ai_provider.AiProviderConfig.codex_vps()
                )).execute("synthetic", research_stage="optimization")
            self.assertFalse(result.success)
            self.assertEqual(result.output, "")
            self.assertEqual(http.call_count, len(replies))
            if len(replies) == 1:
                self.assertEqual(http.call_args.args[0].get_method(), "GET")


    def test_review_without_sdk_is_unavailable_without_execute_fallback(self) -> None:
        reviewers = [ai_provider.AiProviderConfig.claude(), ai_provider.AiProviderConfig.gpt()]
        config = ai_provider.AiServiceConfig.safety(reviewers=reviewers)
        with patch.object(ai_provider, "_HAS_GATEWAY_CLIENT", False), patch.object(
            ai_provider.AiServiceClient, "_call_local",
            return_value=ai_provider.AiCallResult(provider="Codex VPS", success=True, output="approve"),
        ) as local:
            results = ai_provider.AiServiceClient(config).review("synthetic review")
        self.assertEqual([r.provider for r in results], ["Claude", "GPT"])
        self.assertTrue(all(not r.success and not r.output for r in results))
        self.assertTrue(all("ai_gateway_client" in r.note for r in results))
        local.assert_not_called()

    def test_no_sdk_rejects_non_codex_and_non_execute_before_auth_or_http(self) -> None:
        codex = ai_provider.AiProviderConfig.codex_vps()
        providers = [
            ai_provider.AiProviderConfig.claude(), ai_provider.AiProviderConfig.gpt(),
            replace(ai_provider.AiProviderConfig.gpt(), task="execute"),
            replace(codex, task="analyze"), replace(codex, task="review"),
        ]
        for provider in providers:
            for operation in ("_call_single", "verify"):
                with self.subTest(provider=provider.provider, task=provider.task, operation=operation):
                    config = ai_provider.AiServiceConfig.safety(reviewers=[], verifier=provider)
                    with patch.object(ai_provider, "_HAS_GATEWAY_CLIENT", False), patch.dict(
                        ai_provider.os.environ, {"CODEX_AUDIT_SERVICE_URL": "https://gateway.example"}, clear=True,
                    ), patch.object(ai_provider, "_fetch_oidc_token", return_value="synthetic") as auth, patch(
                        "urllib.request.urlopen", return_value=_FakeResponse({"job_id": "synthetic-job"}),
                    ) as http, patch("time.time", side_effect=[0, 1000]):
                        client = ai_provider.AiServiceClient(config)
                        result = (client.verify("synthetic", timeout=1) if operation == "verify"
                                  else client._call_single(provider, "synthetic", 1))
                    self.assertFalse(result.success)
                    self.assertEqual(result.output, "")
                    self.assertIn("ai_gateway_client", result.note)
                    auth.assert_not_called()
                    http.assert_not_called()

    def test_no_sdk_codex_execute_and_verify_preserve_endpoint_identity(self) -> None:
        provider = replace(ai_provider.AiProviderConfig.codex_vps(), label="Claude")
        for operation in ("execute", "verify"):
            with self.subTest(operation=operation):
                config = ai_provider.AiServiceConfig(
                    pattern=ai_provider.AiPattern.RELIABILITY, primary=provider, verifier=provider,
                )
                with patch.object(ai_provider, "_HAS_GATEWAY_CLIENT", False), patch.dict(
                    ai_provider.os.environ, {"CODEX_AUDIT_SERVICE_URL": "https://gateway.example"}, clear=True,
                ), patch.object(ai_provider, "_fetch_oidc_token", return_value="synthetic"), patch(
                    "urllib.request.urlopen", side_effect=[
                        _FakeResponse({"job_id": "synthetic-job"}),
                        _FakeResponse({"status": "succeeded", "output": "synthetic advisory"}),
                    ],
                ) as http, patch("time.sleep", return_value=None):
                    result = getattr(ai_provider.AiServiceClient(config), operation)("synthetic", timeout=1)
                self.assertTrue(result.success)
                self.assertEqual(result.provider, "Codex VPS")
                self.assertEqual(result.output, "synthetic advisory")
                self.assertEqual(http.call_count, 2)
                request = http.call_args_list[0].args[0]
                self.assertEqual(request.full_url, "https://gateway.example/v1/ai/execute/jobs")
                self.assertEqual(json.loads(request.data)["mode"], "review_only")
                self.assertEqual(json.loads(request.data)["task"], "execute")

    def test_sdk_analyze_keeps_actual_provider_instead_of_caller_label(self) -> None:
        provider = replace(ai_provider.AiProviderConfig.gpt(), label="Claude")
        gateway = Mock()
        gateway.analyze.return_value = SimpleNamespace(
            provider="openai", success=True, output="synthetic advisory", error="",
        )
        with patch.object(ai_provider, "_HAS_GATEWAY_CLIENT", True), patch.object(
            ai_provider, "GatewayConfig", create=True,
        ), patch.object(ai_provider, "AiGatewayClient", return_value=gateway, create=True):
            result = ai_provider.AiServiceClient(
                ai_provider.AiServiceConfig.reliability(primary=provider),
            ).execute("synthetic", timeout=1)
        self.assertEqual(result.provider, "openai")
        self.assertTrue(result.success)
        gateway.analyze.assert_called_once_with("synthetic", model=provider.model, timeout=1)
        gateway.execute.assert_not_called()

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
