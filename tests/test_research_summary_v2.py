import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quant_platform_kit.strategy_lifecycle.research_summary import make_summary_callback
from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import _accepted_summary_explanation


def locales():
    return {"zh-CN": dict.fromkeys(["question", "basis", "limits", "suggestion"], "研究证据不足，等待人工考虑。"),
            "en": dict.fromkeys(["question", "basis", "limits", "suggestion"], "Evidence is limited; wait for human review.")}


def callback(payload, **raw_changes):
    raw = {"status": "completed", "result_kind": "advisory", "model_requested": "configured-dot",
           "model_verification": "unavailable"}
    raw.update(raw_changes)
    client = Mock()
    client.execute.return_value = SimpleNamespace(success=True, provider="dot", raw=raw,
                                                  output=json.dumps(payload))
    summarize = make_summary_callback(revision="a" * 40, repository="QuantStrategyLab/Example",
                                      local_facts={"limit": "research only"}, validate_context=dict, client=client)
    return summarize, client


def test_native_bilingual_summary_preserves_unknown_model_identity_and_binding():
    summarize, client = callback({"locales": locales()})
    result = summarize({"question": "synthetic"})
    assert result["status"] == "available" and result["model_verification"] == "unavailable"
    assert "model" not in result and result["model_requested"] == "configured-dot"
    saved = _accepted_summary_explanation(result, {"input_digest": "a" * 64})
    assert saved["binding"] == {"input_digest": "a" * 64} and "model" not in saved
    first_key = client.execute.call_args.kwargs["idempotency_key"]
    summarize({"question": "synthetic"})
    assert client.execute.call_args.kwargs["idempotency_key"] == first_key
    summarize({"question": "changed synthetic"})
    assert client.execute.call_args.kwargs["idempotency_key"] != first_key


@pytest.mark.parametrize("field,value", [
    ("question", "研究收益为９"), ("basis", "123"), ("limits", "x" * 241), ("suggestion", ""),
])
def test_invalid_localized_text_never_becomes_an_available_summary(field, value):
    sections = copy.deepcopy(locales())
    sections["zh-CN"][field] = value
    summarize, _ = callback({"locales": sections})
    assert summarize({})["status"] == "unavailable"


@pytest.mark.parametrize("changes", [{"status": "outcome_unknown"}, {"result_kind": "execution_authority"},
                                      {"model_verification": "verified_by_bot_name"}, {"model_requested": ""}])
def test_nonadvisory_or_unknown_result_is_not_accepted(changes):
    summarize, _ = callback({"locales": locales()}, **changes)
    assert summarize({})["status"] == "unavailable"


def test_missing_summary_route_skips_without_consuming_another_mode(monkeypatch):
    monkeypatch.delenv("AI_SERVICE_SUMMARY_MODEL", raising=False)
    summarize = make_summary_callback(revision="a" * 40, repository="QuantStrategyLab/Example",
                                      local_facts={}, validate_context=dict)
    assert summarize({})["status"] == "unavailable"
