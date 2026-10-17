"""Offline acceptance of the two monitor entrypoints; no real GH adapters.

Run directly with Python -I -S -B. The audit guard is installed before the
actual package import, including the unchanged base namespace initializers.
"""
from __future__ import annotations

import copy
from dataclasses import replace
import importlib
import json
import os
from pathlib import Path
import sys
import unittest


REPO = Path(__file__).resolve().parents[1]
JOB = REPO.parent
GUARD = {"denied": [], "external_attempts": 0, "outside_write_attempts": 0}
sys.path.insert(0, str(REPO / "src"))


def check_path(value, *, write=False):
    if value is None or isinstance(value, int):
        return
    path = Path(os.fsdecode(value)).resolve()
    if write and not path.is_relative_to(JOB):
        GUARD["outside_write_attempts"] += 1
        raise PermissionError("offline: write outside E")
    if path.is_relative_to(Path("/Users/lisiyi")) and not path.is_relative_to(JOB):
        raise PermissionError("offline: non-allowlisted user read")
    if any(part.lower() in {".codex", ".ssh", ".aws", "keychains"} for part in path.parts):
        raise PermissionError("offline: protected path")


def audit(event, args):
    try:
        if event.startswith("socket.") or event in {
            "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn",
            "os.fork", "pty.spawn", "ctypes.dlopen",
        }:
            GUARD["external_attempts"] += 1
            raise PermissionError("offline: external/process/native call")
        if event == "open":
            mode, flags = args[1:3]
            write = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
                isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
            )
            check_path(args[0], write=write)
        elif event in {"os.listdir", "os.scandir"}:
            check_path(args[0])
        elif event in {"os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.truncate", "os.utime"}:
            check_path(args[0], write=True)
        elif event in {"os.rename", "os.link", "os.symlink"}:
            check_path(args[0], write=True)
            check_path(args[1], write=True)
    except PermissionError:
        GUARD["denied"].append({"event": event, "path": str(args[0]) if args else ""})
        raise


sys.addaudithook(audit)


def modules():
    return (
        importlib.import_module("quant_platform_kit.strategy_lifecycle.watch.runner"),
        importlib.import_module("quant_platform_kit.strategy_lifecycle.watch.strategy_watch"),
    )


class ImportTests(unittest.TestCase):
    def test_actual_parent_namespace_and_two_entrypoints(self):
        runner, watch = modules()
        for name in ["quant_platform_kit", "quant_platform_kit.strategy_lifecycle", runner.__name__, watch.__name__]:
            self.assertTrue(Path(sys.modules[name].__file__).resolve().is_relative_to(REPO / "src"))
        self.assertTrue(callable(runner.dispatch_strategy_watch_findings))
        self.assertTrue(callable(watch.build_strategy_monitoring_finding))
        for name in ["run_watcher", "main", "run_research_input_terminal_watcher"]:
            self.assertFalse(hasattr(runner, name))
        for name in ["evaluate_strategy_watch", "finding_to_research_task", "research_task_source_snapshot"]:
            self.assertFalse(hasattr(watch, name))
        for name in sys.modules:
            self.assertNotIn(name.rsplit(".", 1)[-1], {
                "ai_provider", "research_task", "strategy_automation_registry", "strategy_optimization_policy",
            })


class FakeGH:
    """All five adapters are passed explicitly; records are synthetic memory."""

    def __init__(self, runner, watch):
        self.runner, self.watch = runner, watch
        self.calls = []
        self.open = {}
        self.archives = []
        self.read = {"body": "", "comments": []}
        self.fail = set()

    def call(self, name, *args):
        self.calls.append((name, args))
        if name in self.fail:
            raise RuntimeError("synthetic " + name + " unavailable")

    def create(self, repo, title, body):
        self.call("create", repo, title, body)
        return "https://github.com/" + repo + "/issues/7"

    def comment(self, repo, url, body):
        self.call("comment", repo, url, body)
        return url + "#issuecomment-1"

    def read_issue(self, repo, url):
        self.call("read", repo, url)
        return copy.deepcopy(self.read)

    def list_open(self, repo):
        self.call("open", repo)
        return dict(self.open)

    def list_archived(self, repo):
        self.call("archived", repo)
        result = {}
        for key, record in self.archives:
            if self.runner._archived_watcher_issue(record, repository=repo, watcher_key=key):
                result[key] = record["html_url"]
        return result

    def dispatch(self, findings, **kwargs):
        return self.runner.dispatch_strategy_watch_findings(
            findings,
            create_issue=self.create,
            comment_issue=self.comment,
            read_issue=self.read_issue,
            list_issues=self.list_open,
            list_archived_issues=self.list_archived,
            **kwargs,
        )

    def count(self, name):
        return sum(call[0] == name for call in self.calls)


class MonitorWatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner, cls.watch = modules()

    def setUp(self):
        self.io = FakeGH(self.runner, self.watch)
        self.finding = self.build()
        self.repo = self.finding.snapshot.repo
        self.key = self.watch.watcher_issue_key(self.watch.finding_to_automation_task(self.finding))

    def build(self, **changes):
        args = dict(domain="crypto", profile="synthetic-profile", severity="high",
                    metrics={"overall_score": 40}, signals=[{"metric": "score", "reason": "synthetic degradation"}],
                    source="synthetic/health-cycle", generated_at="2026-10-17T00:00:00Z")
        args.update(changes)
        return self.watch.build_strategy_monitoring_finding(**args)

    def archive(self):
        marker = {"automation": "strategy_optimization_watcher", "repository": self.repo,
                  "issue_number": 7, "watcher_issue_key": self.key, "scope_key": "a" * 64,
                  "ticket_id": "synthetic-ticket", "reason": "idle_timeout"}
        return {"number": 7, "state": "CLOSED", "html_url": "https://github.com/" + self.repo + "/issues/7",
                "body": "<!-- strategy-optimization-watcher:" + self.key + " -->\n<!-- research-scope-archived:"
                + json.dumps(marker) + " -->", "user": {"login": "synthetic[bot]"},
                "closed_by": {"login": "synthetic[bot]"}}

    def test_builder_contract_and_issue_only_permission_fields(self):
        finding = self.finding
        self.assertEqual(finding.finding_type, "monitoring_trigger")
        self.assertEqual(finding.snapshot.schema_version, "strategy_monitoring_evidence.v1")
        self.assertEqual(finding.snapshot.metrics_kind, "monitoring_evidence")
        self.assertEqual(finding.snapshot.subject(), self.repo + ":synthetic-profile")
        task = self.watch.finding_to_automation_task(finding)
        data = task.to_dict()
        self.assertEqual(data["proposed_action"]["action"], "open_issue")
        self.assertEqual(data["proposed_action"]["lane"], "research_backlog")
        self.assertFalse(data["proposed_action"]["requires_human_review"])
        self.assertTrue(data["gate_decision"]["allowed"])
        self.assertFalse(data["gate_decision"]["human_review_required"])
        self.assertEqual(data["gate_decision"]["metadata"], {"issue_only": True, "live_impact_allowed": False})
        self.assertEqual(len(data["gate_decision"]["required_checks"]), 3)
        issue = self.watch.issue_for_task(task)
        self.assertIn("<!-- strategy-optimization-watcher:" + self.key + " -->", issue["body"])
        self.assertIn("does not modify strategy code", issue["body"])
        self.assertIn("submit orders", issue["body"])
        self.assertEqual(self.key, self.watch.watcher_issue_key(task))

    def test_domain_routes_unknown_and_explicit_override(self):
        for domain, repository in [("crypto", "CryptoStrategies"), ("cn_equity", "CnEquityStrategies"),
                                   ("hk_equity", "HkEquityStrategies"), ("us_equity", "UsEquityStrategies")]:
            with self.subTest(domain=domain):
                self.assertEqual(self.build(domain=domain).snapshot.repo, "QuantStrategyLab/" + repository)
        for changes in [{"domain": "unknown"}, {"profile": ""}, {"domain": ""}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.build(**changes)
        override = self.build(domain="unknown", repo="QuantStrategyLab/SyntheticRepo", severity="other")
        self.assertEqual(override.severity, "medium")
        result = self.io.dispatch([override], dry_run=True)
        self.assertEqual(result["issues"][0]["repo"], "QuantStrategyLab/SyntheticRepo")
        self.assertEqual(self.io.calls, [])

    def test_invalid_repository_and_source_override_reject_before_io(self):
        for kwargs in [{"findings": [self.build(repo="bad path")]},
                       {"findings": [self.finding], "source_repo": "bad/path/extra"}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.io.dispatch(**kwargs, dry_run=False)
        self.assertEqual(self.io.calls, [])

    def test_coverage_context_and_coverage_schema_cannot_authorize_issue(self):
        for snapshot in [replace(self.finding.snapshot, coverage_context={"coverage_status": "partial"}),
                         replace(self.finding.snapshot, schema_version="strategy_performance.coverage_envelope.v1")]:
            finding = replace(self.finding, snapshot=snapshot)
            with self.subTest(snapshot=snapshot):
                with self.assertRaises(ValueError):
                    self.watch.finding_to_automation_task(finding)
                result = self.io.dispatch([finding], dry_run=False)
                self.assertEqual(result["findings"], 0)
                self.assertEqual(result["issues"], [])
        self.assertEqual(self.io.calls, [])

    def test_snapshot_from_dict_retains_coverage_identity_rejection(self):
        snapshot = self.watch.StrategyWatchSnapshot.from_dict(
            {"schema_version": "strategy_performance.coverage_envelope.v1", "metrics_kind": "performance",
             "payload": {"repo": self.repo, "schema_version": "strategy_performance.v2",
                         "metrics_kind": "performance", "profile": "synthetic-profile"}},
            default_repo="QuantStrategyLab/OtherRepo",
        )
        self.assertTrue(snapshot.coverage_context)
        with self.assertRaises(ValueError):
            self.watch.finding_to_automation_task(replace(self.finding, snapshot=snapshot))
        self.assertEqual(self.io.dispatch([replace(self.finding, snapshot=snapshot)], dry_run=False)["findings"], 0)

    def test_dry_run_calls_no_adapter(self):
        result = self.io.dispatch([self.finding], dry_run=True)
        self.assertEqual((result["status"], result["errors"], result["findings"]), ("ok", 0, 1))
        self.assertTrue(result["issues"][0]["dry_run"])
        self.assertEqual(self.io.calls, [])

    def test_current_caller_create_once_and_same_key_cache_dedup(self):
        changed = self.build(metrics={"overall_score": 30})
        result = self.io.dispatch([self.finding, changed, self.finding], dry_run=False, comment_existing=False)
        self.assertEqual((result["errors"], result["findings"]), (0, 3))
        self.assertEqual(sum(i["created"] for i in result["issues"]), 1)
        self.assertEqual([self.io.count(k) for k in ["open", "archived", "create", "read", "comment"]], [1, 1, 1, 0, 0])
        self.assertEqual(result["issues"][1]["skipped_reason"], "open issue already records this strategy")

    def test_current_caller_existing_issue_skips_read_comment_and_archive(self):
        self.io.open = {self.key: "https://github.com/" + self.repo + "/issues/7"}
        result = self.io.dispatch([self.finding], dry_run=False, comment_existing=False)
        self.assertFalse(result["issues"][0]["created"])
        self.assertEqual([self.io.count(k) for k in ["open", "archived", "create", "read", "comment"]], [1, 0, 0, 0, 0])

    def test_archive_trust_rejects_forged_identity_markers_and_prs(self):
        good = self.archive()
        self.assertTrue(self.runner._archived_watcher_issue(good, repository=self.repo, watcher_key=self.key))
        variations = [{"state": "OPEN"}, {"number": True}, {"number": 8}, {"html_url": "https://github.com/Other/Repo/issues/7"},
                      {"user": {"login": "human"}}, {"closed_by": {"login": "other[bot]"}}, {"pull_request": {}},
                      {"body": good["body"].replace('"scope_key": "' + 'a' * 64, '"scope_key": "bad')},
                      {"body": good["body"].replace('"idle_timeout"', '"arbitrary_reason"')},
                      {"body": good["body"].replace(self.repo, "Other/Repo")},
                      {"body": "<!-- strategy-optimization-watcher:" + self.key + " -->\n<!-- research-scope-archived:{bad} -->"}]
        for changes in variations:
            with self.subTest(changes=changes):
                self.assertFalse(self.runner._archived_watcher_issue({**good, **changes}, repository=self.repo, watcher_key=self.key))

    def test_trusted_archive_suppresses_but_untrusted_archive_does_not(self):
        for trusted in [True, False]:
            io = FakeGH(self.runner, self.watch)
            archive = self.archive()
            if not trusted:
                archive["closed_by"] = {"login": "different[bot]"}
            io.archives = [(self.key, archive)]
            result = io.dispatch([self.finding], dry_run=False, comment_existing=False)
            self.assertEqual(result["errors"], 0)
            self.assertEqual(io.count("create"), 0 if trusted else 1)
            self.assertEqual(result["issues"][0].get("archived", False), trusted)

    def test_archive_failure_blocks_creation_and_further_archive_attempts(self):
        self.io.fail = {"archived"}
        result = self.io.dispatch([self.finding, self.finding], dry_run=False, comment_existing=False)
        self.assertEqual((result["status"], result["errors"]), ("partial_error", 2))
        self.assertTrue(all(i["archive_lookup_failed"] for i in result["issues"]))
        self.assertEqual([self.io.count(k) for k in ["open", "archived", "create"]], [1, 1, 0])

    def test_open_lookup_error_blocks_creation(self):
        self.io.fail = {"open"}
        result = self.io.dispatch([self.finding], dry_run=False, comment_existing=False)
        self.assertEqual((result["status"], result["errors"]), ("partial_error", 1))
        self.assertEqual(self.io.count("create"), 0)
        self.assertEqual(self.io.count("archived"), 0)

    def test_create_error_is_explicit_and_not_claimed_as_created(self):
        self.io.fail = {"create"}
        result = self.io.dispatch([self.finding], dry_run=False, comment_existing=False)
        self.assertEqual(result["errors"], 1)
        self.assertFalse(result["issues"][0]["created"])
        self.assertIn("create unavailable", result["issues"][0]["error"])
        self.assertEqual(self.io.count("create"), 1)

    def test_comment_existing_known_event_is_not_repeated(self):
        self.io.open = {self.key: "https://github.com/" + self.repo + "/issues/7"}
        event = self.watch.finding_event_key(self.finding)
        self.io.read = {"body": "- Event key: `" + event + "`", "comments": []}
        result = self.io.dispatch([self.finding], dry_run=False, comment_existing=True)
        self.assertEqual(result["errors"], 0)
        self.assertEqual((self.io.count("read"), self.io.count("comment")), (1, 0))

    def test_comment_new_event_dedup_and_failure_prevent_second_attempt(self):
        for fail in [False, True]:
            io = FakeGH(self.runner, self.watch)
            io.open = {self.key: "https://github.com/" + self.repo + "/issues/7"}
            if fail:
                io.fail = {"comment"}
            result = io.dispatch([self.finding, self.finding], dry_run=False, comment_existing=True)
            self.assertEqual(result["errors"], int(fail))
            self.assertEqual((io.count("read"), io.count("comment"), io.count("create")), (1, 1, 0))
            self.assertEqual(result["issues"][1]["skipped_reason"], "same watcher event already attempted in this run")

    def test_existing_read_error_blocks_comment_and_create(self):
        self.io.open = {self.key: "https://github.com/" + self.repo + "/issues/7"}
        self.io.fail = {"read"}
        result = self.io.dispatch([self.finding], dry_run=False, comment_existing=True)
        self.assertEqual(result["errors"], 1)
        self.assertEqual((self.io.count("read"), self.io.count("comment"), self.io.count("create")), (1, 0, 0))


if __name__ == "__main__":
    import_only = "--import-only" in sys.argv
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(ImportTests)])
    if not import_only:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(MonitorWatchTests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    summary = {"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
               "skips": len(result.skipped), "guard": GUARD,
               "scope": "offline_import_builder_issue_only_fake_GH_not_monitor_readiness"}
    print(json.dumps(summary, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() and not GUARD["denied"] else 1)
