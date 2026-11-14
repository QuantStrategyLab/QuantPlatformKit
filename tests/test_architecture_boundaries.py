"""Architecture boundary guardrails for pure contract and domain modules.

Enforces that pure contract/domain packages and modules do not import edge
adapters or external broker/cloud SDKs at module or runtime scope.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

CONTRACT_MODULES: tuple[str, ...] = (
    "quant_platform_kit.common",
    "quant_platform_kit.schemas",
    "quant_platform_kit.strategy_spec",
    "quant_platform_kit.risk",
    "quant_platform_kit.strategy_lifecycle.contracts",
)

FORBIDDEN_EDGE_PACKAGES: tuple[str, ...] = (
    "quant_platform_kit.binance",
    "quant_platform_kit.ibkr",
    "quant_platform_kit.longbridge",
    "quant_platform_kit.schwab",
    "quant_platform_kit.quantconnect",
    "quant_platform_kit.cloud",
    "quant_platform_kit.notifications",
)

FORBIDDEN_EXTERNAL_SDKS: tuple[str, ...] = (
    "ib_insync",
    "ibapi",
    "longport",
    "binance",
    "ccxt",
    "boto3",
    "google.cloud",
    "azure",
)

FORBIDDEN_TARGETS: tuple[str, ...] = FORBIDDEN_EDGE_PACKAGES + FORBIDDEN_EXTERNAL_SDKS

# Pre-existing legacy imports frozen on origin/main.
# Never add new entries here; remove entries as legacy code moves behind ports.
LEGACY_EDGE_IMPORTS: frozenset[tuple[str, str]] = frozenset(
    {
        (
            "src/quant_platform_kit/common/automation_setup.py",
            "quant_platform_kit.notifications._redaction",
        ),
        (
            "src/quant_platform_kit/common/execution_commands.py",
            "quant_platform_kit.cloud",
        ),
        (
            "src/quant_platform_kit/common/execution_state.py",
            "quant_platform_kit.cloud",
        ),
        (
            "src/quant_platform_kit/common/feature_snapshot/io.py",
            "quant_platform_kit.cloud",
        ),
        (
            "src/quant_platform_kit/common/health.py",
            "google.cloud",
        ),
        (
            "src/quant_platform_kit/common/operational_notification_localization.py",
            "quant_platform_kit.notifications.presentation",
        ),
        (
            "src/quant_platform_kit/common/platform_runner/app.py",
            "quant_platform_kit.cloud",
        ),
        (
            "src/quant_platform_kit/common/platform_runner/monitor.py",
            "quant_platform_kit.cloud",
        ),
        (
            "src/quant_platform_kit/common/runtime_reports.py",
            "quant_platform_kit.cloud",
        ),
        (
            "src/quant_platform_kit/common/strategy_plugin_artifacts.py",
            "quant_platform_kit.cloud",
        ),
        (
            "src/quant_platform_kit/common/strategy_risk_state.py",
            "quant_platform_kit.cloud",
        ),
        (
            "src/quant_platform_kit/risk/attention.py",
            "quant_platform_kit.notifications.presentation",
        ),
        (
            "src/quant_platform_kit/risk/attention_notify.py",
            "quant_platform_kit.notifications.telegram",
        ),
    }
)


def _matches_forbidden(target: str) -> bool:
    if not target:
        return False
    return any(
        target == forbidden or target.startswith(f"{forbidden}.")
        for forbidden in FORBIDDEN_TARGETS
    )


def _classify_type_checking_guard(test: ast.expr) -> tuple[bool, bool]:
    """Return (is_guard, true_branch_is_type_checking_only)."""
    if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
        return True, True
    if isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
        return True, True
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        is_guard, positive = _classify_type_checking_guard(test.operand)
        if is_guard:
            return True, not positive
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
        for value in test.values:
            is_guard, positive = _classify_type_checking_guard(value)
            if is_guard and positive:
                return True, True
    return False, False


def _resolve_import_from(
    package_parts: tuple[str, ...],
    level: int,
    module: str | None,
) -> str:
    if level == 0:
        return module or ""
    up = level - 1
    if up > len(package_parts):
        return module or ""
    base = package_parts if up == 0 else package_parts[:-up]
    if module:
        return ".".join((*base, *module.split(".")))
    return ".".join(base)


class _RuntimeImportCollector(ast.NodeVisitor):
    """Collect forbidden imports at module or runtime scope, skipping TYPE_CHECKING."""

    def __init__(self, package_parts: tuple[str, ...]) -> None:
        self.package_parts = package_parts
        self.targets: list[str] = []

    def visit_If(self, node: ast.If) -> None:
        is_guard, true_is_tc = _classify_type_checking_guard(node.test)
        if is_guard:
            runtime_stmts = node.orelse if true_is_tc else node.body
            for stmt in runtime_stmts:
                self.visit(stmt)
            return
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if _matches_forbidden(alias.name):
                self.targets.append(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        resolved = _resolve_import_from(self.package_parts, node.level, node.module)
        if _matches_forbidden(resolved):
            self.targets.append(resolved)
            return
        for alias in node.names:
            if alias.name == "*":
                continue
            candidate = f"{resolved}.{alias.name}" if resolved else alias.name
            if _matches_forbidden(candidate):
                self.targets.append(candidate)


def _package_parts_for_rel_path(rel_to_src: Path) -> tuple[str, ...]:
    parts = rel_to_src.with_suffix("").parts
    return tuple(parts[:-1])


def scan_source_for_forbidden_imports(source: str, rel_to_src: Path) -> set[str]:
    tree = ast.parse(source, filename=str(rel_to_src))
    collector = _RuntimeImportCollector(_package_parts_for_rel_path(rel_to_src))
    collector.visit(tree)
    return set(collector.targets)


def iter_contract_python_files() -> list[Path]:
    files: list[Path] = []
    for dotted in CONTRACT_MODULES:
        base = SRC_ROOT / Path(*dotted.split("."))
        module_file = base.with_suffix(".py")
        if module_file.is_file():
            files.append(module_file)
        if base.is_dir():
            files.extend(
                path
                for path in sorted(base.rglob("*.py"))
                if "__pycache__" not in path.parts
            )
    return sorted(set(files))


def collect_contract_boundary_violations() -> frozenset[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for path in iter_contract_python_files():
        rel_repo = path.relative_to(REPO_ROOT).as_posix()
        rel_src = path.relative_to(SRC_ROOT)
        source = path.read_text(encoding="utf-8")
        for target in scan_source_for_forbidden_imports(source, rel_src):
            found.add((rel_repo, target))
    return frozenset(found)


def test_contract_modules_do_not_introduce_edge_or_sdk_imports() -> None:
    files = iter_contract_python_files()
    assert files, "Expected contract/domain Python files to scan"

    found = collect_contract_boundary_violations()
    unexpected = sorted(found - LEGACY_EDGE_IMPORTS)
    assert found <= LEGACY_EDGE_IMPORTS, (
        "New edge/adapter or external SDK import(s) found in pure contract/domain modules: "
        f"{unexpected}"
    )

    stale = sorted(LEGACY_EDGE_IMPORTS - found)
    assert found == LEGACY_EDGE_IMPORTS, (
        "Stale LEGACY_EDGE_IMPORTS exemption(s) remain after cleanup; remove: "
        f"{stale}"
    )


def test_boundary_scanner_handles_relative_runtime_and_type_checking() -> None:
    rel_src = Path("quant_platform_kit/common/sample.py")
    snippet = """
from typing import TYPE_CHECKING
import typing

if TYPE_CHECKING:
    from quant_platform_kit.cloud import ObjectStore
    import boto3

if typing.TYPE_CHECKING:
    from ..ibkr import client

def runtime_helper() -> None:
    from ..cloud import get_object_store
    from .. import binance
    import ccxt
"""
    hits = scan_source_for_forbidden_imports(snippet, rel_src)
    assert hits == {
        "quant_platform_kit.cloud",
        "quant_platform_kit.binance",
        "ccxt",
    }

    nested_rel_src = Path("quant_platform_kit/common/nested/deep.py")
    nested_snippet = """
from ...schwab.client import SchwabClient
import google.cloud.storage
"""
    nested_hits = scan_source_for_forbidden_imports(nested_snippet, nested_rel_src)
    assert nested_hits == {
        "quant_platform_kit.schwab.client",
        "google.cloud.storage",
    }
