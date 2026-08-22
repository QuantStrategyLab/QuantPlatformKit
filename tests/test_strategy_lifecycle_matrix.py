import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).parents[1]


def test_lifecycle_matrix_matches_schema_and_has_unique_ids():
    schema = json.loads((ROOT / "schemas/strategy-lifecycle-matrix.v1.schema.json").read_text())
    matrix = json.loads((ROOT / "docs/registry/strategy_lifecycle_matrix.json").read_text())
    errors = sorted(Draft202012Validator(schema).iter_errors(matrix), key=str)
    assert not errors, "\n".join(error.message for error in errors)
    ids = [entry["id"] for entry in matrix["entries"]]
    assert len(ids) == len(set(ids))


def test_matrix_is_read_only_and_records_all_p0_to_p6_stages():
    matrix = json.loads((ROOT / "docs/registry/strategy_lifecycle_matrix.json").read_text())
    for entry in matrix["entries"]:
        assert set(entry["stages"]) == {f"p{i}" for i in range(7)}
        assert entry["next_action"]
        assert all(isinstance(stage["evidence_refs"], list) for stage in entry["stages"].values())
    assert "promotion" in matrix["source_policy"]
    assert "trading" in matrix["source_policy"]
