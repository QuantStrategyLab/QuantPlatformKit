from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_strategy_evidence_package.py"


def _valid_payload() -> dict[str, object]:
    artifact = {"path": "artifacts/example.json", "sha256": "a" * 64}
    return {
        "schema_version": "strategy_evidence_package.v1",
        "profile": "alpha_momentum",
        "market": "us_equity",
        "requested_stage": "live_candidate",
        "generated_at": "2026-07-07T00:00:00Z",
        "evidence_package_id": "pkg_001",
        "artifacts": {
            "returns": artifact,
            "trades": artifact,
            "positions": artifact,
            "config": artifact,
            "data_manifest": artifact,
            "candidate_registry": artifact,
            "benchmark_registry": artifact,
            "cost_model": artifact,
            "risk_report": artifact,
            "kelly_readiness_report": artifact,
        },
        "validation": {
            "oos_passed": True,
            "overfit_report_present": True,
        },
        "risk": {},
        "kelly_readiness": {
            "level": "K2",
            "full_kelly_allowed": False,
        },
        "ai_optimization": {},
    }


def _run_validator(tmp_path: Path, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_valid_evidence_package_returns_zero(tmp_path: Path) -> None:
    result = _run_validator(tmp_path, _valid_payload())

    assert result.returncode == 0, result.stderr or result.stdout


def test_missing_required_artifact_fails(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["artifacts"] = {
        key: value
        for key, value in payload["artifacts"].items()
        if key != "risk_report"
    }

    result = _run_validator(tmp_path, payload)

    assert result.returncode == 1
    assert "artifacts.risk_report" in result.stderr


@pytest.mark.parametrize("flag", ["oos_passed", "overfit_report_present"])
def test_live_candidate_rejects_false_validation_flags(tmp_path: Path, flag: str) -> None:
    payload = _valid_payload()
    payload["validation"] = dict(payload["validation"])
    payload["validation"][flag] = False

    result = _run_validator(tmp_path, payload)

    assert result.returncode == 1
    assert f"live_candidate requires validation.{flag}=true" in result.stderr


def test_full_kelly_allowed_is_rejected(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["kelly_readiness"] = dict(payload["kelly_readiness"])
    payload["kelly_readiness"]["full_kelly_allowed"] = True

    result = _run_validator(tmp_path, payload)

    assert result.returncode == 1
    assert "kelly_readiness.full_kelly_allowed must be false" in result.stderr
