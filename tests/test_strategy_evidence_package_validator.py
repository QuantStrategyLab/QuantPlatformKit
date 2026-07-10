from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from scripts.validate_strategy_evidence_package import validate_file, validate_payload


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
        "risk": {
            "metrics": {
                "sharpe_ratio": 1.42,
                "sortino_ratio": 2.15,
                "max_drawdown": -0.12,
                "annualized_return": 0.18,
                "annualized_volatility": 0.22,
                "calmar_ratio": 1.5,
                "information_ratio": 0.83,
                "var_95": -0.03,
                "cvar_95": -0.05,
                "turnover": 1.8,
                "trade_count": 128,
                "win_rate": 0.57,
                "profit_factor": 1.34,
            },
            "benchmark": {
                "name": "SPY",
                "alpha": 0.02,
                "beta": 0.95,
            },
            "cost_stress": {
                "slippage_bps": 2.5,
                "commission_bps": 0.8,
                "passed": True,
            },
            "oos": {
                "window_start": "2026-01-01",
                "window_end": "2026-06-30",
                "locked": True,
            },
        },
        "kelly_readiness": {
            "level": "K2",
            "full_kelly_allowed": False,
        },
        "ai_optimization": {},
    }


def test_validate_payload_accepts_minimal_valid_package() -> None:
    assert validate_payload(_valid_payload()) == []


def test_validate_payload_rejects_live_package_without_required_validation_flags() -> None:
    payload = _valid_payload()
    payload["validation"] = {
        "oos_passed": False,
        "overfit_report_present": False,
    }

    issues = validate_payload(payload)

    assert "live_candidate requires validation.oos_passed=true" in issues
    assert "live_candidate requires validation.overfit_report_present=true" in issues


def test_validate_payload_rejects_runtime_enabled_package_without_required_validation_flags() -> None:
    payload = _valid_payload()
    payload["requested_stage"] = "runtime_enabled"
    payload["validation"] = {
        "oos_passed": False,
        "overfit_report_present": False,
    }

    issues = validate_payload(payload)

    assert "runtime_enabled requires validation.oos_passed=true" in issues
    assert "runtime_enabled requires validation.overfit_report_present=true" in issues


def test_validate_payload_rejects_full_kelly_enabled_package() -> None:
    payload = _valid_payload()
    payload["kelly_readiness"] = {
        "level": "K2",
        "full_kelly_allowed": True,
    }

    issues = validate_payload(payload)

    assert "kelly_readiness.full_kelly_allowed must be false" in issues


def test_validate_payload_rejects_missing_risk_metric() -> None:
    payload = _valid_payload()
    del payload["risk"]["metrics"]["sharpe_ratio"]

    issues = validate_payload(payload)

    assert "risk.metrics.sharpe_ratio must be a number" in issues


def test_cli_exit_code_for_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    path.write_text("{", encoding="utf-8")

    assert validate_file(path) == ["invalid JSON: Expecting property name enclosed in double quotes (line 1, column 2)"]

    proc = subprocess.run(
        [sys.executable, "scripts/validate_strategy_evidence_package.py", str(path)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1
    assert "invalid JSON" in proc.stderr


def test_cli_exit_code_for_valid_file(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    artifact_file = artifacts_dir / "example.json"
    artifact_file.write_text('{"ok": true}', encoding="utf-8")
    sha256 = hashlib.sha256(artifact_file.read_bytes()).hexdigest()
    payload = _valid_payload()
    for artifact in payload["artifacts"].values():
        artifact["sha256"] = sha256
    path.write_text(json.dumps(payload), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "scripts/validate_strategy_evidence_package.py", str(path)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    assert proc.stdout == ""
    assert proc.stderr == ""


def test_validate_file_rejects_missing_artifact_file(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(_valid_payload()), encoding="utf-8")

    issues = validate_file(path)

    assert "artifacts.returns.path does not exist: artifacts/example.json" in issues


def test_validate_file_rejects_sha256_mismatch(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    artifact_file = artifacts_dir / "example.json"
    artifact_file.write_text('{"ok": true}', encoding="utf-8")

    payload = _valid_payload()
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    issues = validate_file(path)

    assert any("artifacts.returns.sha256 mismatch" in issue for issue in issues)
