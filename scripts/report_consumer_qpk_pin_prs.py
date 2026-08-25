#!/usr/bin/env python3
"""Report stale generated QPK pin PRs in runtime-consumer repositories.

Consumer repositories may own deployment or broker workflows, so this command
is deliberately read-only.  It exposes recognizable older generated PRs in
the QPK workflow summary without closing, merging, labelling, or changing any
consumer repository state.
"""

from __future__ import annotations

import argparse
import json
import os
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
            "author,baseRefName,headRefName,isCrossRepository,isDraft,number,title,updatedAt,url",
        ],
        env=env,
    )
    return json.loads(result.stdout)


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


def render_row(repo: RepoSpec, current: list[dict[str, Any]], stale: list[dict[str, Any]]) -> str:
    current_refs = ", ".join(f"[#{item['number']}]({item['url']})" for item in current) or "—"
    stale_refs = ", ".join(f"[#{item['number']}]({item['url']})" for item in stale) or "—"
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
    print()
    print("| Repository | Current generated PR | Recognizable stale generated PRs |")
    print("| --- | --- | --- |")
    for repo in CONSUMER_REPOS:
        current, stale = classify_generated_prs(
            generated_prs(repo, env=env),
            current_branch=expected_branch(repo, qpk_sha),
        )
        print(render_row(repo, current, stale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
