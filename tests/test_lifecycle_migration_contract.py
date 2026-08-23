import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from quant_platform_kit.strategy_lifecycle.lifecycle_status import (
    migrate_legacy_lifecycle_status,
    require_canonical_lifecycle_write,
)


ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize(
    "legacy",
    [
        "research_backtest_only",
        "ai_monitored_candidate",
        "shadow_candidate",
        "runtime_enabled",
    ],
)
def test_new_write_boundary_rejects_every_legacy_status(legacy):
    with pytest.raises(ValueError, match="read-only during migration"):
        require_canonical_lifecycle_write(legacy)


@pytest.mark.parametrize(
    "canonical",
    [
        "research_active",
        "shadow_active",
        "paper_active",
        "live_candidate",
        "live_enabled",
    ],
)
def test_new_write_boundary_accepts_canonical_statuses(canonical):
    assert require_canonical_lifecycle_write(canonical) == canonical


def test_catalog_runtime_enabled_never_migrates_to_live_enabled():
    assert (
        migrate_legacy_lifecycle_status("runtime_enabled", source_kind="catalog")
        == "live_candidate"
    )


def test_existing_runtime_requires_external_authority_reference():
    assert (
        migrate_legacy_lifecycle_status(
            "runtime_enabled", source_kind="runtime_deployment"
        )
        == "live_candidate"
    )
    assert (
        migrate_legacy_lifecycle_status(
            "runtime_enabled",
            source_kind="runtime_deployment",
            live_authority_ref="deployment://existing/approval-42",
        )
        == "live_enabled"
    )


def test_migration_schema_requires_authority_and_rollback_for_existing_live():
    schema = json.loads(
        (
            ROOT
            / "src/quant_platform_kit/schemas/lifecycle-migration-snapshot.v1.schema.json"
        ).read_text()
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    snapshot = {
        "schema_version": "lifecycle_migration_snapshot.v1",
        "generated_at": "2026-08-24T00:00:00Z",
        "compatibility_mode": "one_time_read",
        "write_policy": "canonical_only",
        "live_permission_effect": "unchanged",
        "entries": [
            {
                "id": "existing_live",
                "source_kind": "runtime_deployment",
                "source_status": "runtime_enabled",
                "canonical_status": "live_enabled",
                "permission_effect": "none",
                "live_authority_ref": "deployment://existing/approval-42",
                "rollback_ref": "deployment://existing/rollback-42",
            }
        ],
    }
    assert list(validator.iter_errors(snapshot)) == []

    del snapshot["entries"][0]["rollback_ref"]
    assert list(validator.iter_errors(snapshot))
