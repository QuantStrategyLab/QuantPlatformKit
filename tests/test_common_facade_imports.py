"""Facade import guard: prefer execution/reconciliation over wide common imports."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_common_facade_imports.py"


def test_check_common_facade_imports_script_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(REPO_ROOT / "src"))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert excinfo.value.code == 0


def test_execution_and_reconciliation_packages_import() -> None:
    from quant_platform_kit import execution, reconciliation
    from quant_platform_kit.execution_kernel import (
        describe_platform_http_modules,
        describe_platform_thin_main_rules,
    )

    assert "ExecutionCommand" in execution.__all__
    assert "RiskGuardedExecutionPort" in execution.__all__
    assert "BrokerReconciliationEvidence" in reconciliation.__all__
    assert "main" in describe_platform_http_modules()
    assert "no_star_api" in describe_platform_thin_main_rules()
