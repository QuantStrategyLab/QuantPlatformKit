#!/usr/bin/env python3
"""Verify all dependent repos reference the same QPK SHA as QPK_PIN.

Usage:
  python scripts/check_qpk_pin_consistency.py [--fix]

Checks that all git-based dependencies in requirements.txt / pyproject.toml
reference the same QPK commit as recorded in QPK_PIN.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

QPK_REPO_URL = "https://github.com/QuantStrategyLab/QuantPlatformKit.git"
GIT_SHA_RE = re.compile(r"@([a-f0-9]{40})")


def get_qpk_pin_sha() -> str:
    """Read the canonical QPK SHA from QPK_PIN, falling back to remote main."""
    pin_path = Path(__file__).resolve().parent.parent / "QPK_PIN"
    if pin_path.exists():
        sha = pin_path.read_text().strip().split()[0]
        if len(sha) == 40:
            return sha

    # Fallback: query remote
    try:
        result = subprocess.run(
            ["git", "ls-remote", "https://github.com/QuantStrategyLab/QuantPlatformKit.git", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        sha = result.stdout.split()[0]
        if len(sha) == 40:
            return sha
    except subprocess.CalledProcessError:
        pass

    raise RuntimeError("Cannot resolve QPK pin SHA from QPK_PIN or git remote")


def find_dep_files() -> list[Path]:
    """Find all files that might contain QPK dependency pins."""
    files: list[Path] = []
    cwd = Path.cwd()
    for pattern in ("**/requirements*.txt", "**/pyproject.toml"):
        for path in cwd.glob(pattern):
            if "external" not in str(path):
                files.append(path)
    return sorted(set(files))


def extract_qpk_shas(path: Path) -> list[tuple[int, str, str]]:
    """Yield (line_num, raw_match, sha) for each QPK git reference in file."""
    results: list[tuple[int, str, str]] = []
    for i, line in enumerate(path.read_text().splitlines(), 1):
        if "QuantPlatformKit" not in line:
            continue
        matches = GIT_SHA_RE.findall(line)
        for sha in matches:
            results.append((i, line.strip(), sha))
    return results


def main() -> int:
    fix_mode = "--fix" in sys.argv
    target_sha = get_qpk_pin_sha()
    target_short = target_sha[:12]
    print(f"Target QPK SHA: {target_short}...")

    errors: list[str] = []
    files_checked = 0
    mismatches = 0

    for path in find_dep_files():
        refs = extract_qpk_shas(path)
        if not refs:
            continue
        files_checked += 1
        for line_num, raw_line, sha in refs:
            if sha != target_sha:
                mismatches += 1
                msg = (
                    f"❌ {path}:{line_num} references QPK@{sha[:12]} "
                    f"(expected {target_short})"
                )
                errors.append(msg)
                print(msg)
                if fix_mode:
                    new_content = path.read_text().replace(sha, target_sha)
                    path.write_text(new_content)
                    print(f"   → Fixed to {target_short}")

    if mismatches == 0:
        print(f"✅ All {files_checked} files reference QPK@{target_short}")
        return 0

    total_refs = sum(1 for p in find_dep_files() for _ in extract_qpk_shas(p))
    print(f"\n{mismatches}/{total_refs} mismatches in {files_checked} files")
    if fix_mode:
        print("Fixed. Please commit the changes.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
