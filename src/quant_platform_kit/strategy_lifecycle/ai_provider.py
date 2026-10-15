"""Caller-owned lifecycle AI routes over the project-scoped V2 task service.

Route labels describe review roles, not independently verified model identities.
No CLI, provider chain, paid fallback or legacy service endpoint is used here.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AiProviderConfig:
    label: str
    mode: str
    model: str
    profile: str = "default"

    def __post_init__(self):
        if self.mode not in {"api", "agent"} or any(
            not isinstance(value, str) or not value.strip()
            for value in (self.label, self.model, self.profile)
        ):
            raise ValueError("invalid AI task route")

    @classmethod
    def from_env(cls, *, label: str = "primary") -> "AiProviderConfig":
        return cls(label=label, mode=os.environ.get("AI_SERVICE_MODE", "agent"),
                   model=os.environ.get("AI_SERVICE_MODEL", ""),
                   profile=os.environ.get("AI_SERVICE_PROFILE", "default"))


@dataclass(frozen=True)
class AiServiceConfig:
    primary: AiProviderConfig | None = None
    reviewers: tuple[AiProviderConfig, ...] = ()
    verifier: AiProviderConfig | None = None

    @classmethod
    def reliability(cls, *, primary: AiProviderConfig) -> "AiServiceConfig":
        return cls(primary=primary)

    @classmethod
    def safety(cls, *, reviewers: Sequence[AiProviderConfig],
               verifier: AiProviderConfig | None = None) -> "AiServiceConfig":
        reviewers = tuple(reviewers)
        if len({r.label for r in reviewers}) != len(reviewers):
            raise ValueError("review roles must be unique")
        if len({(r.mode, r.profile) for r in reviewers}) != len(reviewers):
            raise ValueError("reviewers must use distinct configured routes")
        return cls(reviewers=reviewers, verifier=verifier)

    @classmethod
    def from_env(cls) -> "AiServiceConfig":
        if not os.environ.get("AI_SERVICE_URL", "").strip():
            return cls.safety(reviewers=[])
        routes = json.loads(os.environ.get("AI_SERVICE_REVIEWERS_JSON", "[]"))
        if not isinstance(routes, list):
            raise ValueError("review routes must be a list")
        verifier = json.loads(os.environ.get("AI_SERVICE_VERIFIER_JSON", "null"))
        return cls.safety(reviewers=[AiProviderConfig(**r) for r in routes],
                          verifier=AiProviderConfig(**verifier) if verifier is not None else None)


@dataclass(frozen=True)
class AiCallResult:
    provider: str
    success: bool
    output: str = ""
    raw: Any = None
    note: str = ""
    label: str = ""

    @classmethod
    def unavailable(cls, label: str, reason: str) -> "AiCallResult":
        return cls(provider="", success=False, note=reason, label=label)


REPORT_SCHEMA = {
    "type": "object", "properties": {"report": {"type": "string", "minLength": 1, "maxLength": 60000}},
    "required": ["report"], "additionalProperties": False,
}


class AiServiceClient:
    def __init__(self, config: AiServiceConfig, *, task_client=None):
        self.config = config
        self._task_client = task_client

    def _client(self):
        if self._task_client is None:
            from ai_service.client import client_from_env
            self._task_client = client_from_env()
        return self._task_client

    def review(self, prompt: str, *, timeout: float = 120.0,
               idempotency_key: str | None = None) -> list[AiCallResult]:
        return [self._call_single(route, prompt, timeout, idempotency_key=idempotency_key)
                for route in self.config.reviewers]

    def verify(self, prompt: str, *, timeout: float = 600.0,
               idempotency_key: str | None = None) -> AiCallResult | None:
        if self.config.verifier is None:
            return None
        return self._call_single(self.config.verifier, prompt, timeout, idempotency_key=idempotency_key)

    def execute(self, prompt: str, *, timeout: float = 600.0,
                idempotency_key: str | None = None, resume_task_id: str | None = None) -> AiCallResult:
        if self.config.primary is None:
            return AiCallResult.unavailable("primary", "ai_route_unconfigured")
        return self._call_single(self.config.primary, prompt, timeout, idempotency_key=idempotency_key,
                                 resume_task_id=resume_task_id)

    def _call_single(self, route: AiProviderConfig, prompt: str, timeout: float, *,
                     idempotency_key: str | None, resume_task_id: str | None = None) -> AiCallResult:
        task_id = resume_task_id
        try:
            if (not isinstance(prompt, str) or not prompt.strip() or isinstance(timeout, bool)
                    or not isinstance(timeout, (int, float)) or not math.isfinite(timeout)
                    or timeout < 1 or timeout > 3600):
                raise ValueError("invalid task limits")
            scope = idempotency_key or os.environ.get("GITHUB_RUN_ID", "")
            if not isinstance(scope, str) or not scope.strip():
                raise ValueError("a caller-owned operation identity is required")
            request = {
                "mode": route.mode, "profile": route.profile, "model": route.model,
                "objective": ("Return an object with one report string containing your answer to the following "
                              "caller-owned task. Preserve any requested JSON format inside that string.\n" + prompt),
                "materials": [], "output_schema": REPORT_SCHEMA, "timeout_seconds": math.ceil(timeout),
            }
            encoded = json.dumps({"role": route.label, "request": request}, sort_keys=True, allow_nan=False)
            key = "lifecycle:" + hashlib.sha256((scope + "\n" + encoded).encode()).hexdigest()
            client = self._client()
            if task_id is None:
                submitted = client.submit(request, key)
                task_id = submitted["id"]
            if not isinstance(task_id, str) or not task_id:
                raise ValueError("invalid task identity")
            record = client.wait(task_id, timeout_seconds=timeout)
            if record.get("id") != task_id or record.get("request") != request:
                raise ValueError("task result binding mismatch")
            if record.get("status") != "completed":
                return AiCallResult(provider=record.get("provider", ""), success=False,
                                    raw={"status": record.get("status"), "id": task_id},
                                    note="ai_task_incomplete", label=route.label)
            output = record.get("output")
            handle = record.get("handle") or {}
            verification = handle.get("model_verification")
            if (record.get("result_kind") != "advisory" or not isinstance(output, dict)
                    or set(output) != {"report"} or not isinstance(output["report"], str)
                    or not output["report"].strip() or not 1 <= len(output["report"]) <= 60000
                    or not isinstance(record.get("provider"), str) or not record["provider"]):
                raise ValueError("invalid advisory result")
            if route.mode == "api":
                if verification != "provider_reported" or handle.get("model") != route.model:
                    raise ValueError("API result model mismatch")
            elif verification != "unavailable":
                raise ValueError("native model identity cannot be attested")
            return AiCallResult(provider=record["provider"], success=True, output=output["report"],
                                raw={"id": task_id, "status": "completed", "result_kind": "advisory",
                                     "model_requested": route.model, "model_verification": verification},
                                label=route.label)
        except TimeoutError:
            return AiCallResult(provider="", success=False, label=route.label,
                                raw={"id": task_id, "status": "outcome_unknown"}, note="ai_task_wait_timeout")
        except (ValueError, TypeError, KeyError, AttributeError):
            return AiCallResult.unavailable(route.label, "ai_task_unavailable")
        except Exception:
            if isinstance(task_id, str) and task_id:
                return AiCallResult(provider="", success=False, label=route.label,
                                    raw={"id": task_id, "status": "outcome_unknown"},
                                    note="ai_task_read_unavailable")
            return AiCallResult.unavailable(route.label, "ai_task_unavailable")
