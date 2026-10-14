"""Independent Actions review-job liveness monitor; alerts only, no reruns."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
from urllib.parse import quote

from .review_disposition import GitHubReviewStore
from .review_loop import deadman, strict_json


def archived_failure(api, base, run):
    """Observe a summary/review failure even when its host job otherwise succeeded."""
    since = quote(run["created_at"], safe="")
    for page in range(1, 101):
        issues = api(base + f"/issues?state=all&since={since}&per_page=100&page={page}")
        for issue in issues:
            if (issue.get("user", {}).get("login") != "github-actions[bot]"
                    or "pull_request" in issue or not (issue.get("body") or "").startswith("<!-- advisory-review:")):
                continue
            state = None
            for comments_page in range(1, 101):
                comments = api(base + f"/issues/{issue['number']}/comments?per_page=100&page={comments_page}")
                for item in comments:
                    body = item.get("body", "")
                    prefix = "<!-- advisory-review-loop-v1 "
                    if item.get("user", {}).get("login") == "github-actions[bot]" and body.startswith(prefix):
                        value = strict_json(body[len(prefix):].split(" -->", 1)[0])
                        if str(value.get("run_id")) == str(run["id"]):
                            state = value
                if len(comments) < 100:
                    break
            else:
                raise ValueError("incomplete archived review state")
            if state and state.get("disposition") in {"review_unavailable", "escalation_unavailable", "outcome_unknown"}:
                return True
        if len(issues) < 100:
            return False
    raise ValueError("incomplete archived outcome history")


def check_lane(api, base, lane, threshold, now):
    workflow, job = lane["workflow"], lane["job"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.ya?ml", workflow) or not isinstance(job, str) or not job:
        raise ValueError("invalid monitored workflow")
    runs = api(base + f"/actions/workflows/{workflow}/runs?status=completed&per_page=100")["workflow_runs"]
    runs = [run for run in runs if run.get("event") in {"schedule", "workflow_dispatch", "pull_request"}]
    # Ask GitHub for the PR state; the workflow-run PR stub omits draft metadata.
    monitored = []
    for run in runs:
        if run.get("event") == "pull_request":
            prs = run.get("pull_requests", [])
            if any(api(base + f"/pulls/{pr['number']}").get("draft") is True for pr in prs):
                continue
        monitored.append(run)
        if len(monitored) >= threshold:
            break
    runs = monitored
    outcomes = []
    for run in runs[:threshold]:
        jobs = api(base + f"/actions/runs/{run['id']}/jobs?per_page=100")
        if jobs["total_count"] != len(jobs["jobs"]):
            raise ValueError("incomplete monitored jobs")
        matches = [item for item in jobs["jobs"] if job in item.get("name", "")]
        passed = matches and all(item.get("conclusion") == "success" for item in matches)
        outcomes.append("unavailable" if passed and archived_failure(api, base, run)
                        else "success" if passed
                        else "skipped" if matches and all(item.get("conclusion") == "skipped" for item in matches)
                        else "failure")
    max_age = lane.get("interval_hours", 0)
    if type(max_age) is not int or not 0 <= max_age <= 8760:
        raise ValueError("invalid review interval")
    stale = False
    if max_age:
        # Adoption time is explicit; absence before adoption is not a failed cycle.
        timestamp = runs[0]["created_at"] if runs else lane["enabled_at"]
        latest = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        stale = (now - latest).total_seconds() >= max_age * 3600 * threshold
    return deadman(outcomes, threshold) or stale, outcomes


def main():
    try:
        lanes = json.loads(os.environ["REVIEW_MONITOR_LANES_JSON"])
        threshold = int(os.environ.get("REVIEW_DEADMAN_THRESHOLD", "3"))
        if not isinstance(lanes, list) or not 1 <= len(lanes) <= 20:
            raise ValueError("explicit review lanes required")
        for lane in lanes:
            identity = "deadman:" + lane["workflow"] + ":" + lane["job"]
            store = GitHubReviewStore(identity)
            unhealthy, outcomes = check_lane(store.api, store.base, lane, threshold, datetime.now(timezone.utc))
            prior = store.load(identity) or {}
            if unhealthy and not prior.get("alerted"):
                store.notify(f"Review dead-man: {lane['workflow']} / {lane['job']} failed, skipped or was missing "
                             f"for {threshold} cycles. Operational alert only; no rerun or live change.")
                store.save({"identity": identity, "alerted": True, "outcomes": outcomes})
            elif not unhealthy and prior.get("alerted"):
                store.save({"identity": identity, "alerted": False, "outcomes": outcomes})
        return 0
    except Exception:
        print("Review dead-man unavailable; no live changes or retries performed.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
