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
    assert "ai_service_url:" in workflow
    assert "quant_platform_kit_ref:" in workflow
    assert "lifecycle_performance_bucket:" in workflow
    assert "caller_event_name:" in workflow
    assert "caller_pr_head_repository:" in workflow
    assert "lifecycle_preflight_artifact:" in workflow
    assert "strategy_profile:" in workflow
    assert "live_stream_id:" in workflow
    assert "LIFECYCLE_LIVE_STREAM_ID: ${{ inputs.live_stream_id }}" in workflow
    assert "ai_service_audience:" in workflow
    assert "ai_service_reviewers_json:" in workflow
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
    assert "LIFECYCLE_STRATEGY_PROFILE: ${{ inputs.strategy_profile }}" in workflow
    assert 'lifecycle_args+=(--strategy "${LIFECYCLE_STRATEGY_PROFILE}")' in workflow
    assert 'lifecycle_args+=(--live-stream-id "${LIFECYCLE_LIVE_STREAM_ID}")' in workflow
    assert "not paper/live account PnL" in workflow
    assert 'quant-lifecycle monitor --domain ${{ inputs.strategy_domain }} --source-revision "${GITHUB_SHA}" "${lifecycle_args[@]}"' in workflow
    assert 'quant-lifecycle doctor --domain ${{ inputs.strategy_domain }} --require-snapshot --require-backtest --max-freshness-days 7 "${lifecycle_args[@]}"' in workflow
    assert 'quant-lifecycle drift --domain ${{ inputs.strategy_domain }} --no-alerts "${lifecycle_args[@]}"' in workflow
    assert 'repository: ${{ inputs.snapshot_repository }}' in workflow
    assert 'ref: ${{ inputs.snapshot_repository_ref }}' in workflow
    assert 'path: ${{ inputs.snapshot_checkout_path }}' in workflow
    assert 'token: ${{ secrets.snapshot_repository_token || github.token }}' in workflow
    assert 'ref: ${{ inputs.quant_platform_kit_ref }}' in workflow
    assert "Download lifecycle preflight artifact" in workflow
    assert "actions/download-artifact@v7" in workflow
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
    assert 'AI_SERVICE_URL: ${{ inputs.ai_service_url }}' in workflow
    assert 'AI_SERVICE_REVIEWERS_JSON: ${{ inputs.ai_service_reviewers_json }}' in workflow
    assert 'from quant_platform_kit.strategy_lifecycle.drift_review import review_critical_drifts' in workflow
    assert 'AIAuditBridge' not in workflow
    assert 'CODEX_AUDIT_SERVICE_URL' not in workflow
    assert 'approved artifact required' in workflow
    assert 'artifact digest mismatch' in workflow
    assert '--no-index' in workflow


def test_reusable_drift_runner_defaults_to_hosted_and_accepts_research_runner():
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "reusable-drift-check.yml").read_text(encoding="utf-8")
    assert "runs-on: ${{ fromJSON(inputs.runner_labels) }}" in workflow
    assert "default: '\"ubuntu-latest\"'" in workflow
    assert "runs-on: ubuntu-latest" not in workflow


def test_drift_review_receives_measured_evidence_and_keeps_rejection(monkeypatch, capsys):
    import json
    import sys
    from types import SimpleNamespace
    from unittest import mock
    import pytest
    import textwrap

    path = Path(__file__).resolve().parents[1] / '.github/workflows/reusable-drift-check.yml'
    step = path.read_text().split('      - name: Review critical drift through task service\n', 1)[1]
    script = textwrap.dedent(step.split('        run: |\n', 1)[1]).strip()
    code = '\n'.join(script.splitlines()[1:-1])
    evidence = {'as_of': '2026-01-01', 'source_revision': 'synthetic-source',
                'baseline_artifact_id': 'synthetic-baseline',
                'dimensions': {'volatility': {'actual': 0.4, 'expected': 0.2, 'threshold': 0.3}}}
    item = SimpleNamespace(strategy_profile='synthetic', domain='crypto', drift_score=0.75,
                           status=SimpleNamespace(value='critical'), to_dict=lambda: evidence)
    reviewer = mock.Mock(return_value={'ok': False, 'state': 'PARKED', 'count': 1,
                                            'results': [{'status': 'completed', 'outcome': 'requires_human'}]})
    detector = mock.Mock(return_value=[item])
    monkeypatch.setitem(sys.modules, 'quant_platform_kit.strategy_lifecycle.drift_detector',
                        SimpleNamespace(run_drift_detection=detector))
    monkeypatch.setitem(sys.modules, 'quant_platform_kit.strategy_lifecycle.drift_review',
                        SimpleNamespace(review_critical_drifts=reviewer))
    monkeypatch.setenv('STRATEGY_DOMAIN', 'crypto')
    monkeypatch.setenv('GITHUB_SHA', 'a' * 40)
    monkeypatch.delenv('AI_SERVICE_REQUIRED_ROLES_JSON', raising=False)
    monkeypatch.delenv('AI_SERVICE_VERIFICATION_ONLY', raising=False)
    with pytest.raises(SystemExit) as stopped:
        exec(compile(code, '<drift-review-workflow>', 'exec'), {})
    assert stopped.value.code == 0
    observation = reviewer.call_args.args[1][0]
    assert observation['evidence'] == evidence
    assert 'deviation_pct' in observation['score_definition']
    assert reviewer.call_args.kwargs['roles'] == ['primary', 'secondary', 'verification']
    assert json.loads(capsys.readouterr().out)['state'] == 'PARKED'
    monkeypatch.setenv('AI_SERVICE_VERIFICATION_ONLY', 'true')
    with pytest.raises(SystemExit) as verified:
        exec(compile(code, '<drift-review-workflow>', 'exec'), {})
    assert verified.value.code == 0
    result = json.loads(capsys.readouterr().out)
    assert result['verification_completed'] is True
    assert result['state'] == 'PARKED' and result['ok'] is False
    reviewer.return_value = {'ok': False, 'count': 1, 'results': [{'status': 'pending'}]}
    with pytest.raises(SystemExit) as pending:
        exec(compile(code, '<drift-review-workflow>', 'exec'), {})
    assert pending.value.code == 3
    for verification in ('false', 'true'):
        monkeypatch.setenv('AI_SERVICE_VERIFICATION_ONLY', verification)
        for status in ('pending', 'unavailable', 'outcome_unknown', 'failed'):
            reviewer.return_value = {'ok': False, 'count': 1, 'results': [{'status': status}]}
            with pytest.raises(SystemExit) as incomplete:
                exec(compile(code, '<drift-review-workflow>', 'exec'), {})
            assert incomplete.value.code == 3
