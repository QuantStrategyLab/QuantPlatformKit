from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEALTH_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "qpk-github-app-health.yml"
DOWNSTREAM_WORKFLOW_PATH = (
    ROOT / ".github" / "workflows" / "open-downstream-qpk-pin-prs.yml"
)
AUTH_DOC_PATH = ROOT / "docs" / "qpk_repo_sync_auth.zh-CN.md"

EXPECTED_REPOS = (
    "QuantPlatformKit",
    "CnEquityStrategies",
    "HkEquityStrategies",
    "UsEquityStrategies",
    "CryptoStrategies",
    "InteractiveBrokersPlatform",
    "LongBridgePlatform",
    "CharlesSchwabPlatform",
    "FirstradePlatform",
    "BinancePlatform",
    "QmtPlatform",
    "CnEquitySnapshotPipelines",
    "HkEquitySnapshotPipelines",
    "UsEquitySnapshotPipelines",
    "CryptoLivePoolPipelines",
)

APP_TOKEN_ACTION = (
    "actions/create-github-app-token@fee1f7d63c2ff003460e3d139729b119787bc349"
)


def _assert_repo_list(workflow: str) -> None:
    for repo in EXPECTED_REPOS:
        assert repo in workflow


def test_github_app_health_workflow_is_read_only_fail_closed() -> None:
    workflow = HEALTH_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "schedule:" in workflow
    assert 'cron: "23 */6 * * *"' in workflow
    assert "workflow_dispatch:" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "QSL_GITHUB_APP_PRIVATE_KEY_SECONDARY" in workflow
    assert "Mint App token (primary)" in workflow
    assert "Mint App token (secondary)" in workflow
    assert "continue-on-error: true" in workflow
    assert "steps.app_token_primary.outcome != 'success'" in workflow
    assert APP_TOKEN_ACTION in workflow
    assert "permission-contents: read" in workflow
    assert "permission-metadata: read" in workflow
    assert "app_token_mint_failed" in workflow
    assert "repo_access_failed:" in workflow
    assert "qpk_pin_readback_invalid" in workflow
    assert "GITHUB_STEP_SUMMARY" in workflow
    assert "token_source" in workflow
    assert "QSL_REPO_SYNC_TOKEN" not in workflow
    assert "secrets.QSL_REPO_SYNC_TOKEN" not in workflow
    assert "echo \"$GH_TOKEN\"" not in workflow
    assert "PRIVATE_KEY" not in workflow.split("Verify repository access", 1)[1]
    _assert_repo_list(workflow)
    assert workflow.count(APP_TOKEN_ACTION) == 2
    assert (
        workflow.index("Mint App token (primary)")
        < workflow.index("Mint App token (secondary)")
        < workflow.index("Select App token source")
        < workflow.index("Verify repository access and QPK_PIN readback")
    )


def test_downstream_pin_workflow_uses_primary_secondary_then_pat_fallback() -> None:
    workflow = DOWNSTREAM_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "QSL_GITHUB_APP_PRIVATE_KEY_SECONDARY" in workflow
    assert "Mint App token (primary)" in workflow
    assert "Mint App token (secondary)" in workflow
    assert "continue-on-error: true" in workflow
    assert "steps.app_token_primary.outcome != 'success'" in workflow
    assert "id: qsl_app_token" not in workflow
    token_expr = (
        "steps.app_token_primary.outputs.token || "
        "steps.app_token_secondary.outputs.token || "
        "secrets.QSL_REPO_SYNC_TOKEN"
    )
    assert workflow.count(token_expr) >= 4
    assert "temporary fallback only" in workflow or "migration" in workflow.lower()
    assert "Binance authority PATs are separate" in workflow
    _assert_repo_list(workflow)
    assert workflow.count(APP_TOKEN_ACTION) == 2


def test_repo_sync_auth_doc_covers_secondary_rotation_and_binance_boundary() -> None:
    doc = AUTH_DOC_PATH.read_text(encoding="utf-8")

    assert "QSL_GITHUB_APP_PRIVATE_KEY_SECONDARY" in doc
    assert "qpk-github-app-health" in doc
    assert "轮换与故障切换" in doc
    assert "Binance authority" in doc
    assert "完全分离" in doc
    assert "continue-on-error" in doc
    assert "不拼接私钥" in doc
    assert "QSL_REPO_SYNC_TOKEN" in doc
