"""Synthetic regression coverage for complete, ordered live-history reads."""
import json
import signal
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from quant_platform_kit.strategy_lifecycle.live_equity import resolve_consecutive_losses
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore

MODULE = "quant_platform_kit.strategy_lifecycle.performance_store"


class ObjectStore:
    def __init__(self, count=402):
        self.objects = {
            f"gs://test/live_runs/us_equity/profile/{index:04}.json": json.dumps({
                "strategy_profile": "profile", "recorded_at": f"{index:04}",
                "record_kind": "execution", "value": index,
            }).encode()
            for index in range(count)
        }
        self.active = self.peak = self.calls = 0
        self.lock = threading.Lock()

    def list(self, prefix):
        return list(self.objects)

    def read_bytes(self, uri):
        with self.lock:
            self.active += 1
            self.calls += 1
            self.peak = max(self.peak, self.active)
        try:
            time.sleep(0.002)
            return self.objects[uri]
        finally:
            with self.lock:
                self.active -= 1


def store_at(tmp_path: Path):
    return PerformanceStore(cloud_bucket="test", local_root=tmp_path)


def test_402_records_use_bounded_concurrency_without_reordering(tmp_path):
    cloud = ObjectStore()
    with patch(f"{MODULE}.get_object_store", return_value=cloud):
        records = store_at(tmp_path).list_live_run_records("us_equity", strategy_profile="profile")
    assert [record["value"] for record in records] == list(range(402))
    assert cloud.calls == 402
    assert 1 < cloud.peak <= 4


def test_completion_order_does_not_change_cloud_last_wins(tmp_path):
    cloud = ObjectStore(2)
    keys = list(cloud.objects)
    for index, key in enumerate(keys):
        cloud.objects[key] = json.dumps({"strategy_profile": "profile", "recorded_at": "same",
                                         "record_kind": "execution", "value": index}).encode()
    local = tmp_path / "live_runs/us_equity/profile/local.json"
    local.parent.mkdir(parents=True)
    local.write_text(json.dumps({"strategy_profile": "profile", "recorded_at": "same",
                                "record_kind": "execution", "value": "local"}))
    original = cloud.read_bytes

    def read(uri):
        if uri == keys[0]:
            time.sleep(0.04)
        return original(uri)

    with patch(f"{MODULE}.get_object_store", return_value=cloud), patch.object(cloud, "read_bytes", read):
        records = store_at(tmp_path).list_live_run_records("us_equity", strategy_profile="profile")
    assert len(records) == 1
    assert records[0]["value"] == 1


@pytest.mark.parametrize("phase", ["list", "read_bytes"])
def test_risk_resolver_does_not_use_partial_or_empty_history_after_io_failure(tmp_path, phase):
    cloud = ObjectStore(2)
    with patch(f"{MODULE}.get_object_store", return_value=cloud), patch.object(
        cloud, phase, side_effect=OSError("private source details")
    ), pytest.raises(RuntimeError, match="^live_run_history_read_failed$"):
        resolve_consecutive_losses(domain="us_equity", strategy_profile="profile", store=store_at(tmp_path))


def test_strict_read_keeps_legacy_non_record_ignore_semantics(tmp_path):
    cloud = ObjectStore(4)
    for key, payload in zip(cloud.objects, [b"not json", b"[]", b"{}", b"null"]):
        cloud.objects[key] = payload
    with patch(f"{MODULE}.get_object_store", return_value=cloud):
        assert store_at(tmp_path).list_live_run_records("us_equity", strict=True) == []


def test_default_reader_preserves_best_effort_behavior(tmp_path):
    cloud = ObjectStore(2)
    with patch(f"{MODULE}.get_object_store", return_value=cloud), patch.object(
        cloud, "read_bytes", side_effect=OSError("unavailable")
    ):
        assert store_at(tmp_path).list_live_run_records("us_equity") == []


def test_one_failed_read_rejects_successful_partial_history(tmp_path):
    cloud = ObjectStore(2)
    keys = list(cloud.objects)
    original = cloud.read_bytes

    def read(uri):
        if uri == keys[1]:
            raise OSError("private source details")
        return original(uri)

    with patch(f"{MODULE}.get_object_store", return_value=cloud), patch.object(cloud, "read_bytes", read):
        with pytest.raises(RuntimeError, match="^live_run_history_read_failed$"):
            store_at(tmp_path).list_live_run_records("us_equity", strict=True)


def test_local_io_failure_is_unknown_but_invalid_encoding_still_ignored(tmp_path):
    path = tmp_path / "live_runs/us_equity/profile/local.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff")
    store = PerformanceStore(local_root=tmp_path)
    assert store.list_live_run_records("us_equity", strict=True) == []
    with patch.object(Path, "read_text", side_effect=PermissionError("private source")):
        with pytest.raises(RuntimeError, match="^live_run_history_read_failed$"):
            store.list_live_run_records("us_equity", strict=True)


@pytest.mark.skipif(not hasattr(signal, "setitimer"), reason="requires POSIX alarms")
def test_alarm_returns_without_waiting_for_active_reads_and_cancels_queue(tmp_path):
    class Deadline(BaseException):
        pass

    def deadline(signum, frame):
        raise Deadline()

    release = threading.Event()
    cloud = ObjectStore(402)

    def blocked(uri):
        with cloud.lock:
            cloud.calls += 1
        release.wait(2)
        return cloud.objects[uri]

    previous = signal.signal(signal.SIGALRM, deadline)
    started = time.monotonic()
    try:
        with patch(f"{MODULE}.get_object_store", return_value=cloud), patch.object(cloud, "read_bytes", blocked):
            signal.setitimer(signal.ITIMER_REAL, 0.15)
            with pytest.raises(Deadline):
                store_at(tmp_path).list_live_run_records("us_equity", strict=True)
            assert time.monotonic() - started < 0.8
            assert not release.is_set()
            release.set()
            time.sleep(0.05)
            assert cloud.calls <= 4
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        release.set()
