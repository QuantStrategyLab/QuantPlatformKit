"""Unified AI Service Provider — thin wrapper around AiGateway client.

Architecture::

    QuantPlatformKit lifecycle      AiGateway (VPS, single service)
    ───────────────────             ─────────────────────────────────
    AiServiceClient                     │
      ├─ review() ──────────────────────┤──▶ POST /v1/ai/review (multi-model)
      ├─ verify() ──────────────────────┤──▶ POST /v1/ai/execute/jobs (async)
      └─ execute()──────────────────────┤──▶ POST /v1/ai/execute/jobs (async)

No API keys in this repo — all AI backends accessed through AiGateway.
Only ``CODEX_AUDIT_SERVICE_URL`` is required.

This module is a backward-compatible wrapper. New code should use
``ai_gateway_client.AiGatewayClient`` directly when available.
"""

from __future__ import annotations

import enum
import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

# Try to import the unified client; fall back to local implementation
try:
    from ai_gateway_client import AiGatewayClient, GatewayConfig, AiResult
    _HAS_GATEWAY_CLIENT = True
except ImportError:
    _HAS_GATEWAY_CLIENT = False


class AiProviderId(str, enum.Enum):
    CODEX_VPS = "codex_vps"
    CLAUDE = "claude"
    GPT = "gpt"


class AiPattern(str, enum.Enum):
    RELIABILITY = "reliability"
    SAFETY = "safety"


@dataclass(frozen=True)
class AiProviderConfig:
    provider: AiProviderId
    label: str
    model: str = ""
    task: str = "analyze"                     # analyze (API) or execute (Codex)
    can_execute_code: bool = False
    can_analyze: bool = True

    @classmethod
    def claude(cls) -> "AiProviderConfig":
        return cls(provider=AiProviderId.CLAUDE, label="Claude",
                   model="claude-sonnet-4-6", task="analyze",
                   can_execute_code=False, can_analyze=True)

    @classmethod
    def gpt(cls) -> "AiProviderConfig":
        return cls(provider=AiProviderId.GPT, label="GPT",
                   model="gpt-5.4-mini", task="analyze",
                   can_execute_code=False, can_analyze=True)

    @classmethod
    def codex_vps(cls) -> "AiProviderConfig":
        return cls(provider=AiProviderId.CODEX_VPS, label="Codex VPS",
                   task="execute",
                   can_execute_code=True, can_analyze=True)


@dataclass(frozen=True)
class AiServiceConfig:
    pattern: AiPattern
    primary: AiProviderConfig | None = None
    fallback: tuple[AiProviderConfig, ...] = ()
    reviewers: tuple[AiProviderConfig, ...] = ()
    verifier: AiProviderConfig | None = None

    @classmethod
    def reliability(cls, *, primary: AiProviderConfig, fallback: Sequence[AiProviderConfig] = ()) -> "AiServiceConfig":
        return cls(pattern=AiPattern.RELIABILITY, primary=primary, fallback=tuple(fallback))

    @classmethod
    def safety(cls, *, reviewers: Sequence[AiProviderConfig], verifier: AiProviderConfig | None = None) -> "AiServiceConfig":
        return cls(pattern=AiPattern.SAFETY, reviewers=tuple(reviewers), verifier=verifier)

    @classmethod
    def from_env(cls) -> "AiServiceConfig":
        """Auto-detect from CODEX_AUDIT_SERVICE_URL (no API keys needed)."""
        has_service = bool(os.environ.get("CODEX_AUDIT_SERVICE_URL", "").strip())
        if not has_service:
            return cls.safety(reviewers=[])
        return cls.safety(
            reviewers=[AiProviderConfig.claude(), AiProviderConfig.gpt()],
            verifier=AiProviderConfig.codex_vps(),
        )


# ── Client ───────────────────────────────────────────────────────────


class AiServiceClient:
    """Backward-compatible wrapper around AiGatewayClient.

    New code should use ``AiGatewayClient`` directly. This class exists
    to keep existing ``codex_integration.py`` and ``ai_reviewer.py`` working
    without changes.
    """

    def __init__(self, config: AiServiceConfig):
        self.config = config
        if _HAS_GATEWAY_CLIENT:
            gw_config = GatewayConfig.from_env()
        else:
            gw_config = None
        self._gw_config = gw_config

    def review(self, prompt: str, *, timeout: float = 120.0) -> list["AiCallResult"]:
        """Run all reviewers concurrently via AiGateway."""
        if not self.config.reviewers:
            return []

        if _HAS_GATEWAY_CLIENT and self._gw_config:
            client = AiGatewayClient(self._gw_config)
            reviewers_list = [
                self._map_provider_label(c)
                for c in self.config.reviewers
            ]
            result = client.review(
                prompt,
                reviewers=reviewers_list,
                verifier="codex" if self.config.verifier else None,
                timeout=timeout,
            )
            return [
                AiCallResult(
                    provider=r.provider, success=r.success,
                    output=r.output, note=r.error if not r.success else "",
                )
                for r in result.results
            ]

        # A Codex execution job cannot replace independent API reviewers.
        return self._review_local(prompt, timeout)

    def verify(self, prompt: str, *, timeout: float = 600.0) -> "AiCallResult | None":
        if self.config.verifier is None:
            return None

        if _HAS_GATEWAY_CLIENT and self._gw_config:
            client = AiGatewayClient(self._gw_config)
            r = client.execute(prompt, mode="review_only", timeout=timeout)
            return AiCallResult(provider=r.provider, success=r.success, output=r.output, note=r.error)

        return self._call_local(self.config.verifier, prompt, timeout)

    def execute(self, prompt: str, *, timeout: float = 600.0, research_stage: str = "") -> "AiCallResult":
        if research_stage:
            primary = self.config.primary
            if primary is None or primary.provider != AiProviderId.CODEX_VPS or primary.task != "execute":
                return AiCallResult.unavailable("codex", "research_requires_codex")
            # A research request never consumes the reliability API fallback.
            return self._call_single(primary, prompt, timeout, research_stage=research_stage)
        if self.config.primary is not None:
            r = self._call_single(self.config.primary, prompt, timeout)
            if r.success:
                return r
        for fb in self.config.fallback:
            r = self._call_single(fb, prompt, timeout)
            if r.success:
                return AiCallResult(provider=r.provider, success=True, output=r.output,
                                    note="Fallback after primary failed")
        return AiCallResult.unavailable("all", "All providers exhausted")

    def _call_single(self, provider: AiProviderConfig, prompt: str, timeout: float, *, research_stage: str = "") -> "AiCallResult":
        if _HAS_GATEWAY_CLIENT and self._gw_config:
            client = AiGatewayClient(self._gw_config)
            if provider.task == "analyze":
                r = client.analyze(prompt, model=provider.model, timeout=timeout)
            else:
                r = client.execute(prompt, mode="review_only", timeout=timeout,
                    **({"research_stage": research_stage, "model": provider.model or None} if research_stage else {}))
            return AiCallResult(provider=r.provider, success=r.success, output=r.output, note=r.error, raw=getattr(r, "raw", None))
        return self._call_local(provider, prompt, timeout, **({"research_stage": research_stage} if research_stage else {}))

    def _review_local(self, prompt: str, timeout: float) -> list["AiCallResult"]:
        """Report unavailable reviewers when the gateway client is not installed."""
        return [
            AiCallResult.unavailable(c.label, "ai_gateway_client required for review")
            for c in self.config.reviewers
        ]

    def _call_local(self, provider: AiProviderConfig, prompt: str, timeout: float, *, research_stage: str = "") -> "AiCallResult":
        """Direct Codex execution only when the gateway client is not installed."""
        if provider.provider != AiProviderId.CODEX_VPS or provider.task != "execute":
            return AiCallResult.unavailable(provider.label, "ai_gateway_client required for this provider/task")

        import json as _json
        import urllib.error as _urllib_err
        import urllib.request as _urllib_req
        import time as _time
        import math as _math

        service_url = os.environ.get("CODEX_AUDIT_SERVICE_URL", "").strip()
        if not service_url:
            return AiCallResult.unavailable(provider.label, "CODEX_AUDIT_SERVICE_URL not configured")

        try:
            token = _fetch_oidc_token()
            base_url = service_url.rstrip("/")
            if research_stage:
                health = _urllib_req.Request(f"{base_url}/healthz", headers={"Authorization": f"Bearer {token}"})
                with _urllib_req.urlopen(health, timeout=10) as response:
                    capabilities = _json.loads(response.read().decode("utf-8"))
                if not isinstance(capabilities, dict) or capabilities.get("codex_research_routing") != "v1":
                    return AiCallResult.unavailable("codex", "codex_research_routing_unavailable")

            payload = _json.dumps({
                "task": provider.task,
                "model": provider.model,
                "prompt": prompt,
                "timeout_seconds": int(timeout),
                "source_repository": os.environ.get("AI_GATEWAY_SOURCE_REPO", "QuantStrategyLab/QuantPlatformKit"),
                "source_ref": "main",
                "mode": "review_only",
                **({"research_stage": research_stage} if research_stage else {}),
            }).encode("utf-8")

            req = _urllib_req.Request(
                f"{base_url}/v1/ai/execute/jobs", data=payload, method="POST",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                         "Accept": "application/json", "User-Agent": "quant-platform-kit-lifecycle"},
            )
            with _urllib_req.urlopen(req, timeout=30) as resp:
                result = _json.loads(resp.read().decode("utf-8"))

            # async job → poll
            job_id = result.get("job_id")
            if not isinstance(job_id, str) or not job_id:
                return AiCallResult.unavailable(provider.label, "No job_id from gateway")

            deadline = _time.time() + timeout + 60
            while _time.time() < deadline:
                _time.sleep(5)
                req2 = _urllib_req.Request(
                    f"{base_url}/v1/ai/execute/jobs/{job_id}", method="GET",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json",
                             "User-Agent": "quant-platform-kit-lifecycle"},
                )
                try:
                    with _urllib_req.urlopen(req2, timeout=30) as resp2:
                        job = _json.loads(resp2.read().decode("utf-8"))
                except _urllib_err.HTTPError:
                    continue
                status = job.get("status")
                if status == "succeeded":
                    if research_stage and (
                        job.get("research_stage") != research_stage
                        or not isinstance(job.get("model"), str) or not job["model"].strip()
                        or job.get("reasoning_effort") not in {"low", "medium", "high", "xhigh"}
                        or (provider.model not in ("", "auto") and job["model"] != provider.model)
                    ):
                        return AiCallResult.unavailable("codex", "codex_research_route_mismatch")
                    return AiCallResult(provider="Codex VPS", success=True,
                                        output=str(job.get("output", "")), raw=job)
                if status == "failed":
                    return AiCallResult(provider="Codex VPS", success=False,
                                        output=job.get("error", "unknown"), raw=job)
            return AiCallResult.unavailable(provider.label, "Timeout")
        except _urllib_err.HTTPError as exc:
            if research_stage and exc.code == 429:
                try:
                    data = _json.loads(exc.read(4096))
                except (ValueError, OSError):
                    data = None
                if isinstance(data, dict) and data.get("status") == "deferred":
                    retry = data.get("retry_at")
                    if type(retry) not in (int, float) or not _math.isfinite(retry) or retry <= 0:
                        retry = None
                    return AiCallResult(provider="codex", success=False, note="codex_research_deferred",
                        raw={"status": "deferred", "retry_at": retry})
            return AiCallResult.unavailable(provider.label, "codex_unavailable")
        except Exception as exc:
            return AiCallResult.unavailable(provider.label, str(exc))

    @staticmethod
    def _map_provider_label(config: AiProviderConfig) -> str:
        if config.provider == AiProviderId.CLAUDE:
            return "claude"
        if config.provider == AiProviderId.GPT:
            return "gpt"
        return "codex"


@dataclass(frozen=True)
class AiCallResult:
    provider: str
    success: bool
    output: str = ""
    raw: Any = None
    note: str = ""

    @classmethod
    def unavailable(cls, provider: str, reason: str) -> "AiCallResult":
        return cls(provider=provider, success=False, output="", note=reason)


def _fetch_oidc_token(audience: str = "quant-codex-audit") -> str:
    import json as _json
    import urllib.request as _urllib_req

    token_url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    token_bearer = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    if token_url and token_bearer:
        separator = "&" if "?" in token_url else "?"
        url = f"{token_url}{separator}audience={_urllib_req.quote(audience, safe='')}"
        req = _urllib_req.Request(url, headers={"Authorization": f"Bearer {token_bearer}"})
        with _urllib_req.urlopen(req, timeout=10) as resp:
            return str(_json.loads(resp.read().decode("utf-8")).get("value", ""))
    return os.environ.get("CODEX_AUDIT_SERVICE_TOKEN", "").strip()
