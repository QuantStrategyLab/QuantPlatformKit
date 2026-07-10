from pathlib import Path


def test_reusable_drift_workflow_enforces_lifecycle_preflight() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "reusable-drift-check.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_call:" in workflow
    assert "strategy_domain:" in workflow
    assert "snapshot_repository:" in workflow
    assert "snapshot_checkout_path:" in workflow
    assert 'python-version: ${{ inputs.python_version }}' in workflow
    assert 'LIFECYCLE_PERFORMANCE_BUCKET: ${{ vars.LIFECYCLE_PERFORMANCE_BUCKET || \'\' }}' in workflow
    assert "quant-lifecycle monitor --domain ${{ inputs.strategy_domain }}" in workflow
    assert (
        "quant-lifecycle doctor --domain ${{ inputs.strategy_domain }} --require-snapshot "
        "--require-backtest --max-freshness-days 7"
    ) in workflow
    assert "quant-lifecycle drift --domain ${{ inputs.strategy_domain }} --no-alerts" in workflow
    assert 'repository: ${{ inputs.snapshot_repository }}' in workflow
    assert 'path: ${{ inputs.snapshot_checkout_path }}' in workflow
    assert 'ref: ${{ steps.quant-platform-kit-ref.outputs.ref }}' in workflow
