"""research_stats stays research-only.

1. No module outside ``quant_platform_kit.research_stats`` imports it.
2. ``research_stats`` imports nothing from the rest of QPK (one-way boundary).
3. Importing core/production packages never loads it.
4. Importing it never requires numpy (optional ``research`` extra).
"""

from __future__ import annotations

import ast
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "quant_platform_kit"
RESEARCH = PKG / "research_stats"
TARGET = "quant_platform_kit.research_stats"


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    rel_parts = path.relative_to(PKG.parent).with_suffix("").parts
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = list(rel_parts[: len(rel_parts) - node.level])
                module = ".".join(base + ([node.module] if node.module else []))
            else:
                module = node.module or ""
            names.append(module)
            names.extend(f"{module}.{alias.name}" for alias in node.names)
    return names


def test_no_production_module_imports_research_stats() -> None:
    offenders = []
    for path in PKG.rglob("*.py"):
        if RESEARCH in path.parents:
            continue
        for name in _imports(path):
            if name == TARGET or name.startswith(TARGET + "."):
                offenders.append(f"{path.relative_to(ROOT)} -> {name}")
    assert offenders == []


def test_research_stats_only_imports_itself_within_qpk() -> None:
    offenders = []
    for path in RESEARCH.rglob("*.py"):
        for name in _imports(path):
            if name.startswith("quant_platform_kit") and not name.startswith(TARGET):
                offenders.append(f"{path.relative_to(ROOT)} -> {name}")
    assert offenders == []


_PROBE = r"""
import importlib, pkgutil, sys
import quant_platform_kit
loaded = []
for info in pkgutil.iter_modules(quant_platform_kit.__path__):
    if info.name == "research_stats":
        continue
    try:
        importlib.import_module(f"quant_platform_kit.{info.name}")
        loaded.append(info.name)
    except Exception:
        pass  # optional third-party SDKs may be absent in CI
bad = sorted(m for m in sys.modules if m == "quant_platform_kit.research_stats" or m.startswith("quant_platform_kit.research_stats."))
print(len(loaded))
sys.exit(1 if bad else 0)
"""


def test_importing_core_packages_does_not_load_research_stats() -> None:
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=ROOT,
        env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""},
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert int(proc.stdout.strip().splitlines()[-1]) >= 5


_NO_NUMPY = r"""
import sys
sys.modules["numpy"] = None
sys.modules["pandas"] = None
import quant_platform_kit.research_stats as rs
assert rs.probabilistic_sharpe_ratio([0.01, -0.02, 0.015] * 20).status == "COMPUTED"
assert rs.cost_stress_recompute([0.01], [1.0], cost_bps_per_side=5).status == "COMPUTED"
try:
    rs.stationary_bootstrap_ci([0.01, -0.02] * 10, seed=1, mean_block_length=2)
except ImportError as exc:
    assert "[research]" in str(exc)
else:
    raise SystemExit("bootstrap should require numpy")
"""


def test_research_stats_imports_without_numpy() -> None:
    proc = subprocess.run(
        [sys.executable, "-c", _NO_NUMPY],
        cwd=ROOT,
        env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_numpy_pandas_are_only_an_optional_research_extra() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["dependencies"] == []
    research = project["optional-dependencies"]["research"]
    assert sorted(research) == ["numpy", "pandas"]
