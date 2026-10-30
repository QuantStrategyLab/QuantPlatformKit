from copy import deepcopy
from datetime import datetime, timezone
import pytest
from quant_platform_kit.notifications.digest_candidates import cycle_evidence, project_reports

TARGET = dict(platform_id="synthetic", strategy_profile="core", service_name="test-service",
    account_scope="test-scope", account_selector=["test-selector"], deployment_selector="test-slot", dry_run_only=False)
NOW = datetime(2026, 10, 16, 2, tzinfo=timezone.utc)


def report(run_id="cycle-1", orders=()):
    return dict(schema_version="runtime_report.v1", platform="synthetic", strategy_profile="core",
        service_name="test-service", runtime_target=deepcopy(TARGET), dry_run=False, status="ok", run_id=run_id,
        started_at="2026-10-16T01:00:00Z", summary={"notification_digest": cycle_evidence(
            {"execution_status": "completed", "broker_submission_done": bool(orders)}, orders)})


def project(reports):
    return project_reports(reports, expected_target=TARGET, opaque_account_uid="synthetic-uid",
        target_id="synthetic-target", now=NOW)["runs"]


def test_all_cycles_aggregate_without_inventing_fills():
    source = [report(), report("cycle-2", [{"status": "filled"}])]
    original = deepcopy(source)
    row = project(source)[0]
    assert (row["order_count"], row["fill_count"], row["cycle_count"], row["status"]) == (1, None, 2, "ok")
    assert source == original
    assert "account_scope" not in row


def test_missing_evidence_is_unknown_not_zero():
    source = report()
    source["summary"] = {}
    row = project([source])[0]
    assert row["fill_count"] is None and row["order_count"] is None and row["status"] == "alert"


@pytest.mark.parametrize("mutation", ["identity", "future", "duplicate", "error"])
def test_bad_source_stays_visible_or_rejects(mutation):
    source = report()
    if mutation == "error":
        source["status"] = "error"
        assert project([source])[0]["status"] == "alert"
        return
    if mutation == "identity": source["runtime_target"]["account_scope"] = "other"
    if mutation == "future": source["started_at"] = "2026-10-17T00:00:00Z"
    with pytest.raises(ValueError):
        project([source, deepcopy(source)] if mutation == "duplicate" else [source])


def test_archive_default_off_and_disabled_target_never_read_or_upload():
    from quant_platform_kit.notifications.digest_archive import emit
    def forbidden(*args): raise AssertionError("unexpected I/O")
    assert emit({}, read=forbidden, upload=forbidden)["status"] == "disabled"
    assert emit({"QSL_ROUTINE_NOTIFICATION_MODE": "daily_digest", "RUNTIME_TARGET_ENABLED": "false"},
        read=forbidden, upload=forbidden)["status"] == "target_disabled"


def test_archive_aggregates_window_and_uploads_once_without_private_output():
    import json
    from quant_platform_kit.notifications.digest_archive import emit
    env = dict(QSL_ROUTINE_NOTIFICATION_MODE="daily_digest", RUNTIME_TARGET_ENABLED="true",
        RUNTIME_TARGET_JSON=json.dumps(TARGET), DIGEST_STORE_TARGET="synthetic-slot",
        DIGEST_OPAQUE_ACCOUNT_UID="synthetic-uid", DIGEST_TARGET_ID="synthetic-target",
        EXECUTION_REPORT_GCS_URI="gs://synthetic-reports/archive",
        DIGEST_CANDIDATES_GCS_URI="gs://synthetic-reports/candidates")
    reports = [report("first", [{"status": "filled"}]), report("second")]
    for source in reports: source["started_at"] = "2026-10-15T20:00:00Z"
    def read(args):
        if args[0] == "ls":
            return [{"url": f"gs://synthetic-reports/archive/synthetic/core/2026-10/{i}.json",
                     "metadata": {"updated": "2026-10-15T20:01:00Z"}} for i in range(2)]
        return reports[int(args[1].rsplit("/", 1)[-1].split(".")[0])]
    uploads = []
    result = emit(env, now=NOW, read=read, upload=lambda *args: uploads.append(args))
    assert result["runs"] == 2 and len(uploads) == 1
    assert "/2026-10-15/" in uploads[0][0]
    row = json.loads(uploads[0][1])["runs"][0]
    assert (row["order_count"], row["fill_count"], row["cycle_count"]) == (1, None, 2)
    calls = []
    def failed_upload(*args):
        calls.append(args)
        raise RuntimeError("unknown write outcome")
    with pytest.raises(RuntimeError): emit(env, now=NOW, read=read, upload=failed_upload)
    assert len(calls) == 1


def test_configured_closed_session_proves_idle_without_inventing_runs(monkeypatch):
    import json
    import quant_platform_kit.common.runtime_heartbeat_policy as policy
    from quant_platform_kit.notifications.digest_archive import emit
    env = dict(QSL_ROUTINE_NOTIFICATION_MODE="daily_digest", RUNTIME_TARGET_ENABLED="true",
        RUNTIME_TARGET_JSON=json.dumps(TARGET), DIGEST_STORE_TARGET="synthetic-slot",
        DIGEST_OPAQUE_ACCOUNT_UID="synthetic-uid", DIGEST_TARGET_ID="synthetic-target",
        EXECUTION_REPORT_GCS_URI="gs://synthetic-reports/archive",
        DIGEST_CANDIDATES_GCS_URI="gs://synthetic-reports/candidates",
        DIGEST_NOTIFICATION_SCHEDULE_JSON=json.dumps({"scheduler": {"main_time": "0 20 * * 1-5", "timezone": "UTC"}}))
    monkeypatch.setattr(policy, "filter_due_targets", lambda *args, **kwargs: ([], True))
    uploads = []
    emit(env, now=NOW, read=lambda args: [], upload=lambda *args: uploads.append(args))
    row = json.loads(uploads[0][1])["runs"][0]
    assert row["actually_ran"] is False and "order_count" not in row and "fill_count" not in row
    monkeypatch.setattr(policy, "filter_due_targets", lambda *args, **kwargs: ([{}], True))
    with pytest.raises(ValueError, match="candidate_due_source_absent"):
        emit(env, now=NOW, read=lambda args: [], upload=lambda *args: uploads.append(args))
    assert len(uploads) == 1


def test_multi_target_bindings_use_each_explicit_enablement_without_a_global_target():
    import json
    from quant_platform_kit.notifications.digest_archive import emit
    result = emit({"QSL_ROUTINE_NOTIFICATION_MODE": "daily_digest",
        "DIGEST_TARGET_BINDINGS_JSON": json.dumps([{"RUNTIME_TARGET_ENABLED": "false"}])},
        read=lambda args: pytest.fail("disabled target must not be read"),
        upload=lambda *args: pytest.fail("disabled target must not be uploaded"))
    assert result == {"status": "projected", "uploaded": False, "targets": 1}


def test_completed_order_count_is_not_used_as_execution_fill_count():
    source = report(orders=[{"status": "filled"}])
    row = project([source])[0]
    assert row["order_count"] == 1 and row["fill_count"] is None and row["status"] == "ok"
    fills = [{"execution_id": f"synthetic-fill-{i}"} for i in range(3)]
    row = project([report(orders=[{"status": "filled", "fills": fills}])])[0]
    assert row["order_count"] == 1 and row["fill_count"] == 3


def test_proven_pending_projects_submission_without_inventing_fills():
    order = {"status": "accepted", "broker_order_id": "synthetic"}
    execution = {"execution_status": "pending_reconciliation", "orders_pending_count": 1}
    assert cycle_evidence(execution, [order])["routine"] is False
    evidence = cycle_evidence(execution, [order], known_pending=True)
    assert (evidence["routine"], evidence["order_count"], evidence["fill_count"]) == (True, 1, None)
    source = report()
    source["summary"] = {"execution_status": "pending_reconciliation", "notification_digest": evidence}
    row = project([source])[0]
    assert (row["status"], row["execution_status"], row["order_count"], row["fill_count"]) == ("ok", "order_submitted", 1, None)
    second = report("cycle-2")
    assert project([source, second])[0]["execution_status"] == "order_submitted"


@pytest.mark.parametrize("issue", ["reconciliation_required", "persistence_error", "notification_error", "auth_expired", "outcome_unknown", "submission_halted"])
def test_proven_acknowledgement_does_not_hide_an_independent_issue(issue):
    execution = {"execution_status": "pending_reconciliation", issue: True}
    assert cycle_evidence(execution, [{"status": "accepted"}], known_pending=True)["routine"] is False


@pytest.mark.parametrize("status", ["accepted", "PendingSubmit", "ApiPending", "ApiPendingSubmit", "Submitted", "PreSubmitted", "PartiallyFilled", "partial"])
def test_known_pending_uses_original_status_without_weakening_default(status):
    execution = {"execution_status": "pending_reconciliation", "no_op_reason": "broker_order_pending_confirmation"}
    orders = [{"status": status, "broker_order_id": "synthetic"}]
    original = deepcopy((execution, orders))
    assert cycle_evidence(execution, orders)["routine"] is False
    assert cycle_evidence(execution, orders, known_pending=True)["routine"] is True
    assert (execution, orders) == original


def test_known_pending_does_not_approve_rejected_order_or_empty_run():
    execution = {"execution_status": "pending_reconciliation"}
    assert cycle_evidence(execution, [{"status": "rejected"}], known_pending=True)["routine"] is False
    assert cycle_evidence(execution, [], known_pending=True)["routine"] is False


def test_observation_counts_use_live_signal_fields_and_do_not_export_content():
    from types import SimpleNamespace
    from quant_platform_kit.notifications.digest_candidates import routine_observation_counts
    signals = [SimpleNamespace(canonical_route="watch", suggested_action="observe", secret="private"),
               SimpleNamespace(canonical_route="watch", suggested_action="watch", error="bad"),
               SimpleNamespace(canonical_route="panic_reversal", suggested_action="notify_manual_review")]
    assert routine_observation_counts(signals) == {"watch": 1, "panic_reversal": 1}
    from quant_platform_kit.notifications.digest_routing import immediate_plugin_signals
    assert immediate_plugin_signals(signals, mode="daily_digest") == (signals[1],)
    source = report()
    source["summary"]["routine_observation_counts"] = {"watch": 1}
    assert "routine_observation_counts" not in project([source])[0]


def test_schwab_source_alias_does_not_change_target_identity():
    target = {**TARGET, "platform_id": "schwab"}
    source = report()
    source.update(platform="charles_schwab", runtime_target=deepcopy(target))
    result = project_reports([source], expected_target=target, opaque_account_uid="u", target_id="t", now=NOW)
    assert result["runs"][0]["platform_id"] == "schwab"
    source["platform"] = "other"
    with pytest.raises(ValueError, match="candidate_source_invalid"):
        project_reports([source], expected_target=target, opaque_account_uid="u", target_id="t", now=NOW)


def test_schwab_archive_uses_report_alias_without_changing_target():
    import json
    from quant_platform_kit.notifications.digest_archive import emit
    target = {**TARGET, "platform_id": "schwab"}
    source = report()
    source.update(platform="charles_schwab", runtime_target=deepcopy(target), started_at="2026-10-15T20:00:00Z")
    env = dict(QSL_ROUTINE_NOTIFICATION_MODE="daily_digest", RUNTIME_TARGET_ENABLED="true",
        RUNTIME_TARGET_JSON=json.dumps(target), DIGEST_STORE_TARGET="slot", DIGEST_OPAQUE_ACCOUNT_UID="u",
        DIGEST_TARGET_ID="t", EXECUTION_REPORT_GCS_URI="gs://synthetic-reports/archive",
        DIGEST_CANDIDATES_GCS_URI="gs://synthetic-reports/candidates")
    calls, uploads = [], []
    def read(args):
        calls.append(args)
        if args[0] == "ls":
            assert "/charles_schwab/" in args[-1]
            return [{"url": "gs://synthetic-reports/archive/charles_schwab/s/2026-10/a.json", "metadata": {"updated": "2026-10-15T20:01:00Z"}}]
        return source
    emit(env, now=NOW, read=read, upload=lambda *args: uploads.append(args))
    assert json.loads(uploads[0][1])["runs"][0]["platform_id"] == "schwab"
