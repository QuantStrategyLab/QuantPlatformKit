"""Dispatch preclassified monitor findings to issue-only records."""
# Existing monitor-only source slice from QPK 330f2d5ed01dd5c0d2e5345fcf9316958ceeb07f.
from __future__ import annotations

import json
import re
import subprocess
from typing import Any, Callable, Mapping

from .strategy_watch import (
    StrategyWatchFinding,
    finding_to_automation_task,
    issue_for_task,
    watcher_issue_key,
)

REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


ISSUE_URL_RE = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/issues/([1-9][0-9]*)$")


EVENT_KEY_RE = re.compile(r"- Event key:\s*`([^`]+)`")


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
            issues = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("failed to parse open issue list") from exc
        if not isinstance(issues, list):
            raise RuntimeError("invalid open issue list response")
        if not issues:
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
            issues = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("failed to parse closed issue list") from exc
        if not isinstance(issues, list):
            raise RuntimeError("invalid closed issue list response")
        if not issues:
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
