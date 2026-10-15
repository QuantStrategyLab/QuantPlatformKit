import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from quant_platform_kit.strategy_lifecycle.task_review import review_material

ROLES = ("primary", "secondary", "independent")


def result(role, *, verdict="approve", status="completed"):
    return SimpleNamespace(label=role, success=status == "completed",
        output=json.dumps({"verdict": verdict, "confidence": .7, "summary": "Synthetic advisory opinion."}),
        raw={"id": "task-" + role, "status": status, "result_kind": "advisory", "model_verification": "unavailable"})


def review(results, **kwargs):
    client = Mock()
    client.review.return_value = results
    return review_material({"synthetic": True}, operation_id="caller:frozen-revision", required_roles=ROLES, client=client, **kwargs), client


def test_completed_quorum_is_advisory_and_operation_stable():
    value, client = review([result(r) for r in ROLES])
    assert value["outcome"] == "agree_approve" and value["execution_authority_granted"] is False
    _, other = review([result(r) for r in ROLES])
    assert client.review.call_args == other.review.call_args


@pytest.mark.parametrize("status", ["running", "outcome_unknown", "cancel_requested"])
def test_unknown_task_never_becomes_approval(status):
    value, _ = review([result(ROLES[0], status=status), *[result(r) for r in ROLES[1:]]])
    assert value["status"] == "pending"
    assert value["tasks"][0]["task_id"] == "task-primary"


@pytest.mark.parametrize("verdict", ["reject", "escalate"])
def test_disagreement_needs_human(verdict):
    value, _ = review([result(ROLES[0], verdict=verdict), *[result(r) for r in ROLES[1:]]])
    assert value["outcome"] == "requires_human"


def test_missing_role_or_reused_task_cannot_form_quorum():
    assert review([result(ROLES[0])])[0]["status"] == "unavailable"
    values = [result(r) for r in ROLES]
    values[1].raw["id"] = values[0].raw["id"]
    assert review(values)[0]["status"] == "unavailable"


@pytest.mark.parametrize("output", [
    '{"verdict":"approve","confidence":NaN,"summary":"x"}',
    '{"verdict":"approve","confidence":true,"summary":"x"}',
    '{"verdict":"reject","verdict":"approve","confidence":0.7,"summary":"x"}',
    '{"verdict":"approve","confidence":0.7,"summary":"x","execute":true}',
])
def test_malformed_opinion_blocks(output):
    values = [result(r) for r in ROLES]
    values[0].output = output
    assert review(values)[0]["status"] == "unavailable"


def test_absent_configuration_makes_no_task(monkeypatch):
    monkeypatch.delenv("AI_SERVICE_URL", raising=False)
    value = review_material({"synthetic": True}, operation_id="caller", required_roles=ROLES)
    assert value["status"] == "unavailable"
