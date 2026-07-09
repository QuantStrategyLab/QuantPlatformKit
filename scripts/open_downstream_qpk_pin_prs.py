#!/usr/bin/env python3
"""Open downstream PRs after QPK_PIN lands on main."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from check_qpk_pin_consistency import get_qpk_pin_sha


@dataclass(frozen=True)
class RepoSpec:
    name: str
    base_branch: str = "main"


DOWNSTREAM_REPOS = (
    RepoSpec("CnEquityStrategies"),
    RepoSpec("HkEquityStrategies"),
    RepoSpec("UsEquityStrategies"),
    RepoSpec("CryptoStrategies"),
    RepoSpec("InteractiveBrokersPlatform"),
    RepoSpec("LongBridgePlatform"),
    RepoSpec("CharlesSchwabPlatform"),
    RepoSpec("FirstradePlatform"),
    RepoSpec("BinancePlatform"),
)


def run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True, check=True)


def has_changes(repo_dir: Path) -> bool:
    result = run(["git", "status", "--porcelain"], cwd=repo_dir)
    return bool(result.stdout.strip())


def maybe_run_uv_lock(repo_dir: Path) -> bool:
    if not (repo_dir / "pyproject.toml").exists() or not (repo_dir / "uv.lock").exists():
        return False
    run(["uv", "lock"], cwd=repo_dir)
    return True


def update_repo(repo_dir: Path, qpk_pin: Path) -> bool:
    script = SCRIPT_ROOT / "check_qpk_pin_consistency.py"
    run(
        ["python3", str(script), "--root", str(repo_dir), "--pin-file", str(qpk_pin), "--fix"],
        cwd=repo_dir,
    )
    maybe_run_uv_lock(repo_dir)
    return has_changes(repo_dir)


def create_branch_commit_and_pr(
    *,
    repo: RepoSpec,
    repo_dir: Path,
    token: str,
    qpk_sha: str,
    dry_run: bool,
) -> str:
    branch = f"auto/qpk-pin-sync-{qpk_sha[:12]}"
    remote_url = f"https://x-access-token:{token}@github.com/QuantStrategyLab/{repo.name}.git"
    run(["git", "checkout", "-B", branch], cwd=repo_dir)
    run(["git", "add", "-A"], cwd=repo_dir)
    run(
        [
            "git",
            "commit",
            "-m",
            f"chore(deps): align QPK pin to {qpk_sha[:12]}",
            "-m",
            "Automated downstream QPK pin update after QPK_PIN landed on main.",
            "-m",
            "Co-Authored-By: Claude <noreply@anthropic.com>",
        ],
        cwd=repo_dir,
    )
    if dry_run:
        return f"[dry-run] {repo.name}: would push {branch} and open PR"

    run(["git", "push", "--force-with-lease", remote_url, f"HEAD:{branch}"], cwd=repo_dir)
    body = "\n".join(
        [
            "## Summary",
            f"- 自动将 QPK pin 对齐到 `{qpk_sha[:12]}`",
            "- 若仓库使用 `uv.lock`，同步刷新 lockfile",
            "",
            "## Test plan",
            "- [ ] Repo CI 转绿",
            "",
            "🤖 Generated with Claude Code",
        ]
    )
    env = {**os.environ, "GH_TOKEN": token}
    result = run(
        [
            "gh",
            "pr",
            "create",
            "--repo",
            f"QuantStrategyLab/{repo.name}",
            "--base",
            repo.base_branch,
            "--head",
            branch,
            "--title",
            f"chore(deps): align QPK pin to {qpk_sha[:12]}",
            "--body",
            body,
        ],
        cwd=repo_dir,
        env=env,
    )
    return result.stdout.strip()


def clone_repo(repo: RepoSpec, root: Path, token: str, *, dry_run: bool) -> Path:
    repo_dir = root / repo.name
    remote = (
        f"https://github.com/QuantStrategyLab/{repo.name}.git"
        if dry_run
        else f"https://x-access-token:{token}@github.com/QuantStrategyLab/{repo.name}.git"
    )
    run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            repo.base_branch,
            remote,
            str(repo_dir),
        ]
    )
    return repo_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open downstream QPK pin sync PRs.")
    parser.add_argument("--token-env", default="QSL_REPO_SYNC_TOKEN")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo", action="append", default=[], help="Limit to one or more repo names")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get(args.token_env, "").strip()
    if not token and not args.dry_run:
        print(f"Missing required token env: {args.token_env}")
        return 2

    qpk_pin = Path(__file__).resolve().parent.parent / "QPK_PIN"
    qpk_sha = get_qpk_pin_sha(pin_file=qpk_pin)
    repo_specs = [repo for repo in DOWNSTREAM_REPOS if not args.repo or repo.name in args.repo]
    if not repo_specs:
        print("No downstream repos selected.")
        return 0

    results: list[str] = []
    with tempfile.TemporaryDirectory(prefix="qpk-downstream-") as tmp:
        root = Path(tmp)
        for repo in repo_specs:
            repo_dir = clone_repo(repo, root, token, dry_run=args.dry_run)
            if not update_repo(repo_dir, qpk_pin):
                results.append(f"{repo.name}: no changes needed")
                continue
            try:
                results.append(
                    create_branch_commit_and_pr(
                        repo=repo,
                        repo_dir=repo_dir,
                        token=token,
                        qpk_sha=qpk_sha,
                        dry_run=args.dry_run,
                    )
                )
            except subprocess.CalledProcessError as exc:
                stderr = (exc.stderr or exc.stdout).strip()
                results.append(f"{repo.name}: failed to open PR: {stderr}")
    print("\n".join(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
