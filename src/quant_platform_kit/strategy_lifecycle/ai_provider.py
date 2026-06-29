"""Unified AI Service Provider — two backend paths.

Architecture:
  API calls (Claude/GPT) → direct API call (needs API_KEY secret)
  Codex VPS calls        → CodexAuditBridge service (needs CODEX_AUDIT_SERVICE_URL)

The two paths exist because the VPS only runs Codex CLI. Claude/GPT are called
directly from the GitHub Actions workflow using repo/org-level secrets.

Two built-in patterns:

  RELIABILITY  — Codex VPS primary → Claude fallback → GPT fallback
                 Used by: CodexAuditBridge (code audit, must complete).

  SAFETY       — Rules → Claude → GPT → Codex VPS verify → consensus
                 Used by: strategy_lifecycle (parameter approval, must be correct).
"""

from __future__ import annotations

import enum
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
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

    # For API-based providers (Claude, GPT)
    api_key_env: str = ""
    model: str = ""
    base_url: str = ""

    # For Codex VPS
    service_url_env: str = "CODEX_AUDIT_SERVICE_URL"
    audience_env: str = "CODEX_AUDIT_SERVICE_AUDIENCE"
    source_repo: str = "QuantStrategyLab/QuantStrategyLifecycle"
    source_ref: str = "main"

    can_execute_code: bool = False
    can_analyze: bool = True

    def resolve_api_key(self) -> str | None:
        if not self.api_key_env:
            return None
        return os.environ.get(self.api_key_env, "").strip() or None

    def resolve_service_url(self) -> str | None:
        return os.environ.get(self.service_url_env, "").strip() or None

    @classmethod
    def claude(cls) -> "AiProviderConfig":
        return cls(provider=AiProviderId.CLAUDE, label="Claude",
                   api_key_env="ANTHROPIC_API_KEY", model="claude-sonnet-4-6",
                   can_execute_code=False, can_analyze=True)

    @classmethod
    def gpt(cls) -> "AiProviderConfig":
        return cls(provider=AiProviderId.GPT, label="GPT",
                   api_key_env="OPENAI_API_KEY", model="gpt-5.4-mini",
                   can_execute_code=False, can_analyze=True)

    @classmethod
    def codex_vps(cls) -> "AiProviderConfig":
        return cls(provider=AiProviderId.CODEX_VPS, label="Codex VPS",
                   can_execute_code=True, can_analyze=True)


@dataclass(frozen=True)
class AiServiceConfig:
    pattern: AiPattern
    primary: AiProviderConfig | None = None
    fallback: tuple[AiProviderConfig, ...] = ()
    reviewers: tuple[AiProviderConfig, ...] = ()
    verifier: AiProviderConfig | None = None
    require_consensus: bool = True

    @classmethod
    def reliability(cls, *, primary: AiProviderConfig, fallback: Sequence[AiProviderConfig] = ()) -> "AiServiceConfig":
        return cls(pattern=AiPattern.RELIABILITY, primary=primary, fallback=tuple(fallback))

    @classmethod
    def safety(cls, *, reviewers: Sequence[AiProviderConfig], verifier: AiProviderConfig | None = None,
               require_consensus: bool = True) -> "AiServiceConfig":
        return cls(pattern=AiPattern.SAFETY, reviewers=tuple(reviewers), verifier=verifier)

    @classmethod
    def from_env(cls) -> "AiServiceConfig":
        """Auto-detect available backends from env vars."""
        has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
        has_gpt = bool(os.environ.get("OPENAI_API_KEY", "").strip())
        has_codex = bool(os.environ.get("CODEX_AUDIT_SERVICE_URL", "").strip())

        reviewers: list[AiProviderConfig] = []
        if has_api_key:
            reviewers.append(AiProviderConfig.claude())
        if has_gpt:
            reviewers.append(AiProviderConfig.gpt())

        verifier = AiProviderConfig.codex_vps() if has_codex else None

        if reviewers:
            return cls.safety(reviewers=reviewers, verifier=verifier)
        if has_codex:
            return cls.reliability(primary=AiProviderConfig.codex_vps())
        return cls.safety(reviewers=[])


# ── AI Service Client ────────────────────────────────────────────────


class AiServiceClient:
    def __init__(self, config: AiServiceConfig):
        self.config = config

    def review(self, prompt: str, *, timeout: float = 45.0) -> list["AiCallResult"]:
        import concurrent.futures
        if not self.config.reviewers:
            return []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(self.config.reviewers), 3)) as pool:
            futures = {pool.submit(self._call_provider, c, prompt, timeout): c for c in self.config.reviewers}
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
        return self._call_provider(self.config.verifier, prompt, timeout)

    def execute(self, prompt: str, *, timeout: float = 600.0) -> "AiCallResult":
        if self.config.primary is not None:
            r = self._call_provider(self.config.primary, prompt, timeout)
            if r.success:
                return r
        for fb in self.config.fallback:
            r = self._call_provider(fb, prompt, timeout)
            if r.success:
                return AiCallResult(provider=r.provider, success=True, output=r.output, raw=r.raw,
                                    note=f"Fallback after primary failed")
        return AiCallResult.unavailable("all", "All providers exhausted")

    # ── Core call routing ────────────────────────────────────────

    def _call_provider(self, provider: AiProviderConfig, prompt: str, timeout: float) -> "AiCallResult":
        if provider.provider == AiProviderId.CODEX_VPS:
            return self._call_codex_vps(provider, prompt, timeout)
        return self._call_llm_api(provider, prompt, timeout)

    def _call_llm_api(self, provider: AiProviderConfig, prompt: str, timeout: float) -> "AiCallResult":
        """Call Claude or GPT directly via API (uses repo secret)."""
        api_key = provider.resolve_api_key()
        if not api_key:
            return AiCallResult.unavailable(provider.label, "API key not configured")

        try:
            from quant_strategy_plugins.ai_audit import AiAuditEndpoint, call_ai_audit

            endpoint = AiAuditEndpoint(
                name=f"ai_provider_{provider.provider.value}",
                api_key=api_key,
                provider="anthropic" if provider.provider == AiProviderId.CLAUDE else "openai",
                model=provider.model,
                base_url=provider.base_url or (
                    "https://api.anthropic.com/v1" if provider.provider == AiProviderId.CLAUDE else "https://api.openai.com/v1"
                ),
            )
            raw = call_ai_audit(endpoint, [{"role": "user", "content": prompt}], timeout=timeout)
            output = raw if isinstance(raw, str) else json.dumps(raw)
            return AiCallResult(provider=provider.label, success=True, output=output, raw=raw)
        except ImportError:
            return AiCallResult.unavailable(provider.label, "quant_strategy_plugins not installed")
        except Exception as exc:
            return AiCallResult.unavailable(provider.label, str(exc))

    def _call_codex_vps(self, provider: AiProviderConfig, prompt: str, timeout: float) -> "AiCallResult":
        """Call Codex VPS via the async job API."""
        service_url = provider.resolve_service_url()
        if not service_url:
            return AiCallResult.unavailable(provider.label, "CODEX_AUDIT_SERVICE_URL not configured")

        try:
            token = _fetch_oidc_token()
            audience = os.environ.get(provider.audience_env, "quant-codex-audit")
            base_url = service_url.rstrip("/")

            payload = json.dumps({
                "source_repository": provider.source_repo,
                "source_ref": provider.source_ref,
                "task": "strategy_review",
                "mode": "review_only",
                "prompt": prompt,
                "timeout_seconds": int(timeout),
                "model": "",  # service default model
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{base_url}/v1/codex-audit/jobs", data=payload, method="POST",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                         "Accept": "application/json", "User-Agent": "strategy-lifecycle"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                submit = json.loads(resp.read().decode("utf-8"))
            job_id = submit.get("job_id")
            if not isinstance(job_id, str) or not job_id:
                return AiCallResult.unavailable(provider.label, "No job_id")

            deadline = time.time() + timeout + 60
            while time.time() < deadline:
                time.sleep(5)
                req2 = urllib.request.Request(
                    f"{base_url}/v1/codex-audit/jobs/{job_id}", method="GET",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json",
                             "User-Agent": "strategy-lifecycle"},
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
                elif status == "failed":
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
        req = urllib.request.Request(f"{token_url}&audience={audience}",
            headers={"Authorization": f"Bearer {token_bearer}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return str(json.loads(resp.read().decode("utf-8")).get("value", ""))
    return os.environ.get("CODEX_AUDIT_SERVICE_TOKEN", "").strip()
