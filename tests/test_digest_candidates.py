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
    assert (row["order_count"], row["fill_count"], row["cycle_count"], row["status"]) == (1, 1, 2, "ok")
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
