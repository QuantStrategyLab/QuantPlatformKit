"""Synthetic contract checks for lifecycle task routing and advisory results."""
import copy
import json
import os
from unittest.mock import patch

import pytest

from quant_platform_kit.strategy_lifecycle.ai_provider import (
    AiProviderConfig, AiServiceConfig, AiServiceClient,
)


class Tasks:
    def __init__(self, *, change=None, fail=None):
        self.calls = []
        self.change = change
        self.fail = fail

    def submit(self, request, key):
        self.calls.append((copy.deepcopy(request), key))
        self.request = request
        return {"id": "task-synthetic"}

    def wait(self, task_id, **kwargs):
        if self.fail:
            raise self.fail
        value = {"id": task_id, "request": copy.deepcopy(self.request), "status": "completed",
                 "provider": "dot", "result_kind": "advisory", "output": {"report": "synthetic advice"},
                 "handle": {"model_verification": "unavailable"}}
        if self.change:
            self.change(value)
        return value


def client(tasks, *, mode="agent", profile="default"):
    route = AiProviderConfig("primary", mode, "configured-model", profile)
    return AiServiceClient(AiServiceConfig.reliability(primary=route), task_client=tasks)


def test_native_advice_does_not_forge_a_model_attestation():
    tasks = Tasks()
    result = client(tasks).execute("synthetic", idempotency_key="operation-synthetic")
    assert result.success and result.provider == "dot"
    assert result.raw["model_verification"] == "unavailable"
    assert result.raw["model_requested"] == "configured-model"
    assert result.raw["result_kind"] == "advisory"
    request, _ = tasks.calls[0]
    assert set(request) == {"mode", "profile", "model", "objective", "materials", "output_schema", "timeout_seconds"}
    assert request["mode"] == "agent"


@pytest.mark.parametrize("change", [
    lambda r: r.update(id="another-task"),
    lambda r: r["request"].update(objective="other materials"),
    lambda r: r.update(result_kind="execution_authority"),
    lambda r: r.update(output={"report": "advice", "trade": True}),
    lambda r: r.update(output={"report": ""}),
    lambda r: r.update(output={"report": "x" * 60001}),
    lambda r: r.update(handle={"model_verification": "provider_reported"}),
    lambda r: r.update(provider=""),
])
def test_rejects_wrong_binding_or_invalid_native_results(change):
    result = client(Tasks(change=change)).execute("synthetic", idempotency_key="operation-synthetic")
    assert not result.success and not result.output


@pytest.mark.parametrize("status", ["running", "outcome_unknown", "failed", "invalid_output", "cancelled"])
def test_noncompletion_never_falls_back_or_becomes_advice(status):
    tasks = Tasks(change=lambda r: r.update(status=status))
    result = client(tasks).execute("synthetic", idempotency_key="operation-synthetic")
    assert not result.success and result.raw["status"] == status
    assert len(tasks.calls) == 1 and result.output == ""


def test_wait_timeout_preserves_task_identity_and_does_not_resubmit():
    tasks = Tasks(fail=TimeoutError("private upstream text"))
    result = client(tasks).execute("synthetic", idempotency_key="operation-synthetic")
    assert result.raw == {"id": "task-synthetic", "status": "outcome_unknown"}
    assert "private" not in result.note and len(tasks.calls) == 1


def test_caller_retry_reuses_key_and_material_or_route_changes_bind_a_new_key():
    tasks = Tasks()
    first = client(tasks)
    for prompt in ["synthetic", "synthetic", "changed synthetic"]:
        first.execute(prompt, idempotency_key="operation-synthetic")
    client(tasks, profile="second-opinion").execute("synthetic", idempotency_key="operation-synthetic")
    keys = [key for _, key in tasks.calls]
    assert keys[0] == keys[1]
    assert len({keys[0], keys[2], keys[3]}) == 3


def test_missing_operation_identity_or_only_legacy_config_never_submits():
    tasks = Tasks()
    with patch.dict(os.environ, {"CODEX_AUDIT_SERVICE_URL": "https://old.invalid"}, clear=True):
        assert AiServiceConfig.from_env().reviewers == ()
        assert not client(tasks).execute("synthetic").success
    assert tasks.calls == []


@pytest.mark.parametrize("timeout", [True, 0, -1, float("nan"), float("inf"), 3601])
def test_invalid_limits_never_submit(timeout):
    tasks = Tasks()
    assert not client(tasks).execute("synthetic", timeout=timeout, idempotency_key="operation").success
    assert tasks.calls == []


@pytest.mark.parametrize("verification,model,success", [
    ("provider_reported", "configured-model", True),
    ("unavailable", "configured-model", False),
    ("provider_reported", "other-model", False),
])
def test_api_results_require_matching_provider_reported_model(verification, model, success):
    tasks = Tasks(change=lambda r: r.update(handle={"model_verification": verification, "model": model}))
    assert client(tasks, mode="api").execute("synthetic", idempotency_key="operation").success is success


def test_review_roles_require_distinct_routes_but_do_not_prove_account_isolation():
    routes = [AiProviderConfig("reviewer-primary", "agent", "dot-model"),
              AiProviderConfig("reviewer-secondary", "agent", "grok-model", "second-opinion")]
    tasks = Tasks()
    results = AiServiceClient(AiServiceConfig.safety(reviewers=routes), task_client=tasks).review(
        "synthetic", idempotency_key="review-operation")
    assert [r.label for r in results] == ["reviewer-primary", "reviewer-secondary"]
    assert all(r.raw["model_verification"] == "unavailable" for r in results)
    with pytest.raises(ValueError):
        AiServiceConfig.safety(reviewers=[routes[0], AiProviderConfig("other-role", "agent", "another-model")])
    with pytest.raises(ValueError):
        AiServiceConfig.safety(reviewers=[routes[0], AiProviderConfig("reviewer-primary", "api", "api-model")])


def test_env_uses_explicit_routes_and_does_not_invent_a_verifier():
    routes = [{"label": "reviewer-primary", "mode": "agent", "model": "configured-dot"}]
    with patch.dict(os.environ, {"AI_SERVICE_URL": "https://service.invalid",
                                "AI_SERVICE_REVIEWERS_JSON": json.dumps(routes)}, clear=True):
        config = AiServiceConfig.from_env()
    assert config.reviewers[0].model == "configured-dot" and config.verifier is None


def test_resume_reads_existing_task_and_never_submits_a_new_one():
    tasks = Tasks()
    adapter = client(tasks)
    adapter.execute("synthetic", idempotency_key="operation")
    result = adapter.execute("synthetic", idempotency_key="operation", resume_task_id="task-synthetic")
    assert result.success and len(tasks.calls) == 1
    assert not adapter.execute("different materials", idempotency_key="operation",
                               resume_task_id="task-synthetic").success
    assert len(tasks.calls) == 1


def test_lost_read_response_preserves_task_identity_and_redacts_upstream():
    tasks = Tasks(fail=RuntimeError("private upstream detail"))
    result = client(tasks).execute("synthetic", idempotency_key="operation")
    assert result.raw == {"id": "task-synthetic", "status": "outcome_unknown"}
    assert len(tasks.calls) == 1 and "private" not in result.note
