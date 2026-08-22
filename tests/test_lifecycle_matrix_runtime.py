import json

import pytest

from quant_platform_kit.strategy_lifecycle.lifecycle_matrix_runtime import (
    LifecycleMatrixInputError,
    build_lifecycle_matrix,
)


def _write(tmp_path, name, **payload):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_aggregates_read_only_terminal_artifacts_without_running_anything(tmp_path):
    paths = [
        _write(
            tmp_path,
            "p1.json",
            strategy_id="tqqq_core_only_p2_v5",
            display_name="TQQQ successor",
            kind="strategy",
            lineage="p2_v5",
            stage="p1",
            status="verified",
            evidence_ref="p1/manifest.json",
            digest="sha256:p1",
        ),
        _write(
            tmp_path,
            "p3.json",
            strategy_id="tqqq_core_only_p2_v5",
            kind="strategy",
            lineage="p2_v5",
            stage="p3",
            status="verified",
            evidence_refs=["p3/evidence.json"],
            digest="sha256:p3",
        ),
    ]
    matrix = build_lifecycle_matrix(paths, generated_at="2026-08-23")
    entry = matrix["entries"][0]
    assert matrix["schema_version"] == "strategy_lifecycle_matrix.v1"
    assert entry["stages"]["p1"]["digest"] == "sha256:p1"
    assert entry["stages"]["p3"]["evidence_refs"] == ["p3/evidence.json"]
    assert entry["stages"]["p4"]["status"] == "not_started"
    assert "promotion" in matrix["source_policy"]


def test_rejects_duplicate_or_unattributed_artifacts_fail_closed(tmp_path):
    base = dict(
        strategy_id="soxl_core_only",
        kind="strategy",
        lineage="successor",
        stage="p3",
        status="verified",
        evidence_ref="p3/evidence.json",
    )
    first = _write(tmp_path, "first.json", **base)
    second = _write(tmp_path, "second.json", **base)
    with pytest.raises(LifecycleMatrixInputError, match="duplicate"):
        build_lifecycle_matrix([first, second])

    missing_ref = _write(tmp_path, "missing.json", **{**base, "evidence_ref": ""})
    with pytest.raises(LifecycleMatrixInputError, match="evidence_ref"):
        build_lifecycle_matrix([missing_ref])

