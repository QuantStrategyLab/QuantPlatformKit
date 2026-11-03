from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from quant_platform_kit.common.strategies import (
    StrategyCatalog,
    StrategyDefinition,
    StrategyMetadata,
)
from quant_platform_kit.common.strategy_catalogs import merge_strategy_catalogs


FIELDS = ("definitions", "metadata", "compatible_platforms", "profile_aliases")
CONFLICT_MESSAGES = (
    "Duplicate strategy definition for profile 'alpha'",
    "Duplicate strategy metadata for profile 'alpha'",
    "Duplicate strategy platform compatibility for profile 'alpha'",
    "Duplicate strategy alias 'alpha'",
)


def _catalog(profile: str = "alpha") -> StrategyCatalog:
    return StrategyCatalog(
        definitions={profile: StrategyDefinition(profile, "us_equity", frozenset({"ibkr"}))},
        metadata={profile: StrategyMetadata(profile, profile.title(), "Example strategy")},
        compatible_platforms={profile: frozenset({"ibkr"})},
        profile_aliases={profile: profile},
    )


@pytest.mark.parametrize("field,message", tuple(zip(FIELDS, CONFLICT_MESSAGES)))
@pytest.mark.parametrize("relationship", ("disjoint", "equal", "conflicting"))
def test_merge_conflict_matrix(field, message, relationship):
    first = _catalog()
    values = {
        "definitions": replace(first.definitions["alpha"], domain="hk_equity"),
        "metadata": replace(first.metadata["alpha"], description="Different description"),
        "compatible_platforms": frozenset({"longbridge"}),
        "profile_aliases": "beta",
    }
    key = "beta" if relationship == "disjoint" else "alpha"
    value = (
        deepcopy(getattr(first, field)["alpha"])
        if relationship == "equal"
        else values[field]
    )
    second = StrategyCatalog(**{"definitions": {}, field: {key: value}})
    before = deepcopy((first, second))

    if relationship == "conflicting":
        with pytest.raises(ValueError) as exc:
            merge_strategy_catalogs(first, second)
        assert type(exc.value) is ValueError
        assert str(exc.value) == message
    else:
        merged = merge_strategy_catalogs(first, second)
        for name in FIELDS:
            expected = dict(getattr(first, name))
            if name == field:
                expected[key] = value
            assert getattr(merged, name) == expected
        # Equal duplicates retain the later value, rather than the first object.
        assert getattr(merged, field)[key] is value

    assert (first, second) == before


def test_merge_no_catalogs_returns_independent_empty_mappings():
    first = merge_strategy_catalogs()
    second = merge_strategy_catalogs()

    assert first == StrategyCatalog(definitions={})
    assert second == first
    for field in FIELDS:
        assert getattr(first, field) is not getattr(second, field)
    assert len({id(getattr(first, field)) for field in FIELDS}) == len(FIELDS)


def test_merge_one_catalog_copies_mappings_and_preserves_values():
    source = _catalog()
    merged = merge_strategy_catalogs(source)

    assert merged == source
    assert merged is not source
    for field in FIELDS:
        original = getattr(source, field)
        result = getattr(merged, field)
        assert result is not original
        assert result["alpha"] is original["alpha"]
        result.clear()
        assert "alpha" in original


def test_merge_multiple_catalogs_preserves_insertion_order():
    first, second, third = (_catalog(profile) for profile in ("zeta", "alpha", "beta"))
    merged = merge_strategy_catalogs(first, StrategyCatalog(definitions={}), second, third, first)

    for field in FIELDS:
        result = getattr(merged, field)
        assert list(result) == ["zeta", "alpha", "beta"]
        assert result == {
            **getattr(first, field),
            **getattr(second, field),
            **getattr(third, field),
        }


@pytest.mark.parametrize("first_conflict", range(len(FIELDS)), ids=FIELDS)
def test_merge_reports_first_conflicting_field(first_conflict):
    first = _catalog()
    different = StrategyCatalog(
        definitions={"alpha": replace(first.definitions["alpha"], domain="hk_equity")},
        metadata={"alpha": replace(first.metadata["alpha"], description="Different")},
        compatible_platforms={"alpha": frozenset({"longbridge"})},
        profile_aliases={"alpha": "beta"},
    )
    second = StrategyCatalog(**{
        field: getattr(first if index < first_conflict else different, field)
        for index, field in enumerate(FIELDS)
    })

    with pytest.raises(ValueError) as exc:
        merge_strategy_catalogs(first, second)
    assert type(exc.value) is ValueError
    assert str(exc.value) == CONFLICT_MESSAGES[first_conflict]


def test_merge_preserves_raw_keys_and_does_not_add_catalog_validation():
    first = _catalog(" Alpha ")
    second = StrategyCatalog(
        definitions={},
        metadata={"unknown": StrategyMetadata("unknown", "Unknown", "Example")},
        compatible_platforms={"unknown": frozenset({"longbridge"})},
        profile_aliases={" ALIAS ": " Missing ", " Alpha ": " Alpha "},
    )

    merged = merge_strategy_catalogs(first, second)

    assert merged.definitions == first.definitions
    assert merged.metadata == {**first.metadata, **second.metadata}
    assert merged.compatible_platforms == {**first.compatible_platforms, **second.compatible_platforms}
    assert merged.profile_aliases == {" Alpha ": " Alpha ", " ALIAS ": " Missing "}
