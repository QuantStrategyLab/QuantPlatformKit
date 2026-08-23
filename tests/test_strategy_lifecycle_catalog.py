import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_catalog_covers_supported_domains_and_reuses_p0_to_p6_template():
    catalog = json.loads(
        (ROOT / "docs/registry/strategy_lifecycle_catalog.json").read_text()
    )
    assert catalog["lifecycle_template"] == [f"p{i}" for i in range(7)]
    entries = catalog["entries"]
    assert len({entry["id"] for entry in entries}) == len(entries)
    assert {entry["domain"] for entry in entries} >= {
        "us_equity", "hk_equity", "cn_equity", "crypto", "quant_combo", "cross_domain"
    }
    assert {entry["kind"] for entry in entries} == {"strategy", "portfolio", "plugin"}


def test_catalog_is_inventory_only_and_every_entry_has_traceable_owner():
    catalog = json.loads(
        (ROOT / "docs/registry/strategy_lifecycle_catalog.json").read_text()
    )
    assert "do not claim evidence" in catalog["source_policy"]
    for entry in catalog["entries"]:
        assert entry["owner_repo"]
        assert entry["inventory_refs"]
        assert entry["next_step"]
