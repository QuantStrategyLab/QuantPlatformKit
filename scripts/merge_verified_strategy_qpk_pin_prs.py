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
import time
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
        ".github/workflows/drift-check.yml",
    }
)
QPK_REF_RE = re.compile(
    r"QuantPlatformKit\.git(?:\?rev=|@)([a-f0-9]{40})",
    re.IGNORECASE,
)
AUTOMATION_AUTHOR = "Pigbibi"
GENERATED_BRANCH_PREFIX = "auto/qpk-pin-sync-"
GENERATED_TITLE_PREFIX = "chore(deps): align QPK pin to "


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

    expected_title = f"{GENERATED_TITLE_PREFIX}{qpk_sha[:12]}"
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


def superseded_pr_reason(*, pr: dict[str, Any], current_branch: str) -> str | None:
    """Return a reason unless this is a safely recognizable obsolete PR."""

    author = (pr.get("author") or {}).get("login")
    if author != AUTOMATION_AUTHOR:
        return "unexpected_author"
    if pr.get("baseRefName") != "main" or pr.get("isCrossRepository") or pr.get("isDraft"):
        return "unexpected_pr_target"
    head_ref = pr.get("headRefName") or ""
    if head_ref == current_branch:
        return "current_branch"
    if not head_ref.startswith(GENERATED_BRANCH_PREFIX):
        return "unexpected_branch"
    if not (pr.get("title") or "").startswith(GENERATED_TITLE_PREFIX):
        return "unexpected_title"
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
        pr_view_command(repo, pr_number),
        env=env,
    )


def current_candidate(
    repo: RepoSpec,
    *,
    branch: str,
    qpk_sha: str,
    env: dict[str, str],
) -> tuple[dict[str, Any] | None, str | None]:
    """Read one generated candidate and classify it without mutating GitHub."""

    pr = open_pr_payload(repo, branch, env=env)
    if pr is None:
        return None, "no_current_generated_pr"
    return pr, candidate_reason(
        pr=pr,
        changed_files=changed_files(repo, int(pr["number"]), env=env),
        pyproject_text=pyproject_text(repo, pr["headRefOid"], env=env),
        qpk_sha=qpk_sha,
    )


def wait_for_current_candidate(
    repo: RepoSpec,
    *,
    branch: str,
    qpk_sha: str,
    env: dict[str, str],
    wait_for_ci_seconds: int,
    poll_interval_seconds: int,
    monotonic: Any = time.monotonic,
    sleep: Any = time.sleep,
) -> tuple[dict[str, Any] | None, str | None]:
    """Wait only for a generated strategy PR's pending CI to settle.

    The caller still validates author, branch, changed files, exact pin, and
    completed green checks before requesting GitHub auto-merge. A timeout is
    fail-closed and never treats missing or pending CI as success.
    """

    if wait_for_ci_seconds < 0:
        raise ValueError("wait_for_ci_seconds must be non-negative")
    if poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be positive")

    deadline = monotonic() + wait_for_ci_seconds
    while True:
        pr, reason = current_candidate(
            repo,
            branch=branch,
            qpk_sha=qpk_sha,
            env=env,
        )
        if reason not in {"missing_ci", "ci_not_green"}:
            return pr, reason

        remaining = deadline - monotonic()
        if remaining <= 0:
            return pr, reason
        sleep(min(poll_interval_seconds, remaining))


def pr_view_command(repo: RepoSpec, pr_number: str) -> list[str]:
    return [
        "gh",
        "pr",
        "view",
        pr_number,
        "--repo",
        f"QuantStrategyLab/{repo.name}",
        "--json",
        "author,baseRefName,headRefName,headRefOid,isCrossRepository,isDraft,number,statusCheckRollup,title,url",
    ]


def open_generated_prs(repo: RepoSpec, *, env: dict[str, str]) -> list[dict[str, Any]]:
    payload = _json(
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
            "number",
        ],
        env=env,
    )
    return [
        _json(pr_view_command(repo, str(item["number"])), env=env)
        for item in payload
    ]


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


def qpk_ref_from_pyproject(text: str) -> str | None:
    refs = set(QPK_REF_RE.findall(text))
    return next(iter(refs)) if len(refs) == 1 else None


def is_main_history_ancestor(*, candidate_sha: str, qpk_sha: str, env: dict[str, str]) -> bool:
    status = run(
        [
            "gh",
            "api",
            f"repos/QuantStrategyLab/QuantPlatformKit/compare/{candidate_sha}...{qpk_sha}",
            "--jq",
            ".status",
        ],
        env=env,
    ).stdout.strip()
    return status == "ahead"


def close_superseded_candidates(
    repo: RepoSpec,
    *,
    current_branch: str,
    qpk_sha: str,
    env: dict[str, str],
) -> list[str]:
    """Close only fully recognizable older pins that lead to the current pin."""

    results: list[str] = []
    for pr in open_generated_prs(repo, env=env):
        reason = superseded_pr_reason(pr=pr, current_branch=current_branch)
        if reason is not None:
            continue
        old_qpk_sha = qpk_ref_from_pyproject(pyproject_text(repo, pr["headRefOid"], env=env))
        if old_qpk_sha is None or not is_main_history_ancestor(
            candidate_sha=old_qpk_sha,
            qpk_sha=qpk_sha,
            env=env,
        ):
            continue
        run(
            [
                "gh",
                "pr",
                "close",
                str(pr["number"]),
                "--repo",
                f"QuantStrategyLab/{repo.name}",
                "--delete-branch",
            ],
            env=env,
        )
        results.append(str(pr["number"]))
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge verified generated strategy QPK pin PRs.")
    parser.add_argument("--qpk-sha", required=True)
    parser.add_argument("--token-env", default="QSL_REPO_SYNC_TOKEN")
    parser.add_argument(
        "--wait-for-ci-seconds",
        type=int,
        default=0,
        help="Bounded wait for the current generated strategy PR CI to settle.",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=int,
        default=30,
        help="Polling interval used only while a generated strategy PR CI is pending.",
    )
    parser.add_argument(
        "--close-superseded",
        action="store_true",
        help="Close only verified older generated strategy pin PRs after a current PR is green.",
    )
    return parser.parse_args()


def process_repo(
    repo: RepoSpec,
    *,
    qpk_sha: str,
    close_superseded: bool,
    env: dict[str, str],
    wait_for_ci_seconds: int = 0,
    poll_interval_seconds: int = 30,
) -> None:
    """Queue the current pin when eligible, then retire verified older pins.

    A current generated PR may already have merged by the time the hourly
    workflow runs again.  Cleanup must therefore be independent of finding an
    open current PR; otherwise historical proposal branches accumulate forever.
    """

    branch = expected_branch(repo, qpk_sha)
    pr, reason = wait_for_current_candidate(
        repo,
        branch=branch,
        qpk_sha=qpk_sha,
        env=env,
        wait_for_ci_seconds=wait_for_ci_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    if pr is None:
        print(f"{repo.name}: no current generated PR")
    else:
        if reason is not None:
            print(f"{repo.name}: skipped:{reason}")
        else:
            merge_candidate(repo, pr, env=env)
            print(f"{repo.name}: queued:{pr['url']}")

    if close_superseded:
        closed = close_superseded_candidates(
            repo,
            current_branch=branch,
            qpk_sha=qpk_sha,
            env=env,
        )
        if closed:
            print(f"{repo.name}: closed_superseded:{','.join(closed)}")


def main() -> int:
    args = parse_args()
    qpk_sha = args.qpk_sha.strip()
    if not re.fullmatch(r"[a-f0-9]{40}", qpk_sha):
        raise SystemExit("qpk_sha must be a full lowercase SHA")
    if args.wait_for_ci_seconds < 0:
        raise SystemExit("wait_for_ci_seconds must be non-negative")
    if args.poll_interval_seconds <= 0:
        raise SystemExit("poll_interval_seconds must be positive")
    token = os.environ.get(args.token_env, "").strip()
    if not token:
        raise SystemExit(f"missing required token env: {args.token_env}")
    env = {**os.environ, "GH_TOKEN": token}

    failures = 0
    for repo in STRATEGY_REPOS:
        try:
            process_repo(
                repo,
                qpk_sha=qpk_sha,
                close_superseded=args.close_superseded,
                env=env,
                wait_for_ci_seconds=args.wait_for_ci_seconds,
                poll_interval_seconds=args.poll_interval_seconds,
            )
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
