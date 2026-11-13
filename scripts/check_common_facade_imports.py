#!/usr/bin/env python3
"""Guardrails for quant_platform_kit.common facade growth and import paths.

Checks:
  1. common/__init__.py stays within a line budget (blocks unbounded facade growth).
  2. Topic subpackages ``execution`` and ``reconciliation`` import cleanly and
     expose every name listed in their ``__all__``.
  3. ``execution_kernel.platform_http`` documents the Wave2 thin-main template
     (module map + explicit re-export rules).
  4. Optionally (--strict) fail on wide ``from quant_platform_kit.common import``
     in src/ outside ``common/`` itself (legacy code may still use the facade).

Usage:
    PYTHONPATH=src python scripts/check_common_facade_imports.py
    PYTHONPATH=src python scripts/check_common_facade_imports.py --strict
"""

from __future__ import annotations

import argparse
import ast
import importlib
import sys
from pathlib import Path

# Baseline after #782; keep closed so new APIs land in subpackages, not here.
COMMON_INIT_LINE_BUDGET = 620

FORBIDDEN_IMPORT_PREFIX = "from quant_platform_kit.common import"
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "build", "dist"}

SUBPACKAGES = (
    "quant_platform_kit.execution",
    "quant_platform_kit.reconciliation",
    "quant_platform_kit.execution_kernel",
)

PLATFORM_HTTP_MODULE_KEYS = frozenset(
    {
        "main",
        "http_routes",
        "runtime_wiring",
        "notifications_runtime",
        "strategy_plugins_runtime",
        "platform_entry",
    }
)
PLATFORM_THIN_MAIN_RULE_KEYS = frozenset(
    {
        "explicit_reexports",
        "all_list",
        "no_star_api",
        "entry_bind",
        "behavior",
    }
)


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def check_common_line_budget(root: Path) -> list[str]:
    common_init = root / "src" / "quant_platform_kit" / "common" / "__init__.py"
    if not common_init.is_file():
        return [f"missing {common_init}"]
    line_count = len(common_init.read_text(encoding="utf-8").splitlines())
    if line_count > COMMON_INIT_LINE_BUDGET:
        return [
            f"{common_init.relative_to(root)} has {line_count} lines "
            f"(budget {COMMON_INIT_LINE_BUDGET}); add APIs via subpackages, "
            "do not grow the facade"
        ]
    return []


def check_subpackage_exports(package_name: str) -> list[str]:
    errors: list[str] = []
    try:
        module = importlib.import_module(package_name)
    except Exception as exc:  # noqa: BLE001 — report import failures to the user
        return [f"failed to import {package_name}: {exc}"]

    exported = getattr(module, "__all__", None)
    if not exported:
        return [f"{package_name} has no __all__"]
    for name in exported:
        if not hasattr(module, name):
            errors.append(f"{package_name}: __all__ lists missing name {name!r}")
    return errors


def check_platform_http_template() -> list[str]:
    errors: list[str] = []
    try:
        from quant_platform_kit.execution_kernel.platform_http import (
            describe_platform_http_modules,
            describe_platform_thin_main_rules,
        )
    except Exception as exc:  # noqa: BLE001
        return [f"failed to import platform_http template: {exc}"]

    modules = describe_platform_http_modules()
    missing_modules = PLATFORM_HTTP_MODULE_KEYS - frozenset(modules)
    if missing_modules:
        errors.append(
            "platform_http.describe_platform_http_modules missing keys: "
            + ", ".join(sorted(missing_modules))
        )

    rules = describe_platform_thin_main_rules()
    missing_rules = PLATFORM_THIN_MAIN_RULE_KEYS - frozenset(rules)
    if missing_rules:
        errors.append(
            "platform_http.describe_platform_thin_main_rules missing keys: "
            + ", ".join(sorted(missing_rules))
        )
    return errors


def iter_python_files(root: Path) -> list[Path]:
    src = root / "src"
    files: list[Path] = []
    for path in src.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


def file_uses_wide_common_import(path: Path, common_pkg_dir: Path) -> bool:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return False
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "quant_platform_kit.common":
            if node.names and any(alias.name != "*" for alias in node.names):
                return True
    return FORBIDDEN_IMPORT_PREFIX in source and "quant_platform_kit.common import" in source


def check_forbidden_wide_imports(root: Path) -> list[str]:
    common_pkg_dir = root / "src" / "quant_platform_kit" / "common"
    violations: list[str] = []
    for path in iter_python_files(root):
        if common_pkg_dir in path.parents or path.parent == common_pkg_dir:
            continue
        if file_uses_wide_common_import(path, common_pkg_dir):
            violations.append(str(path.relative_to(root)))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail when src/ (outside common/) uses from quant_platform_kit.common import",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="repository root (default: parent of scripts/)",
    )
    args = parser.parse_args()
    root = args.root or repo_root_from_script()

    errors: list[str] = []
    errors.extend(check_common_line_budget(root))
    for package in SUBPACKAGES:
        errors.extend(check_subpackage_exports(package))
    errors.extend(check_platform_http_template())

    wide_import_hits = check_forbidden_wide_imports(root)
    if wide_import_hits:
        print(
            "Note: prefer quant_platform_kit.execution, quant_platform_kit.reconciliation, "
            "or quant_platform_kit.common.<module> instead of:\n"
            f"  {FORBIDDEN_IMPORT_PREFIX} ...\n",
            file=sys.stderr,
        )
        if args.strict:
            for hit in sorted(wide_import_hits):
                errors.append(f"wide common facade import: {hit}")
        else:
            print(
                f"Found {len(wide_import_hits)} file(s) with wide common imports "
                "(not failing; use --strict to enforce).",
                file=sys.stderr,
            )

    if errors:
        print("check_common_facade_imports failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("check_common_facade_imports passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
