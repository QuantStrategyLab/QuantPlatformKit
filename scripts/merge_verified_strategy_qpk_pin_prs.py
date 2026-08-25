#!/usr/bin/env python3
"""Merge only fully validated, generated strategy QPK pin PRs.

This script deliberately excludes broker and runtime repositories.  A strategy
library pin is merged only after its own CI has succeeded; consumer-platform
PRs remain proposal-only because their repositories can carry deployment
workflows.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
from typing import Any

try:  # Package import for tests and module execution.
    from scripts.open_downstream_qpk_pin_prs import (  # type: ignore[import-not-found]
        STRATEGY_REPOS,
        RepoSpec,
        command_failure_summary,
    )
except ModuleNotFoundError:  # Direct `python scripts/<file>.py` execution in Actions.
    from open_downstream_qpk_pin_prs import STRATEGY_REPOS, RepoSpec, command_failure_summary


ALLOWED_CHANGED_FILES = frozenset(
    {
        "pyproject.toml",
        "qsl.toml",
        "tests/test_qsl_compat_metadata.py",
        "uv.lock",
    }
)
QPK_REF_RE = re.compile(
    r"QuantPlatformKit\.git(?:\?rev=|@)([a-f0-9]{40})",
    re.IGNORECASE,
)
AUTOMATION_AUTHOR = "Pigbibi"


def run(command: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=True, env=env)


def _json(command: list[str], *, env: dict[str, str]) -> Any:
    return json.loads(run(command, env=env).stdout)


def expected_branch(repo: RepoSpec, qpk_sha: str) -> str:
    return f"auto/qpk-pin-sync-{qpk_sha[:12]}-{repo.name.lower()}"


def candidate_reason(
    *,
    pr: dict[str, Any],
    changed_files: list[str],
    pyproject_text: str,
    qpk_sha: str,
) -> str | None:
    """Return a fail-closed reason when a generated PR is not mergeable."""

    expected_title = f"chore(deps): align QPK pin to {qpk_sha[:12]}"
    author = (pr.get("author") or {}).get("login")
    if author != AUTOMATION_AUTHOR:
        return "unexpected_author"
    if pr.get("baseRefName") != "main" or pr.get("isCrossRepository") or pr.get("isDraft"):
        return "unexpected_pr_target"
    if pr.get("title") != expected_title:
        return "unexpected_title"
    if set(changed_files) != ALLOWED_CHANGED_FILES:
        return "unexpected_changed_files"

    checks = pr.get("statusCheckRollup") or []
    if not checks:
        return "missing_ci"
    for check in checks:
        if check.get("status") != "COMPLETED" or check.get("conclusion") != "SUCCESS":
            return "ci_not_green"

    if set(QPK_REF_RE.findall(pyproject_text)) != {qpk_sha}:
        return "qpk_pin_mismatch"
    return None


def open_pr_payload(repo: RepoSpec, branch: str, *, env: dict[str, str]) -> dict[str, Any] | None:
    payload = _json(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            f"QuantStrategyLab/{repo.name}",
            "--state",
            "open",
            "--head",
            branch,
            "--json",
            "number",
        ],
        env=env,
    )
    if not payload:
        return None
    if len(payload) != 1:
        raise RuntimeError(f"ambiguous_generated_prs:count={len(payload)}")
    pr_number = str(payload[0]["number"])
    return _json(
        [
            "gh",
            "pr",
            "view",
            pr_number,
            "--repo",
            f"QuantStrategyLab/{repo.name}",
            "--json",
            "author,baseRefName,headRefName,headRefOid,isCrossRepository,isDraft,number,statusCheckRollup,title,url",
        ],
        env=env,
    )


def changed_files(repo: RepoSpec, pr_number: int, *, env: dict[str, str]) -> list[str]:
    output = run(
        [
            "gh",
            "api",
            "--paginate",
            f"repos/QuantStrategyLab/{repo.name}/pulls/{pr_number}/files",
            "--jq",
            ".[].filename",
        ],
        env=env,
    ).stdout
    return [line for line in output.splitlines() if line]


def pyproject_text(repo: RepoSpec, head_sha: str, *, env: dict[str, str]) -> str:
    content = run(
        [
            "gh",
            "api",
            f"repos/QuantStrategyLab/{repo.name}/contents/pyproject.toml?ref={head_sha}",
            "--jq",
            ".content",
        ],
        env=env,
    ).stdout
    return base64.b64decode(content).decode("utf-8")


def merge_candidate(repo: RepoSpec, pr: dict[str, Any], *, env: dict[str, str]) -> None:
    run(
        [
            "gh",
            "pr",
            "merge",
            str(pr["number"]),
            "--repo",
            f"QuantStrategyLab/{repo.name}",
            "--auto",
            "--rebase",
            "--delete-branch",
            "--match-head-commit",
            pr["headRefOid"],
        ],
        env=env,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge verified generated strategy QPK pin PRs.")
    parser.add_argument("--qpk-sha", required=True)
    parser.add_argument("--token-env", default="QSL_REPO_SYNC_TOKEN")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    qpk_sha = args.qpk_sha.strip()
    if not re.fullmatch(r"[a-f0-9]{40}", qpk_sha):
        raise SystemExit("qpk_sha must be a full lowercase SHA")
    token = os.environ.get(args.token_env, "").strip()
    if not token:
        raise SystemExit(f"missing required token env: {args.token_env}")
    env = {**os.environ, "GH_TOKEN": token}

    failures = 0
    for repo in STRATEGY_REPOS:
        try:
            branch = expected_branch(repo, qpk_sha)
            pr = open_pr_payload(repo, branch, env=env)
            if pr is None:
                print(f"{repo.name}: no current generated PR")
                continue
            reason = candidate_reason(
                pr=pr,
                changed_files=changed_files(repo, int(pr["number"]), env=env),
                pyproject_text=pyproject_text(repo, pr["headRefOid"], env=env),
                qpk_sha=qpk_sha,
            )
            if reason is not None:
                print(f"{repo.name}: skipped:{reason}")
                continue
            merge_candidate(repo, pr, env=env)
            print(f"{repo.name}: queued:{pr['url']}")
        except (RuntimeError, subprocess.CalledProcessError, ValueError, UnicodeDecodeError) as exc:
            failures += 1
            if isinstance(exc, subprocess.CalledProcessError):
                detail = command_failure_summary(exc)
            else:
                detail = type(exc).__name__
            print(f"{repo.name}: merge_evaluation_failed:{detail}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
