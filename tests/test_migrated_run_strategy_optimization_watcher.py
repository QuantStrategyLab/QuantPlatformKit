from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch

from quant_platform_kit.strategy_lifecycle.watch.runner import (
    dispatch_strategy_watch_findings,
    list_archived_issue_urls,
    list_open_issue_urls,
    parse_bool,
    resolve_input_path,
    run_watcher,
    run_research_input_terminal_watcher,
    main,
)
from quant_platform_kit.strategy_lifecycle.watch.strategy_watch import build_strategy_monitoring_finding, finding_to_automation_task, watcher_issue_key
from quant_platform_kit.strategy_lifecycle.research_task import calculate_task_sha256
from test_migrated_strategy_watch import coverage_export_fixture, guard_external_io
import quant_platform_kit.strategy_lifecycle.watch.strategy_watch as watch


def _performance_payload(*, repo: str = "QuantStrategyLab/TestStrategies", profile: str = "live", sharpe: float = 0.5) -> dict[str, object]:
    return {
        "repo": repo,
        "profile": profile,
        "schema_version": "strategy_performance.v2",
        "metrics_kind": "performance",
        "current_metrics": {"sharpe": sharpe, "cagr": 0.1, "calmar": 0.7, "win_rate": 0.52, "max_dd": 0.12},
        "baseline_metrics": {"sharpe": 1.0, "cagr": 0.2, "calmar": 1.0, "win_rate": 0.58, "max_dd": 0.08},
    }


def _verified_p3_payload(*, sharpe: float = 0.5) -> dict[str, object]:
    return {
        **_performance_payload(repo="QuantStrategyLab/UsEquitySnapshotPipelines", profile="tqqq_core_only_p2_v5", sharpe=sharpe),
        "candidate_kind": "individual",
        "domain": "us_equity",
        "generated_at": "2026-08-20T00:00:00Z",
        "research_task_evidence": {
            "p1_input_digest": "a" * 64,
            "p2_config_digest": "b" * 64,
            "p3_evidence_id": "c" * 64,
            "strategy_revision": "d" * 40,
            "producer_revision": "e" * 40,
        },
    }


class RunStrategyOptimizationWatcherTest(unittest.TestCase):

    def test_main_reads_terminal_status_relative_to_trusted_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory)
            terminal_path = source_root / "data/output/p1-status.json"
            terminal_path.parent.mkdir(parents=True)
            terminal_path.write_text(
                json.dumps(
                    {
                        "status": "DEFERRED",
                        "reason_code": "ALPACA_SIP_ACCESS_FORBIDDEN",
                        "candidate": {"candidate_id": "soxl_soxx_core_only_p2_v3"},
                    }
                ),
                encoding="utf-8",
            )
            absent_metrics_path = "data/output/strategy_performance.v2.json"
            original = dict(os.environ)
            try:
                os.environ.update(
                    {
                        "STRATEGY_WATCH_SOURCE_ROOT": str(source_root),
                        "STRATEGY_WATCH_METRICS_PATH": absent_metrics_path,
                        "STRATEGY_WATCH_TERMINAL_STATUS_PATH": "data/output/p1-status.json",
                        "STRATEGY_WATCH_SOURCE_REPO": "QuantStrategyLab/UsEquitySnapshotPipelines",
                        "STRATEGY_WATCH_TERMINAL_PROFILE": "soxl_soxx_trend_income",
                        "STRATEGY_WATCH_DRY_RUN": "true",
                    }
                )
                self.assertEqual(main(), 0)
            finally:
                os.environ.clear()
                os.environ.update(original)

    def test_deferred_terminal_creates_issue_only_finding(self) -> None:
        created = []

        result = run_research_input_terminal_watcher(
            {
                "status": "DEFERRED",
                "reason_code": "ALPACA_SIP_ACCESS_FORBIDDEN",
                "date_cutoff": "2026-08-21",
                "candidate": {"candidate_id": "soxl_soxx_core_only_p2_v3"},
            },
            source_repo="QuantStrategyLab/UsEquitySnapshotPipelines",
            profile="soxl_soxx_trend_income",
            dry_run=False,
            create_issue=lambda repo, title, body: created.append((repo, title, body)) or "https://example.test/issues/1",
            list_issues=lambda _repo: {},
            list_archived_issues=lambda _repo: {},
        )

        self.assertEqual(result["findings"], 1)
        self.assertEqual(len(created), 1)
        self.assertEqual(result["issues"][0]["task"]["trigger"]["kind"], "strategy_research_input_unavailable")

    def test_accepted_terminal_is_visible_but_not_a_watcher_failure(self) -> None:
        result = run_research_input_terminal_watcher(
            {
                "status": "ACCEPTED",
                "reason_code": "",
                "candidate": {"candidate_id": "soxl_soxx_core_only_p2_v3"},
            },
            source_repo="QuantStrategyLab/UsEquitySnapshotPipelines",
            profile="soxl_soxx_trend_income",
            dry_run=False,
        )

        snapshot = result["research_task_source_snapshot"]
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["dry_run"])
        self.assertEqual(result["errors"], 0)
        self.assertEqual(result["findings"], 0)
        self.assertEqual(snapshot["data_status"], "unavailable")
        self.assertEqual(snapshot["tasks"], [])
        self.assertIn("p1_terminal_accepted", snapshot["errors"])
        self.assertIn("research_task_context_unavailable", snapshot["errors"])

    def test_main_publishes_unavailable_snapshot_when_metrics_do_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original = dict(os.environ)
            output = StringIO()
            try:
                os.environ.update(
                    {
                        "STRATEGY_WATCH_SOURCE_ROOT": directory,
                        "STRATEGY_WATCH_METRICS_PATH": "data/output/not-yet-published.json",
                        "STRATEGY_WATCH_SOURCE_REPO": "QuantStrategyLab/UsEquitySnapshotPipelines",
                        "STRATEGY_WATCH_DRY_RUN": "true",
                    }
                )
                with redirect_stdout(output):
                    self.assertEqual(main(), 0)
            finally:
                os.environ.clear()
                os.environ.update(original)

        result = json.loads(output.getvalue())
        snapshot = result["research_task_source_snapshot"]
        self.assertEqual(result["status"], "ok")
        self.assertEqual(snapshot["data_status"], "unavailable")
        self.assertIn("comparable_metrics_unavailable", snapshot["errors"])

    def test_monitoring_dispatch_does_not_repeat_existing_issue(self) -> None:
        finding = build_strategy_monitoring_finding(
            domain="crypto",
            profile="crypto_live_pool_rotation",
            severity="high",
            metrics={"overall_score": 27.7},
            signals=[{"metric": "overall_score", "reason": "overall_score=27.7"}],
            source="quant-monitor/health-cycle",
        )
        issue_key = watcher_issue_key(finding_to_automation_task(finding))
        comment_calls: list[tuple[str, str, str]] = []

        result = dispatch_strategy_watch_findings(
            [finding],
            dry_run=False,
            comment_existing=False,
            create_issue=lambda repo, title, body: "https://example.test/new",
            comment_issue=lambda repo, url, body: comment_calls.append((repo, url, body)) or "",
            list_issues=lambda repo: {issue_key: "https://example.test/existing"},
            list_archived_issues=lambda _repo: {},
        )

        self.assertEqual(result["errors"], 0)
        self.assertEqual(result["issues"][0]["existing_url"], "https://example.test/existing")
        self.assertEqual(result["issues"][0]["skipped_reason"], "open issue already records this strategy")
        self.assertEqual(comment_calls, [])

    def test_dry_run_does_not_create_issue(self) -> None:
        calls: list[tuple[str, str, str]] = []

        result = run_watcher(
            _performance_payload(),
            dry_run=True,
            create_issue=lambda repo, title, body: calls.append((repo, title, body)) or "https://example.test/1",
            comment_issue=lambda repo, url, body: "https://example.test/comment",
            list_issues=lambda repo: {},
            list_archived_issues=lambda _repo: {},
        )

        self.assertEqual(result["findings"], 1)
        self.assertEqual(result["errors"], 0)
        self.assertTrue(result["issues"][0]["dry_run"])
        self.assertNotIn("metrics", result["issues"][0]["task"]["trigger"])
        self.assertEqual(calls, [])
        self.assertEqual(result["research_task_source_snapshot"]["data_status"], "unavailable")

    def test_verified_p3_degradation_creates_one_bounded_research_task(self) -> None:
        result = run_watcher(
            _verified_p3_payload(),
            source_repo="QuantStrategyLab/UsEquitySnapshotPipelines",
            dry_run=True,
        )

        snapshot = result["research_task_source_snapshot"]
        self.assertEqual(snapshot["schema_version"], "qsl_research_task_source_snapshot.v1")
        self.assertEqual(snapshot["data_status"], "ready")
        self.assertEqual(snapshot["errors"], [])
        self.assertEqual(len(snapshot["tasks"]), 1)
        task = snapshot["tasks"][0]
        self.assertEqual(task["target"]["repository"], "QuantStrategyLab/UsEquityStrategies")
        self.assertEqual(task["authority"], {"research_only": True, "no_order": True, "size_zero_required": True, "p4_p5_p6_authorized": False})
        self.assertEqual(task["experiment"]["max_runs"], 1)
        self.assertEqual(task["task_sha256"], calculate_task_sha256(task))

    def test_healthy_verified_p3_observation_publishes_an_empty_ready_queue(self) -> None:
        result = run_watcher(
            _verified_p3_payload(sharpe=1.0) | {
                "current_metrics": {"sharpe": 1.0, "cagr": 0.2, "calmar": 1.0, "win_rate": 0.58, "max_dd": 0.08},
                "baseline_metrics": {"sharpe": 1.0, "cagr": 0.2, "calmar": 1.0, "win_rate": 0.58, "max_dd": 0.08},
            },
            source_repo="QuantStrategyLab/UsEquitySnapshotPipelines",
            dry_run=True,
        )

        snapshot = result["research_task_source_snapshot"]
        self.assertEqual(result["findings"], 0)
        self.assertEqual(snapshot["data_status"], "ready")
        self.assertEqual(snapshot["tasks"], [])

    def test_non_dry_run_uses_source_repo_override(self) -> None:
        calls: list[tuple[str, str, str]] = []

        result = run_watcher(
            _performance_payload(repo="QuantStrategyLab/IssueRepo", sharpe=1.0) | {
                "current_metrics": {"sharpe": 1.0, "cagr": 0.2, "calmar": 1.0, "win_rate": 0.58, "max_dd": 0.2},
                "baseline_metrics": {"sharpe": 1.0, "cagr": 0.2, "calmar": 1.0, "win_rate": 0.58, "max_dd": 0.1},
            },
            source_repo="QuantStrategyLab/IssueRepo",
            dry_run=False,
            create_issue=lambda repo, title, body: calls.append((repo, title, body)) or "https://example.test/issue/1",
            comment_issue=lambda repo, url, body: "https://example.test/comment",
            list_issues=lambda repo: {},
            list_archived_issues=lambda _repo: {},
        )

        self.assertTrue(result["issues"][0]["created"])
        self.assertEqual(result["issues"][0]["url"], "https://example.test/issue/1")
        self.assertEqual(calls[0][0], "QuantStrategyLab/IssueRepo")

    def test_non_dry_run_skips_existing_open_issue(self) -> None:
        calls: list[tuple[str, str, str]] = []
        payload = _performance_payload()
        dry_result = run_watcher(payload, dry_run=True)
        issue_key = dry_result["issues"][0]["watcher_issue_key"]

        result = run_watcher(
            payload,
            source_repo="QuantStrategyLab/TestStrategies",
            dry_run=False,
            create_issue=lambda repo, title, body: calls.append((repo, title, body)) or "https://example.test/new",
            comment_issue=lambda repo, url, body: "https://example.test/comment",
            read_issue=lambda _repo, _url: {
                "state": "OPEN",
                "body": f"- Event key: `{dry_result['issues'][0]['task']['event_key']}`",
                "comments": [],
            },
            list_issues=lambda repo: {issue_key: "https://example.test/existing"},
            list_archived_issues=lambda _repo: {},
        )

        self.assertFalse(result["issues"][0]["created"])
        self.assertEqual(result["issues"][0]["existing_url"], "https://example.test/existing")
        self.assertNotIn("comment_url", result["issues"][0])
        self.assertNotIn("commented", result["issues"][0])
        self.assertEqual(result["issues"][0]["skipped_reason"], "same watcher event already recorded")
        self.assertEqual(calls, [])

    def test_new_event_comments_existing_issue_once_and_reuses_url(self) -> None:
        payload = _performance_payload() | {"generated_at": "2026-08-21T00:00:00Z"}
        original = run_watcher(_performance_payload(), dry_run=True)
        issue_key = original["issues"][0]["watcher_issue_key"]
        old_event = original["issues"][0]["task"]["event_key"]
        comments: list[str] = []
        result = run_watcher(
            payload,
            source_repo="QuantStrategyLab/TestStrategies",
            dry_run=False,
            comment_issue=lambda _repo, _url, body: comments.append(body) or "https://example.test/comment",
            read_issue=lambda _repo, _url: {
                "state": "OPEN", "body": f"- Event key: `{old_event}`", "comments": [],
            },
            list_issues=lambda _repo: {issue_key: "https://example.test/existing"},
            list_archived_issues=lambda _repo: {},
        )
        self.assertEqual(result["issues"][0]["existing_url"], "https://example.test/existing")
        self.assertEqual(result["issues"][0]["comment_url"], "https://example.test/comment")
        self.assertEqual(len(comments), 1)

    def test_uncertain_comment_write_is_not_retried_for_duplicate_event_in_same_run(self) -> None:
        payload = {
            "repo": "QuantStrategyLab/TestStrategies",
            "snapshots": [_performance_payload(), _performance_payload()],
        }
        dry = run_watcher(payload, dry_run=True)
        issue_key = dry["issues"][0]["watcher_issue_key"]
        calls: list[str] = []

        def fail_comment(_repo: str, _url: str, _body: str) -> str:
            calls.append("attempt")
            raise RuntimeError("comment result unknown")

        result = run_watcher(
            payload,
            source_repo="QuantStrategyLab/TestStrategies",
            dry_run=False,
            comment_issue=fail_comment,
            read_issue=lambda _repo, _url: {"state": "OPEN", "body": "- Event key: `old-event`", "comments": []},
            list_issues=lambda _repo: {issue_key: "https://example.test/existing"},
            list_archived_issues=lambda _repo: {},
        )
        self.assertEqual(len(calls), 1)
        self.assertIn("error", result["issues"][0])
        self.assertEqual(
            result["issues"][0]["skipped_reason"],
            "existing issue state or comment outcome unavailable; no further attempt in this run",
        )
        self.assertEqual(result["issues"][1]["skipped_reason"], "same watcher event already attempted in this run")

    def test_resolve_input_path_rejects_metrics_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                resolve_input_path(source_root=tmp, metrics_path="../outside.json")
            with self.assertRaises(ValueError):
                resolve_input_path(source_root=tmp, metrics_path="/tmp/outside.json")

    def test_resolve_input_path_accepts_source_relative_metrics_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            resolved = resolve_input_path(source_root=tmp, metrics_path="data/output/strategy_metrics.json")

        self.assertTrue(str(resolved).endswith("data/output/strategy_metrics.json"))

    def test_find_existing_open_issue_paginates_until_exact_match(self) -> None:
        calls: list[list[str]] = []
        first_page = [{"title": f"other-{i}", "body": "", "html_url": f"https://example.test/{i}"} for i in range(100)]
        second_page = [{"title": "target", "body": "<!-- strategy-optimization-watcher:abc12345 -->", "html_url": "https://example.test/target"}]

        def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(cmd)
            page = "2" if "page=2" in cmd else "1"
            payload = second_page if page == "2" else first_page
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

        with patch("quant_platform_kit.strategy_lifecycle.watch.runner.subprocess.run", fake_run):
            issues = list_open_issue_urls("QuantStrategyLab/TestStrategies")

        self.assertEqual(issues["abc12345"], "https://example.test/target")
        self.assertEqual(len(calls), 2)
        self.assertIn("--method", calls[0])
        self.assertIn("GET", calls[0])

    def test_run_watcher_requires_source_repo_for_non_dry_run(self) -> None:
        with self.assertRaises(ValueError):
            run_watcher(
                _performance_payload(),
                dry_run=False,
            )

    def test_run_watcher_rejects_mismatched_source_repo_payload(self) -> None:
        with self.assertRaises(ValueError):
            run_watcher(
                _performance_payload(repo="QuantStrategyLab/Other"),
                source_repo="QuantStrategyLab/TestStrategies",
            )

    def test_run_watcher_uses_validated_source_repo_in_task_summary(self) -> None:
        result = run_watcher(
            _performance_payload(repo="", profile="live"),
            source_repo="QuantStrategyLab/TestStrategies",
            dry_run=True,
        )

        self.assertIn("QuantStrategyLab/TestStrategies:live", result["issues"][0]["title"])
        self.assertNotRegex(result["issues"][0]["title"], r"\[[a-f0-9]{12}\]$")
        self.assertEqual(result["issues"][0]["task"]["proposed_action"]["target"], "QuantStrategyLab/TestStrategies")

    def test_run_watcher_records_issue_errors_per_finding(self) -> None:
        payload = {
            "repo": "QuantStrategyLab/TestStrategies",
            "snapshots": [
                _performance_payload(profile="a"),
                _performance_payload(profile="b", sharpe=0.4),
            ],
        }

        result = run_watcher(
            payload,
            source_repo="QuantStrategyLab/TestStrategies",
            dry_run=False,
            create_issue=lambda repo, title, body: (_ for _ in ()).throw(RuntimeError("boom")) if ":a" in title else "https://example.test/new",
            comment_issue=lambda repo, url, body: "https://example.test/comment",
            list_issues=lambda repo: {},
            list_archived_issues=lambda _repo: {},
        )

        self.assertEqual(result["status"], "partial_error")
        self.assertEqual(result["errors"], 1)
        self.assertEqual(len(result["issues"]), 2)

    def test_run_watcher_updates_cache_after_create(self) -> None:
        create_calls: list[tuple[str, str, str]] = []
        payload = {
            "repo": "QuantStrategyLab/TestStrategies",
            "snapshots": [
                _performance_payload(profile="same"),
                _performance_payload(profile="same"),
            ],
        }

        result = run_watcher(
            payload,
            source_repo="QuantStrategyLab/TestStrategies",
            dry_run=False,
            create_issue=lambda repo, title, body: create_calls.append((repo, title, body)) or "https://example.test/new",
            comment_issue=lambda repo, url, body: "https://example.test/comment",
            list_issues=lambda repo: {},
            list_archived_issues=lambda _repo: {},
        )

        self.assertEqual(result["findings"], 2)
        self.assertEqual(len(create_calls), 1)
        self.assertEqual(result["issues"][1]["existing_url"], "https://example.test/new")

    def test_run_watcher_caches_open_issues_per_repo(self) -> None:
        list_calls: list[str] = []
        create_calls: list[tuple[str, str, str]] = []
        payload = {
            "repo": "QuantStrategyLab/TestStrategies",
            "snapshots": [
                _performance_payload(profile="a"),
                _performance_payload(profile="b", sharpe=0.4),
            ],
        }

        result = run_watcher(
            payload,
            source_repo="QuantStrategyLab/TestStrategies",
            dry_run=False,
            create_issue=lambda repo, title, body: create_calls.append((repo, title, body)) or "https://example.test/new",
            list_issues=lambda repo: list_calls.append(repo) or {},
            list_archived_issues=lambda _repo: {},
        )

        self.assertEqual(result["findings"], 2)
        self.assertEqual(list_calls, ["QuantStrategyLab/TestStrategies"])
        self.assertEqual(len(create_calls), 2)

    def test_closed_archive_lookup_failure_never_creates_or_emits_tasks(self) -> None:
        created: list[tuple[str, str, str]] = []
        result = run_watcher(
            _verified_p3_payload(),
            source_repo="QuantStrategyLab/UsEquitySnapshotPipelines",
            dry_run=False,
            list_issues=lambda _repo: {},
            list_archived_issues=lambda _repo: (_ for _ in ()).throw(RuntimeError("closed state unavailable")),
            create_issue=lambda repo, title, body: created.append((repo, title, body)) or "https://example.test/new",
        )

        self.assertEqual(result["status"], "partial_error")
        self.assertEqual(result["errors"], 1)
        self.assertEqual(created, [])
        self.assertEqual(result["research_task_source_snapshot"]["tasks"], [])
        self.assertEqual(result["blocked_research_task_ids"], ["watcher-" + result["issues"][0]["task"]["event_key"]])

    def test_trusted_archived_issue_is_reused_without_recreating_task(self) -> None:
        payload = _verified_p3_payload()
        dry = run_watcher(payload, source_repo="QuantStrategyLab/UsEquitySnapshotPipelines", dry_run=True)
        issue = dry["issues"][0]
        key = issue["watcher_issue_key"]
        result = run_watcher(
            payload,
            source_repo="QuantStrategyLab/UsEquitySnapshotPipelines",
            dry_run=False,
            list_issues=lambda _repo: {},
            list_archived_issues=lambda _repo: {key: "https://github.com/QuantStrategyLab/UsEquitySnapshotPipelines/issues/123"},
            create_issue=lambda *_: (_ for _ in ()).throw(AssertionError("archived issue must not be recreated")),
        )
        self.assertTrue(result["issues"][0]["archived"])
        self.assertEqual(result["research_task_source_snapshot"]["tasks"], [])
        self.assertEqual(result["archived_research_task_ids"], [issue["task"]["event_key"] and "watcher-" + issue["task"]["event_key"]])

    def test_closed_archive_marker_requires_trusted_identity_and_scope(self) -> None:
        body = "<!-- strategy-optimization-watcher:abc12345 -->\n<!-- research-scope-archived:{\"automation\":\"strategy_optimization_watcher\",\"issue_number\":123,\"reason\":\"idle_timeout\",\"repository\":\"QuantStrategyLab/TestStrategies\",\"scope_key\":\"" + "a" * 64 + "\",\"ticket_id\":\"rpt_x\",\"watcher_issue_key\":\"abc12345\"} -->"
        issue = {"state": "closed", "number": 123, "body": body, "html_url": "https://github.com/QuantStrategyLab/TestStrategies/issues/123",
                 "user": {"login": "strategy-watcher[bot]"}, "closed_by": {"login": "strategy-watcher[bot]"}}
        with patch("quant_platform_kit.strategy_lifecycle.watch.runner.subprocess.run", side_effect=[
            subprocess.CompletedProcess([], 0, stdout=json.dumps([issue]), stderr=""),
            subprocess.CompletedProcess([], 0, stdout=json.dumps(issue), stderr=""),
        ]):
            self.assertEqual(list_archived_issue_urls("QuantStrategyLab/TestStrategies")["abc12345"], issue["html_url"])

    def test_list_open_issue_urls_fails_closed_on_bad_json(self) -> None:
        def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(cmd, 0, stdout="not-json", stderr="")

        with patch("quant_platform_kit.strategy_lifecycle.watch.runner.subprocess.run", fake_run):
            with self.assertRaises(RuntimeError):
                list_open_issue_urls("QuantStrategyLab/TestStrategies")

    def test_parse_bool_defaults_safely(self) -> None:
        self.assertTrue(parse_bool("true"))
        self.assertFalse(parse_bool("false"))
        self.assertTrue(parse_bool(None, default=True))
        with self.assertRaises(ValueError):
            parse_bool("flase")

    def test_run_watcher_opens_data_quality_finding_for_operational_payload(self) -> None:
        result = run_watcher(
            {
                "repo": "QuantStrategyLab/TestStrategies",
                "profile": "live",
                "schema_version": "strategy_operational_metrics.v1",
                "metrics_kind": "operational_quality",
                "current_metrics": {"pool_size": 10},
                "baseline_metrics": {"pool_size": 9},
            },
            dry_run=True,
        )

        self.assertEqual(result["findings"], 1)
        self.assertEqual(result["issues"][0]["task"]["trigger"]["kind"], "strategy_metrics_contract_invalid")
        self.assertEqual(result["issues"][0]["task"]["proposed_action"]["target"], "QuantStrategyLab/TestStrategies")
        self.assertEqual(result["issues"][0]["task"]["finding_type"], "data_quality")


class RunCoverageReaderTest(unittest.TestCase):
    def setUp(self):
        self.external_guards = guard_external_io(self)
        self.forbidden_callbacks = {
            name: Mock(name="forbidden_" + name, side_effect=AssertionError("external issue callback forbidden"))
            for name in ("create_issue", "comment_issue", "read_issue", "list_issues", "list_archived_issues")
        }
        # The product binds callbacks at definition time. Patching module names
        # alone would not isolate run_watcher, main, or direct dispatch.
        for entrypoint in (run_watcher, dispatch_strategy_watch_findings):
            guard = patch.dict(entrypoint.__kwdefaults__, self.forbidden_callbacks)
            guard.start()
            self.addCleanup(guard.stop)
        self.addCleanup(self.assert_no_issue_callback_attempts)

    def assert_no_issue_callback_attempts(self):
        for callback in self.forbidden_callbacks.values():
            callback.assert_not_called()

    def test_coverage_run_never_dispatches_issues_research_or_metric_provider(self):
        for requested in [False,True]:
            payload=coverage_export_fixture(gap=True,requested=requested)
            with patch("quant_platform_kit.strategy_lifecycle.watch.runner.dispatch_strategy_watch_findings") as dispatch, \
                 patch.object(watch,"evaluate_strategy_metrics") as evaluator, \
                 patch.object(watch,"build_strategy_diagnosis_task") as builder:
                result=run_watcher(payload,source_repo="QuantStrategyLab/CryptoStrategies",dry_run=False)
                dispatch.assert_not_called()
                evaluator.assert_not_called()
                builder.assert_not_called()
            self.assertEqual(result["findings"],0)
            self.assertEqual(result["issues"],[])
            self.assertEqual(result["research_task_source_snapshot"]["tasks"],[])
            self.assertEqual(result["research_task_source_snapshot"]["data_status"],"unavailable")
            self.assertIn("interval_scope_binding_unavailable",result["research_task_source_snapshot"]["errors"])
            self.assertEqual(result["coverage_status"][0]["effective_window"]["return_count"],4)
            self.assertNotIn("provenance",json.dumps(result))
            self.assertNotIn("metadata",json.dumps(result))

    def test_wrapped_identity_cannot_bypass_validated_repo_or_domain(self):
        for key,value in [("repo","QuantStrategyLab/Other"),("repository","QuantStrategyLab/Other"),("domain","us_equity")]:
            payload=coverage_export_fixture()
            payload["snapshots"][0]["payload"][key]=value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError,"repository|domain"):
                run_watcher(payload,source_repo="QuantStrategyLab/CryptoStrategies",dry_run=False)
        payload=coverage_export_fixture()
        payload["snapshots"][0]["payload"]["metadata"]["domain"]="us_equity"
        with self.assertRaisesRegex(ValueError,"domain"):
            run_watcher(payload,source_repo="QuantStrategyLab/CryptoStrategies",dry_run=False)

    def test_trusted_repository_domain_cannot_be_redeclared_through_wrapper(self):
        payload=coverage_export_fixture()
        payload["domain"]="us_equity"
        payload["snapshots"][0]["payload"]["metadata"]["domain"]="us_equity"
        with self.assertRaisesRegex(ValueError,"domain"):
            run_watcher(payload,source_repo="QuantStrategyLab/CryptoStrategies",dry_run=False)

    def test_invalid_coverage_is_unavailable_without_external_interfaces(self):
        payload=coverage_export_fixture()
        payload["snapshots"][0]["payload"]["metadata"]["interval_return_coverage"]["return_count"]=True
        with patch("quant_platform_kit.strategy_lifecycle.watch.runner.dispatch_strategy_watch_findings") as dispatch:
            result=run_watcher(payload,source_repo="QuantStrategyLab/CryptoStrategies",dry_run=False)
            dispatch.assert_not_called()
        self.assertEqual(result["findings"],0)
        self.assertEqual(result["coverage_status"][0]["read_status"],"invalid")
        self.assertEqual(result["research_task_source_snapshot"]["data_status"],"unavailable")

    def test_mixed_runner_preserves_legacy_p3_issue_and_task_exactly(self):
        legacy=_verified_p3_payload()
        legacy.update(repo="QuantStrategyLab/CryptoStrategies",domain="crypto",profile="crypto_legacy_p3_case")
        callbacks={"source_repo":"QuantStrategyLab/CryptoStrategies","dry_run":False,
                   "create_issue":Mock(return_value="https://github.com/QuantStrategyLab/CryptoStrategies/issues/1"),
                   "list_issues":Mock(side_effect=lambda _repo:{}),"list_archived_issues":Mock(side_effect=lambda _repo:{}),
                   "read_issue":Mock(side_effect=AssertionError("unexpected issue read")),
                   "comment_issue":Mock(side_effect=AssertionError("unexpected comment"))}
        baseline=run_watcher(legacy,**callbacks)
        self.assertEqual(len(baseline["research_task_source_snapshot"]["tasks"]),1)
        payload=coverage_export_fixture()
        payload["snapshots"].append({"schema_version":payload["schema_version"],"metrics_kind":"performance","payload":legacy})
        result=run_watcher(payload,**callbacks)
        self.assertEqual(result["issues"],baseline["issues"])
        self.assertEqual(result["research_task_source_snapshot"]["tasks"],baseline["research_task_source_snapshot"]["tasks"])
        self.assertEqual(result["research_task_source_snapshot"]["data_status"],"ready")
        self.assertEqual(result["findings"],1)
        self.assertEqual(result["coverage_status"][0]["optimization_status"],"unavailable")
        self.assertEqual(callbacks["create_issue"].call_count, 2)
        self.assertEqual(callbacks["list_issues"].call_count, 2)
        self.assertEqual(callbacks["list_archived_issues"].call_count, 2)
        callbacks["read_issue"].assert_not_called()
        callbacks["comment_issue"].assert_not_called()

    def test_direct_dispatch_cannot_reopen_coverage_issue_lane(self):
        snapshot=watch.StrategyWatchSnapshot.from_dict(coverage_export_fixture()["snapshots"][0]["payload"])
        finding=watch.StrategyWatchFinding(snapshot,"high",[])
        result=dispatch_strategy_watch_findings([finding],source_repo="QuantStrategyLab/CryptoStrategies",dry_run=False)
        self.assertEqual(result["findings"],0)
        self.assertEqual(result["issues"],[])

    def test_main_reads_real_envelope_and_prints_safe_unavailable_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"coverage.json"
            path.write_text(json.dumps(coverage_export_fixture()))
            output=StringIO()
            with patch.dict(os.environ,{"STRATEGY_WATCH_INPUT":str(path),"STRATEGY_WATCH_SOURCE_ROOT":"",
                    "STRATEGY_WATCH_METRICS_PATH":"","STRATEGY_WATCH_SOURCE_REPO":"QuantStrategyLab/CryptoStrategies",
                    "STRATEGY_WATCH_DRY_RUN":"false"}), redirect_stdout(output):
                self.assertEqual(main(),0)
            result=json.loads(output.getvalue())
            self.assertEqual(result["issues"],[])
            self.assertEqual(result["research_task_source_snapshot"]["tasks"],[])
            self.assertEqual(result["coverage_status"][0]["comparison_status"],"unknown")


if __name__ == "__main__":
    unittest.main()
