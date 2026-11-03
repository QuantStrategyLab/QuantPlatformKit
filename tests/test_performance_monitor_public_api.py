"""Preserve the monitor's main-branch public surface without eager numerics."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


# Implicit star-import surface of main at 31009f36b9d144497410cfe3a5b78e2517052961.
# Includes historical imported aliases, not only functions defined here.
MAIN_PUBLIC_NAMES = {
    "Any", "DEFAULT_WINDOWS", "Mapping", "Path", "PerformanceMonitor",
    "PerformanceStore", "ReturnCollector", "Sequence", "StrategyPerformanceSnapshot",
    "annotations", "annualization_basis_is_comparable", "compare_with_backtest",
    "compute_window_metrics", "date", "infer_strategy_domain",
    "interval_return_coverage_comparison_reason", "logger", "logging",
    "normalize_interval_return_coverage", "normalize_return_series", "os", "pd", "re",
    "replace", "resolve_lifecycle_stream_id", "resolve_monitor_source_revision",
    "resolve_return_observation_contract", "resolve_strategy_benchmark", "run_monitor",
    "try_record_platform_execution", "utc_now_iso",
}
LAZY_EXPORTS = {
    "pd": ("pandas", None),
    "ReturnCollector": ("quant_platform_kit.strategy_lifecycle.return_collector", "ReturnCollector"),
    "resolve_strategy_benchmark": (
        "quant_platform_kit.strategy_lifecycle.return_collector", "resolve_strategy_benchmark"),
    **{name: ("quant_platform_kit.strategy_lifecycle.performance_metrics", name) for name in (
        "annualization_basis_is_comparable", "compare_with_backtest",
        "compute_window_metrics", "normalize_return_series",
    )},
}


def _probe(code: str) -> None:
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    result = subprocess.run([sys.executable, "-c", code], env=env, text=True,
                            capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_public_surface_and_type_hints_without_prior_attribute_access():
    _probe(f'''
import sys
import typing
import quant_platform_kit.strategy_lifecycle.performance_monitor as monitor
assert "pandas" not in sys.modules
assert "numpy" not in sys.modules
expected = {MAIN_PUBLIC_NAMES!r}
assert set(monitor.__all__) == expected
assert {{name for name in dir(monitor) if not name.startswith("_")}} == expected
assert not (expected & {{"pd", "ReturnCollector"}}) & vars(monitor).keys()
hints = typing.get_type_hints(monitor.run_monitor)
from quant_platform_kit.strategy_lifecycle.return_collector import ReturnCollector
assert hints["collector"] == ReturnCollector | None
assert monitor.ReturnCollector is ReturnCollector
namespace = {{}}
exec("from quant_platform_kit.strategy_lifecycle.performance_monitor import *", namespace)
assert set(namespace) - {{"__builtins__"}} == expected
assert namespace["ReturnCollector"] is ReturnCollector
try:
    monitor.not_a_public_symbol
except AttributeError:
    pass
else:
    raise AssertionError("unknown attributes must raise AttributeError")
''')


@pytest.mark.parametrize("name,target", LAZY_EXPORTS.items())
def test_legacy_direct_import_identity(name, target):
    _probe(f'''
import importlib
import inspect
from quant_platform_kit.strategy_lifecycle.performance_monitor import {name} as actual
module = importlib.import_module({target[0]!r})
expected = getattr(module, {target[1]!r}) if {target[1]!r} else module
assert actual is expected
if callable(expected):
    assert inspect.signature(actual) == inspect.signature(expected)
''')


@pytest.mark.parametrize("blocked", ["pandas", "numpy"])
def test_core_import_and_fail_closed_optional_exports(blocked):
    _probe(f'''
import importlib.abc
import sys
class BlockNumerics(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] == {blocked!r}:
            raise ModuleNotFoundError("blocked optional dependency", name={blocked!r})
sys.meta_path.insert(0, BlockNumerics())
import quant_platform_kit.strategy_lifecycle.performance_monitor as monitor
assert "pandas" not in sys.modules
assert "numpy" not in sys.modules
assert set(monitor.__all__) <= set(dir(monitor))
for name in {list(LAZY_EXPORTS)!r}:
    try:
        getattr(monitor, name)
    except ImportError as exc:
        assert "quant-platform-kit[research]" in str(exc), str(exc)
        assert isinstance(exc.__cause__, ModuleNotFoundError)
    else:
        raise AssertionError(name + " must require the research extra")
''')
