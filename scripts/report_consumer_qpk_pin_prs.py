#!/usr/bin/env python3
"""Report stale generated QPK pin PRs in runtime-consumer repositories.

Consumer repositories may own deployment or broker workflows, so this command
is deliberately read-only.  It exposes recognizable older generated PRs in
the QPK workflow summary without closing, merging, labelling, or changing any
consumer repository state.

Downgrade safety note: opener defaults to upgrade-only. This reporter flags
generated PRs whose target SHA is older than the current candidate so humans
can close leftover downgrade/superseded PRs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from collections.abc import Iterable
from typing import Any

try:  # Package import for tests and module execution.
    from scripts.merge_verified_strategy_qpk_pin_prs import (
        expected_branch,
        superseded_pr_reason,
    )
    from scripts.open_downstream_qpk_pin_prs import CONSUMER_REPOS, RepoSpec
except ModuleNotFoundError:  # Direct `python scripts/<file>.py` execution in Actions.
    from merge_verified_strategy_qpk_pin_prs import expected_branch, superseded_pr_reason
    from open_downstream_qpk_pin_prs import CONSUMER_REPOS, RepoSpec

_GENERATED_BRANCH_SHA_RE = re.compile(
    r"^auto/qpk-pin-sync-([a-f0-9]{12})-",
    re.IGNORECASE,
)


def run(command: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=True, env=env)


def generated_prs(repo: RepoSpec, *, env: dict[str, str]) -> list[dict[str, Any]]:
    result = run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            f"QuantStrategyLab/{repo.name}",
            "--state",
            "open",
            "--limit",
            "100",
            "--json",
            "author,baseRefName,headRefName,isCrossRepository,isDraft,number,statusCheckRollup,title,updatedAt,url",
        ],
        env=env,
    )
    return json.loads(result.stdout)


def ci_status(pr: dict[str, Any]) -> str:
    """Return a display-only CI state; never use it to mutate consumer PRs."""

    checks = pr.get("statusCheckRollup")
    if not isinstance(checks, list) or not checks:
        return "MISSING"
    if any(not isinstance(check, dict) or check.get("status") != "COMPLETED" for check in checks):
        return "PENDING"
    conclusions = {str(check.get("conclusion") or "").upper() for check in checks}
    if conclusions == {"SUCCESS"}:
        return "GREEN"
    if conclusions & {"FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"}:
        return "FAILED"
    return "NON_GREEN"


def classify_generated_prs(
    prs: Iterable[dict[str, Any]],
    *,
    current_branch: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return current and recognizable stale generated PRs, ignoring all others."""

    current: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    for pr in prs:
        reason = superseded_pr_reason(pr=pr, current_branch=current_branch)
        if reason == "current_branch":
            current.append(pr)
            continue
        if reason is None:
            stale.append(pr)
    return current, stale


def target_sha_prefix_from_branch(branch: str) -> str | None:
    match = _GENERATED_BRANCH_SHA_RE.match(branch.strip())
    return match.group(1).lower() if match else None


def hygiene_label_for_pr(*, branch: str, candidate_sha: str) -> str:
    """Label generated PR targets relative to the candidate SHA prefix."""
    prefix = target_sha_prefix_from_branch(branch)
    candidate_prefix = candidate_sha[:12].lower()
    if prefix is None:
        return "unrecognized"
    if prefix == candidate_prefix:
        return "current-target"
    return "close-as-superseded-or-downgrade"


def render_row(
    repo: RepoSpec,
    current: list[dict[str, Any]],
    stale: list[dict[str, Any]],
    *,
    candidate_sha: str,
) -> str:
    current_refs = ", ".join(
        f"[#{item['number']}]({item['url']}) · {ci_status(item)}" for item in current
    ) or "—"
    stale_refs = ", ".join(
        (
            f"[#{item['number']}]({item['url']})"
            f" · {hygiene_label_for_pr(branch=str(item.get('headRefName') or ''), candidate_sha=candidate_sha)}"
        )
        for item in stale
    ) or "—"
    return f"| {repo.name} | {current_refs} | {stale_refs} |"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qpk-sha", required=True)
    parser.add_argument("--token-env", default="QSL_REPO_SYNC_TOKEN")
    args = parser.parse_args()
    qpk_sha = args.qpk_sha.strip()
    if len(qpk_sha) != 40 or any(char not in "0123456789abcdef" for char in qpk_sha):
        raise SystemExit("qpk_sha must be a full lowercase SHA")
    token = os.environ.get(args.token_env, "").strip()
    if not token:
        raise SystemExit(f"missing required token env: {args.token_env}")

    env = {**os.environ, "GH_TOKEN": token}
    print("## Consumer QPK pin PR hygiene")
    print()
    print("Consumer repositories are report-only: they are never auto-merged or auto-closed.")
    print(
        "Opener policy is upgrade-only; stale generated PRs targeting older SHAs should be "
        "closed as superseded/downgrade leftovers."
    )
    print()
    print("| Repository | Current generated PR (CI) | Recognizable stale generated PRs |")
    print("| --- | --- | --- |")
    for repo in CONSUMER_REPOS:
        current, stale = classify_generated_prs(
            generated_prs(repo, env=env),
            current_branch=expected_branch(repo, qpk_sha),
        )
        print(render_row(repo, current, stale, candidate_sha=qpk_sha))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
