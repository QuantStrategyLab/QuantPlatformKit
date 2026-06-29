"""Unified AI Service Provider — one interface, two usage patterns.

This module abstracts the three AI backends (Codex VPS, Claude API, GPT API)
behind a single configurable provider. Systems choose their pattern by config,
not by hardcoding different codepaths.

Two built-in patterns:

  RELIABILITY  — Codex executes → if fail, Claude → if fail, GPT
                 Best for: code audit, automated fixes, tasks that MUST complete.
                 Codex is primary because it's the only AI that can run code.
                 Used by: CodexAuditBridge (already follows this pattern).

  SAFETY       — Rules → Claude → if escalate, GPT → if escalate, Codex verify
                 Multiple independent AIs must reach consensus before action.
                 Best for: parameter approval, risk decisions, deployment gates.
                 Used by: strategy_lifecycle ai_reviewer.

Each system configures which AIs to use via env vars or config dicts.
No system should hardcode provider names or API endpoints.
"""

from __future__ import annotations

import enum
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

# ── Provider definitions ─────────────────────────────────────────────


class AiProviderId(str, enum.Enum):
    CODEX_VPS = "codex_vps"
    CLAUDE = "claude"
    GPT = "gpt"


class AiPattern(str, enum.Enum):
    RELIABILITY = "reliability"   # sequential fallback — ensure completion
    SAFETY = "safety"             # adversarial consensus — ensure correctness


@dataclass(frozen=True)
class AiProviderConfig:
    """Configuration for a single AI provider backend."""

    provider: AiProviderId
    label: str

    # For API-based providers (Claude, GPT)
    api_key_env: str = ""
    model: str = ""
    base_url: str = ""

    # For Codex VPS
    service_url_env: str = "CODEX_AUDIT_SERVICE_URL"
    audience_env: str = "CODEX_AUDIT_SERVICE_AUDIENCE"
    source_repo: str = "QuantStrategyLab/UsEquitySnapshotPipelines"
    source_ref: str = "main"

    # Capabilities
    can_execute_code: bool = False   # can run commands, edit files
    can_analyze: bool = True         # can review, evaluate, reason

    def resolve_api_key(self) -> str | None:
        if not self.api_key_env:
            return None
        return os.environ.get(self.api_key_env, "").strip() or None

    def resolve_service_url(self) -> str | None:
        if self.provider != AiProviderId.CODEX_VPS:
            return None
        return os.environ.get(self.service_url_env, "").strip() or None

    @classmethod
    def claude(cls) -> "AiProviderConfig":
        return cls(
            provider=AiProviderId.CLAUDE, label="Claude",
            api_key_env="ANTHROPIC_API_KEY", model="claude-sonnet-4-6",
            can_execute_code=False, can_analyze=True,
        )

    @classmethod
    def gpt(cls) -> "AiProviderConfig":
        return cls(
            provider=AiProviderId.GPT, label="GPT",
            api_key_env="OPENAI_API_KEY", model="gpt-5.4-mini",
            can_execute_code=False, can_analyze=True,
        )

    @classmethod
    def codex_vps(cls) -> "AiProviderConfig":
        return cls(
            provider=AiProviderId.CODEX_VPS, label="Codex VPS",
            can_execute_code=True, can_analyze=True,
        )


@dataclass(frozen=True)
class AiServiceConfig:
    """Top-level configuration for the AI service layer.

    Example (reliability):
        AiServiceConfig.reliability(
            primary=AiProviderConfig.codex_vps(),
            fallback=[AiProviderConfig.claude(), AiProviderConfig.gpt()],
        )

    Example (safety):
        AiServiceConfig.safety(
            reviewers=[AiProviderConfig.claude(), AiProviderConfig.gpt()],
            verifier=AiProviderConfig.codex_vps(),
        )
    """

    pattern: AiPattern
    primary: AiProviderConfig | None = None       # reliability: the executor
    fallback: tuple[AiProviderConfig, ...] = ()    # reliability: sequential fallbacks
    reviewers: tuple[AiProviderConfig, ...] = ()    # safety: adversarial reviewers
    verifier: AiProviderConfig | None = None        # safety: execution verifier (Codex)
    require_consensus: bool = True                  # safety: all must agree

    @classmethod
    def reliability(
        cls,
        *,
        primary: AiProviderConfig,
        fallback: Sequence[AiProviderConfig] = (),
    ) -> "AiServiceConfig":
        return cls(
            pattern=AiPattern.RELIABILITY,
            primary=primary,
            fallback=tuple(fallback),
        )

    @classmethod
    def safety(
        cls,
        *,
        reviewers: Sequence[AiProviderConfig],
        verifier: AiProviderConfig | None = None,
        require_consensus: bool = True,
    ) -> "AiServiceConfig":
        return cls(
            pattern=AiPattern.SAFETY,
            reviewers=tuple(reviewers),
            verifier=verifier,
            require_consensus=require_consensus,
        )

    @classmethod
    def from_env(cls) -> "AiServiceConfig":
        """Auto-detect the best available config from environment variables."""
        has_codex = bool(os.environ.get("CODEX_AUDIT_SERVICE_URL", "").strip())
        has_claude = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
        has_gpt = bool(os.environ.get("OPENAI_API_KEY", "").strip())

        reviewers: list[AiProviderConfig] = []
        if has_claude:
            reviewers.append(AiProviderConfig.claude())
        if has_gpt:
            reviewers.append(AiProviderConfig.gpt())

        verifier = AiProviderConfig.codex_vps() if has_codex else None

        if reviewers and verifier:
            return cls.safety(reviewers=reviewers, verifier=verifier)
        if reviewers:
            return cls.safety(reviewers=reviewers)
        if has_codex:
            return cls.reliability(primary=AiProviderConfig.codex_vps())

        # Nothing available → rule-based only
        return cls.safety(reviewers=[])


# ── AI Service Client ────────────────────────────────────────────────


class AiServiceClient:
    """Unified client for calling AI providers.

    Usage::

        config = AiServiceConfig.from_env()
        client = AiServiceClient(config)

        # Safety pattern: ask all reviewers
        prompt = "Is this proposal safe to deploy?"
        for verdict in client.review(prompt):
            print(f"{verdict.provider}: {verdict.decision}")

        # Reliability pattern: execute with fallback
        result = client.execute("Run the backtest and report results")
    """

    def __init__(self, config: AiServiceConfig):
        self.config = config

    # ── Safety pattern methods ───────────────────────────────────

    def review(self, prompt: str, *, timeout: float = 45.0) -> list["AiCallResult"]:
        """Run all configured reviewers in parallel and return their verdicts."""
        import concurrent.futures

        results: list[AiCallResult] = []
        if not self.config.reviewers:
            return results

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(self.config.reviewers), 3)) as pool:
            futures = {
                pool.submit(self._call_provider, provider, prompt, timeout): provider
                for provider in self.config.reviewers
            }
            for future in concurrent.futures.as_completed(futures):
                provider = futures[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    results.append(AiCallResult.unavailable(provider.label, str(exc)))
        return results

    def verify(self, prompt: str, *, timeout: float = 600.0) -> "AiCallResult | None":
        """Run the verifier (typically Codex VPS) to execute and validate."""
        if self.config.verifier is None:
            return None
        return self._call_provider(self.config.verifier, prompt, timeout)

    # ── Reliability pattern methods ──────────────────────────────

    def execute(self, prompt: str, *, timeout: float = 600.0) -> "AiCallResult":
        """Execute with primary → fallback chain. Always returns a result."""
        # Try primary
        if self.config.primary is not None:
            result = self._call_provider(self.config.primary, prompt, timeout)
            if result.success:
                return result

        # Sequential fallback
        for provider in self.config.fallback:
            result = self._call_provider(provider, prompt, timeout)
            if result.success:
                return AiCallResult(
                    provider=result.provider, success=True,
                    output=result.output, raw=result.raw,
                    note=f"Fallback after primary failed",
                )

        return AiCallResult.unavailable("all", "All providers exhausted")

    # ── Core call logic ──────────────────────────────────────────

    def _call_provider(
        self, provider: AiProviderConfig, prompt: str, timeout: float
    ) -> "AiCallResult":
        """Route to the correct backend based on provider type."""
        if provider.provider == AiProviderId.CODEX_VPS:
            return self._call_codex_vps(provider, prompt, timeout)
        return self._call_llm_api(provider, prompt, timeout)

    def _call_codex_vps(
        self, provider: AiProviderConfig, prompt: str, timeout: float
    ) -> "AiCallResult":
        """Call Codex VPS via the async job API (same as CodexAuditBridge)."""
        service_url = provider.resolve_service_url()
        if not service_url:
            return AiCallResult.unavailable(provider.label, "Service URL not configured")

        try:
            token = _fetch_oidc_token(os.environ.get(provider.audience_env, "quant-codex-audit"))
            service_url = service_url.rstrip("/")
            audience = os.environ.get(provider.audience_env, "quant-codex-audit")

            payload = json.dumps({
                "source_repository": provider.source_repo,
                "source_ref": provider.source_ref,
                "task": "strategy_proposal_verify",
                "mode": "review_only",
                "prompt": prompt,
                "timeout_seconds": int(timeout),
            }).encode("utf-8")

            # Submit
            req = urllib.request.Request(
                f"{service_url}/v1/codex-audit/jobs", data=payload, method="POST",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                         "Accept": "application/json", "User-Agent": "ai-provider-codex"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                submit = json.loads(resp.read().decode("utf-8"))
            job_id = submit.get("job_id")
            if not isinstance(job_id, str) or not job_id:
                return AiCallResult.unavailable(provider.label, "No job_id returned")

            # Poll
            deadline = time.time() + timeout + 60
            while time.time() < deadline:
                time.sleep(5)
                req2 = urllib.request.Request(
                    f"{service_url}/v1/codex-audit/jobs/{job_id}", method="GET",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json",
                             "User-Agent": "ai-provider-codex"},
                )
                try:
                    with urllib.request.urlopen(req2, timeout=30) as resp2:
                        job = json.loads(resp2.read().decode("utf-8"))
                except urllib.error.HTTPError:
                    continue

                status = job.get("status")
                if status == "succeeded":
                    output = str(job.get("output", ""))
                    return AiCallResult(provider=provider.label, success=True, output=output, raw=job)
                elif status == "failed":
                    return AiCallResult(provider=provider.label, success=False,
                                        output=job.get("error", "unknown"), raw=job)
            return AiCallResult.unavailable(provider.label, "Timeout")
        except Exception as exc:
            return AiCallResult.unavailable(provider.label, str(exc))

    def _call_llm_api(
        self, provider: AiProviderConfig, prompt: str, timeout: float
    ) -> "AiCallResult":
        """Call Claude or GPT via QuantStrategyPlugins ai_audit.py."""
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
            messages = [{"role": "user", "content": prompt}]
            raw = call_ai_audit(endpoint, messages, timeout=timeout)

            output = raw if isinstance(raw, str) else json.dumps(raw)
            return AiCallResult(provider=provider.label, success=True, output=output, raw=raw)
        except ImportError:
            return AiCallResult.unavailable(provider.label, "quant_strategy_plugins not installed")
        except Exception as exc:
            return AiCallResult.unavailable(provider.label, str(exc))


# ── Result type ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class AiCallResult:
    """Result from a single AI provider call."""

    provider: str
    success: bool
    output: str = ""
    raw: Any = None
    note: str = ""

    @classmethod
    def unavailable(cls, provider: str, reason: str) -> "AiCallResult":
        return cls(provider=provider, success=False, output="", note=reason)


# ── OIDC token helper ────────────────────────────────────────────────


def _fetch_oidc_token(audience: str) -> str:
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
