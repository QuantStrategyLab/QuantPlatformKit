#!/usr/bin/env python3
"""Open downstream PRs after QPK_PIN lands on main."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PinRelation = Literal["equal", "behind", "ahead", "diverged"]
SyncMode = Literal["upgrade-affected", "cohort-all"]

_NON_RUNTIME_PATH_PREFIXES = (
    "docs/",
    "doc/",
    ".github/",
    "tests/",
    "test/",
    "examples/",
    "notes/",
)
_NON_RUNTIME_EXACT = {
    "readme.md",
    "readme.zh-cn.md",
    "changelog.md",
    "license",
    "license.md",
    "security.md",
    "contributing.md",
    "code_of_conduct.md",
    "qpk_pin",
    "qsl-pins.txt",
    "constraints.txt",
}

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
CI_QPK_EXPECTED_PIN_RE = re.compile(
    r"(?m)(?P<prefix>QPK_EXPECTED_PIN=)(?P<sha>[a-f0-9]{40})(?P<suffix>\s+uv run --no-sync python scripts/check_qpk_pin_consistency\.py)"
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

# These repositories receive generated dependency PRs only.  The workflow never
# merges them or deploys them: execution platforms need their own runtime review,
# while P1 pipelines need their own evidence/data review.
EXECUTION_CONSUMER_REPOS = (
    RepoSpec("InteractiveBrokersPlatform"),
    RepoSpec("LongBridgePlatform"),
    RepoSpec("CharlesSchwabPlatform"),
    RepoSpec("FirstradePlatform"),
    RepoSpec("BinancePlatform"),
    RepoSpec("QmtPlatform"),
)

PIPELINE_CONSUMER_REPOS = (
    RepoSpec("CnEquitySnapshotPipelines"),
    RepoSpec("HkEquitySnapshotPipelines"),
    RepoSpec("UsEquitySnapshotPipelines"),
    RepoSpec("CryptoLivePoolPipelines"),
)

CONSUMER_REPOS = (*EXECUTION_CONSUMER_REPOS, *PIPELINE_CONSUMER_REPOS)

STRATEGY_QSL_KEYS = {
    "CnEquityStrategies": "cn_equity_strategies",
    "HkEquityStrategies": "hk_equity_strategies",
    "UsEquityStrategies": "us_equity_strategies",
    "CryptoStrategies": "crypto_strategies",
}

def run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True, check=True)


def command_failure_summary(exc: subprocess.CalledProcessError) -> str:
    """Return an actionable failure marker without copying command output to logs."""
    command = exc.cmd
    if isinstance(command, (list, tuple)) and command:
        executable = Path(str(command[0])).name
    elif isinstance(command, str):
        executable = command.split(maxsplit=1)[0]
    else:
        executable = "unknown"
    return f"command={executable}:exit={exc.returncode}"


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


def classify_pin_relation(
    current: str,
    candidate: str,
    *,
    is_ancestor: Callable[[str, str], bool],
) -> PinRelation:
    """Classify consumer pin relative to a candidate QPK SHA.

    * equal: already on candidate
    * behind: current is an ancestor of candidate (safe to upgrade)
    * ahead: candidate is a strict ancestor of current (opening a PR would downgrade)
    * diverged: neither is ancestor of the other (needs human review)
    """
    current_sha = current.strip().lower()
    candidate_sha = candidate.strip().lower()
    if not re.fullmatch(r"[a-f0-9]{40}", current_sha):
        raise ValueError(f"invalid current sha: {current}")
    if not re.fullmatch(r"[a-f0-9]{40}", candidate_sha):
        raise ValueError(f"invalid candidate sha: {candidate}")
    if current_sha == candidate_sha:
        return "equal"
    current_is_ancestor = is_ancestor(current_sha, candidate_sha)
    candidate_is_ancestor = is_ancestor(candidate_sha, current_sha)
    if current_is_ancestor and not candidate_is_ancestor:
        return "behind"
    if candidate_is_ancestor and not current_is_ancestor:
        return "ahead"
    return "diverged"


def should_open_upgrade_pr(relation: PinRelation, *, mode: SyncMode) -> bool:
    """Refuse equal/ahead/diverged in every mode; never open a downgrade PR."""
    del mode  # mode selects repo set / path filter elsewhere; downgrade policy is absolute
    return relation == "behind"


def paths_affect_runtime(paths: list[str]) -> bool:
    """Return True when changed paths may affect runtime consumers."""
    for raw in paths:
        path = raw.strip().replace("\\", "/")
        while path.startswith("./"):
            path = path[2:]
        if not path:
            continue
        lower = path.lower()
        if lower in _NON_RUNTIME_EXACT:
            continue
        if any(lower.startswith(prefix) for prefix in _NON_RUNTIME_PATH_PREFIXES):
            continue
        return True
    return False


def git_is_ancestor(*, repo_dir: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repo_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def changed_paths_between(repo_dir: Path, before_sha: str, after_sha: str) -> list[str]:
    result = run(
        ["git", "diff", "--name-only", f"{before_sha}..{after_sha}"],
        cwd=repo_dir,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def resolve_repo_relation(
    repo_dir: Path,
    *,
    candidate_sha: str,
    qpk_repo_dir: Path,
) -> tuple[PinRelation | None, str]:
    """Return relation for a consumer checkout, or None when no pin is present."""
    refs = sorted(qpk_refs(repo_dir))
    if not refs:
        return None, "missing_qpk_pin"
    if len(refs) > 1:
        return "diverged", f"multiple_qpk_pins:{','.join(ref[:12] for ref in refs)}"

    current = refs[0]

    def is_ancestor(ancestor: str, descendant: str) -> bool:
        return git_is_ancestor(
            repo_dir=qpk_repo_dir,
            ancestor=ancestor,
            descendant=descendant,
        )

    # Ensure both SHAs exist locally before ancestry checks.
    run(["git", "fetch", "--no-tags", "origin", current, candidate_sha], cwd=qpk_repo_dir)
    relation = classify_pin_relation(current, candidate_sha, is_ancestor=is_ancestor)
    return relation, current


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


def update_ci_qpk_pin_contract(
    repo_dir: Path,
    *,
    qpk_sha: str,
    previous_qpk_refs: set[str],
) -> bool:
    """Update a consumer CI pin only when it matches the prior dependency pin."""

    path = repo_dir / ".github" / "workflows" / "ci.yml"
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    matches = list(CI_QPK_EXPECTED_PIN_RE.finditer(original))
    if not matches:
        return False
    if len(matches) != 1:
        raise RuntimeError(f"ci_qpk_pin_contract_update_failed:matches={len(matches)}")
    previous_sha = matches[0].group("sha")
    if previous_sha == qpk_sha:
        return False
    if previous_sha not in previous_qpk_refs:
        raise RuntimeError("ci_qpk_pin_contract_update_failed:unexpected_prior_pin")
    updated = CI_QPK_EXPECTED_PIN_RE.sub(rf"\g<prefix>{qpk_sha}\g<suffix>", original)
    path.write_text(updated, encoding="utf-8")
    return True


def collect_qpk_workflow_pins(text: str) -> set[str]:
    """Collect SHAs only from explicit QuantPlatformKit workflow pins."""
    pins: set[str] = set()
    pins.update(
        re.findall(
            r"QuantStrategyLab/QuantPlatformKit(?:/\.github/workflows/[^\s@]+)?@([a-f0-9]{40})",
            text,
        )
    )
    pins.update(
        re.findall(
            r"repository:\s*QuantStrategyLab/QuantPlatformKit\n\s*ref:\s*([a-f0-9]{40})",
            text,
        )
    )
    pins.update(re.findall(r"quant_platform_kit_ref:\s*([a-f0-9]{40})", text))
    return pins


def rewrite_qpk_workflow_pin_contexts(text: str, *, prior_sha: str, qpk_sha: str) -> str:
    """Rewrite one prior SHA only inside explicit QPK repository/ref/uses/input contexts."""
    updated = re.sub(
        rf"(QuantStrategyLab/QuantPlatformKit(?:/\.github/workflows/[^\s@]+)?@){prior_sha}",
        rf"\g<1>{qpk_sha}",
        text,
    )
    updated = re.sub(
        rf"(repository:\s*QuantStrategyLab/QuantPlatformKit\n\s*ref:\s*){prior_sha}",
        rf"\g<1>{qpk_sha}",
        updated,
    )
    updated = re.sub(
        rf"(quant_platform_kit_ref:\s*){prior_sha}",
        rf"\g<1>{qpk_sha}",
        updated,
    )
    return updated


def update_drift_workflow_file(
    repo_dir: Path,
    *,
    qpk_sha: str,
    previous_qpk_refs: set[str],
) -> bool:
    """Keep strategy drift-check.yml QPK refs aligned with the package pin.

    ``check_qpk_pin_consistency --fix`` intentionally leaves immutable workflow
    pins alone. Strategy drift workflows are different: their contract tests
    assert the same SHA the package pin uses. Update only explicit QuantPlatformKit
    repository/ref/uses/input pins so checkout pins, snapshot SHAs, and other
    unrelated hashes stay untouched.
    """
    path = repo_dir / ".github" / "workflows" / "drift-check.yml"
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    workflow_pins = collect_qpk_workflow_pins(original)
    # previous_qpk_refs may include package pins; never treat non-QPK workflow
    # hashes as rewrite targets even if a caller accidentally collected them.
    previous = {
        sha
        for sha in previous_qpk_refs
        if re.fullmatch(r"[a-f0-9]{40}", sha) and sha != qpk_sha
    }
    priors = {sha for sha in (previous | workflow_pins) if sha in workflow_pins and sha != qpk_sha}
    updated = original
    for prior in sorted(priors):
        updated = rewrite_qpk_workflow_pin_contexts(
            updated,
            prior_sha=prior,
            qpk_sha=qpk_sha,
        )
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def update_drift_workflow_test_contract(
    repo_dir: Path,
    *,
    qpk_sha: str,
    previous_qpk_refs: set[str],
) -> bool:
    """Keep workflow-content assertions aligned with an updated reusable workflow pin.

    Strategy repositories deliberately test their pinned reusable drift workflow
    reference.  That test is a dependency surface just like ``pyproject.toml``
    and ``drift-check.yml``; leaving it stale makes an otherwise coherent pin
    update fail CI.  Only QPK SHAs observed before the update are replaced.
    """
    path = repo_dir / "tests" / "test_drift_workflow_config.py"
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    updated = original
    for previous_ref in sorted(previous_qpk_refs):
        if re.fullmatch(r"[a-f0-9]{40}", previous_ref) and previous_ref != qpk_sha:
            updated = updated.replace(previous_ref, qpk_sha)
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def update_qpk_test_pin_contracts(
    repo_dir: Path,
    *,
    qpk_sha: str,
    previous_qpk_refs: set[str],
) -> bool:
    """Refresh explicit QPK SHA assertions in consumer test contracts only.

    Some P1 pipelines assert their declared QPK revision in a test instead of
    reading the declaration dynamically.  Those assertions are part of the
    dependency surface, but must not leave a generated update red.  Restrict
    replacement to test files that explicitly name QuantPlatformKit and to an
    SHA that was already declared by the repository before this sync.
    """
    tests_dir = repo_dir / "tests"
    if not tests_dir.is_dir():
        return False

    changed = False
    previous = {
        sha
        for sha in previous_qpk_refs
        if re.fullmatch(r"[a-f0-9]{40}", sha) and sha != qpk_sha
    }
    for path in sorted(tests_dir.rglob("test_*.py")):
        original = path.read_text(encoding="utf-8")
        if "QuantPlatformKit" not in original:
            continue
        updated = original
        for prior_sha in sorted(previous):
            updated = updated.replace(prior_sha, qpk_sha)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed = True
    return changed


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
    previous_qpk_refs = qpk_refs(repo_dir)
    qpk_sha = get_qpk_pin_sha(pin_file=qpk_pin)
    run(
        ["python3", str(script), "--root", str(repo_dir), "--pin-file", str(qpk_pin), "--fix"],
        cwd=repo_dir,
    )
    update_qsl_compat_qpk_pin(repo_dir, qpk_sha)
    update_qpk_revision_contract(
        repo_dir,
        qpk_sha,
    )
    drift_workflow = repo_dir / ".github" / "workflows" / "drift-check.yml"
    if drift_workflow.is_file():
        previous_qpk_refs.update(
            collect_qpk_workflow_pins(drift_workflow.read_text(encoding="utf-8"))
        )
    update_drift_workflow_file(
        repo_dir,
        qpk_sha=qpk_sha,
        previous_qpk_refs=previous_qpk_refs,
    )
    update_drift_workflow_test_contract(
        repo_dir,
        qpk_sha=get_qpk_pin_sha(pin_file=qpk_pin),
        previous_qpk_refs=previous_qpk_refs,
    )
    if strategy_heads:
        update_ci_qpk_pin_contract(
            repo_dir,
            qpk_sha=qpk_sha,
            previous_qpk_refs=previous_qpk_refs,
        )
        update_qpk_test_pin_contracts(
            repo_dir,
            qpk_sha=qpk_sha,
            previous_qpk_refs=previous_qpk_refs,
        )
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


def previous_qpk_pin_sha(repo_dir: Path) -> str | None:
    """Return the prior QPK_PIN value from git history, if available."""
    history = run(
        ["git", "log", "-2", "--pretty=%H", "--", "QPK_PIN"],
        cwd=repo_dir,
    )
    commits = [line.strip() for line in history.stdout.splitlines() if line.strip()]
    if len(commits) < 2:
        return None
    prior = run(["git", "show", f"{commits[1]}:QPK_PIN"], cwd=repo_dir).stdout.strip()
    return prior if re.fullmatch(r"[a-f0-9]{40}", prior) else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open downstream QPK pin sync PRs.")
    parser.add_argument("--token-env", default="QSL_REPO_SYNC_TOKEN")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--phase",
        choices=("auto", "strategies", "consumers"),
        default="auto",
        help="Roll out strategy pins before aggregate and execution/P1 pipeline consumer pins.",
    )
    parser.add_argument(
        "--mode",
        choices=("upgrade-affected", "cohort-all"),
        default="upgrade-affected",
        help=(
            "upgrade-affected (default): only behind repos, and only when candidate "
            "changes runtime paths; never open downgrade PRs. "
            "cohort-all: still refuse downgrades/equal/diverged, but ignore path filter."
        ),
    )
    parser.add_argument(
        "--before-sha",
        default="",
        help="Optional previous QPK SHA for affected-path filtering (defaults to prior QPK_PIN).",
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
    mode: SyncMode = args.mode
    before_sha = args.before_sha.strip() or (previous_qpk_pin_sha(bundle_root) or "")
    if mode == "upgrade-affected" and before_sha and before_sha != qpk_sha:
        try:
            changed = changed_paths_between(bundle_root, before_sha, qpk_sha)
        except subprocess.CalledProcessError:
            changed = ["src/quant_platform_kit/unknown.py"]  # fail open to behind-only upgrades
        if not paths_affect_runtime(changed):
            print(
                "skip_all:candidate_has_no_runtime_path_impact "
                f"before={before_sha[:12]} candidate={qpk_sha[:12]}"
            )
            return 0

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
            try:
                relation, detail = resolve_repo_relation(
                    repo_dir,
                    candidate_sha=qpk_sha,
                    qpk_repo_dir=bundle_root,
                )
            except subprocess.CalledProcessError as exc:
                results.append(
                    f"{repo.name}: pin_relation_failed:{command_failure_summary(exc)}"
                )
                failures += 1
                continue
            if relation is not None and not should_open_upgrade_pr(relation, mode=mode):
                results.append(f"{repo.name}: skip_{relation}:{detail}")
                continue
            try:
                changed = update_repo(
                    repo_dir,
                    qpk_pin,
                    strategy_heads=strategy_heads if phase == "consumers" else None,
                )
            except subprocess.CalledProcessError as exc:
                results.append(
                    f"{repo.name}: dependency_update_failed:{command_failure_summary(exc)}"
                )
                failures += 1
                continue
            if not changed:
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
                stderr = (exc.stderr or exc.stdout or "").strip()
                results.append(f"{repo.name}: failed to open PR: {stderr}")
                failures += 1
    print(f"phase={phase}")
    print(f"mode={mode}")
    print("\n".join(results))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
