from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "update-qpk-pin.yml"
DOWNSTREAM_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "open-downstream-qpk-pin-prs.yml"
OLD_QPK_SHA = "5d4bbd0e7ef9a1434010e8b6a69905d39ee55f1b"
STRATEGY_REFS = {
    "us-equity-strategies": (
        "UsEquityStrategies",
        "702f9989940187e28102e132887f6216edd4ef66",
    ),
    "hk-equity-strategies": (
        "HkEquityStrategies",
        "1a2155e3a48a212e062f0584f6982f2f2b40d955",
    ),
    "cn-equity-strategies": (
        "CnEquityStrategies",
        "bbff0fcea74231b521c990d5c87d4611ab2d8c53",
    ),
    "crypto-strategies": (
        "CryptoStrategies",
        "2083cc03cf4af075d3518d4d6372be027f3f8eab",
    ),
}


def _workflow() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _step_run_block(workflow: str, step_name: str) -> str:
    lines = workflow.splitlines()
    marker = f"      - name: {step_name}"
    step_index = lines.index(marker)
    run_index = next(
        index
        for index in range(step_index + 1, len(lines))
        if lines[index] == "        run: |"
    )
    block: list[str] = []
    for line in lines[run_index + 1 :]:
        if line.startswith("      - "):
            break
        if line and not line.startswith("          "):
            break
        block.append(line[10:] if line else "")
    return "\n".join(block) + "\n"


def _verification_run_block(workflow: str) -> str:
    return _step_run_block(workflow, "Verify QPK candidate")


def _run_script(
    script: str,
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        cwd=cwd,
        env={**os.environ, **(env or {})},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _manifest_text(qpk_sha: str) -> str:
    lines = [
        "# synthetic aggregate fixture",
        (
            "quant-platform-kit @ "
            "git+https://github.com/QuantStrategyLab/QuantPlatformKit.git@"
            f"{qpk_sha}"
        ),
    ]
    lines.extend(
        f"{package} @ git+https://github.com/QuantStrategyLab/{repo}.git@{sha}"
        for package, (repo, sha) in STRATEGY_REFS.items()
    )
    return "\n".join(lines) + "\n"


def _init_pin_fixture(root: Path) -> str:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "QPK Test"], cwd=root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "qpk-test@example.invalid"],
        cwd=root,
        check=True,
    )
    root.joinpath("QPK_PIN").write_text(f"{OLD_QPK_SHA}\n", encoding="utf-8")
    manifest = _manifest_text(OLD_QPK_SHA)
    root.joinpath("qsl-pins.txt").write_text(manifest, encoding="utf-8")
    root.joinpath("constraints.txt").write_text(manifest, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def _install_fake_python(bin_dir: Path) -> None:
    bin_dir.mkdir(parents=True)
    fake_python = bin_dir / "python"
    fake_python.write_text(
        """#!/usr/bin/env python3
import os
import shutil
import sys
from pathlib import Path

args = sys.argv[1:]
if args[:2] == ["-m", "venv"]:
    target = Path(args[2]) / "bin" / "python"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(__file__), target)
    target.chmod(0o755)
    raise SystemExit(0)
if args[:3] == ["-m", "pip", "install"]:
    if "--no-deps" in args:
        raise SystemExit(0)
    if os.environ.get("PIN_RESOLVER_FIXTURE") == "conflict":
        sys.stderr.write(
            f"credential={os.environ['FIXTURE_SECRET']} "
            f"path={os.environ['FIXTURE_PRIVATE_PATH']}\\n"
        )
        raise SystemExit(42)
    raise SystemExit(0)
if args[:3] == ["-m", "pip", "check"] or args[:1] == ["-c"]:
    raise SystemExit(0)
raise SystemExit(f"unexpected fake-python arguments: {args!r}")
""",
        encoding="utf-8",
    )
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)


def test_pin_update_advances_only_qpk_pin(tmp_path: Path) -> None:
    workflow = _workflow()
    update_script = _step_run_block(workflow, "Update QPK_PIN")

    assert "git ls-remote" not in update_script
    assert all(repo not in update_script for repo, _sha in STRATEGY_REFS.values())

    expected_qpk_sha = _init_pin_fixture(tmp_path)
    output_path = tmp_path / "github-output"
    result = _run_script(
        update_script,
        cwd=tmp_path,
        env={"GITHUB_OUTPUT": str(output_path)},
    )

    assert result.returncode == 0, result.stderr
    assert output_path.read_text(encoding="utf-8") == "changed=true\n"
    assert tmp_path.joinpath("QPK_PIN").read_text(encoding="utf-8") == (
        f"{expected_qpk_sha}\n"
    )
    expected_manifest = _manifest_text(OLD_QPK_SHA)
    assert tmp_path.joinpath("qsl-pins.txt").read_text(encoding="utf-8") == expected_manifest
    assert tmp_path.joinpath("constraints.txt").read_text(encoding="utf-8") == expected_manifest


def test_dependency_conflict_fails_closed_before_pr_without_sensitive_output(
    tmp_path: Path,
) -> None:
    workflow = _workflow()
    verify_script = _verification_run_block(workflow)
    fake_bin = tmp_path / "bin"
    _install_fake_python(fake_bin)
    tmp_path.joinpath("QPK_PIN").write_text(f"{OLD_QPK_SHA}\n", encoding="utf-8")
    fixture_secret = "fixture-secret-value"
    fixture_private_path = "/private/fixture/path"

    result = _run_script(
        verify_script,
        cwd=tmp_path,
        env={
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "PIN_RESOLVER_FIXTURE": "conflict",
            "FIXTURE_SECRET": fixture_secret,
            "FIXTURE_PRIVATE_PATH": fixture_private_path,
        },
    )
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "qpk_candidate_install_failed" in output
    assert fixture_secret not in output
    assert fixture_private_path not in output
    assert "--no-deps" not in workflow
    assert "- name: Verify QPK candidate" in workflow
    assert workflow.index("- name: Verify QPK candidate") < workflow.index(
        "- name: Create PR for pin update"
    )


def test_dependency_success_reaches_only_guarded_pr_step(tmp_path: Path) -> None:
    workflow = _workflow()
    verify_script = _verification_run_block(workflow)
    fake_bin = tmp_path / "bin"
    _install_fake_python(fake_bin)
    tmp_path.joinpath("QPK_PIN").write_text(f"{OLD_QPK_SHA}\n", encoding="utf-8")
    result = _run_script(
        verify_script,
        cwd=tmp_path,
        env={
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "PIN_RESOLVER_FIXTURE": "success",
            "FIXTURE_SECRET": "unused-fixture-secret",
            "FIXTURE_PRIVATE_PATH": "/unused/fixture/path",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "qpk_candidate_install_passed" in result.stdout
    assert "id: verify" in workflow
    assert (
        "if: steps.update.outputs.changed == 'true' && "
        "steps.verify.outcome == 'success'"
    ) in workflow
    assert '      - ".github/workflows/update-qpk-pin.yml"' in workflow
    assert '      - "scripts/open_downstream_qpk_pin_prs.py"' in workflow
    assert '      - "tests/test_qpk_pin_consistency.py"' in workflow
    assert '      - "tests/test_update_qpk_pin_workflow.py"' in workflow
    assert "workflow_dispatch:" not in workflow


def test_downstream_rollout_is_scheduled_and_phase_gated() -> None:
    workflow = DOWNSTREAM_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert '      - "QPK_PIN"' in workflow
    assert '    - cron: "17 * * * *"' in workflow
    assert "- auto" in workflow
    assert "- strategies" in workflow
    assert "- consumers" in workflow
    assert 'open_downstream_qpk_pin_prs.py --phase "$QSL_PIN_PHASE"' in workflow
    assert "Create coherent aggregate bundle PR" in workflow
