from __future__ import annotations

import json
from pathlib import Path

import pytest

from quant_platform_kit.data.research_input import (
    RESEARCH_INPUT_MANIFEST_SCHEMA_VERSION,
    ResearchInputManifestValidationError,
    validate_research_input_manifest,
)


def _valid_manifest() -> dict[str, object]:
    return {
        "schema_version": RESEARCH_INPUT_MANIFEST_SCHEMA_VERSION,
        "manifest_id": "tqqq-research-inputs-2026-07-30",
        "created_at": "2026-07-30T00:00:00Z",
        "as_of": "2026-07-29T20:00:00Z",
        "inputs": [
            {
                "input_id": "daily-prices",
                "kind": "market_data",
                "artifact_uri": "s3://research-fixtures/tqqq/prices.csv",
                "sha256": "a" * 64,
                "as_of": "2026-07-29T20:00:00Z",
            }
        ],
    }


def test_manifest_contract_accepts_complete_immutable_input_metadata() -> None:
    manifest = _valid_manifest()

    assert validate_research_input_manifest(manifest) == manifest


def test_manifest_contract_rejects_missing_or_mutable_input_identity() -> None:
    manifest = _valid_manifest()
    manifest["inputs"] = [
        {
            "input_id": "daily-prices",
            "kind": "market_data",
            "artifact_uri": "s3://research-fixtures/tqqq/prices.csv",
            "sha256": "not-a-digest",
            "as_of": "2026-07-29T20:00:00Z",
        }
    ]

    with pytest.raises(ResearchInputManifestValidationError):
        validate_research_input_manifest(manifest)


def test_manifest_contract_rejects_duplicate_input_ids_and_future_implementation_fields() -> None:
    manifest = _valid_manifest()
    manifest["inputs"] = [*manifest["inputs"], dict(manifest["inputs"][0])]
    manifest["provider"] = {"name": "must-not-be-added-in-s0"}

    with pytest.raises(ResearchInputManifestValidationError):
        validate_research_input_manifest(manifest)


def test_schema_declares_the_same_closed_s0_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    schema = json.loads(
        (root / "src/quant_platform_kit/schemas/research-input-manifest.v1.schema.json").read_text(encoding="utf-8")
    )

    assert schema["properties"]["schema_version"]["const"] == RESEARCH_INPUT_MANIFEST_SCHEMA_VERSION
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["schema_version", "manifest_id", "created_at", "as_of", "inputs"]
    assert schema["$defs"]["input"]["additionalProperties"] is False
