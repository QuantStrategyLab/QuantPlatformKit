#!/usr/bin/env python3
"""Verify dependent repos reference QPK_PIN across pyproject, lockfiles, and overrides."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

QPK_REPO_NAME = "QuantPlatformKit"
QPK_PACKAGE_NAMES = frozenset({"quant-platform-kit", "quant_platform_kit"})
GIT_SHA_AT_RE = re.compile(r"@([a-f0-9]{40})")
GIT_SHA_REV_RE = re.compile(
    r"QuantPlatformKit\.git\?rev=([a-f0-9]{40})",
    re.IGNORECASE,
)
GIT_SHA_HASH_RE = re.compile(
    r"QuantPlatformKit\.git#[a-f0-9]{40}#([a-f0-9]{40})",
    re.IGNORECASE,
)
QSL_REF_RE = re.compile(r"github\.com/QuantStrategyLab/([A-Za-z0-9_.-]+)\.git@([A-Za-z0-9._/-]+)")
TRACKED_FILENAMES = (
    "pyproject.toml",
    "uv.lock",
    "requirements.txt",
    "requirements-lock.txt",
)
PINNED_FILE_GLOBS = ("requirements*.txt", "constraints*.txt", "pyproject.toml")


def get_qpk_pin_sha(*, pin_file: Path | None = None) -> str:
    """Read canonical QPK SHA from QPK_PIN, falling back to remote main."""
    candidates = []
    if pin_file is not None:
        candidates.append(pin_file)
    candidates.append(Path(__file__).resolve().parent.parent / "QPK_PIN")

    for pin_path in candidates:
        if not pin_path.is_file():
            continue
        sha = pin_path.read_text(encoding="utf-8").strip().split()[0]
        if len(sha) == 40:
            return sha

    try:
        result = subprocess.run(
            ["git", "ls-remote", f"https://github.com/QuantStrategyLab/{QPK_REPO_NAME}.git", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        sha = result.stdout.split()[0]
        if len(sha) == 40:
            return sha
    except subprocess.CalledProcessError:
        pass

    raise RuntimeError("Cannot resolve QPK pin SHA from QPK_PIN or git remote")


def repo_root_from_args(argv: list[str]) -> Path:
    parser = argparse.ArgumentParser(description="Check QPK git pin consistency.")
    parser.add_argument("--fix", action="store_true", help="Rewrite mismatched SHAs to QPK_PIN.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Consumer repository root.")
    parser.add_argument(
        "--pin-file",
        type=Path,
        default=None,
        help="Optional QPK_PIN path (defaults to QPK repo adjacent to this script).",
    )
    args = parser.parse_args(argv)
    return args.root.resolve(), args.pin_file, args.fix


def find_dep_files(root: Path) -> list[Path]:
    paths: dict[str, Path] = {}
    for name in TRACKED_FILENAMES:
        path = root / name
        if path.is_file():
            paths[str(path)] = path
    for pattern in PINNED_FILE_GLOBS:
        for path in root.glob(pattern):
            if "external" in path.parts:
                continue
            paths[str(path)] = path
    return sorted(paths.values())


def check_qsl_cross_file_consistency(root: Path) -> list[str]:
    qsl_refs: dict[str, list[tuple[Path, int, str]]] = {}
    for path in find_dep_files(root):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for repo, ref in QSL_REF_RE.findall(line):
                qsl_refs.setdefault(repo, []).append((path, line_no, ref))

    errors: list[str] = []
    for repo, matches in sorted(qsl_refs.items()):
        refs = sorted({ref for _, _, ref in matches})
        if len(refs) <= 1:
            continue
        errors.append(f"❌ inconsistent QuantStrategyLab dependency pin for {repo}:")
        for path, line_no, ref in matches:
            errors.append(f"   {path.relative_to(root)}:{line_no}: {ref}")
    return errors


def _line_refs(line: str) -> list[str]:
    if QPK_REPO_NAME not in line and "quant-platform-kit" not in line and "quant_platform_kit" not in line:
        return []
    refs: list[str] = []
    refs.extend(GIT_SHA_AT_RE.findall(line))
    refs.extend(GIT_SHA_REV_RE.findall(line))
    refs.extend(GIT_SHA_HASH_RE.findall(line))
    return refs


def extract_qpk_shas(path: Path) -> list[tuple[int, str, str]]:
    results: list[tuple[int, str, str]] = []
    for line_num, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for sha in _line_refs(line):
            results.append((line_num, line.strip(), sha))
    return results


def extract_override_qpk_sha(pyproject_text: str) -> str | None:
    try:
        data = tomllib.loads(pyproject_text)
    except tomllib.TOMLDecodeError:
        return None
    overrides = (data.get("tool") or {}).get("uv", {}).get("override-dependencies") or []
    if not isinstance(overrides, list):
        return None
    for item in overrides:
        if not isinstance(item, str):
            continue
        if QPK_REPO_NAME not in item and "quant-platform-kit" not in item:
            continue
        matches = GIT_SHA_AT_RE.findall(item)
        if matches:
            return matches[0]
    return None


def check_repo(*, root: Path, target_sha: str, fix_mode: bool) -> tuple[int, int, list[str]]:
    errors: list[str] = []
    files_checked = 0
    mismatches = 0
    target_short = target_sha[:12]

    pyproject = root / "pyproject.toml"
    override_sha = None
    if pyproject.is_file():
        override_sha = extract_override_qpk_sha(pyproject.read_text(encoding="utf-8"))

    for path in find_dep_files(root):
        refs = extract_qpk_shas(path)
        if not refs:
            continue
        files_checked += 1
        for line_num, _raw_line, sha in refs:
            if sha == target_sha:
                continue
            mismatches += 1
            hint = ""
            if path.name == "uv.lock" and pyproject.is_file():
                hint = " (run `uv lock` after aligning pyproject.toml)"
            msg = (
                f"❌ {path.relative_to(root)}:{line_num} references QPK@{sha[:12]} "
                f"(expected {target_short}){hint}"
            )
            errors.append(msg)
            if fix_mode:
                path.write_text(path.read_text(encoding="utf-8").replace(sha, target_sha), encoding="utf-8")

    if override_sha and override_sha != target_sha:
        mismatches += 1
        msg = (
            f"❌ pyproject.toml tool.uv.override-dependencies references QPK@{override_sha[:12]} "
            f"(expected {target_short})"
        )
        errors.append(msg)

    if pyproject.is_file() and (root / "uv.lock").is_file():
        lock_shas = {sha for _ln, _raw, sha in extract_qpk_shas(root / "uv.lock")}
        declared = {sha for _ln, _raw, sha in extract_qpk_shas(pyproject)}
        if override_sha:
            declared.add(override_sha)
        if lock_shas and declared and lock_shas != declared:
            mismatches += 1
            errors.append(
                "❌ uv.lock QPK pin(s) "
                f"{{{', '.join(sorted(s[:12] for s in lock_shas))}}} "
                f"do not match pyproject/override "
                f"{{{', '.join(sorted(s[:12] for s in declared))}}}; run `uv lock`"
            )

    cross_errors = check_qsl_cross_file_consistency(root)
    errors.extend(cross_errors)
    mismatches += sum(1 for err in cross_errors if err.startswith("❌ inconsistent"))

    return files_checked, mismatches, errors


def main(argv: list[str] | None = None) -> int:
    root, pin_file, fix_mode = repo_root_from_args(argv or sys.argv[1:])
    target_sha = get_qpk_pin_sha(pin_file=pin_file)
    target_short = target_sha[:12]
    print(f"Target QPK SHA: {target_short}...")

    files_checked, mismatches, errors = check_repo(root=root, target_sha=target_sha, fix_mode=fix_mode)
    for msg in errors:
        print(msg)
        if fix_mode and "→" not in msg:
            print(f"   → Fixed to {target_short}")

    if mismatches == 0:
        print(f"✅ All {files_checked} dependency files reference QPK@{target_short}")
        return 0

    print(f"\n{mismatches} mismatch(es) in {files_checked} file(s)")
    if fix_mode:
        print("Fixed. Please commit the changes and run `uv lock` if uv.lock was touched.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
