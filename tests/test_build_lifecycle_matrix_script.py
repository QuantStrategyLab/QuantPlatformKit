import json

from scripts.build_lifecycle_matrix import main


def _write(tmp_path, name, **payload):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_script_exports_existing_artifacts_without_running_producers(tmp_path):
    _write(
        tmp_path,
        "tqqq-p1.json",
        strategy_id="tqqq_core_only_p2_v5",
        kind="strategy",
        lineage="p2_v5",
        stage="p1",
        status="verified",
        evidence_ref="artifact://tqqq/p1",
    )
    output = tmp_path / "matrix.json"

    assert main([str(tmp_path), "--output", str(output), "--generated-at", "2026-08-23"]) == 0
    matrix = json.loads(output.read_text(encoding="utf-8"))
    assert matrix["generated_at"] == "2026-08-23"
    assert matrix["entries"][0]["stages"]["p1"]["status"] == "verified"
    assert "never authorizes promotion" in matrix["source_policy"]


def test_script_fails_closed_for_missing_input(tmp_path, capsys):
    assert main([str(tmp_path / "missing")]) == 2
    assert "does not exist" in capsys.readouterr().err
