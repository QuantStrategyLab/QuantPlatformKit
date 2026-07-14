from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from quant_platform_kit.strategy_lifecycle.qpk_vnext_n1 import ResultContract
from quant_platform_kit.strategy_lifecycle.qpk_vnext_n2_store import IsolatedResultStore, StoreError


def contract(**changes):
    values = dict(domain="us_equity", profile="SOXL", timing="next_open", identity_version=1,
                  persist_mode="durable", strategy_id="strategy", run_id="run-1",
                  param_set_id="baseline", param_version=1, source_revision="rev1",
                  computed_at="2026-07-15T00:00:00.000000Z", params={"x": 1})
    values.update(changes)
    return ResultContract(**values)


def test_write_read_idempotent_and_ephemeral_side_effect_free(tmp_path):
    store = IsolatedResultStore(tmp_path)
    item = contract()
    assert store.put(item) == "created"
    assert store.put(item) == "idempotent"
    assert store.get(item.key) == item
    before = sorted(tmp_path.rglob("*"))
    with pytest.raises(StoreError):
        store.put(replace(item, persist_mode="ephemeral"))
    assert sorted(tmp_path.rglob("*")) == before


def test_symlink_root_and_key_segments_fail_closed(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    store = IsolatedResultStore(link)
    with pytest.raises(StoreError):
        store.get(contract().key)
    store = IsolatedResultStore(target)
    with pytest.raises(StoreError):
        store.get("qpk-vnext/result/v2/us_equity/SOXL/../run/next_open/i1/p1/x.json")
    item = contract()
    store.put(item)
    outside = tmp_path / "outside"
    outside.mkdir()
    leaf = target.joinpath(*item.key.split("/")[:-1])
    leaf.rename(target / "leaf-backup")
    leaf.symlink_to(outside, target_is_directory=True)
    with pytest.raises(StoreError):
        store.get(item.key)
    nested = tmp_path / "nested"
    nested.mkdir()
    actual = nested / "actual"
    actual.mkdir()
    ancestor = tmp_path / "ancestor-link"
    ancestor.symlink_to(nested, target_is_directory=True)
    with pytest.raises(StoreError):
        IsolatedResultStore(ancestor / "actual").get(item.key)


def test_concurrent_identical_and_conflicting_writers(tmp_path):
    store = IsolatedResultStore(tmp_path)
    item = contract()
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda _: store.put(item), range(8)))
    assert outcomes.count("created") == 1
    assert outcomes.count("idempotent") == 7
    with pytest.raises(StoreError):
        store.put(contract(computed_at="2026-07-16T00:00:00.000000Z"))


def test_validated_listing_exact_timing_and_corrupt_rejection(tmp_path):
    store = IsolatedResultStore(tmp_path)
    first = contract()
    second = contract(timing="next_close")
    store.put(first)
    store.put(second)
    assert store.list_keys(domain="us_equity", profile="SOXL", timing="next_open") == (first.key,)
    assert store.list_keys(domain="us_equity", profile="SOXL", timing="next_close") == (second.key,)
    path = tmp_path / second.key
    path.write_bytes(b"{}")
    with pytest.raises(StoreError):
        store.list_keys(domain="us_equity", profile="SOXL", timing="next_close")
    for profile in ("..", "SOXL/../x"):
        with pytest.raises(StoreError):
            store.list_keys(domain="us_equity", profile=profile, timing="next_open")


def test_special_file_is_rejected_without_blocking(tmp_path):
    store = IsolatedResultStore(tmp_path)
    item = contract()
    store.put(item)
    path = tmp_path / item.key
    path.unlink()
    path.parent.mkdir(exist_ok=True)
    path = path.parent / path.name
    path.unlink(missing_ok=True)
    import os
    os.mkfifo(path)
    with pytest.raises(StoreError):
        store.get(item.key)


def test_temp_cleanup_on_atomic_failure(tmp_path, monkeypatch):
    store = IsolatedResultStore(tmp_path)
    monkeypatch.setattr("quant_platform_kit.strategy_lifecycle.qpk_vnext_n2_store.os.link", lambda *_a, **_k: (_ for _ in ()).throw(OSError("injected")))
    with pytest.raises(StoreError):
        store.put(contract())
    assert not list(tmp_path.rglob("*.tmp"))
