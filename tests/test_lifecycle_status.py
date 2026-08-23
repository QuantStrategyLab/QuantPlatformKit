import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from quant_platform_kit.strategy_lifecycle.lifecycle_status import (
    CANONICAL_LIFECYCLE_STATES,
    catalog_status_grants_execution_permission,
    normalize_catalog_lifecycle_status,
)


ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize(
    ("legacy", "canonical"),
    [
        ("research_backtest_only", "research_active"),
        ("ai_monitored_candidate", "research_active"),
        ("shadow_candidate", "shadow_active"),
        ("runtime_enabled", "live_candidate"),
    ],
)
def test_legacy_catalog_statuses_map_conservatively(legacy, canonical):
    assert normalize_catalog_lifecycle_status(legacy) == canonical


@pytest.mark.parametrize("status", sorted(CANONICAL_LIFECYCLE_STATES))
def test_canonical_statuses_are_stable(status):
    assert normalize_catalog_lifecycle_status(status) == status


def test_unknown_status_fails_closed():
    with pytest.raises(ValueError, match="unsupported lifecycle status"):
        normalize_catalog_lifecycle_status("approved_for_everything")


@pytest.mark.parametrize(
    "status",
    ["runtime_enabled", "live_candidate", "live_enabled", "paper_active"],
)
def test_catalog_status_never_grants_execution_permission(status):
    assert catalog_status_grants_execution_permission(status) is False


def test_catalog_status_schema_keeps_permission_effect_read_only():
    schema = json.loads(
        (
            ROOT
            / "src/quant_platform_kit/schemas/lifecycle-catalog-status.v1.schema.json"
        ).read_text()
    )
    assert schema["properties"]["permission_effect"] == {"const": "none"}
    assert set(schema["properties"]["canonical_status"]["enum"]) == (
        CANONICAL_LIFECYCLE_STATES
    )

    validator = Draft202012Validator(schema)
    valid_record = {
        "schema_version": "lifecycle_catalog_status.v1",
        "canonical_status": "live_candidate",
        "source_status": "runtime_enabled",
        "source_kind": "catalog",
        "permission_effect": "none",
    }
    assert list(validator.iter_errors(valid_record)) == []

    invalid_record = {**valid_record, "permission_effect": "broker_order"}
    assert list(validator.iter_errors(invalid_record))
