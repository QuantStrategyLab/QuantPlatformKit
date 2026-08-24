import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_runtime_selectable_allowlist_document_keeps_permission_boundary():
    text = (ROOT / "docs/runtime_selectable_allowlist_v1.zh-CN.md").read_text()
    assert "qsl.runtime_selectable_allowlist.v1" in text
    assert '"permission_effect": "none"' in text
    assert "不等于策略生命周期状态" in text
    assert "不授予 live 权限" in text


def test_allowlist_example_is_not_an_authority_policy():
    example = {
        "schema": "qsl.runtime_selectable_allowlist.v1",
        "platform": "example",
        "domain": "us_equity",
        "profiles": ["example_profile"],
        "source_digest": "0" * 64,
        "generated_at": "2026-08-24T00:00:00Z",
        "permission_effect": "none",
    }
    assert json.loads(json.dumps(example))["permission_effect"] == "none"
    assert "authority" not in example
    assert "broker" not in example
