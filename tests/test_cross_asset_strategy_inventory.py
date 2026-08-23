import json
from pathlib import Path

from quant_platform_kit.strategy_lifecycle.lifecycle_status import (
    CANONICAL_LIFECYCLE_STATES,
    require_canonical_lifecycle_write,
)


ROOT = Path(__file__).parents[1]


def _inventory():
    return json.loads(
        (ROOT / "docs/registry/cross_asset_strategy_inventory.json").read_text()
    )


def test_inventory_is_metadata_only_and_covers_non_us_domains():
    data = _inventory()
    assert data["inventory_only"] is True
    assert "trading authority" in data["source_policy"]
    domains = {entry["domain"] for entry in data["entries"]}
    assert {"cn_equity", "hk_equity", "crypto"} <= domains


def test_inventory_entries_have_explicit_next_actions_and_no_live_grant():
    inventory = _inventory()
    assert inventory["schema_version"] == "cross_asset_strategy_inventory.v2"
    assert inventory["permission_effect"] == "none"
    entries = inventory["entries"]
    assert entries
    ids = [entry["id"] for entry in entries]
    assert len(ids) == len(set(ids))
    for entry in entries:
        assert entry["owner_repo"]
        assert "catalog_status" not in entry
        assert "canonical_status" not in entry
        assert entry["lifecycle_status"] in CANONICAL_LIFECYCLE_STATES
        assert (
            require_canonical_lifecycle_write(entry["lifecycle_status"])
            == entry["lifecycle_status"]
        )
        assert entry["next_action"]
        assert "live" not in entry.get("authority", "").lower()
