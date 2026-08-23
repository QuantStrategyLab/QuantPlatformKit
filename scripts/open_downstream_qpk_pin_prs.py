#!/usr/bin/env python3
"""Open downstream PRs after QPK_PIN lands on main."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from check_qpk_pin_consistency import find_dep_files, get_qpk_pin_sha


QSL_QPK_REQUIREMENT_RE = re.compile(
    r"(quant-platform-kit\s*@\s*git\+https://github\.com/QuantStrategyLab/QuantPlatformKit\.git@)[a-f0-9]{40}"
)
QSL_REQUIRES_TABLE_RE = re.compile(
    r"(?ms)^[ \t]*(?P<header>\[qsl\.requires\][^\n]*\n)(?P<body>.*?)(?=^[ \t]*\[|\Z)"
)
QSL_QPK_REQUIRES_MAP_RE = re.compile(
    r"""(^[ \t]*(?:["']quant-platform-kit["']|quant-platform-kit|["']quant_platform_kit["']|quant_platform_kit)\s*=\s*)(['"])[a-f0-9]{40}(\2)""",
    re.MULTILINE,
)
QPK_REVISION_RE = re.compile(
    r'''(?m)^(?P<prefix>QPK_REVISION\s*=\s*["'])(?P<sha>[a-f0-9]{40})(?P<suffix>["']\s*)$'''
)


@dataclass(frozen=True)
class RepoSpec:
    name: str
    base_branch: str = "main"


STRATEGY_REPOS = (
    RepoSpec("CnEquityStrategies"),
    RepoSpec("HkEquityStrategies"),
    RepoSpec("UsEquityStrategies"),
    RepoSpec("CryptoStrategies"),
)

CONSUMER_REPOS = (
    RepoSpec("InteractiveBrokersPlatform"),
    RepoSpec("LongBridgePlatform"),
    RepoSpec("CharlesSchwabPlatform"),
    RepoSpec("FirstradePlatform"),
    RepoSpec("QmtPlatform"),
)

STRATEGY_QSL_KEYS = {
    "CnEquityStrategies": "cn_equity_strategies",
    "HkEquityStrategies": "hk_equity_strategies",
    "UsEquityStrategies": "us_equity_strategies",
    "CryptoStrategies": "crypto_strategies",
}

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


def qpk_refs(repo_dir: Path) -> set[str]:
    pattern = re.compile(
        r"QuantPlatformKit\.git(?:\?rev=|@)([a-f0-9]{40})",
        re.IGNORECASE,
    )
    refs: set[str] = set()
    paths = (
        *find_dep_files(repo_dir),
        repo_dir / "qsl.toml",
        repo_dir / "tests" / "test_qsl_compat_metadata.py",
    )
    for path in paths:
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            refs.update(pattern.findall(text))
            refs.update(match.group("sha") for match in QPK_REVISION_RE.finditer(text))
    return refs


def update_qpk_revision_contract(repo_dir: Path, qpk_sha: str) -> bool:
    path = repo_dir / "tests" / "test_qsl_compat_metadata.py"
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    updated, count = QPK_REVISION_RE.subn(
        rf"\g<prefix>{qpk_sha}\g<suffix>",
        original,
    )
    if count != 1:
        raise RuntimeError(f"qpk_revision_contract_update_failed:matches={count}")
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def update_strategy_dependency_pins(
    repo_dir: Path,
    strategy_heads: dict[str, str],
) -> bool:
    changed = False
    paths = {*find_dep_files(repo_dir), repo_dir / "qsl.toml"}
    for path in sorted(paths):
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8")
        updated = original
        for strategy_repo, strategy_sha in strategy_heads.items():
            pattern = re.compile(
                rf"(git\+https://github\.com/QuantStrategyLab/{re.escape(strategy_repo)}\.git@)[a-f0-9]{{40}}"
            )
            updated = pattern.sub(rf"\g<1>{strategy_sha}", updated)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed = True
    return changed


def update_qsl_strategy_requires(
    repo_dir: Path,
    strategy_heads: dict[str, str],
) -> bool:
    path = repo_dir / "qsl.toml"
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    updated = original
    table_match = QSL_REQUIRES_TABLE_RE.search(updated)
    if table_match is None:
        return False
    body = table_match.group("body")
    updated_body = body
    for repo, sha in strategy_heads.items():
        key = STRATEGY_QSL_KEYS[repo]
        pattern = re.compile(
            rf'''(?m)^(?P<prefix>\s*["']?{re.escape(key)}["']?\s*=\s*["'])[a-f0-9]{{40}}(?P<suffix>["']\s*)$'''
        )
        updated_body = pattern.sub(rf"\g<prefix>{sha}\g<suffix>", updated_body)
    if updated_body == body:
        return False
    start, end = table_match.span("body")
    updated = updated[:start] + updated_body + updated[end:]
    path.write_text(updated, encoding="utf-8")
    return True


def update_qsl_metadata_test_contract(
    repo_dir: Path,
    *,
    qpk_sha: str,
    strategy_heads: dict[str, str],
) -> bool:
    path = repo_dir / "tests" / "test_qsl_metadata.py"
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    updated = original
    expected = {"quant_platform_kit": qpk_sha}
    expected.update(
        {
            STRATEGY_QSL_KEYS[repo]: sha
            for repo, sha in strategy_heads.items()
        }
    )
    for key, sha in expected.items():
        pattern = re.compile(
            rf'''(?m)(requires\[["']{re.escape(key)}["']\]\s*==\s*["'])[a-f0-9]{{40}}(["'])'''
        )
        updated = pattern.sub(rf"\g<1>{sha}\g<2>", updated)
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def update_aggregate_bundle(
    root: Path,
    *,
    qpk_sha: str,
    strategy_heads: dict[str, str],
) -> bool:
    replacements = {"QuantPlatformKit": qpk_sha, **strategy_heads}
    changed = False
    for filename in ("qsl-pins.txt", "constraints.txt"):
        path = root / filename
        original = path.read_text(encoding="utf-8")
        updated = original
        for repo, sha in replacements.items():
            pattern = re.compile(
                rf"(git\+https://github\.com/QuantStrategyLab/{re.escape(repo)}\.git@)[a-f0-9]{{40}}"
            )
            updated, count = pattern.subn(rf"\g<1>{sha}", updated)
            if count != 1:
                raise RuntimeError(
                    f"aggregate_pin_update_failed:{filename}:{repo}:matches={count}"
                )
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed = True
    return changed


def verify_dependency_closure(repo_dir: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="qpk-resolver-") as tmp:
        resolver_python = Path(tmp) / "bin" / "python"
        run(["uv", "venv", "--python", sys.executable, tmp], cwd=repo_dir)
        run(
            [
                "uv",
                "pip",
                "install",
                "--dry-run",
                "--python",
                str(resolver_python),
                ".",
            ],
            cwd=repo_dir,
        )


def update_qsl_compat_qpk_pin(repo_dir: Path, qpk_sha: str) -> bool:
    qsl_path = repo_dir / "qsl.toml"
    if not qsl_path.is_file():
        return False

    original = qsl_path.read_text(encoding="utf-8")
    updated, requirement_replacements = QSL_QPK_REQUIREMENT_RE.subn(rf"\g<1>{qpk_sha}", original)
    requires_map_replacements = 0

    def update_requires_table(match: re.Match[str]) -> str:
        nonlocal requires_map_replacements
        body, replacements = QSL_QPK_REQUIRES_MAP_RE.subn(rf"\g<1>\g<2>{qpk_sha}\g<3>", match.group("body"))
        requires_map_replacements += replacements
        return match.group("header") + body

    updated = QSL_REQUIRES_TABLE_RE.sub(update_requires_table, updated)
    replacements = requirement_replacements + requires_map_replacements
    if replacements == 0 or updated == original:
        return False

    qsl_path.write_text(updated, encoding="utf-8")
    return True


def update_repo(
    repo_dir: Path,
    qpk_pin: Path,
    *,
    strategy_heads: dict[str, str] | None = None,
) -> bool:
    script = SCRIPT_ROOT / "check_qpk_pin_consistency.py"
    run(
        ["python3", str(script), "--root", str(repo_dir), "--pin-file", str(qpk_pin), "--fix"],
        cwd=repo_dir,
    )
    update_qsl_compat_qpk_pin(repo_dir, get_qpk_pin_sha(pin_file=qpk_pin))
    update_qpk_revision_contract(
        repo_dir,
        get_qpk_pin_sha(pin_file=qpk_pin),
    )
    if strategy_heads:
        update_strategy_dependency_pins(repo_dir, strategy_heads)
        update_qsl_strategy_requires(repo_dir, strategy_heads)
        update_qsl_metadata_test_contract(
            repo_dir,
            qpk_sha=get_qpk_pin_sha(pin_file=qpk_pin),
            strategy_heads=strategy_heads,
        )
    maybe_run_uv_lock(repo_dir)
    verify_dependency_closure(repo_dir)
    return has_changes(repo_dir)


def create_branch_commit_and_pr(
    *,
    repo: RepoSpec,
    repo_dir: Path,
    token: str,
    qpk_sha: str,
    dry_run: bool,
) -> str:
    branch = f"auto/qpk-pin-sync-{qpk_sha[:12]}-{repo.name.lower()}"
    remote_url = f"https://x-access-token:{token}@github.com/QuantStrategyLab/{repo.name}.git"
    run(["git", "checkout", "-B", branch], cwd=repo_dir)
    run(
        ["git", "config", "user.name", os.environ.get("QSL_PIN_SYNC_GIT_NAME", "QuantStrategyLab QPK Sync")],
        cwd=repo_dir,
    )
    run(
        ["git", "config", "user.email", os.environ.get("QSL_PIN_SYNC_GIT_EMAIL", "qpk-sync@users.noreply.github.com")],
        cwd=repo_dir,
    )
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

    remote_ref = f"refs/heads/{branch}"
    remote_branch = run(["git", "ls-remote", remote_url, remote_ref], cwd=repo_dir)
    remote_sha = remote_branch.stdout.split()[0] if remote_branch.stdout.strip() else ""
    push_cmd = ["git", "push"]
    if remote_sha:
        push_cmd.append(f"--force-with-lease={remote_ref}:{remote_sha}")
    push_cmd.extend([remote_url, f"HEAD:{branch}"])
    run(push_cmd, cwd=repo_dir)
    env = {**os.environ, "GH_TOKEN": token}
    existing = run(
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
            "url",
            "--jq",
            ".[0].url // empty",
        ],
        cwd=repo_dir,
        env=env,
    ).stdout.strip()
    if existing:
        return f"{repo.name}: updated existing PR {existing}"
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
    parser.add_argument(
        "--phase",
        choices=("auto", "strategies", "consumers"),
        default="auto",
        help="Roll out strategy pins before aggregate and broker/QMT consumer pins.",
    )
    parser.add_argument("--repo", action="append", default=[], help="Limit to one or more repo names")
    return parser.parse_args()


def discover_strategy_heads(
    root: Path,
    *,
    token: str,
    qpk_sha: str,
    dry_run: bool,
) -> tuple[dict[str, str], list[str]]:
    heads: dict[str, str] = {}
    blocked: list[str] = []
    for repo in STRATEGY_REPOS:
        repo_dir = clone_repo(repo, root, token, dry_run=dry_run)
        head = run(["git", "rev-parse", "HEAD"], cwd=repo_dir).stdout.strip()
        heads[repo.name] = head
        refs = qpk_refs(repo_dir)
        if refs != {qpk_sha}:
            rendered = ",".join(sorted(ref[:12] for ref in refs)) or "missing"
            blocked.append(f"{repo.name}:qpk_refs={rendered}")
    return heads, blocked


def main() -> int:
    args = parse_args()
    token = os.environ.get(args.token_env, "").strip()
    if not token and not args.dry_run:
        print(f"Missing required token env: {args.token_env}")
        return 2

    bundle_root = Path(__file__).resolve().parent.parent
    qpk_pin = bundle_root / "QPK_PIN"
    qpk_sha = get_qpk_pin_sha(pin_file=qpk_pin)

    results: list[str] = []
    failures = 0
    with tempfile.TemporaryDirectory(prefix="qpk-downstream-") as tmp:
        root = Path(tmp)
        audit_root = root / "strategy-audit"
        audit_root.mkdir()
        strategy_heads, blocked = discover_strategy_heads(
            audit_root,
            token=token,
            qpk_sha=qpk_sha,
            dry_run=args.dry_run,
        )
        phase = args.phase
        if phase == "auto":
            phase = "strategies" if blocked else "consumers"
        if phase == "consumers" and blocked:
            print("consumer_phase_parked:strategy_qpk_alignment_incomplete")
            print("\n".join(blocked))
            return 3

        available = STRATEGY_REPOS if phase == "strategies" else CONSUMER_REPOS
        repo_specs = [
            repo for repo in available if not args.repo or repo.name in args.repo
        ]
        if not repo_specs:
            print(f"No downstream repos selected for phase: {phase}")
            return 0

        if phase == "consumers":
            update_aggregate_bundle(
                bundle_root,
                qpk_sha=qpk_sha,
                strategy_heads=strategy_heads,
            )
        target_root = root / "targets"
        target_root.mkdir()
        for repo in repo_specs:
            repo_dir = clone_repo(repo, target_root, token, dry_run=args.dry_run)
            if not update_repo(
                repo_dir,
                qpk_pin,
                strategy_heads=strategy_heads if phase == "consumers" else None,
            ):
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
                failures += 1
    print(f"phase={phase}")
    print("\n".join(results))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
