#!/usr/bin/env python3
"""Run the issue-only strategy optimization watcher."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Any, Callable, Mapping

from .strategy_watch import (  # noqa: E402
    StrategyWatchFinding,
    STRATEGY_WATCH_REGISTRY,
    _coverage_protocol_present,
    build_research_input_unavailable_finding,
    evaluate_strategy_watch,
    finding_to_automation_task,
    issue_for_task,
    research_task_context_available,
    research_task_source_snapshot,
    finding_to_research_task,
    watcher_issue_key,
    strategy_watch_coverage_status,
)

REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ISSUE_URL_RE = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/issues/([1-9][0-9]*)$")
EVENT_KEY_RE = re.compile(r"- Event key:\s*`([^`]+)`")


def parse_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise ValueError("boolean value must be one of true/false/yes/no/on/off/1/0")


def resolve_input_path(
    *,
    input_path: str = "",
    source_root: str = "",
    metrics_path: str = "",
) -> Path | None:
    if source_root and metrics_path:
        normalized = PurePosixPath(metrics_path.replace("\\", "/"))
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError("metrics_path must be a relative path inside the source checkout")
        root = Path(source_root).resolve()
        candidate = (root / Path(*normalized.parts)).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("metrics_path resolves outside the source checkout") from exc
        return candidate
    if not input_path:
        return None
    candidate = Path(input_path).resolve()
    if source_root:
        root = Path(source_root).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("input path resolves outside the source checkout") from exc
    return candidate


def load_payload(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("strategy watch input must be a JSON object")
    return payload


def list_open_issue_urls(repo: str) -> dict[str, str]:
    if not REPO_RE.fullmatch(repo):
        raise ValueError("repository must be in owner/name form")
    page = 1
    open_issues: dict[str, str] = {}
    while True:
        result = subprocess.run(
            ["gh", "api", "--method", "GET", f"/repos/{repo}/issues", "-f", "state=open", "-f", "per_page=100", "-f", f"page={page}"],
            check=True,
            capture_output=True,
            text=True,
        )
        try:
            issues = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            raise RuntimeError("failed to parse open issue list") from exc
        if not isinstance(issues, list) or not issues:
            return open_issues
        for issue in issues:
            if not isinstance(issue, dict) or "pull_request" in issue:
                continue
            body = str(issue.get("body") or "")
            match = re.search(r"<!--\s*strategy-optimization-watcher:([A-Za-z0-9_-]{8,64})\s*-->", body)
            if match and match.group(1) not in open_issues:
                open_issues[match.group(1)] = str(issue.get("html_url") or issue.get("url") or "")
        if len(issues) < 100:
            return open_issues
        page += 1


_ARCHIVE_MARKER_RE = re.compile(r"<!--\s*research-scope-archived:(\{.*?\})\s*-->")


def _archived_watcher_issue(issue: Any, *, repository: str, watcher_key: str) -> bool:
    if not isinstance(issue, dict) or "pull_request" in issue:
        return False
    if str(issue.get("state") or "").upper() != "CLOSED":
        return False
    number = issue.get("number")
    if type(number) is not int or number <= 0:
        return False
    body = str(issue.get("body") or "")
    if f"<!-- strategy-optimization-watcher:{watcher_key} -->" not in body:
        return False
    match = _ARCHIVE_MARKER_RE.search(body)
    if not match:
        return False
    try:
        marker = json.loads(match.group(1))
    except (TypeError, ValueError):
        return False
    return (
        isinstance(marker, dict)
        and marker.get("automation") == "strategy_optimization_watcher"
        and marker.get("repository") == repository
        and marker.get("issue_number") == number
        and marker.get("watcher_issue_key") == watcher_key
        and isinstance(marker.get("scope_key"), str)
        and bool(re.fullmatch(r"[0-9a-f]{64}", marker["scope_key"]))
        and isinstance(marker.get("ticket_id"), str)
        and bool(marker["ticket_id"])
        and marker.get("reason") in {"no_improvement_limit", "idle_timeout"}
        and isinstance(issue.get("html_url"), str)
        and (url_match := ISSUE_URL_RE.fullmatch(issue["html_url"])) is not None
        and url_match.group(1) == repository
        and int(url_match.group(2)) == number
        and isinstance(issue.get("user"), dict)
        and isinstance(issue.get("closed_by"), dict)
        and issue["user"].get("login") == issue["closed_by"].get("login")
        and isinstance(issue["user"].get("login"), str)
        and issue["user"]["login"].endswith("[bot]")
    )


def list_archived_issue_urls(repo: str) -> dict[str, str]:
    """Read closed Issues and suppress only trusted research archive markers."""
    if not REPO_RE.fullmatch(repo):
        raise ValueError("repository must be in owner/name form")
    page = 1
    archived: dict[str, str] = {}
    while True:
        result = subprocess.run(
            ["gh", "api", "--method", "GET", f"/repos/{repo}/issues",
             "-f", "state=closed", "-f", "per_page=100", "-f", f"page={page}"],
            check=True, capture_output=True, text=True,
        )
        try:
            issues = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            raise RuntimeError("failed to parse closed issue list") from exc
        if not isinstance(issues, list) or not issues:
            return archived
        for issue in issues:
            if not isinstance(issue, dict) or "pull_request" in issue:
                continue
            body = str(issue.get("body") or "")
            watcher_match = re.search(r"<!--\s*strategy-optimization-watcher:([A-Za-z0-9_-]{8,64})\s*-->", body)
            if not watcher_match or str(issue.get("state") or "").upper() != "CLOSED":
                continue
            try:
                detail = subprocess.run(
                    ["gh", "api", "--method", "GET", f"/repos/{repo}/issues/{issue['number']}"],
                    check=True, capture_output=True, text=True,
                )
                detail_issue = json.loads(detail.stdout or "{}")
            except (KeyError, OSError, ValueError, subprocess.CalledProcessError):
                raise RuntimeError("failed to verify closed watcher issue") from None
            if not _archived_watcher_issue(detail_issue, repository=repo, watcher_key=watcher_match.group(1)):
                continue
            url = str(detail_issue.get("html_url") or "")
            if url:
                archived[watcher_match.group(1)] = url
        if len(issues) < 100:
            return archived
        page += 1


def find_existing_open_issue(repo: str, issue_key: str) -> str:
    return list_open_issue_urls(repo).get(issue_key, "")


def task_public_summary(task: Any) -> dict[str, Any]:
    payload = task.to_dict()
    trigger = payload.get("trigger") if isinstance(payload.get("trigger"), dict) else {}
    proposed_action = payload.get("proposed_action") if isinstance(payload.get("proposed_action"), dict) else {}
    gate_decision = payload.get("gate_decision") if isinstance(payload.get("gate_decision"), dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    return {
        "trigger": {
            "source": trigger.get("source", ""),
            "kind": trigger.get("kind", ""),
            "severity": trigger.get("severity", ""),
            "subject": trigger.get("subject", ""),
            "reason": trigger.get("reason", ""),
            "signals": [
                {"reason": str(item)}
                for item in trigger.get("evidence", [])
                if isinstance(item, str)
            ],
        },
        "proposed_action": {
            "action": proposed_action.get("action", ""),
            "lane": proposed_action.get("lane", ""),
            "target": proposed_action.get("target", ""),
            "requires_human_review": proposed_action.get("requires_human_review", True),
        },
        "gate_decision": {
            "allowed": gate_decision.get("allowed", False),
            "human_review_required": gate_decision.get("human_review_required", True),
        },
        "finding_type": metadata.get("finding_type", "metric_degradation"),
        "event_key": metadata.get("event_key", ""),
        "status": payload.get("status", ""),
    }


def comment_github_issue(repo: str, issue_url: str, body: str) -> str:
    if not REPO_RE.fullmatch(repo):
        raise ValueError("repository must be in owner/name form")
    result = subprocess.run(
        ["gh", "issue", "comment", issue_url, "--repo", repo, "--body", body],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def read_existing_watcher_issue(repo: str, issue_url: str) -> dict[str, Any]:
    """Read the existing issue body/comments before appending an event update."""
    if not REPO_RE.fullmatch(repo) or not ISSUE_URL_RE.fullmatch(issue_url):
        raise ValueError("watcher issue identity is invalid")
    result = subprocess.run(
        ["gh", "issue", "view", issue_url, "--repo", repo, "--json", "state,body,comments"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    payload = json.loads(result.stdout)
    if (
        not isinstance(payload, dict)
        or str(payload.get("state") or "").upper() != "OPEN"
        or not isinstance(payload.get("body"), str)
        or not isinstance(payload.get("comments"), list)
        or any(not isinstance(item, dict) or not isinstance(item.get("body"), str) for item in payload["comments"])
    ):
        raise ValueError("existing watcher issue state is unavailable")
    return payload


def _issue_event_keys(issue: Mapping[str, Any]) -> set[str]:
    bodies = [issue.get("body")]
    comments = issue.get("comments")
    if isinstance(comments, list):
        bodies.extend(item.get("body") for item in comments if isinstance(item, Mapping))
    return {match.group(1) for body in bodies if isinstance(body, str) for match in EVENT_KEY_RE.finditer(body)}


def create_github_issue(repo: str, title: str, body: str) -> str:
    if not REPO_RE.fullmatch(repo):
        raise ValueError("repository must be in owner/name form")
    result = subprocess.run(
        ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _payload_for_source_repo(payload: dict[str, Any], source_repo: str) -> dict[str, Any]:
    if not source_repo:
        return payload
    normalized = copy.deepcopy(payload)
    raw_snapshots = normalized.get("snapshots")
    qualified = _coverage_protocol_present(normalized) or (isinstance(raw_snapshots, list)
        and any(isinstance(item, dict) and _coverage_protocol_present(item) for item in raw_snapshots))
    source_domain = next((item.domain for item in STRATEGY_WATCH_REGISTRY if item.repository == source_repo), "") if qualified else ""

    def bind_identity(item: dict[str, Any], domain: str = "") -> str:
        for key in ("repo", "repository"):
            embedded = str(item.get(key) or "").strip()
            if embedded and embedded != source_repo:
                raise ValueError("metrics payload repository does not match validated source repository")
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        domains = {str(value).strip() for value in (source_domain, domain, item.get("domain"), metadata.get("domain")) if value} if qualified else set()
        if len(domains) > 1:
            raise ValueError("metrics payload domain does not match source container domain")
        return next(iter(domains), "")

    domain = bind_identity(normalized)
    normalized["repo"] = source_repo
    raw_snapshots = normalized.get("snapshots")
    if isinstance(raw_snapshots, list):
        for item in raw_snapshots:
            if not isinstance(item, dict):
                continue
            item_domain = bind_identity(item, domain)
            if isinstance(item.get("payload"), dict):
                inner = item["payload"]
                bind_identity(inner, item_domain)
                inner["repo"] = source_repo
            else:
                item["repo"] = source_repo
    elif isinstance(normalized.get("payload"), dict):
        bind_identity(normalized["payload"], domain)
        normalized["payload"]["repo"] = source_repo
        # A standalone item is an exact three-key envelope.
        normalized.pop("repo", None)
    return normalized


def dispatch_strategy_watch_findings(
    findings: list[StrategyWatchFinding],
    *,
    source_repo: str = "",
    dry_run: bool = True,
    comment_existing: bool = True,
    create_issue: Callable[[str, str, str], str] = create_github_issue,
    comment_issue: Callable[[str, str, str], str] = comment_github_issue,
    read_issue: Callable[[str, str], dict[str, Any]] = read_existing_watcher_issue,
    list_issues: Callable[[str], dict[str, str]] = list_open_issue_urls,
    list_archived_issues: Callable[[str], dict[str, str]] = list_archived_issue_urls,
) -> dict[str, Any]:
    if source_repo and not REPO_RE.fullmatch(source_repo):
        raise ValueError("source_repo must be in owner/name form")
    findings = [finding for finding in findings if not finding.snapshot.coverage_context
                and not finding.snapshot.schema_version.startswith("strategy_performance.coverage")]
    issues: list[dict[str, Any]] = []
    open_issue_cache: dict[str, dict[str, str]] = {}
    archived_issue_cache: dict[str, dict[str, str]] = {}
    archive_lookup_failed: dict[str, str] = {}
    known_event_keys: dict[tuple[str, str], set[str]] = {}
    attempted_event_keys: dict[tuple[str, str], set[str]] = {}
    for finding in findings:
        task = finding_to_automation_task(finding)
        issue = issue_for_task(task)
        issue_key = watcher_issue_key(task)
        repo = source_repo or finding.snapshot.repo
        if not REPO_RE.fullmatch(repo):
            raise ValueError("finding repository must be in owner/name form")
        issue_result: dict[str, Any] = {
            "repo": repo,
            "title": issue["title"],
            "task": task_public_summary(task),
            "watcher_issue_key": issue_key,
            "created": False,
        }
        if dry_run:
            issue_result["dry_run"] = True
        else:
            try:
                if repo not in open_issue_cache:
                    open_issue_cache[repo] = list_issues(repo)
                existing_url = open_issue_cache[repo].get(issue_key, "")
                if existing_url:
                    issue_result["existing_url"] = existing_url
                    if comment_existing:
                        event_key = str(issue_result["task"].get("event_key") or "")
                        try:
                            if (repo, existing_url) not in known_event_keys:
                                known_event_keys[(repo, existing_url)] = _issue_event_keys(read_issue(repo, existing_url))
                            attempted = attempted_event_keys.setdefault((repo, existing_url), set())
                            if event_key in attempted:
                                issue_result["skipped_reason"] = "same watcher event already attempted in this run"
                            elif not event_key or event_key in known_event_keys[(repo, existing_url)]:
                                issue_result["skipped_reason"] = "same watcher event already recorded"
                            else:
                                attempted.add(event_key)
                                issue_result["comment_url"] = comment_issue(repo, existing_url, issue["body"])
                                issue_result["commented"] = True
                                known_event_keys[(repo, existing_url)].add(event_key)
                                issue_result["skipped_reason"] = "open issue already exists; appended new watcher event"
                        except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                            issue_result["error"] = str(exc)
                            issue_result["skipped_reason"] = "existing issue state or comment outcome unavailable; no further attempt in this run"
                    else:
                        issue_result["skipped_reason"] = "open issue already records this strategy"
                else:
                    if repo in archive_lookup_failed:
                        issue_result["archive_lookup_failed"] = True
                        issue_result["error"] = archive_lookup_failed[repo]
                        issues.append(issue_result)
                        continue
                    if repo not in archived_issue_cache:
                        try:
                            archived_issue_cache[repo] = list_archived_issues(repo)
                        except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
                            archive_lookup_failed[repo] = str(exc)
                            issue_result["archive_lookup_failed"] = True
                            issue_result["error"] = archive_lookup_failed[repo]
                            issues.append(issue_result)
                            continue
                    archived_url = archived_issue_cache[repo].get(issue_key, "")
                    if archived_url:
                        issue_result["existing_url"] = archived_url
                        issue_result["archived"] = True
                        issue_result["skipped_reason"] = "trusted archived research scope"
                    else:
                        issue_result["url"] = create_issue(repo, issue["title"], issue["body"])
                        open_issue_cache[repo][issue_key] = str(issue_result["url"])
                        known_event_keys[(repo, str(issue_result["url"]))] = {
                            str(issue_result["task"].get("event_key") or "")
                        }
                        issue_result["created"] = True
            except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
                issue_result["error"] = str(exc)
        issues.append(issue_result)
    errors = sum(1 for issue in issues if issue.get("error"))
    return {
        "status": "partial_error" if errors else "ok",
        "dry_run": dry_run,
        "findings": len(findings),
        "issues": issues,
        "errors": errors,
    }


def run_watcher(
    payload: dict[str, Any],
    *,
    source_repo: str = "",
    dry_run: bool = True,
    task_builder=finding_to_research_task,
    create_issue: Callable[[str, str, str], str] = create_github_issue,
    comment_issue: Callable[[str, str, str], str] = comment_github_issue,
    read_issue: Callable[[str, str], dict[str, Any]] = read_existing_watcher_issue,
    list_issues: Callable[[str], dict[str, str]] = list_open_issue_urls,
    list_archived_issues: Callable[[str], dict[str, str]] = list_archived_issue_urls,
) -> dict[str, Any]:
    if not dry_run and not source_repo:
        raise ValueError("source_repo is required for non-dry-run strategy watcher runs")
    if source_repo and not REPO_RE.fullmatch(source_repo):
        raise ValueError("source_repo must be in owner/name form")
    watch_payload = _payload_for_source_repo(payload, source_repo)
    findings = evaluate_strategy_watch(watch_payload)
    coverage_status = strategy_watch_coverage_status(watch_payload)
    if coverage_status and not findings:
        reason = ("interval_coverage_contract_invalid" if any(item["read_status"] == "invalid" for item in coverage_status)
                  else "interval_scope_binding_unavailable")
        result = no_comparable_metrics_result(reason=reason, dry_run=dry_run)
        result["coverage_status"] = coverage_status
        return result
    result = dispatch_strategy_watch_findings(
        findings,
        source_repo=source_repo,
        dry_run=dry_run,
        create_issue=create_issue,
        comment_issue=comment_issue,
        read_issue=read_issue,
        list_issues=list_issues,
        list_archived_issues=list_archived_issues,
    )
    result["research_task_source_snapshot"] = research_task_source_snapshot(
        findings,
        task_builder=task_builder,
        context_available=research_task_context_available(watch_payload),
        computed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    if coverage_status:
        result["coverage_status"] = coverage_status
    archived_event_keys = {
        str(issue.get("task", {}).get("event_key") or "")
        for issue in result["issues"]
        if issue.get("archived") and isinstance(issue.get("task"), dict)
    }
    if archived_event_keys:
        snapshot = result["research_task_source_snapshot"]
        tasks = snapshot.get("tasks")
        if isinstance(tasks, list):
            snapshot["tasks"] = [
                task for task in tasks
                if str(task.get("task_id") or "").removeprefix("watcher-") not in archived_event_keys
            ]
        result["archived_research_task_ids"] = [
            f"watcher-{event_key}" for event_key in sorted(archived_event_keys) if event_key
        ]
    blocked_event_keys = {
        str(issue.get("task", {}).get("event_key") or "")
        for issue in result["issues"]
        if issue.get("archive_lookup_failed") and isinstance(issue.get("task"), dict)
    }
    if blocked_event_keys:
        snapshot = result["research_task_source_snapshot"]
        snapshot["tasks"] = []
        result["blocked_research_task_ids"] = [
            f"watcher-{event_key}" for event_key in sorted(blocked_event_keys) if event_key
        ]
    return result


def run_research_input_terminal_watcher(
    terminal: dict[str, Any],
    *,
    source_repo: str,
    profile: str = "",
    source: str = "",
    dry_run: bool = True,
    create_issue: Callable[[str, str, str], str] = create_github_issue,
    comment_issue: Callable[[str, str, str], str] = comment_github_issue,
    read_issue: Callable[[str, str], dict[str, Any]] = read_existing_watcher_issue,
    list_issues: Callable[[str], dict[str, str]] = list_open_issue_urls,
    list_archived_issues: Callable[[str], dict[str, str]] = list_archived_issue_urls,
) -> dict[str, Any]:
    """Surface a trusted deferred P1 record as an issue-only finding.

    An accepted P1 terminal record is not a failure.  It simply means that
    the producer has not yet emitted the two comparable P3 observations the
    watcher needs.  Keep that state visible to the unified console without
    opening a misleading issue or failing the scheduled watcher.
    """
    candidate = terminal.get("candidate") if isinstance(terminal.get("candidate"), dict) else {}
    status = str(terminal.get("status") or "").strip().upper()
    reason_code = str(terminal.get("reason_code") or "").strip()
    if status != "DEFERRED" or not reason_code:
        reason = "p1_terminal_accepted" if status == "ACCEPTED" else "p1_terminal_contract_unavailable"
        return no_comparable_metrics_result(reason=reason, dry_run=dry_run)
    finding = build_research_input_unavailable_finding(
        repo=source_repo,
        profile=profile,
        status=status,
        reason_code=reason_code,
        candidate_id=str(candidate.get("candidate_id") or ""),
        date_cutoff=str(terminal.get("date_cutoff") or ""),
        source=source,
    )
    result = dispatch_strategy_watch_findings(
        [finding],
        source_repo=source_repo,
        dry_run=dry_run,
        create_issue=create_issue,
        comment_issue=comment_issue,
        read_issue=read_issue,
        list_issues=list_issues,
        list_archived_issues=list_archived_issues,
    )
    result["research_task_source_snapshot"] = research_task_source_snapshot(
        [finding],
        context_available=False,
        computed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    return result


def no_comparable_metrics_result(
    *, reason: str = "comparable_metrics_unavailable", dry_run: bool = True
) -> dict[str, Any]:
    """Return a successful, source-owned unavailable queue snapshot.

    This is deliberately not an exception: optimization requires two trusted
    comparable P3 observations.  Until they exist, the console must show an
    unavailable source rather than silently retaining stale tasks or marking
    an accepted P1 acquisition as a watcher failure.
    """
    snapshot = research_task_source_snapshot(
        [],
        context_available=False,
        computed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    snapshot["errors"] = sorted(set(snapshot["errors"] + [reason]))
    return {
        "status": "ok",
        "dry_run": dry_run,
        "findings": 0,
        "issues": [],
        "errors": 0,
        "research_task_source_snapshot": snapshot,
    }


def main() -> int:
    try:
        input_path = resolve_input_path(
            input_path=os.environ.get("STRATEGY_WATCH_INPUT", "").strip(),
            source_root=os.environ.get("STRATEGY_WATCH_SOURCE_ROOT", "").strip(),
            metrics_path=os.environ.get("STRATEGY_WATCH_METRICS_PATH", "").strip(),
        )
    except ValueError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
        return 2
    if input_path is None:
        result = no_comparable_metrics_result(reason="metrics_input_not_configured")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    terminal_path_text = os.environ.get("STRATEGY_WATCH_TERMINAL_STATUS_PATH", "").strip()
    terminal_path = None
    if terminal_path_text:
        try:
            terminal_path = resolve_input_path(
                source_root=os.environ.get("STRATEGY_WATCH_SOURCE_ROOT", "").strip(),
                metrics_path=terminal_path_text,
            )
        except ValueError as exc:
            print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
            return 2
    if not input_path.exists():
        if terminal_path is None or not terminal_path.is_file():
            result = no_comparable_metrics_result()
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0
        try:
            terminal = load_payload(terminal_path)
            dry_run = parse_bool(os.environ.get("STRATEGY_WATCH_DRY_RUN"), default=True)
            result = run_research_input_terminal_watcher(
                terminal,
                source_repo=os.environ.get("STRATEGY_WATCH_SOURCE_REPO", "").strip(),
                profile=os.environ.get("STRATEGY_WATCH_TERMINAL_PROFILE", "").strip(),
                source=str(terminal_path),
                dry_run=dry_run,
            )
        except (OSError, json.JSONDecodeError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
            print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
            return 2
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 1 if int(result.get("errors", 0)) > 0 or result.get("status") != "ok" else 0
    if not input_path.is_file():
        print(json.dumps({"status": "error", "error": "strategy metrics input is not a file"}, sort_keys=True))
        return 2
    try:
        payload = load_payload(input_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
        return 2
    try:
        dry_run = parse_bool(os.environ.get("STRATEGY_WATCH_DRY_RUN"), default=True)
    except ValueError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
        return 2
    try:
        result = run_watcher(
            payload,
            source_repo=os.environ.get("STRATEGY_WATCH_SOURCE_REPO", "").strip(),
            dry_run=dry_run,
        )
    except (ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if int(result.get("errors", 0)) > 0 or result.get("status") != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
