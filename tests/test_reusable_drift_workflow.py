from pathlib import Path


def test_reusable_drift_workflow_enforces_lifecycle_preflight() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "reusable-drift-check.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_call:" in workflow
    assert "timeout-minutes: 60" in workflow
    assert "strategy_domain:" in workflow
    assert "snapshot_repository:" in workflow
    assert "snapshot_repository_token:" in workflow
    assert "snapshot_checkout_path:" in workflow
    assert "snapshot_repository_ref:" in workflow
    assert "ai_gateway_service_url:" in workflow
    assert "quant_platform_kit_ref:" in workflow
    assert "lifecycle_performance_bucket:" in workflow
    assert "caller_event_name:" in workflow
    assert "caller_pr_head_repository:" in workflow
    assert "lifecycle_preflight_artifact:" in workflow
    assert "codex_audit_service_url:" in workflow
    assert 'python-version: ${{ inputs.python_version }}' in workflow
    assert "LIFECYCLE_PERFORMANCE_BUCKET: ${{ inputs.lifecycle_performance_bucket || vars.LIFECYCLE_PERFORMANCE_BUCKET || '' }}" in workflow
    assert "Validate trusted caller" in workflow
    assert "Untrusted reusable workflow caller" in workflow
    assert "caller_event_name must be provided by the caller workflow" in workflow
    assert "Unsupported caller_event_name" in workflow
    assert "pull_request callers are not trusted" in workflow
    assert "snapshot_repository mismatch for caller" in workflow
    assert "Fork pull_request callers are not trusted" in workflow
    assert "SNAPSHOT_REPOSITORY_TOKEN:" not in workflow
    assert "quant-lifecycle monitor --domain ${{ inputs.strategy_domain }}" in workflow
    assert (
        "quant-lifecycle doctor --domain ${{ inputs.strategy_domain }} --require-snapshot "
        "--require-backtest --max-freshness-days 7"
    ) in workflow
    assert "quant-lifecycle drift --domain ${{ inputs.strategy_domain }} --no-alerts" in workflow
    assert 'repository: ${{ inputs.snapshot_repository }}' in workflow
    assert 'ref: ${{ inputs.snapshot_repository_ref }}' in workflow
    assert 'path: ${{ inputs.snapshot_checkout_path }}' in workflow
    assert 'token: ${{ secrets.snapshot_repository_token || github.token }}' in workflow
    assert 'ref: ${{ inputs.quant_platform_kit_ref }}' in workflow
    assert "Download lifecycle preflight artifact" in workflow
    assert "actions/download-artifact@v6" in workflow
    assert "name: ${{ inputs.lifecycle_preflight_artifact }}" in workflow
    assert "path: ${{ runner.temp }}/lifecycle-preflight" in workflow
    assert "Restore lifecycle preflight inputs" in workflow
    assert "snapshot_checkout_path must remain under external/" in workflow
    assert "lifecycle preflight artifact must not contain symlinks" in workflow
    assert "snapshot checkout resolved outside the external workspace" in workflow
    assert "snapshot checkout must not contain symlinks" in workflow
    assert 'rm -rf -- "$LIFECYCLE_LOCAL_ROOT" "$snapshot_target"' in workflow
    assert 'cp -a "$lifecycle_source/." "$LIFECYCLE_LOCAL_ROOT/"' in workflow
    assert 'GH_TOKEN: ${{ github.token }}' in workflow
    assert 'os.environ["CODEX_AUDIT_ORG"] = owner' in workflow
    assert 'os.environ["CODEX_AUDIT_ORCHESTRATOR_REPO"] = repository' in workflow
    assert "create_issues_for_domain" in workflow
    assert 'CODEX_AUDIT_SERVICE_URL: ${{ secrets.codex_audit_service_url }}' in workflow
    assert 'AI_GATEWAY_SERVICE_URL: ${{ inputs.ai_gateway_service_url }}' in workflow
    assert 'ref: 5f37f07953a5ced8adc0f055ca7afc6dfee6b6d6' in workflow
    assert workflow.count('GH_TOKEN: ${{ github.token }}') >= 2
    assert "emit_parked_record" in workflow
    assert '"schema": "qsl.drift_dual_review_availability.v1"' in workflow
    assert '"state": "PARKED"' in workflow
    assert '"next_action": "retry_on_next_drift_cycle"' in workflow
    assert "review_script_unavailable" in workflow
    assert "codex_audit_service_unconfigured" in workflow
    assert "review_output_unavailable" in workflow
    assert "review_provider_degraded" in workflow
    assert "review_completed_blocked" in workflow
    assert 'completed_outcomes = {"fail", "disagreement"}' in workflow
    assert 'emit_parked_record "review_completed_blocked"' in workflow
    assert "Dual review completed and blocked promotion" in workflow
    assert "invalid_review_json" in workflow
    assert 'if [ ! -f "$review_output" ]; then' in workflow
    assert workflow.index('if [ ! -f "$review_output" ]; then') < workflow.index('cat "$review_output"')
    assert 'if [ "$review_rc" -ne 0 ]; then' in workflow
    assert 'exit "$review_rc"' not in workflow
