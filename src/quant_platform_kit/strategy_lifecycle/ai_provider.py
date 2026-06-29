"""Unified AI Service Provider — routes all calls through AiGateway.

Architecture::

    QuantStrategyLifecycle          AiGateway (VPS, single service)
    ───────────────────             ─────────────────────────────────
    AiServiceClient                     │
      ├─ review() ── task=analyze ──────┤──▶ LlmAdapter  (Claude/GPT API)
      ├─ verify() ── task=execute ──────┤──▶ CodexAdapter (codex exec)
      └─ execute()── task=execute ──────┤──▶ CodexAdapter (codex exec)

No API keys in this repo — all AI backends accessed through AiGateway.
Only `CODEX_AUDIT_SERVICE_URL` is required.

Benefits:
  - API keys live on the VPS (one place), not in N repos
  - New backends = new adapter on the gateway, callers unchanged
  - REPAIR/SAFETY patterns unchanged, just the transport is unified
"""

from __future__ import annotations

import enum
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


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
    model: str = ""                           # sent as "model" to gateway
    task: str = "analyze"                     # analyze (API) or execute (Codex)
    can_execute_code: bool = False
    can_analyze: bool = True

    def resolve_service_url(self) -> str | None:
        return os.environ.get("CODEX_AUDIT_SERVICE_URL", "").strip() or None

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
    def __init__(self, config: AiServiceConfig):
        self.config = config

    def review(self, prompt: str, *, timeout: float = 120.0) -> list["AiCallResult"]:
        """Run all reviewers (analyze/sync)."""
        import concurrent.futures
        if not self.config.reviewers:
            return []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(self.config.reviewers), 3)) as pool:
            futures = {pool.submit(self._call, c, prompt, timeout): c for c in self.config.reviewers}
            results = []
            for f in concurrent.futures.as_completed(futures):
                try:
                    results.append(f.result())
                except Exception as exc:
                    results.append(AiCallResult.unavailable(futures[f].label, str(exc)))
        return results

    def verify(self, prompt: str, *, timeout: float = 600.0) -> "AiCallResult | None":
        if self.config.verifier is None:
            return None
        return self._call(self.config.verifier, prompt, timeout)

    def execute(self, prompt: str, *, timeout: float = 600.0) -> "AiCallResult":
        if self.config.primary is not None:
            r = self._call(self.config.primary, prompt, timeout)
            if r.success:
                return r
        for fb in self.config.fallback:
            r = self._call(fb, prompt, timeout)
            if r.success:
                return AiCallResult(provider=r.provider, success=True, output=r.output, raw=r.raw,
                                    note="Fallback after primary failed")
        return AiCallResult.unavailable("all", "All providers exhausted")

    def _call(self, provider: AiProviderConfig, prompt: str, timeout: float) -> "AiCallResult":
        """Call the AiGateway — all providers use the same endpoint."""
        service_url = provider.resolve_service_url()
        if not service_url:
            return AiCallResult.unavailable(provider.label, "CODEX_AUDIT_SERVICE_URL not configured")

        try:
            token = _fetch_oidc_token()
            base_url = service_url.rstrip("/")

            payload = json.dumps({
                "task": provider.task,
                "model": provider.model,
                "prompt": prompt,
                "timeout_seconds": int(timeout),
                "source_repository": os.environ.get("AI_GATEWAY_SOURCE_REPO", "QuantStrategyLab/QuantStrategyLifecycle"),
                "source_ref": "main",
                "mode": "review_only",
            }).encode("utf-8")

            sync = provider.task == "analyze"
            req = urllib.request.Request(
                f"{base_url}/v1/codex-audit/jobs", data=payload, method="POST",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                         "Accept": "application/json", "User-Agent": "quant-strategy-lifecycle"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            if sync:
                # Analyze returns result inline
                status = result.get("status")
                if status == "succeeded":
                    return AiCallResult(provider=provider.label, success=True,
                                        output=str(result.get("output", "")), raw=result)
                return AiCallResult(provider=provider.label, success=False,
                                    output=result.get("error", "unknown"), raw=result)

            # Execute returns async job_id → poll
            job_id = result.get("job_id")
            if not isinstance(job_id, str) or not job_id:
                return AiCallResult.unavailable(provider.label, "No job_id from gateway")

            deadline = time.time() + timeout + 60
            while time.time() < deadline:
                time.sleep(5)
                req2 = urllib.request.Request(
                    f"{base_url}/v1/codex-audit/jobs/{job_id}", method="GET",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json",
                             "User-Agent": "quant-strategy-lifecycle"},
                )
                try:
                    with urllib.request.urlopen(req2, timeout=30) as resp2:
                        job = json.loads(resp2.read().decode("utf-8"))
                except urllib.error.HTTPError:
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
    token_url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    token_bearer = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    if token_url and token_bearer:
        req = urllib.request.Request(
            f"{token_url}&audience={audience}",
            headers={"Authorization": f"Bearer {token_bearer}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return str(json.loads(resp.read().decode("utf-8")).get("value", ""))
    return os.environ.get("CODEX_AUDIT_SERVICE_TOKEN", "").strip()
