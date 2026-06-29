"""Unified AI Service Provider — thin wrapper around AiGateway client.

Architecture::

    QuantStrategyLifecycle          AiGateway (VPS, single service)
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

        # Fallback: local implementation (no gateway client available)
        return self._review_local(prompt, timeout)

    def verify(self, prompt: str, *, timeout: float = 600.0) -> "AiCallResult | None":
        if self.config.verifier is None:
            return None

        if _HAS_GATEWAY_CLIENT and self._gw_config:
            client = AiGatewayClient(self._gw_config)
            r = client.execute(prompt, mode="review_only", timeout=timeout)
            return AiCallResult(provider=r.provider, success=r.success, output=r.output, note=r.error)

        return self._call_local(self.config.verifier, prompt, timeout)

    def execute(self, prompt: str, *, timeout: float = 600.0) -> "AiCallResult":
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

    def _call_single(self, provider: AiProviderConfig, prompt: str, timeout: float) -> "AiCallResult":
        if _HAS_GATEWAY_CLIENT and self._gw_config:
            client = AiGatewayClient(self._gw_config)
            if provider.task == "analyze":
                r = client.analyze(prompt, model=provider.model, timeout=timeout)
            else:
                r = client.execute(prompt, mode="review_only", timeout=timeout)
            return AiCallResult(provider=r.provider, success=r.success, output=r.output, note=r.error)
        return self._call_local(provider, prompt, timeout)

    def _review_local(self, prompt: str, timeout: float) -> list["AiCallResult"]:
        """Local fallback when gateway client is not installed."""
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(self.config.reviewers), 3)) as pool:
            futures = {pool.submit(self._call_local, c, prompt, timeout): c for c in self.config.reviewers}
            results = []
            for f in concurrent.futures.as_completed(futures):
                try:
                    results.append(f.result())
                except Exception as exc:
                    results.append(AiCallResult.unavailable(futures[f].label, str(exc)))
        return results

    def _call_local(self, provider: AiProviderConfig, prompt: str, timeout: float) -> "AiCallResult":
        """Direct HTTP call to AiGateway — used when client library not installed."""
        import json as _json
        import urllib.error as _urllib_err
        import urllib.request as _urllib_req
        import time as _time

        service_url = os.environ.get("CODEX_AUDIT_SERVICE_URL", "").strip()
        if not service_url:
            return AiCallResult.unavailable(provider.label, "CODEX_AUDIT_SERVICE_URL not configured")

        try:
            token = _fetch_oidc_token()
            base_url = service_url.rstrip("/")

            payload = _json.dumps({
                "task": provider.task,
                "model": provider.model,
                "prompt": prompt,
                "timeout_seconds": int(timeout),
                "source_repository": os.environ.get("AI_GATEWAY_SOURCE_REPO", "QuantStrategyLab/QuantStrategyLifecycle"),
                "source_ref": "main",
                "mode": "review_only",
            }).encode("utf-8")

            req = _urllib_req.Request(
                f"{base_url}/v1/ai/execute/jobs", data=payload, method="POST",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                         "Accept": "application/json", "User-Agent": "quant-strategy-lifecycle"},
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
                             "User-Agent": "quant-strategy-lifecycle"},
                )
                try:
                    with _urllib_req.urlopen(req2, timeout=30) as resp2:
                        job = _json.loads(resp2.read().decode("utf-8"))
                except _urllib_err.HTTPError:
                    continue
                status = job.get("status")
                if status == "succeeded":
                    return AiCallResult(provider=provider.label, success=True,
                                        output=str(job.get("output", "")), raw=job)
                if status == "failed":
                    return AiCallResult(provider=provider.label, success=False,
                                        output=job.get("error", "unknown"), raw=job)
            return AiCallResult.unavailable(provider.label, "Timeout")
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
