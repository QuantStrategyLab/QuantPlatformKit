"""Tests for strategy_lifecycle.performance_store defaults."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from quant_platform_kit.strategy_lifecycle.contracts import (
    BacktestResult,
    BacktestValidationIdentity,
    ResearchDailyLedger,
    ResearchLedgerEvent,
    ResearchLedgerDay,
    ResearchPositionMark,
    ResearchTrialRecord,
    ResearchTrialStatus,
)
from quant_platform_kit.strategy_lifecycle.performance_store import (
    DEFAULT_LOCAL_ROOT,
    PerformanceStore,
    SCHEMA_VERSION,
)


def _backtest(**overrides: object) -> BacktestResult:
    payload: dict[str, object] = {
        "strategy_profile": "global_etf_rotation",
        "domain": "us_equity",
        "param_set_id": "candidate",
        "params": {},
        "param_version": 1,
        "sharpe_ratio": 1.0,
        "calmar_ratio": 1.0,
        "max_drawdown": -0.1,
        "cagr": 0.2,
        "volatility": 0.2,
        "win_rate": 0.55,
        "computed_at": "2026-01-01T00:00:00Z",
        "run_id": "run-a",
    }
    payload.update(overrides)
    return BacktestResult(**payload)


def _run_digest(run_id: str) -> str:
    return hashlib.sha256(run_id.encode("utf-8")).hexdigest()


def _run_file(root: Path, run_id: str, version: int = 1) -> Path:
    return (
        root
        / "backtest"
        / "us_equity"
        / "global_etf_rotation"
        / "runs"
        / _run_digest(run_id)
        / f"backtest_v{version}.json"
    )


class _UriObjectStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def read_bytes(self, uri: str) -> bytes:
        return self.objects[uri]

    def write_bytes(self, uri: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self.objects[uri] = data
        return uri

    def list(self, prefix: str) -> list[str]:
        return sorted(uri for uri in self.objects if uri.startswith(prefix))


class PerformanceStoreDefaultsTest(unittest.TestCase):

    def test_default_local_root_uses_platform_lifecycle_name(self) -> None:
        self.assertEqual(
            DEFAULT_LOCAL_ROOT,
            Path(tempfile.gettempdir()) / "quant_platform_lifecycle",
        )

    def test_from_env_uses_default_local_root_without_override(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            store = PerformanceStore.from_env()
        self.assertEqual(store.local_root, DEFAULT_LOCAL_ROOT)

    def test_cloud_backtest_storage_uses_uri_object_store_contract(self) -> None:
        class UriObjectStore:
            def __init__(self) -> None:
                self.objects: dict[str, bytes] = {}

            def read_bytes(self, uri: str) -> bytes:
                return self.objects[uri]

            def write_bytes(self, uri: str, data: bytes, content_type: str = "application/octet-stream") -> str:
                self.objects[uri] = data
                return uri

            def list(self, prefix: str) -> list[str]:
                return sorted(uri for uri in self.objects if uri.startswith(prefix))

        with tempfile.TemporaryDirectory() as tmp:
            object_store = UriObjectStore()
            store = PerformanceStore(
                cloud_bucket="lifecycle-bucket",
                cloud_prefix="production",
                local_root=Path(tmp),
            )
            result = BacktestResult(
                strategy_profile="global_etf_rotation",
                domain="us_equity",
                param_set_id="baseline",
                params={},
                param_version=1,
                sharpe_ratio=1.0,
                calmar_ratio=1.0,
                max_drawdown=-0.1,
                cagr=0.2,
                volatility=0.2,
                win_rate=0.55,
            )
            with patch(
                "quant_platform_kit.strategy_lifecycle.performance_store.get_object_store",
                return_value=object_store,
            ):
                store.save_backtest_result(result)
                keys = store._list_cloud_keys("backtest/us_equity/global_etf_rotation/")
                payload = store._read_cloud_json(keys[0])

        self.assertEqual(len(keys), 1)
        self.assertTrue(keys[0].startswith("backtest/us_equity/global_etf_rotation/"))
        self.assertEqual(payload["strategy_profile"], "global_etf_rotation")


class BacktestRunIdentityTest(unittest.TestCase):
    def _store(self, root: Path) -> PerformanceStore:
        return PerformanceStore(local_root=root)

    def _files(self, root: Path) -> list[Path]:
        directory = root / "backtest" / "us_equity" / "global_etf_rotation"
        return sorted(directory.glob("*.json"))

    def test_same_computed_at_different_run_ids_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = self._store(root)
            store.save_backtest_result(_backtest(run_id="run-a", sharpe_ratio=1.1))
            store.save_backtest_result(_backtest(run_id="run-b", sharpe_ratio=2.2))

            loaded_a = store.load_backtest_by_run_id("us_equity", "global_etf_rotation", "run-a")
            loaded_b = store.load_backtest_by_run_id("us_equity", "global_etf_rotation", "run-b")
            run_a_exists = _run_file(root, "run-a").is_file()
            run_b_exists = _run_file(root, "run-b").is_file()
            flat_collision = (
                root / "backtest" / "us_equity" / "global_etf_rotation" / f"backtest_v1_{_run_digest('run-a')}.json"
            ).exists()

        self.assertTrue(run_a_exists)
        self.assertTrue(run_b_exists)
        self.assertFalse(flat_collision)
        self.assertIsNotNone(loaded_a)
        self.assertIsNotNone(loaded_b)
        self.assertEqual(loaded_a.run_id, "run-a")
        self.assertEqual(loaded_b.run_id, "run-b")
        self.assertEqual(loaded_a.sharpe_ratio, 1.1)
        self.assertEqual(loaded_b.sharpe_ratio, 2.2)

    def test_long_special_run_ids_keep_distinct_digest_paths(self) -> None:
        shared = "a" * 120
        first = shared + " ONE/α:left"
        second = shared + " TWO/α:right"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = self._store(root)
            store.save_backtest_result(_backtest(run_id=first, sharpe_ratio=0.4))
            store.save_backtest_result(_backtest(run_id=second, sharpe_ratio=0.8))
            loaded_first = store.load_backtest_by_run_id("us_equity", "global_etf_rotation", first)
            loaded_second = store.load_backtest_by_run_id("us_equity", "global_etf_rotation", second)
            first_path = _run_file(root, first)
            second_path = _run_file(root, second)

        self.assertNotEqual(first_path.parent, second_path.parent)
        self.assertEqual(first_path.parent.name, _run_digest(first))
        self.assertNotIn(first, first_path.as_posix())
        self.assertLess(len(first_path.parent.name), 100)
        self.assertLess(len(first_path.name), 100)
        self.assertEqual(loaded_first.run_id, first)
        self.assertEqual(loaded_second.run_id, second)
        self.assertEqual(loaded_first.sharpe_ratio, 0.4)
        self.assertEqual(loaded_second.sharpe_ratio, 0.8)

    def test_legacy_filename_and_digest_path_both_read_back(self) -> None:
        legacy_run_id = "legacy/run id"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = self._store(root)
            legacy_dir = root / "backtest" / "us_equity" / "global_etf_rotation"
            legacy_dir.mkdir(parents=True)
            legacy_path = legacy_dir / "backtest_v1_2026-01-01T00-00-00Z.json"
            decoy_digest = _run_digest(legacy_run_id)
            decoy_path = legacy_dir / f"backtest_v1_{decoy_digest}.json"
            legacy_payload = _backtest(run_id=legacy_run_id, sharpe_ratio=0.3).to_dict()
            decoy_payload = _backtest(run_id="not-the-legacy-run", sharpe_ratio=9.0).to_dict()
            legacy_path.write_text(json.dumps(legacy_payload), encoding="utf-8")
            decoy_path.write_text(json.dumps(decoy_payload), encoding="utf-8")
            store.save_backtest_result(_backtest(run_id="new-run", sharpe_ratio=1.7))

            loaded_legacy = store.load_backtest_by_run_id("us_equity", "global_etf_rotation", legacy_run_id)
            loaded_new = store.load_backtest_by_run_id("us_equity", "global_etf_rotation", "new-run")
            names = {path.name for path in self._files(root)}
            new_run_exists = _run_file(root, "new-run").is_file()

        self.assertIn("backtest_v1_2026-01-01T00-00-00Z.json", names)
        self.assertTrue(new_run_exists)
        self.assertEqual(loaded_legacy.run_id, legacy_run_id)
        self.assertEqual(loaded_legacy.sharpe_ratio, 0.3)
        self.assertEqual(loaded_new.run_id, "new-run")
        self.assertEqual(loaded_new.sharpe_ratio, 1.7)

    def test_same_run_and_version_rewrites_one_stable_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = self._store(root)
            store.save_backtest_result(_backtest(run_id="stable-run", computed_at="2026-01-01T00:00:00Z", sharpe_ratio=1.0))
            store.save_backtest_result(_backtest(run_id="stable-run", computed_at="2026-02-01T00:00:00Z", sharpe_ratio=3.5))
            loaded = store.load_backtest_by_run_id("us_equity", "global_etf_rotation", "stable-run")
            run_files = list(_run_file(root, "stable-run").parent.glob("*.json"))

        self.assertEqual(run_files, [_run_file(root, "stable-run")])
        self.assertEqual(loaded.run_id, "stable-run")
        self.assertEqual(loaded.sharpe_ratio, 3.5)
        self.assertEqual(loaded.computed_at, "2026-02-01T00:00:00Z")

    def test_blank_run_id_keeps_computed_at_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = self._store(root)
            store.save_backtest_result(_backtest(run_id="", param_set_id="baseline_set"))
            files = self._files(root)

        self.assertEqual([path.name for path in files], ["backtest_v1_2026-01-01T00-00-00Z.json"])

    def test_exact_run_read_is_not_latest_and_latest_keeps_baseline_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = self._store(root)
            store.save_backtest_result(_backtest(
                run_id="older-run",
                param_set_id="walk_forward",
                computed_at="2026-01-01T00:00:00Z",
                sharpe_ratio=0.2,
            ))
            store.save_backtest_result(_backtest(
                run_id="baseline-run",
                param_set_id="rotation_baseline",
                computed_at="2026-03-01T00:00:00Z",
                sharpe_ratio=4.0,
            ))

            exact = store.load_backtest_by_run_id("us_equity", "global_etf_rotation", "older-run")
            latest = store.load_latest_backtest("us_equity", "global_etf_rotation")
            missing = store.load_backtest_by_run_id("us_equity", "global_etf_rotation", "")

        self.assertEqual(exact.run_id, "older-run")
        self.assertEqual(exact.sharpe_ratio, 0.2)
        self.assertEqual(latest.param_set_id, "rotation_baseline")
        self.assertIsNone(missing)

    def test_cloud_uri_store_keeps_distinct_run_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            object_store = _UriObjectStore()
            store = PerformanceStore(
                cloud_bucket="lifecycle-bucket",
                cloud_prefix="production",
                local_root=Path(tmp),
            )
            with patch(
                "quant_platform_kit.strategy_lifecycle.performance_store.get_object_store",
                return_value=object_store,
            ):
                store.save_backtest_result(_backtest(run_id="cloud-a", sharpe_ratio=1.2))
                store.save_backtest_result(_backtest(run_id="cloud-b", sharpe_ratio=2.4))
                for path in Path(tmp).rglob("*.json"):
                    path.unlink()
                loaded_a = store.load_backtest_by_run_id("us_equity", "global_etf_rotation", "cloud-a")
                loaded_b = store.load_backtest_by_run_id("us_equity", "global_etf_rotation", "cloud-b")

        self.assertCountEqual(object_store.objects, [
            f"gs://lifecycle-bucket/production/backtest/us_equity/global_etf_rotation/runs/{_run_digest('cloud-a')}/backtest_v1.json",
            f"gs://lifecycle-bucket/production/backtest/us_equity/global_etf_rotation/runs/{_run_digest('cloud-b')}/backtest_v1.json",
        ])
        self.assertEqual(loaded_a.run_id, "cloud-a")
        self.assertEqual(loaded_b.run_id, "cloud-b")
        self.assertEqual(loaded_a.sharpe_ratio, 1.2)
        self.assertEqual(loaded_b.sharpe_ratio, 2.4)

    def test_exact_read_rejects_clean_key_domain_and_profile_collision(self) -> None:
        run_id = "collide-run"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = self._store(root)
            directory = root / "backtest" / "us-equity" / "global-etf"
            directory.mkdir(parents=True)
            hyphen = _backtest(
                domain="us-equity",
                strategy_profile="global-etf",
                run_id=run_id,
                param_version=1,
                sharpe_ratio=1.0,
            )
            spaced = _backtest(
                domain="us equity",
                strategy_profile="global etf",
                run_id=run_id,
                param_version=1,
                sharpe_ratio=2.0,
            )
            (directory / f"backtest_v1_{_run_digest(run_id)}.json").write_text(
                json.dumps(hyphen.to_dict()),
                encoding="utf-8",
            )
            self.assertIsNone(store.load_backtest_by_run_id("us equity", "global etf", run_id))

            (directory / "backtest_v1_2026-01-01T00-00-00Z.json").write_text(
                json.dumps(spaced.to_dict()),
                encoding="utf-8",
            )
            spaced_loaded = store.load_backtest_by_run_id("us equity", "global etf", run_id)
            hyphen_loaded = store.load_backtest_by_run_id("us-equity", "global-etf", run_id)

        self.assertEqual(spaced_loaded.domain, "us equity")
        self.assertEqual(spaced_loaded.strategy_profile, "global etf")
        self.assertEqual(spaced_loaded.sharpe_ratio, 2.0)
        self.assertEqual(hyphen_loaded.domain, "us-equity")
        self.assertEqual(hyphen_loaded.strategy_profile, "global-etf")
        self.assertEqual(hyphen_loaded.sharpe_ratio, 1.0)

    def test_same_run_id_across_versions_follows_sort_key_not_enum_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = self._store(root)
            store.save_backtest_result(_backtest(
                run_id="versioned-run",
                param_version=1,
                computed_at="2026-01-01T00:00:00Z",
                sharpe_ratio=1.0,
            ))
            store.save_backtest_result(_backtest(
                run_id="versioned-run",
                param_version=2,
                computed_at="2026-06-01T00:00:00Z",
                sharpe_ratio=2.5,
            ))
            store.save_backtest_result(_backtest(
                run_id="baseline-run",
                param_set_id="rotation_baseline",
                param_version=1,
                computed_at="2026-01-15T00:00:00Z",
                sharpe_ratio=0.1,
            ))

            selected = store.load_backtest_by_run_id("us_equity", "global_etf_rotation", "versioned-run")
            pinned = store.load_backtest_by_run_id(
                "us_equity",
                "global_etf_rotation",
                "versioned-run",
                param_version=1,
            )
            missing_version = store.load_backtest_by_run_id(
                "us_equity",
                "global_etf_rotation",
                "versioned-run",
                param_version=9,
            )
            latest = store.load_latest_backtest("us_equity", "global_etf_rotation")

            store.save_backtest_result(_backtest(
                run_id="later-lower-version",
                param_version=1,
                computed_at="2026-08-01T00:00:00Z",
                sharpe_ratio=4.0,
            ))
            store.save_backtest_result(_backtest(
                run_id="later-lower-version",
                param_version=2,
                computed_at="2026-03-01T00:00:00Z",
                sharpe_ratio=0.4,
            ))
            later_lower_version = store.load_backtest_by_run_id(
                "us_equity",
                "global_etf_rotation",
                "later-lower-version",
            )

        self.assertEqual(selected.param_version, 2)
        self.assertEqual(selected.sharpe_ratio, 2.5)
        self.assertEqual(pinned.param_version, 1)
        self.assertEqual(pinned.sharpe_ratio, 1.0)
        self.assertIsNone(missing_version)
        self.assertEqual(latest.param_set_id, "rotation_baseline")
        self.assertEqual(later_lower_version.param_version, 1)
        self.assertEqual(later_lower_version.sharpe_ratio, 4.0)

    def test_legacy_stamp_equal_to_digest_is_not_replaced_by_run_directory(self) -> None:
        run_id = "stamp-collision"
        digest = _run_digest(run_id)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = self._store(root)
            directory = root / "backtest" / "us_equity" / "global_etf_rotation"
            directory.mkdir(parents=True)
            legacy = directory / f"backtest_v1_{digest}.json"
            legacy_payload = _backtest(
                run_id="unrelated-stamp",
                param_set_id="walk_forward",
                computed_at="2026-01-01T00:00:00Z",
                sharpe_ratio=9.0,
            ).to_dict()
            legacy.write_text(json.dumps(legacy_payload), encoding="utf-8")
            original = legacy.read_text(encoding="utf-8")
            store.save_backtest_result(_backtest(
                run_id=run_id,
                computed_at="2026-05-01T00:00:00Z",
                sharpe_ratio=1.5,
            ))
            nested = _run_file(root, run_id)
            latest = store.load_latest_backtest("us_equity", "global_etf_rotation")
            loaded = store.load_backtest_by_run_id("us_equity", "global_etf_rotation", run_id)
            preserved = legacy.read_text(encoding="utf-8")
            nested_exists = nested.is_file()
            segment_lengths = [len(part) for part in nested.relative_to(root).parts]

        self.assertEqual(preserved, original)
        self.assertTrue(nested_exists)
        self.assertTrue(all(length < 100 for length in segment_lengths))
        self.assertEqual(loaded.run_id, run_id)
        self.assertEqual(loaded.sharpe_ratio, 1.5)
        self.assertEqual(latest.run_id, run_id)
        self.assertEqual(latest.sharpe_ratio, 1.5)

    def test_same_run_merges_newer_legacy_with_new_path_and_pins_version(self) -> None:
        run_id = "mixed-run"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = self._store(root)
            directory = root / "backtest" / "us_equity" / "global_etf_rotation"
            directory.mkdir(parents=True)
            legacy = directory / "backtest_v1_2026-09-01T00-00-00Z.json"
            legacy.write_text(json.dumps(_backtest(
                run_id=run_id,
                param_version=1,
                computed_at="2026-09-01T00:00:00Z",
                sharpe_ratio=8.0,
            ).to_dict()), encoding="utf-8")
            store.save_backtest_result(_backtest(
                run_id=run_id,
                param_version=1,
                computed_at="2026-01-01T00:00:00Z",
                sharpe_ratio=1.0,
            ))
            store.save_backtest_result(_backtest(
                run_id=run_id,
                param_version=2,
                computed_at="2026-02-01T00:00:00Z",
                sharpe_ratio=2.0,
            ))

            selected = store.load_backtest_by_run_id("us_equity", "global_etf_rotation", run_id)
            pinned_legacy = store.load_backtest_by_run_id(
                "us_equity",
                "global_etf_rotation",
                run_id,
                param_version=1,
            )
            pinned_new = store.load_backtest_by_run_id(
                "us_equity",
                "global_etf_rotation",
                run_id,
                param_version=2,
            )
            legacy_remains = legacy.is_file()
            new_v1 = _run_file(root, run_id, 1).is_file()
            new_v2 = _run_file(root, run_id, 2).is_file()

        self.assertTrue(legacy_remains)
        self.assertTrue(new_v1)
        self.assertTrue(new_v2)
        self.assertEqual(selected.param_version, 1)
        self.assertEqual(selected.sharpe_ratio, 8.0)
        self.assertEqual(selected.computed_at, "2026-09-01T00:00:00Z")
        self.assertEqual(pinned_legacy.param_version, 1)
        self.assertEqual(pinned_legacy.sharpe_ratio, 8.0)
        self.assertEqual(pinned_new.param_version, 2)
        self.assertEqual(pinned_new.sharpe_ratio, 2.0)


def _validation_identity() -> BacktestValidationIdentity:
    return BacktestValidationIdentity(
        protocol="purged_walk_forward.v1",
        fold_id="candidate_wf0",
        fold_role="test",
        train_start=date(2020, 1, 2),
        train_end=date(2021, 1, 4),
        test_start=date(2021, 2, 1),
        test_end=date(2021, 6, 1),
        locked_oos_start=date(2022, 1, 3),
        locked_oos_end=date(2023, 1, 4),
        purge_days=5,
        embargo_days=3,
    )


def _plant_backtest(root: Path, run_id: str, payload: dict[str, object]) -> None:
    path = _run_file(root, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class BacktestReadbackMetadataTest(unittest.TestCase):
    def test_exact_readback_keeps_two_distinct_cost_inputs(self) -> None:
        low = {"commission_bps": 1.0, "slippage_bps": 2.0, "market_impact_bps": 0.0}
        high = {"commission_bps": 5.5, "slippage_bps": 3.0, "market_impact_bps": 1.25}
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_backtest_result(_backtest(run_id="cost-low", cost_inputs=low, sharpe_ratio=0.4))
            store.save_backtest_result(_backtest(run_id="cost-high", cost_inputs=high, sharpe_ratio=0.8))
            loaded_low = store.load_backtest_by_run_id("us_equity", "global_etf_rotation", "cost-low")
            loaded_high = store.load_backtest_by_run_id("us_equity", "global_etf_rotation", "cost-high")

        self.assertEqual(dict(loaded_low.cost_inputs), low)
        self.assertEqual(dict(loaded_high.cost_inputs), high)
        self.assertIsNone(loaded_low.validation_identity)
        self.assertIsNone(loaded_high.validation_identity)

    def test_validation_identity_round_trip(self) -> None:
        identity = _validation_identity()
        costs = {"commission_bps": 2.0, "slippage_bps": 1.0, "market_impact_bps": 0.5}
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_backtest_result(_backtest(
                run_id="identity-run",
                validation_identity=identity,
                cost_inputs=costs,
            ))
            loaded = store.load_backtest_by_run_id("us_equity", "global_etf_rotation", "identity-run")

        self.assertEqual(loaded.validation_identity, identity)
        self.assertEqual(dict(loaded.cost_inputs), costs)

    def test_legacy_file_without_cost_or_identity_keeps_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PerformanceStore(local_root=root)
            payload = _backtest(run_id="legacy-meta", sharpe_ratio=0.2).to_dict()
            payload.pop("cost_inputs")
            payload.pop("validation_identity")
            _plant_backtest(root, "legacy-meta", payload)
            loaded = store.load_backtest_by_run_id("us_equity", "global_etf_rotation", "legacy-meta")

        self.assertIsNotNone(loaded)
        self.assertEqual(dict(loaded.cost_inputs), {})
        self.assertIsNone(loaded.validation_identity)
        self.assertEqual(loaded.sharpe_ratio, 0.2)

    def test_malformed_cost_inputs_or_identity_fail_closed(self) -> None:
        identity = _validation_identity().to_dict()
        malformed: dict[str, dict[str, object]] = {
            "null-cost": {"cost_inputs": None},
            "bool-cost": {"cost_inputs": {"commission_bps": True}},
            "text-cost": {"cost_inputs": {"commission_bps": "1"}},
            "nonfinite-cost": {"cost_inputs": {"commission_bps": float("nan")}},
            "negative-cost": {"cost_inputs": {"commission_bps": -1}},
            "bad-identity-type": {"validation_identity": "purged_walk_forward.v1"},
            "partial-identity": {"validation_identity": {"protocol": "purged_walk_forward.v1"}},
            "bool-purge": {"validation_identity": {**identity, "purge_days": True}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PerformanceStore(local_root=root)
            for run_id, changes in malformed.items():
                payload = _backtest(run_id=run_id, cost_inputs={"commission_bps": 1.0}).to_dict()
                payload["validation_identity"] = identity
                payload.update(changes)
                _plant_backtest(root, run_id, payload)
                loaded = store.load_backtest_by_run_id("us_equity", "global_etf_rotation", run_id)
                self.assertIsNone(loaded, run_id)



_PARAMS = {"lookback": 20}
_COSTS = {"commission_bps": 1.0, "slippage_bps": 0.5}
_INITIAL = date(2024, 1, 1)
_START = date(2024, 1, 2)
_END = date(2024, 1, 3)


def _identity_digest(domain: str, profile: str, trial_id: str) -> str:
    return hashlib.sha256(f"{domain}\0{profile}\0{trial_id}".encode()).hexdigest()


def _research_file(root: Path, domain: str, profile: str, trial_id: str, name: str) -> Path:
    return root / "research_trial" / _identity_digest(domain, profile, trial_id) / f"{name}.json"


def _mark_day(
    session: date,
    cash: float,
    quantity: float,
    valuation: float,
    flow: float,
    fees: float,
    nav: float,
    previous: float,
    income_cashflow: float = 0.0,
    external_cashflow: float = 0.0,
    dividend_receivable: float = 0.0,
    declared_event_ids: tuple[str, ...] | None = None,
    events: tuple[ResearchLedgerEvent, ...] = (),
    restricted_cash: float = 0.0,
    option_settlement_cashflow: float = 0.0,
    position_marks: tuple[ResearchPositionMark, ...] | None = None,
    equity_trade_cashflow: float | None = None,
    equity_trade_quantities: dict[str, float] | None = None,
    equity_trade_phase: str | None = None,
) -> ResearchLedgerDay:
    positions = position_marks if position_marks is not None else (
        () if quantity == 0 else (ResearchPositionMark("SOXL", quantity, valuation),)
    )
    return ResearchLedgerDay(
        session,
        cash,
        positions,
        flow,
        fees,
        nav,
        nav / (previous + external_cashflow) - 1.0,
        income_cashflow,
        external_cashflow,
        dividend_receivable,
        declared_event_ids,
        events,
        restricted_cash,
        option_settlement_cashflow,
        equity_trade_cashflow,
        equity_trade_quantities,
        equity_trade_phase,
    )


def _option_mark(
    symbol: str,
    quantity: float,
    valuation: float,
    *,
    right: str,
    strike: float,
    expiration: date,
    premium_cashflow: float,
    underlying: str = "SOXL",
    multiplier: float = 100.0,
) -> ResearchPositionMark:
    return ResearchPositionMark(
        symbol=symbol,
        quantity=quantity,
        valuation=valuation,
        option_underlying=underlying,
        option_right=right,
        option_strike=strike,
        option_expiration=expiration,
        option_multiplier=multiplier,
        option_premium_cashflow=premium_cashflow,
    )


def _ledger(trial_id: str = "trial-a", run_id: str = "run-a", version: int = 1, domain: str = "us_equity", profile: str = "global_etf_rotation") -> ResearchDailyLedger:
    return ResearchDailyLedger(
        trial_id=trial_id,
        domain=domain,
        strategy_profile=profile,
        run_id=run_id,
        param_version=version,
        input_id="input-a",
        calendar_id="XNYS",
        periods_per_year=252.0,
        cost_source="synthetic_cost_v1",
        cost_inputs=dict(_COSTS),
        initial_session_date=_INITIAL,
        initial_nav=100.0,
        initial_cash=100.0,
        initial_positions=(),
        days=(
            _mark_day(_START, 59, 2, 40, -40, 1, 99, 100),
            _mark_day(_END, 59, 2, 50, 0, 0, 109, 99),
        ),
        synthetic=True,
    )


def _trial(status: ResearchTrialStatus, **overrides: object) -> ResearchTrialRecord:
    succeeded = status is ResearchTrialStatus.SUCCEEDED
    payload: dict[str, object] = {
        "trial_id": "trial-a",
        "domain": "us_equity",
        "strategy_profile": "global_etf_rotation",
        "status": status,
        "candidate_config_id": "candidate-a",
        "actual_params": dict(_PARAMS) if succeeded else None,
        "param_set_id": "set-a" if succeeded else None,
        "source_revision": "rev-a" if succeeded else None,
        "input_id": "input-a",
        "window_start": _INITIAL,
        "window_end": _END,
        "calendar_id": "XNYS",
        "periods_per_year": 252.0,
        "cost_source": "synthetic_cost_v1",
        "cost_inputs": dict(_COSTS),
        "reason_code": "" if succeeded or status is ResearchTrialStatus.STARTED else "config_unparsed",
        "synthetic": True,
        "run_id": "run-a" if succeeded else None,
        "param_version": 1 if succeeded else None,
    }
    payload.update(overrides)
    return ResearchTrialRecord(**payload)


def _result(ledger: ResearchDailyLedger, **overrides: object) -> BacktestResult:
    payload: dict[str, object] = {
        "strategy_profile": ledger.strategy_profile,
        "domain": ledger.domain,
        "param_set_id": "set-a",
        "params": dict(_PARAMS),
        "param_version": ledger.param_version,
        "run_id": ledger.run_id,
        "start_date": ledger.window_start,
        "end_date": ledger.window_end,
        "observation_count": ledger.observation_count,
        "total_return": ledger.total_return,
        "calendar_id": ledger.calendar_id,
        "periods_per_year": ledger.periods_per_year,
        "cost_model": ledger.cost_source,
        "cost_inputs": dict(ledger.cost_inputs),
        "source_revision": "rev-a",
        "sharpe_ratio": 1.0,
        "computed_at": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)
    return BacktestResult(**payload)


class _ResearchCloud:
    """In-memory object store. A successful round trip here is not GCS persistence."""

    def __init__(self) -> None:
        self.objects: dict[str, str] = {}
        self.fail_exists = False
        self.fail_read = False
        self.fail_create = False
        self.create_calls = 0

    def exists(self, uri: str) -> bool:
        if self.fail_exists:
            raise OSError("exists down")
        return uri in self.objects

    def read_text(self, uri: str) -> str:
        if self.fail_read:
            raise OSError("read down")
        return self.objects[uri]

    def read_bytes(self, uri: str) -> bytes:
        return self.read_text(uri).encode()

    def write_bytes(self, uri: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self.objects[uri] = data.decode()
        return uri

    def create_text(self, uri: str, data: str, content_type: str = "text/plain") -> bool:
        self.create_calls += 1
        if self.fail_create:
            raise OSError("create down")
        if uri in self.objects:
            return False
        self.objects[uri] = data
        return True

    def list(self, prefix: str) -> list[str]:
        return [uri for uri in self.objects if uri.startswith(prefix)]


class ResearchTrialLedgerStoreTest(unittest.TestCase):
    def test_external_cashflow_is_excluded_from_daily_and_total_return_and_matches_result(self) -> None:
        day = _mark_day(
            _END,
            cash=200.0,
            quantity=0.0,
            valuation=0.0,
            flow=0.0,
            fees=0.0,
            nav=200.0,
            previous=100.0,
            external_cashflow=100.0,
        )
        ledger = ResearchDailyLedger(
            trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
            run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
            periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
            initial_session_date=_INITIAL, initial_nav=100.0, initial_cash=100.0,
            initial_positions=(), days=(day,), synthetic=True,
        )
        self.assertEqual(ledger.days[0].daily_return, 0.0)
        self.assertEqual(ledger.total_return, 0.0)
        self.assertEqual(ledger.to_dict()["days"][0]["external_cashflow"], 100.0)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PerformanceStore(local_root=root)
            result = _result(ledger)
            store.save_backtest_result(result)
            store.save_research_ledger(ledger)
            store.save_research_trial(_trial(ResearchTrialStatus.SUCCEEDED))
            loaded = store.load_research_trial("us_equity", "global_etf_rotation", "trial-a")
        self.assertEqual(result.total_return, 0.0)
        self.assertEqual(loaded.status, ResearchTrialStatus.SUCCEEDED)

    def test_legacy_non_integer_nav_total_return_uses_original_formula(self) -> None:
        first_return = 1.2 / 1.1 - 1.0
        second_return = 1.3 / 1.2 - 1.0
        self.assertNotEqual((1.0 + first_return) * (1.0 + second_return) - 1.0, 1.3 / 1.1 - 1.0)
        ledger = ResearchDailyLedger(
            trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
            run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
            periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
            initial_session_date=_INITIAL, initial_nav=1.1, initial_cash=1.1, initial_positions=(),
            days=(
                _mark_day(_START, 1.2, 0.0, 0.0, 0.1, 0.0, 1.2, 1.1),
                _mark_day(_END, 1.3, 0.0, 0.0, 0.1, 0.0, 1.3, 1.2),
            ), synthetic=True,
        )
        self.assertEqual(ledger.total_return, ledger.days[-1].nav / ledger.initial_nav - 1.0)
        result = _result(ledger)
        self.assertEqual(result.total_return, ledger.total_return)

    def test_explicit_empty_event_declaration_is_complete_and_round_trips(self) -> None:
        ledger = ResearchDailyLedger(
            trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
            run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
            periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
            initial_session_date=_INITIAL, initial_nav=100.0, initial_cash=100.0, initial_positions=(),
            days=(_mark_day(
                _START, 100.0, 0.0, 0.0, 0.0, 0.0, 100.0, 100.0, declared_event_ids=(),
            ),), synthetic=True,
        )
        self.assertTrue(ledger.events_complete)
        self.assertEqual(ledger.days[0].to_dict()["declared_event_ids"], [])
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_research_ledger(ledger)
            loaded = store.load_research_ledger("us_equity", "global_etf_rotation", "trial-a", "run-a", 1)
        self.assertEqual(loaded, ledger)

    def test_long_leaps_purchase_keeps_nav_flat_and_round_trips(self) -> None:
        leaps = _option_mark(
            "SOXL-2026-01-16-90C", 1.0, 9000.0, right="call", strike=90.0,
            expiration=date(2026, 1, 16), premium_cashflow=-9000.0,
        )
        day = ResearchLedgerDay(
            _START, 1000.0, (leaps,), -9000.0, 0.0, 10000.0, 0.0,
            declared_event_ids=("leaps-buy",),
            events=(ResearchLedgerEvent("leaps-buy", "option_trade", leaps.symbol, amount=-9000.0),),
        )
        ledger = ResearchDailyLedger(
            trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
            run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
            periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
            initial_session_date=_INITIAL, initial_nav=10000.0, initial_cash=10000.0,
            initial_positions=(), days=(day,), synthetic=True,
        )
        self.assertEqual(ledger.days[0].nav, ledger.initial_nav)
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_research_ledger(ledger)
            loaded = store.load_research_ledger("us_equity", "global_etf_rotation", "trial-a", "run-a", 1)
        self.assertEqual(loaded, ledger)
        self.assertEqual(loaded.days[0].positions[0].symbol, "SOXL-2026-01-16-90C")

    def test_zero_mark_option_can_expire_worthless_without_share_delivery(self) -> None:
        call = _option_mark(
            "SOXL-2024-01-03-90C", 1.0, 0.0, right="call", strike=90.0,
            expiration=_END, premium_cashflow=-100.0,
        )
        expired = _mark_day(
            _END, 1000.0, 0.0, 0.0, 0.0, 0.0, 1000.0, 1000.0,
            declared_event_ids=("call-expiry",),
            events=(ResearchLedgerEvent("call-expiry", "option_settlement", "SOXL", settlement_price=75.0),),
        )
        ledger = ResearchDailyLedger(
            trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
            run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
            periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
            initial_session_date=_INITIAL, initial_nav=1000.0, initial_cash=1000.0,
            initial_positions=(call,), days=(expired,), synthetic=True,
        )
        self.assertEqual(ledger.days[0].nav, ledger.initial_nav)
        self.assertEqual(ledger.days[0].option_settlement_cashflow, 0.0)

    def test_option_close_cashflow_sign_matches_open_position_side(self) -> None:
        short = _option_mark(
            "SOXL-2024-01-17-90P", -1.0, -900.0, right="put", strike=90.0,
            expiration=date(2024, 1, 17), premium_cashflow=900.0,
        )
        long = _option_mark(
            "SOXL-2024-01-17-80P", 1.0, 700.0, right="put", strike=80.0,
            expiration=date(2024, 1, 17), premium_cashflow=-700.0,
        )
        for short_close, long_close in ((100.0, 100.0), (-100.0, -100.0)):
            with self.subTest(short_close=short_close, long_close=long_close):
                flow = short_close + long_close
                day = _mark_day(
                    _START, 1000.0 + flow, 0.0, 0.0, flow, 0.0, 1000.0 + flow, 800.0,
                    declared_event_ids=("short-close", "long-close", "collateral-release"),
                    events=(
                        ResearchLedgerEvent("short-close", "option_trade", short.symbol, amount=short_close),
                        ResearchLedgerEvent("long-close", "option_trade", long.symbol, amount=long_close),
                        ResearchLedgerEvent("collateral-release", "collateral_change", "CASH", amount=-800.0),
                    ),
                    restricted_cash=0.0,
                )
                with self.assertRaisesRegex(ValueError, "ledger_option_trade"):
                    ResearchDailyLedger(
                        trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
                        run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
                        periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
                        initial_session_date=_INITIAL, initial_nav=800.0, initial_cash=1000.0,
                        initial_positions=(short, long), days=(day,), synthetic=True,
                        initial_restricted_cash=800.0,
                    )

    def test_put_credit_spread_settles_physical_legs_and_releases_collateral(self) -> None:
        expiration = _END
        short = _option_mark(
            "SOXL-2024-01-03-90P", -1.0, -900.0, right="put", strike=90.0,
            expiration=expiration, premium_cashflow=900.0,
        )
        long = _option_mark(
            "SOXL-2024-01-03-80P", 1.0, 700.0, right="put", strike=80.0,
            expiration=expiration, premium_cashflow=-700.0,
        )
        opened = _mark_day(
            _START, 1200.0, 0.0, 0.0, 200.0, 0.0, 1000.0, 1000.0,
            declared_event_ids=("short-open", "long-open", "collateral-lock"),
            events=(
                ResearchLedgerEvent("short-open", "option_trade", short.symbol, amount=900.0),
                ResearchLedgerEvent("long-open", "option_trade", long.symbol, amount=-700.0),
                ResearchLedgerEvent("collateral-lock", "collateral_change", "CASH", amount=800.0),
            ),
            restricted_cash=800.0,
            position_marks=(short, long),
        )
        settled = _mark_day(
            _END, 200.0, 0.0, 0.0, 0.0, 0.0, 200.0, 1000.0,
            declared_event_ids=("expiry", "collateral-release"),
            events=(
                ResearchLedgerEvent("expiry", "option_settlement", "SOXL", settlement_price=75.0),
                ResearchLedgerEvent("collateral-release", "collateral_change", "CASH", amount=-800.0),
            ),
            restricted_cash=0.0,
            option_settlement_cashflow=-1000.0,
        )
        ledger = ResearchDailyLedger(
            trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
            run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
            periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
            initial_session_date=_INITIAL, initial_nav=1000.0, initial_cash=1000.0,
            initial_positions=(), days=(opened, settled), synthetic=True,
        )
        self.assertEqual(opened.nav, 1000.0)
        self.assertEqual(opened.restricted_cash, 800.0)
        self.assertEqual(settled.cash, 200.0)
        self.assertEqual(settled.nav, 200.0)
        self.assertEqual(settled.daily_return, -0.8)
        self.assertEqual(ledger.total_return, -0.8)
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_research_ledger(ledger)
            loaded = store.load_research_ledger("us_equity", "global_etf_rotation", "trial-a", "run-a", 1)
        self.assertEqual(loaded, ledger)

        repeated_settlement = _mark_day(
            date(2024, 1, 4), 200.0, 0.0, 0.0, 0.0, 0.0, 200.0, 200.0,
            declared_event_ids=("expiry-repeat",),
            events=(ResearchLedgerEvent("expiry-repeat", "option_settlement", "SOXL", settlement_price=75.0),),
        )
        with self.assertRaisesRegex(ValueError, "ledger_option_settlement"):
            ResearchDailyLedger(
                trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
                run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
                periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
                initial_session_date=_INITIAL, initial_nav=1000.0, initial_cash=1000.0,
                initial_positions=(), days=(opened, settled, repeated_settlement), synthetic=True,
            )

    def test_equity_rebalance_and_option_trade_cashflows_are_explicitly_decomposed(self) -> None:
        short = _option_mark(
            "SOXL-2024-01-17-90P", -1.0, -900.0, right="put", strike=90.0,
            expiration=_END, premium_cashflow=900.0,
        )
        long = _option_mark(
            "SOXL-2024-01-17-80P", 1.0, 700.0, right="put", strike=80.0,
            expiration=_END, premium_cashflow=-700.0,
        )
        equity = ResearchPositionMark("SOXL", 2.0, 200.0)
        opened = _mark_day(
            _START, 1100.0, 2.0, 200.0, 100.0, 0.0, 1100.0, 1100.0,
            declared_event_ids=("short-open", "long-open", "collateral-lock"),
            events=(
                ResearchLedgerEvent("short-open", "option_trade", short.symbol, amount=900.0),
                ResearchLedgerEvent("long-open", "option_trade", long.symbol, amount=-700.0),
                ResearchLedgerEvent("collateral-lock", "collateral_change", "CASH", amount=800.0),
            ),
            restricted_cash=800.0,
            position_marks=(equity, short, long),
            equity_trade_cashflow=-100.0,
        )
        ledger = ResearchDailyLedger(
            trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
            run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
            periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
            initial_session_date=_INITIAL, initial_nav=1100.0, initial_cash=1000.0,
            initial_positions=(ResearchPositionMark("SOXL", 1.0, 100.0),),
            days=(opened,), synthetic=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_research_ledger(ledger)
            loaded = store.load_research_ledger("us_equity", "global_etf_rotation", "trial-a", "run-a", 1)
        self.assertEqual(loaded, ledger)
        self.assertEqual(loaded.days[0].trade_net_cashflow, 100.0)
        self.assertEqual(loaded.days[0].equity_trade_cashflow, -100.0)

    def test_option_trade_day_rejects_missing_or_unbalanced_equity_cashflow(self) -> None:
        short = _option_mark(
            "SOXL-2024-01-17-90P", -1.0, -900.0, right="put", strike=90.0,
            expiration=_END, premium_cashflow=900.0,
        )
        long = _option_mark(
            "SOXL-2024-01-17-80P", 1.0, 700.0, right="put", strike=80.0,
            expiration=_END, premium_cashflow=-700.0,
        )
        common = dict(
            session_date=_START, cash=1100.0, positions=(ResearchPositionMark("SOXL", 2.0, 200.0), short, long),
            trade_net_cashflow=100.0, fees=0.0, nav=1100.0, daily_return=0.0,
            declared_event_ids=("short-open", "long-open"),
            events=(
                ResearchLedgerEvent("short-open", "option_trade", short.symbol, amount=900.0),
                ResearchLedgerEvent("long-open", "option_trade", long.symbol, amount=-700.0),
            ),
        )
        for equity_cashflow in (None, -90.0):
            with self.subTest(equity_cashflow=equity_cashflow), self.assertRaises(ValueError):
                day = ResearchLedgerDay(**common, equity_trade_cashflow=equity_cashflow)
                ResearchDailyLedger(
                    trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
                    run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
                    periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
                    initial_session_date=_INITIAL, initial_nav=1100.0, initial_cash=1000.0,
                    initial_positions=(ResearchPositionMark("SOXL", 1.0, 100.0),),
                    days=(day,), synthetic=True,
                )
    def test_single_itm_put_assignment_requires_full_cash_and_stock_delivery(self) -> None:
        expiration = _END
        short = _option_mark(
            "SOXL-2024-01-03-90P", -1.0, -900.0, right="put", strike=90.0,
            expiration=expiration, premium_cashflow=900.0,
        )
        long = _option_mark(
            "SOXL-2024-01-03-80P", 1.0, 700.0, right="put", strike=80.0,
            expiration=expiration, premium_cashflow=-700.0,
        )
        opened = _mark_day(
            _START, 10200.0, 0.0, 0.0, 200.0, 0.0, 10000.0, 10000.0,
            declared_event_ids=("short-open", "long-open", "collateral-lock"),
            events=(
                ResearchLedgerEvent("short-open", "option_trade", short.symbol, amount=900.0),
                ResearchLedgerEvent("long-open", "option_trade", long.symbol, amount=-700.0),
                ResearchLedgerEvent("collateral-lock", "collateral_change", "CASH", amount=800.0),
            ),
            restricted_cash=800.0,
            position_marks=(short, long),
        )
        stock = ResearchPositionMark("SOXL", 100.0, 8500.0)
        expiration_day = _mark_day(
            _END, 1200.0, 100.0, 8500.0, 0.0, 0.0, 9700.0, 10000.0,
            declared_event_ids=("expiry", "collateral-release"),
            events=(
                ResearchLedgerEvent("expiry", "option_settlement", "SOXL", settlement_price=85.0),
                ResearchLedgerEvent("collateral-release", "collateral_change", "CASH", amount=-800.0),
            ),
            restricted_cash=0.0,
            option_settlement_cashflow=-9000.0,
        )
        ledger = ResearchDailyLedger(
            trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
            run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
            periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
            initial_session_date=_INITIAL, initial_nav=10000.0, initial_cash=10000.0,
            initial_positions=(), days=(opened, dataclasses.replace(expiration_day, positions=(stock,))),
            synthetic=True,
        )
        self.assertEqual(ledger.days[-1].cash, 1200.0)
        self.assertEqual(ledger.days[-1].positions[0].quantity, 100.0)
        self.assertEqual(ledger.days[-1].nav, 9700.0)

        with self.assertRaisesRegex(ValueError, "ledger_event_type"):
            ResearchLedgerEvent("early-assignment", "option_assignment", "SOXL", amount=-9000.0)

        funded_open = _mark_day(
            _START, 1200.0, 0.0, 0.0, 200.0, 0.0, 1000.0, 1000.0,
            declared_event_ids=("short-open", "long-open", "collateral-lock"),
            events=(
                ResearchLedgerEvent("short-open", "option_trade", short.symbol, amount=900.0),
                ResearchLedgerEvent("long-open", "option_trade", long.symbol, amount=-700.0),
                ResearchLedgerEvent("collateral-lock", "collateral_change", "CASH", amount=800.0),
            ), restricted_cash=800.0, position_marks=(short, long),
        )
        explicitly_funded = _mark_day(
            _END, 200.0, 100.0, 8500.0, 0.0, 0.0, 8700.0, 1000.0,
            external_cashflow=8000.0,
            declared_event_ids=("expiry", "collateral-release"),
            events=(
                ResearchLedgerEvent("expiry", "option_settlement", "SOXL", settlement_price=85.0),
                ResearchLedgerEvent("collateral-release", "collateral_change", "CASH", amount=-800.0),
            ), restricted_cash=0.0, option_settlement_cashflow=-9000.0,
        )
        funded_ledger = ResearchDailyLedger(
            trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
            run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
            periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
            initial_session_date=_INITIAL, initial_nav=1000.0, initial_cash=1000.0,
            initial_positions=(), days=(funded_open, explicitly_funded), synthetic=True,
        )
        self.assertEqual(funded_ledger.days[-1].external_cashflow, 8000.0)
        self.assertEqual(funded_ledger.days[-1].cash, 200.0)

    def test_option_settlement_allows_declared_same_day_equity_trades_and_fees(self) -> None:
        call = _option_mark(
            "TQQQ-2024-01-03-90C", 1.0, 100.0, right="call", strike=90.0,
            expiration=_END, premium_cashflow=-100.0, underlying="TQQQ",
        )

        def make_ledger(
            initial_cash: float,
            *,
            initial_equity: bool = False,
            include_quantities: bool = True,
            declared_equity_cashflow: float | None = 1800.0,
            trade_phase: str | None = "after_settlement",
        ) -> ResearchDailyLedger:
            starting_stock = ResearchPositionMark("TQQQ", 20.0, 2000.0) if initial_equity else None
            initial_positions = (call,) if starting_stock is None else (call, starting_stock)
            settlement_cashflow = -9000.0
            net_equity_flow = 1800.0
            fees = 5.0
            ending_cash = initial_cash + net_equity_flow - fees + settlement_cashflow
            ending_shares = 100.0 if initial_equity else 80.0
            ending_nav = ending_cash + ending_shares * 100.0 + 2 * 100.0
            day = _mark_day(
                _END, ending_cash, ending_shares, ending_shares * 100.0,
                net_equity_flow, fees, ending_nav,
                initial_cash + call.valuation + (2000.0 if initial_equity else 0.0),
                declared_event_ids=("call-expiry",),
                events=(ResearchLedgerEvent(
                    "call-expiry", "option_settlement", "TQQQ", settlement_price=100.0,
                ),),
                option_settlement_cashflow=settlement_cashflow,
                equity_trade_cashflow=declared_equity_cashflow,
                equity_trade_quantities={"TQQQ": -20.0, "SPY": 2.0} if include_quantities else None,
                equity_trade_phase=trade_phase if include_quantities else None,
                position_marks=(
                    ResearchPositionMark("TQQQ", ending_shares, ending_shares * 100.0),
                    ResearchPositionMark("SPY", 2.0, 200.0),
                ),
            )
            return ResearchDailyLedger(
                trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
                run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
                periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
                initial_session_date=_INITIAL,
                initial_nav=initial_cash + call.valuation + (2000.0 if initial_equity else 0.0),
                initial_cash=initial_cash, initial_positions=initial_positions, days=(day,), synthetic=True,
            )

        ledger = make_ledger(9900.0)
        self.assertEqual(ledger.days[0].cash, 2695.0)
        self.assertEqual(ledger.days[0].nav, 10895.0)
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_research_ledger(ledger)
            loaded = store.load_research_ledger("us_equity", "global_etf_rotation", "trial-a", "run-a", 1)
        self.assertEqual(loaded, ledger)
        self.assertEqual(loaded.days[0].equity_trade_quantities, {"SPY": 2.0, "TQQQ": -20.0})

        with self.assertRaisesRegex(ValueError, "ledger_equity_trade_quantity"):
            make_ledger(9900.0, trade_phase="before_settlement")

        before_settlement = make_ledger(
            8500.0, initial_equity=True, trade_phase="before_settlement",
        )
        self.assertEqual(before_settlement.days[0].cash, 1295.0)
        self.assertEqual(before_settlement.days[0].nav, 11495.0)

        with self.assertRaisesRegex(ValueError, "ledger_equity_trade_quantity"):
            make_ledger(9900.0, include_quantities=False)
        with self.assertRaisesRegex(ValueError, "ledger_option_settlement"):
            make_ledger(9900.0, declared_equity_cashflow=1700.0)
        with self.assertRaisesRegex(ValueError, "ledger_option_funding"):
            make_ledger(8000.0)

    def test_insufficient_collateral_funding_missing_settlement_and_repeat_fail_closed(self) -> None:
        expiration = _END
        short = _option_mark(
            "SOXL-2024-01-03-90P", -1.0, -900.0, right="put", strike=90.0,
            expiration=expiration, premium_cashflow=900.0,
        )
        long = _option_mark(
            "SOXL-2024-01-03-80P", 1.0, 700.0, right="put", strike=80.0,
            expiration=expiration, premium_cashflow=-700.0,
        )
        events = (
            ResearchLedgerEvent("short-open", "option_trade", short.symbol, amount=900.0),
            ResearchLedgerEvent("long-open", "option_trade", long.symbol, amount=-700.0),
            ResearchLedgerEvent("collateral-lock", "collateral_change", "CASH", amount=700.0),
        )
        under_collateralized = _mark_day(
            _START, 1200.0, 0.0, 0.0, 200.0, 0.0, 1000.0, 1000.0,
            declared_event_ids=tuple(event.event_id for event in events), events=events, restricted_cash=700.0,
            position_marks=(short, long),
        )
        base = dict(
            trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
            run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
            periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
            initial_session_date=_INITIAL, initial_nav=1000.0, initial_cash=1000.0,
            initial_positions=(), synthetic=True,
        )
        with self.assertRaisesRegex(ValueError, "ledger_option_collateral"):
            ResearchDailyLedger(**base, days=(under_collateralized,))

        funded_events = (
            events[0], events[1],
            ResearchLedgerEvent("collateral-lock", "collateral_change", "CASH", amount=800.0),
        )
        funded_open = dataclasses.replace(
            under_collateralized,
            declared_event_ids=tuple(event.event_id for event in funded_events),
            events=funded_events,
            restricted_cash=800.0,
        )

        insufficient_settlement = _mark_day(
            _END, -7800.0, 100.0, 8500.0, 0.0, 0.0, 700.0, 1000.0,
            declared_event_ids=("expiry", "collateral-release"),
            events=(
                ResearchLedgerEvent("expiry", "option_settlement", "SOXL", settlement_price=85.0),
                ResearchLedgerEvent("collateral-release", "collateral_change", "CASH", amount=-800.0),
            ), restricted_cash=0.0, option_settlement_cashflow=-9000.0,
        )
        with self.assertRaisesRegex(ValueError, "ledger_option_funding"):
            ResearchDailyLedger(**base, days=(funded_open, insufficient_settlement))

        missing_settlement = _mark_day(
            _END, 1200.0, 0.0, 0.0, 0.0, 0.0, 1000.0, 1000.0,
            declared_event_ids=(), restricted_cash=800.0, position_marks=(short, long),
        )
        with self.assertRaisesRegex(ValueError, "ledger_option_settlement"):
            ResearchDailyLedger(**base, days=(funded_open, missing_settlement))

    def test_dividend_accrual_and_payment_preserve_nav_and_read_back(self) -> None:
        accrual = ResearchLedgerEvent("div-ex-1", "dividend_accrual", "SOXL", per_share=5.0)
        payment = ResearchLedgerEvent(
            "div-pay-1", "dividend_payment", "SOXL", amount=5.0, reference_event_id="div-ex-1"
        )
        ex_day = _mark_day(
            _START, 0.0, 1.0, 95.0, 0.0, 0.0, 100.0, 100.0,
            dividend_receivable=5.0, declared_event_ids=("div-ex-1",), events=(accrual,),
        )
        pay_day = _mark_day(
            _END, 5.0, 1.0, 95.0, 0.0, 0.0, 100.0, 100.0, income_cashflow=5.0,
            declared_event_ids=("div-pay-1",), events=(payment,),
        )
        ledger = ResearchDailyLedger(
            trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
            run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
            periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
            initial_session_date=_INITIAL, initial_nav=100.0, initial_cash=0.0,
            initial_positions=(ResearchPositionMark("SOXL", 1.0, 100.0),),
            days=(ex_day, pay_day), synthetic=True,
        )
        self.assertEqual((ex_day.nav, ex_day.dividend_receivable, ex_day.daily_return), (100.0, 5.0, 0.0))
        self.assertEqual((pay_day.nav, pay_day.dividend_receivable, pay_day.daily_return), (100.0, 0.0, 0.0))
        self.assertEqual(ledger.total_return, 0.0)
        self.assertTrue(ledger.events_complete)
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_research_ledger(ledger)
            loaded = store.load_research_ledger("us_equity", "global_etf_rotation", "trial-a", "run-a", 1)
        self.assertEqual(loaded, ledger)
        self.assertTrue(all(day.declared_event_ids is not None for day in loaded.days))

    def test_split_preserves_wealth_and_validates_quantity(self) -> None:
        day = _mark_day(
            _START, 0.0, 2.0, 100.0, 0.0, 0.0, 100.0, 100.0,
            declared_event_ids=("split-1",),
            events=(ResearchLedgerEvent("split-1", "split", "SOXL", ratio=2.0),),
        )
        ledger = ResearchDailyLedger(
            trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
            run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
            periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
            initial_session_date=_INITIAL, initial_nav=100.0, initial_cash=0.0,
            initial_positions=(ResearchPositionMark("SOXL", 1.0, 100.0),), days=(day,), synthetic=True,
        )
        self.assertEqual(ledger.days[0].positions[0].quantity * 50.0, 100.0)
        with self.assertRaisesRegex(ValueError, "ledger_split_quantity"):
            ResearchDailyLedger(
                trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
                run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
                periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
                initial_session_date=_INITIAL, initial_nav=100.0, initial_cash=0.0,
                initial_positions=(ResearchPositionMark("SOXL", 1.0, 100.0),),
                days=(_mark_day(
                    _START, 0.0, 3.0, 150.0, 0.0, 0.0, 150.0, 100.0,
                    declared_event_ids=("split-1",),
                    events=(ResearchLedgerEvent("split-1", "split", "SOXL", ratio=2.0),),
                ),), synthetic=True,
            )

    def test_event_declarations_pairing_duplicates_and_split_trade_fail_closed(self) -> None:
        accrual = ResearchLedgerEvent("ex-1", "dividend_accrual", "SOXL", per_share=1.0)
        day = _mark_day(
            _START, 0.0, 1.0, 99.0, 0.0, 0.0, 100.0, 100.0,
            dividend_receivable=1.0, declared_event_ids=("wrong-id",), events=(accrual,),
        )
        with self.assertRaisesRegex(ValueError, "ledger_event_set"):
            ResearchDailyLedger(
                trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
                run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
                periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
                initial_session_date=_INITIAL, initial_nav=100.0, initial_cash=0.0,
                initial_positions=(ResearchPositionMark("SOXL", 1.0, 100.0),), days=(day,), synthetic=True,
            )
        payment = ResearchLedgerEvent(
            "pay-1", "dividend_payment", "SOXL", amount=1.0, reference_event_id="missing-ex"
        )
        with self.assertRaisesRegex(ValueError, "ledger_dividend_pair"):
            ResearchDailyLedger(
                trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
                run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
                periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
                initial_session_date=_INITIAL, initial_nav=100.0, initial_cash=0.0,
                initial_positions=(ResearchPositionMark("SOXL", 1.0, 100.0),),
                days=(_mark_day(
                    _START, 1.0, 1.0, 99.0, 0.0, 0.0, 100.0, 100.0, income_cashflow=1.0,
                    declared_event_ids=("pay-1",), events=(payment,),
                ),), synthetic=True,
            )
        split = ResearchLedgerEvent("split-2", "split", "SOXL", ratio=2.0)
        with self.assertRaisesRegex(ValueError, "ledger_split_trade"):
            ResearchDailyLedger(
                trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
                run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
                periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
                initial_session_date=_INITIAL, initial_nav=100.0, initial_cash=0.0,
                initial_positions=(ResearchPositionMark("SOXL", 1.0, 100.0),),
                days=(_mark_day(
                    _START, -10.0, 2.0, 110.0, -10.0, 0.0, 100.0, 100.0,
                    declared_event_ids=("split-2",), events=(split,),
                ),), synthetic=True,
            )
        valid_day = _mark_day(
            _START, 0.0, 1.0, 99.0, 0.0, 0.0, 100.0, 100.0,
            dividend_receivable=1.0, declared_event_ids=("ex-1",), events=(accrual,),
        )
        repeated = ResearchLedgerEvent("ex-1", "dividend_accrual", "SOXL", per_share=1.0)
        with self.assertRaisesRegex(ValueError, "ledger_event_duplicate"):
            ResearchDailyLedger(
                trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
                run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
                periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
                initial_session_date=_INITIAL, initial_nav=100.0, initial_cash=0.0,
                initial_positions=(ResearchPositionMark("SOXL", 1.0, 100.0),),
                days=(valid_day, _mark_day(
                    _END, 0.0, 1.0, 98.0, 0.0, 0.0, 100.0, 100.0,
                    dividend_receivable=2.0, declared_event_ids=("ex-1",), events=(repeated,),
                )), synthetic=True,
            )
        with self.assertRaisesRegex(ValueError, "ledger_dividend_pair"):
            ResearchDailyLedger(
                trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
                run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
                periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
                initial_session_date=_INITIAL, initial_nav=100.0, initial_cash=0.0,
                initial_positions=(ResearchPositionMark("SOXL", 1.0, 100.0),),
                days=(
                    valid_day,
                    _mark_day(
                        _END, 1.0, 1.0, 99.0, 0.0, 0.0, 100.0, 100.0, income_cashflow=1.0,
                        declared_event_ids=("pay-1",), events=(ResearchLedgerEvent(
                            "pay-1", "dividend_payment", "SOXL", amount=1.0, reference_event_id="ex-1"
                        ),),
                    ),
                    _mark_day(
                        date(2024, 1, 4), 2.0, 1.0, 99.0, 0.0, 0.0, 101.0, 100.0, income_cashflow=1.0,
                        declared_event_ids=("pay-retry",), events=(ResearchLedgerEvent(
                            "pay-retry", "dividend_payment", "SOXL", amount=1.0,
                            reference_event_id="ex-1",
                        ),),
                    ),
                ), synthetic=True,
            )
        with self.assertRaisesRegex(ValueError, "ledger_event_set"):
            ResearchDailyLedger(
                trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
                run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
                periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
                initial_session_date=_INITIAL, initial_nav=100.0, initial_cash=0.0,
                initial_positions=(ResearchPositionMark("SOXL", 1.0, 100.0),),
                days=(day, _mark_day(_END, 0.0, 1.0, 100.0, 0.0, 0.0, 100.0, 100.0)), synthetic=True,
            )
        with self.assertRaisesRegex(ValueError, "ledger_event_set"):
            ResearchDailyLedger(
                trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
                run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
                periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
                initial_session_date=_INITIAL, initial_nav=100.0, initial_cash=0.0,
                initial_positions=(ResearchPositionMark("SOXL", 1.0, 100.0),),
                days=(_mark_day(
                    _START, 0.0, 1.0, 99.0, 0.0, 0.0, 100.0, 100.0,
                    dividend_receivable=1.0, events=(accrual,),
                ),), synthetic=True,
            )
        with self.assertRaisesRegex(ValueError, "ledger_dividend_cashflow"):
            ResearchDailyLedger(
                trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
                run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
                periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
                initial_session_date=_INITIAL, initial_nav=100.0, initial_cash=0.0,
                initial_positions=(ResearchPositionMark("SOXL", 1.0, 100.0),),
                days=(
                    _mark_day(
                        _START, 0.0, 1.0, 99.0, 0.0, 0.0, 100.0, 100.0,
                        dividend_receivable=1.0, declared_event_ids=("ex-1",), events=(accrual,),
                    ),
                    _mark_day(
                        _END, 2.0, 1.0, 99.0, 0.0, 0.0, 101.0, 100.0, income_cashflow=2.0,
                        declared_event_ids=("pay-extra",), events=(ResearchLedgerEvent(
                            "pay-extra", "dividend_payment", "SOXL", amount=1.0,
                            reference_event_id="ex-1",
                        ),),
                    ),
                ), synthetic=True,
            )

    def test_income_cashflow_conserves_cash_and_preserves_legacy_zero_payload(self) -> None:
        income_day = _mark_day(
            _START,
            cash=105.0,
            quantity=1.0,
            valuation=110.0,
            flow=0.0,
            fees=0.0,
            nav=215.0,
            previous=200.0,
            income_cashflow=5.0,
        )
        ledger = ResearchDailyLedger(
            trial_id="trial-a",
            domain="us_equity",
            strategy_profile="global_etf_rotation",
            run_id="run-a",
            param_version=1,
            input_id="input-a",
            calendar_id="XNYS",
            periods_per_year=252.0,
            cost_source="synthetic_cost_v1",
            cost_inputs=dict(_COSTS),
            initial_session_date=_INITIAL,
            initial_nav=200.0,
            initial_cash=100.0,
            initial_positions=(ResearchPositionMark("SOXL", 1.0, 100.0),),
            days=(income_day,),
            synthetic=True,
        )
        self.assertEqual(ledger.days[0].cash, 105.0)
        self.assertEqual(ledger.days[0].nav, 215.0)
        self.assertAlmostEqual(ledger.days[0].daily_return, 0.075)
        self.assertEqual(ledger.days[0].to_dict()["income_cashflow"], 5.0)
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_research_ledger(ledger)
            loaded_income = store.load_research_ledger(
                "us_equity", "global_etf_rotation", "trial-a", "run-a", 1
            )
        self.assertEqual(loaded_income, ledger)
        self.assertEqual(loaded_income.days[0].income_cashflow, 5.0)

        old_ledger = _ledger()
        old_payload = {"schema_version": SCHEMA_VERSION, **old_ledger.to_dict()}
        old_day_payload = old_payload["days"][0]
        self.assertNotIn("income_cashflow", old_day_payload)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "research_trial" / _identity_digest("us_equity", "global_etf_rotation", "trial-a") / "ledger.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(old_payload), encoding="utf-8")
            loaded_old = PerformanceStore(local_root=root).load_research_ledger(
                "us_equity", "global_etf_rotation", "trial-a", "run-a", 1
            )
        self.assertEqual(loaded_old, old_ledger)
        self.assertEqual(loaded_old.days[0].income_cashflow, 0.0)
        self.assertEqual(loaded_old.days[0].dividend_receivable, 0.0)
        self.assertIsNone(loaded_old.days[0].declared_event_ids)
        self.assertFalse(loaded_old.events_complete)

    def test_tampered_cash_does_not_match_income_cashflow(self) -> None:
        income_day = _mark_day(
            _START,
            cash=105.0,
            quantity=1.0,
            valuation=110.0,
            flow=0.0,
            fees=0.0,
            nav=215.0,
            previous=200.0,
            income_cashflow=5.0,
        )
        ledger = ResearchDailyLedger(
            trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
            run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
            periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
            initial_session_date=_INITIAL, initial_nav=200.0, initial_cash=100.0,
            initial_positions=(ResearchPositionMark("SOXL", 1.0, 100.0),),
            days=(income_day,), synthetic=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PerformanceStore(local_root=root)
            store.save_research_ledger(ledger)
            path = root / "research_trial" / _identity_digest("us_equity", "global_etf_rotation", "trial-a") / "ledger.json"
            planted = json.loads(path.read_text())
            planted["days"][0]["cash"] = 104.0
            path.write_text(json.dumps(planted), encoding="utf-8")
            self.assertIsNone(store.load_research_ledger("us_equity", "global_etf_rotation", "trial-a", "run-a", 1))

    def test_event_ledger_readback_rejects_tampered_cash_and_nav(self) -> None:
        event = ResearchLedgerEvent("ex-1", "dividend_accrual", "SOXL", per_share=5.0)
        day = _mark_day(
            _START, 0.0, 1.0, 95.0, 0.0, 0.0, 100.0, 100.0,
            dividend_receivable=5.0, declared_event_ids=("ex-1",), events=(event,),
        )
        ledger = ResearchDailyLedger(
            trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
            run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
            periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
            initial_session_date=_INITIAL, initial_nav=100.0, initial_cash=0.0,
            initial_positions=(ResearchPositionMark("SOXL", 1.0, 100.0),), days=(day,), synthetic=True,
        )
        for key, value in (("cash", 1.0), ("nav", 101.0)):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                store = PerformanceStore(local_root=root)
                store.save_research_ledger(ledger)
                path = root / "research_trial" / _identity_digest(
                    "us_equity", "global_etf_rotation", "trial-a"
                ) / "ledger.json"
                payload = json.loads(path.read_text())
                payload["days"][0][key] = value
                path.write_text(json.dumps(payload), encoding="utf-8")
                self.assertIsNone(store.load_research_ledger(
                    "us_equity", "global_etf_rotation", "trial-a", "run-a", 1
                ))

    def test_rejected_before_parse_keeps_null_actual_params_and_cost_inputs(self) -> None:
        for field in dataclasses.fields(ResearchTrialRecord):
            if field.name == "research_identity":
                self.assertIsNone(field.default)
                continue
            self.assertIs(field.default, dataclasses.MISSING)
            self.assertIs(field.default_factory, dataclasses.MISSING)
        with self.assertRaises(ValueError) as unknown:
            _trial(ResearchTrialStatus.REJECTED, actual_params="unknown")
        with self.assertRaises(ValueError) as blank:
            _trial(ResearchTrialStatus.REJECTED, actual_params="")
        self.assertEqual(str(unknown.exception), "actual_params")
        self.assertEqual(str(blank.exception), "actual_params")
        trial = _trial(ResearchTrialStatus.REJECTED, actual_params=None, cost_inputs=dict(_COSTS))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PerformanceStore(local_root=root)
            store.save_research_trial(trial)
            loaded = store.load_research_trial("us_equity", "global_etf_rotation", "trial-a")
            path = _research_file(root, "us_equity", "global_etf_rotation", "trial-a", "terminal")
            payload = json.loads(path.read_text())
            self.assertFalse(any(item.parts[len(root.parts)] == "backtest" for item in root.rglob("*") if item != root))
        self.assertEqual(loaded, trial)
        self.assertIsNone(loaded.actual_params)
        self.assertIsNone(loaded.run_id)
        self.assertIsNone(loaded.param_version)
        self.assertEqual(dict(loaded.cost_inputs), _COSTS)
        self.assertIsNone(payload["actual_params"])
        self.assertEqual(path.parent.name, _identity_digest("us_equity", "global_etf_rotation", "trial-a"))
        self.assertEqual(path.name, "terminal.json")
        for banned in ("sharpe_ratio", "total_return", "promotion_eligible"):
            self.assertNotIn(banned, payload)

    def test_legacy_trial_payload_without_research_identity_round_trips(self) -> None:
        legacy = {
            "schema_version": SCHEMA_VERSION,
            **_trial(ResearchTrialStatus.REJECTED, actual_params=None).to_dict(),
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = _research_file(root, "us_equity", "global_etf_rotation", "trial-a", "terminal")
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(legacy), encoding="utf-8")
            loaded = PerformanceStore(local_root=root).load_research_trial(
                "us_equity", "global_etf_rotation", "trial-a"
            )
        self.assertEqual(loaded, _trial(ResearchTrialStatus.REJECTED, actual_params=None))
        self.assertIsNone(loaded.research_identity)
        self.assertNotIn("research_identity", legacy)

    def test_research_identity_requires_a_nonempty_json_mapping(self) -> None:
        for identity in ([], {}, {"source": object()}, {"source": float("nan")}):
            with self.subTest(identity=identity):
                with self.assertRaises(ValueError) as malformed:
                    _trial(ResearchTrialStatus.REJECTED, actual_params=None, research_identity=identity)
                self.assertEqual(str(malformed.exception), "research_identity")

    def test_orphan_ledger_still_allows_failed_and_aborted_records(self) -> None:
        started = _trial(ResearchTrialStatus.STARTED, actual_params=None, cost_inputs={}, reason_code="")
        changed = _trial(ResearchTrialStatus.STARTED, actual_params=None, cost_inputs={}, reason_code="", input_id="input-b")
        failed = _trial(ResearchTrialStatus.FAILED, reason_code="result_rejected", cost_inputs=dict(_COSTS), actual_params=None)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PerformanceStore(local_root=root)
            store.save_research_trial(started)
            store.save_research_trial(started)
            started_path = _research_file(root, "us_equity", "global_etf_rotation", "trial-a", "started")
            started_bytes = started_path.read_text()
            with self.assertRaises(ValueError) as changed_error:
                store.save_research_trial(changed)
            self.assertEqual(str(changed_error.exception), "research_trial_conflict")
            self.assertEqual(started_path.read_text(), started_bytes)
            store.save_research_ledger(_ledger())
            store.save_research_trial(failed)
            loaded = store.load_research_trial("us_equity", "global_etf_rotation", "trial-a")
            ledger = store.load_research_ledger("us_equity", "global_etf_rotation", "trial-a", "run-a", 1)
            terminal = _research_file(root, "us_equity", "global_etf_rotation", "trial-a", "terminal")
            planted = json.loads(terminal.read_text())
            planted["sharpe_ratio"] = 1.2
            terminal.write_text(json.dumps(planted))
            planted_text = terminal.read_text()
            self.assertIsNone(store.load_research_trial("us_equity", "global_etf_rotation", "trial-a"))
            with self.assertRaises(ValueError) as malformed:
                store.save_research_trial(failed)
            self.assertEqual(str(malformed.exception), "research_trial_malformed")
            self.assertEqual(terminal.read_text(), planted_text)
            self.assertIn("sharpe_ratio", terminal.read_text())
            self.assertEqual(len(list(root.rglob("started.json"))), 1)
        self.assertEqual(loaded, failed)
        self.assertIsNone(loaded.run_id)
        self.assertEqual(dict(loaded.cost_inputs), _COSTS)
        self.assertEqual(ledger.run_id, "run-a")
        with self.assertRaises(ValueError) as linked:
            _trial(ResearchTrialStatus.FAILED, run_id="run-a", reason_code="result_rejected")
        self.assertEqual(str(linked.exception), "research_trial_result_link")
        aborted = _trial(ResearchTrialStatus.ABORTED, trial_id="trial-b", reason_code="operator_abort", cost_inputs=dict(_COSTS))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PerformanceStore(local_root=root)
            store.save_research_ledger(_ledger(trial_id="trial-b"))
            store.save_research_trial(aborted)
            loaded_aborted = store.load_research_trial("us_equity", "global_etf_rotation", "trial-b")
        self.assertEqual(loaded_aborted, aborted)
        self.assertIsNone(loaded_aborted.run_id)
        self.assertEqual(dict(loaded_aborted.cost_inputs), _COSTS)

    def test_same_params_keep_distinct_trials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PerformanceStore(local_root=root)
            saved = []
            for trial_id, run_id in (("trial-a", "run-a"), ("trial-b", "run-b")):
                ledger = _ledger(trial_id=trial_id, run_id=run_id)
                trial = _trial(ResearchTrialStatus.SUCCEEDED, trial_id=trial_id, run_id=run_id)
                store.save_backtest_result(_result(ledger))
                store.save_research_ledger(ledger)
                store.save_research_trial(trial)
                saved.append(trial)
                self.assertEqual(
                    store.load_research_trial("us_equity", "global_etf_rotation", trial_id, run_id=run_id, param_version=1),
                    trial,
                )
            self.assertIsNone(store.load_research_trial("us_equity", "global_etf_rotation", "trial-a", run_id="run-b"))
            self.assertIsNone(store.load_research_trial("us_equity", "global_etf_rotation", "trial-a", param_version=2))
            names = {path.relative_to(root).parts[0] for path in root.rglob("*.json")}
        self.assertEqual(names, {"research_trial", "backtest"})
        self.assertEqual(saved[0].actual_params, saved[1].actual_params)
        self.assertNotEqual(saved[0].trial_id, saved[1].trial_id)

    def test_nul_in_domain_or_profile_is_rejected(self) -> None:
        colliding = (("a\0b", "c"), ("a", "b\0c"))
        for domain, profile in colliding:
            with self.subTest(domain=domain, profile=profile):
                with self.assertRaises(ValueError) as caught:
                    _trial(ResearchTrialStatus.REJECTED, domain=domain, strategy_profile=profile)
                self.assertEqual(str(caught.exception), "identity")

    def test_original_identity_does_not_collapse_cleaned_keys(self) -> None:
        spaced = _trial(ResearchTrialStatus.REJECTED, domain="us equity", strategy_profile="global etf", actual_params=None)
        hyphen = _trial(ResearchTrialStatus.REJECTED, domain="us-equity", strategy_profile="global-etf", actual_params=None)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PerformanceStore(local_root=root)
            store.save_research_trial(spaced)
            store.save_research_trial(hyphen)
            self.assertEqual(store.load_research_trial("us equity", "global etf", "trial-a"), spaced)
            self.assertEqual(store.load_research_trial("us-equity", "global-etf", "trial-a"), hyphen)
            self.assertIsNone(store.load_research_trial("us equity", "global-etf", "trial-a"))
            self.assertIsNone(store.load_research_trial("us-equity", "global etf", "trial-a"))
            path = _research_file(root, "us equity", "global etf", "trial-a", "terminal")
            planted = json.loads(path.read_text())
            planted["trial_id"] = "trial-other"
            path.write_text(json.dumps(planted))
            self.assertIsNone(store.load_research_trial("us equity", "global etf", "trial-a"))
            with self.assertRaises(ValueError) as conflict:
                store.save_research_trial(spaced)
            self.assertEqual(str(conflict.exception), "research_trial_conflict")
            self.assertEqual(json.loads(path.read_text())["trial_id"], "trial-other")

    def test_illegal_ledger_is_rejected_and_planted_cash_is_not_rewritten(self) -> None:
        with self.assertRaises(ValueError) as bad_bool:
            _mark_day(_START, 59, True, 40, -40, 1, 99, 100)
        with self.assertRaises(ValueError) as bad_nan:
            _mark_day(_START, float("nan"), 2, 40, -40, 1, 99, 100)
        with self.assertRaises(ValueError) as bad_income:
            _mark_day(_START, 100, 0, 0, 0, 0, 100, 100, income_cashflow=float("inf"))
        with self.assertRaises(ValueError) as bad_fee:
            _mark_day(_START, 59, 2, 40, -40, -1, 99, 100)
        self.assertEqual(str(bad_bool.exception), "invalid_number")
        self.assertEqual(str(bad_nan.exception), "invalid_number")
        self.assertEqual(str(bad_income.exception), "invalid_number")
        self.assertEqual(str(bad_fee.exception), "ledger_fee")
        day = _mark_day(_START, 59, 2, 40, -40, 1, 99, 100)
        earlier = _mark_day(date(2024, 1, 1), 100, 0, 0, 0, 0, 100, 100)
        with self.assertRaises(ValueError) as bad_dates:
            ResearchDailyLedger(
                trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
                run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
                periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
                initial_session_date=_INITIAL, initial_nav=100.0, initial_cash=100.0,
                initial_positions=(), days=(day, earlier), synthetic=True,
            )
        self.assertEqual(str(bad_dates.exception), "ledger_dates")
        with self.assertRaises(ValueError) as same_session:
            ResearchDailyLedger(
                trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
                run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
                periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
                initial_session_date=_START, initial_nav=100.0, initial_cash=100.0,
                initial_positions=(), days=(day,), synthetic=True,
            )
        self.assertEqual(str(same_session.exception), "ledger_dates")
        short_cash = _mark_day(_START, 50, 2, 40, -40, 1, 90, 100)
        with self.assertRaises(ValueError) as bad_cash:
            ResearchDailyLedger(
                trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
                run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
                periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
                initial_session_date=_INITIAL, initial_nav=100.0, initial_cash=100.0,
                initial_positions=(), days=(short_cash,), synthetic=True,
            )
        self.assertEqual(str(bad_cash.exception), "ledger_cash")
        broken = _mark_day(_START, 59, 2, 40, -40, 1, 99, 100)
        object.__setattr__(broken, "daily_return", 0.0)
        with self.assertRaises(ValueError) as bad_return:
            ResearchDailyLedger(
                trial_id="trial-a", domain="us_equity", strategy_profile="global_etf_rotation",
                run_id="run-a", param_version=1, input_id="input-a", calendar_id="XNYS",
                periods_per_year=252.0, cost_source="synthetic_cost_v1", cost_inputs=dict(_COSTS),
                initial_session_date=_INITIAL, initial_nav=100.0, initial_cash=100.0,
                initial_positions=(), days=(broken,), synthetic=True,
            )
        self.assertEqual(str(bad_return.exception), "ledger_return")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PerformanceStore(local_root=root)
            store.save_research_ledger(_ledger())
            path = _research_file(root, "us_equity", "global_etf_rotation", "trial-a", "ledger")
            planted = json.loads(path.read_text())
            planted["days"][0]["cash"] = 1
            path.write_text(json.dumps(planted))
            planted_text = path.read_text()
            self.assertIsNone(store.load_research_ledger("us_equity", "global_etf_rotation", "trial-a", "run-a", 1))
            with self.assertRaises(ValueError) as malformed:
                store.save_research_ledger(_ledger())
            self.assertEqual(str(malformed.exception), "research_ledger_malformed")
            self.assertEqual(path.read_text(), planted_text)

    def test_terminal_resave_is_identical_only(self) -> None:
        trial = _trial(ResearchTrialStatus.REJECTED, actual_params=None, cost_inputs=dict(_COSTS))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PerformanceStore(local_root=root)
            store.save_research_trial(trial)
            store.save_research_trial(trial)
            path = _research_file(root, "us_equity", "global_etf_rotation", "trial-a", "terminal")
            original = path.read_text()
            other = _trial(ResearchTrialStatus.REJECTED, actual_params=None, cost_inputs=dict(_COSTS), reason_code="operator_abort")
            with self.assertRaises(ValueError) as conflict:
                store.save_research_trial(other)
            self.assertEqual(str(conflict.exception), "research_trial_conflict")
            self.assertEqual(path.read_text(), original)

    def test_success_is_written_last_and_binds_result_fields(self) -> None:
        ledger = _ledger()
        result = _result(ledger)
        started = _trial(ResearchTrialStatus.STARTED, actual_params=dict(_PARAMS), param_set_id="set-a", source_revision="rev-a", cost_inputs={})
        success = _trial(ResearchTrialStatus.SUCCEEDED)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PerformanceStore(local_root=root)
            store.save_research_trial(started)
            with self.assertRaises(ValueError) as missing_result:
                store.save_research_trial(success)
            self.assertEqual(str(missing_result.exception), "research_trial_result_missing")
            self.assertFalse(_research_file(root, "us_equity", "global_etf_rotation", "trial-a", "terminal").exists())
            store.save_backtest_result(result)
            with self.assertRaises(ValueError) as missing_ledger:
                store.save_research_trial(success)
            self.assertEqual(str(missing_ledger.exception), "research_trial_ledger_missing")
            self.assertFalse(_research_file(root, "us_equity", "global_etf_rotation", "trial-a", "ledger").exists())
            self.assertFalse(_research_file(root, "us_equity", "global_etf_rotation", "trial-a", "terminal").exists())
            store.save_research_ledger(ledger)
            store.save_research_trial(success)
            store.save_research_trial(success)
            loaded = store.load_research_trial("us_equity", "global_etf_rotation", "trial-a", run_id="run-a", param_version=1)
            ledger_path = _research_file(root, "us_equity", "global_etf_rotation", "trial-a", "ledger")
            ledger_bytes = ledger_path.read_text()
            with self.assertRaises(ValueError) as second_ledger:
                store.save_research_ledger(_ledger(run_id="run-b"))
            self.assertEqual(str(second_ledger.exception), "research_trial_conflict")
            self.assertEqual(ledger_path.read_text(), ledger_bytes)
            self.assertTrue(_run_file(root, "run-a").exists())
        self.assertEqual(loaded, success)
        self.assertEqual(dict(loaded.actual_params), dict(result.params))
        self.assertEqual(loaded.param_set_id, result.param_set_id)
        self.assertEqual(loaded.source_revision, result.source_revision)
        self.assertEqual(dict(loaded.cost_inputs), dict(result.cost_inputs))
        self.assertEqual(loaded.calendar_id, result.calendar_id)
        self.assertEqual(loaded.run_id, result.run_id)
        self.assertEqual((ledger.initial_nav, ledger.days[0].nav, ledger.days[1].nav), (100.0, 99.0, 109.0))
        self.assertEqual(ledger.initial_session_date, _INITIAL)
        self.assertEqual(ledger.window_start, _INITIAL)
        self.assertEqual(ledger.days[0].session_date, _START)
        self.assertEqual(ledger.observation_count, 2)
        self.assertEqual(result.start_date, _INITIAL)
        self.assertEqual(result.end_date, _END)
        self.assertEqual(result.observation_count, 2)
        self.assertEqual(loaded.window_start, result.start_date)
        self.assertEqual(ledger.observation_count, result.observation_count)
        self.assertEqual(ledger.total_return, result.total_return)

    def test_research_identity_round_trips_and_must_match_result_params(self) -> None:
        identity = {"producer": "research-runner", "source": {"revision": "rev-a", "input": "input-a"}}
        ledger = _ledger()
        started = _trial(
            ResearchTrialStatus.STARTED,
            actual_params=dict(_PARAMS),
            param_set_id="set-a",
            source_revision="rev-a",
            cost_inputs={},
            research_identity=identity,
        )
        success = _trial(ResearchTrialStatus.SUCCEEDED, research_identity=identity)
        result = _result(ledger, params={**_PARAMS, "research_identity": identity})
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_backtest_result(result)
            store.save_research_ledger(ledger)
            store.save_research_trial(started)
            store.save_research_trial(success)
            loaded = store.load_research_trial("us_equity", "global_etf_rotation", "trial-a")
        self.assertEqual(loaded, success)
        self.assertEqual(dict(loaded.research_identity), identity)

        for params in (_PARAMS, {**_PARAMS, "research_identity": {"producer": "other"}}):
            with self.subTest(params=params):
                with tempfile.TemporaryDirectory() as tmp:
                    store = PerformanceStore(local_root=Path(tmp))
                    store.save_backtest_result(_result(ledger, params=params))
                    store.save_research_ledger(ledger)
                    with self.assertRaises(ValueError) as mismatch:
                        store.save_research_trial(success)
                    self.assertEqual(str(mismatch.exception), "research_trial_result_mismatch")
                    self.assertFalse(
                        _research_file(Path(tmp), "us_equity", "global_etf_rotation", "trial-a", "terminal").exists()
                    )

    def test_started_trial_rejects_changed_research_identity(self) -> None:
        started = _trial(ResearchTrialStatus.STARTED, research_identity={"producer": "runner-a"})
        terminal = _trial(
            ResearchTrialStatus.FAILED,
            reason_code="result_rejected",
            research_identity={"producer": "runner-b"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PerformanceStore(local_root=root)
            store.save_research_trial(started)
            with self.assertRaises(ValueError) as conflict:
                store.save_research_trial(terminal)
            self.assertEqual(str(conflict.exception), "research_trial_conflict")
            self.assertFalse(
                _research_file(root, "us_equity", "global_etf_rotation", "trial-a", "terminal").exists()
            )

    def test_research_identity_comparison_preserves_json_value_types(self) -> None:
        started = _trial(ResearchTrialStatus.STARTED, research_identity={"schema": {"version": True}})
        terminal = _trial(
            ResearchTrialStatus.FAILED,
            reason_code="result_rejected",
            research_identity={"schema": {"version": 1}},
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_research_trial(started)
            with self.assertRaises(ValueError) as conflict:
                store.save_research_trial(terminal)
            self.assertEqual(str(conflict.exception), "research_trial_conflict")

        ledger = _ledger()
        success = _trial(
            ResearchTrialStatus.SUCCEEDED,
            research_identity={"schema": {"version": 1}},
        )
        result = _result(
            ledger,
            params={**_PARAMS, "research_identity": {"schema": {"version": True}}},
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_backtest_result(result)
            store.save_research_ledger(ledger)
            with self.assertRaises(ValueError) as mismatch:
                store.save_research_trial(success)
            self.assertEqual(str(mismatch.exception), "research_trial_result_mismatch")

    def test_actual_params_comparison_preserves_json_value_types(self) -> None:
        started = _trial(ResearchTrialStatus.STARTED, actual_params={"flag": True})
        terminal = _trial(
            ResearchTrialStatus.FAILED,
            reason_code="result_rejected",
            actual_params={"flag": 1},
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_research_trial(started)
            with self.assertRaises(ValueError) as conflict:
                store.save_research_trial(terminal)
            self.assertEqual(str(conflict.exception), "research_trial_conflict")

        ledger = _ledger()
        success = _trial(ResearchTrialStatus.SUCCEEDED, actual_params={"flag": 1})
        result = _result(ledger, params={"flag": True})
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_backtest_result(result)
            store.save_research_ledger(ledger)
            with self.assertRaises(ValueError) as mismatch:
                store.save_research_trial(success)
            self.assertEqual(str(mismatch.exception), "research_trial_result_mismatch")

    def test_param_or_source_mismatch_does_not_create_terminal(self) -> None:
        ledger = _ledger()
        cases = {
            "params": {"params": {"lookback": 21}},
            "source_revision": {"source_revision": "rev-other"},
            "param_set_id": {"param_set_id": "set-other"},
            "calendar": {"calendar_id": "XNAS"},
            "cost_inputs": {"cost_inputs": {"commission_bps": 9.0}},
            "cost_model": {"cost_model": "other_cost"},
            "observation_count": {"observation_count": 9},
            "total_return": {"total_return": 0.5},
            "window": {"start_date": _START},
        }
        for name, overrides in cases.items():
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    store = PerformanceStore(local_root=root)
                    store.save_backtest_result(_result(ledger, **overrides))
                    store.save_research_ledger(ledger)
                    with self.assertRaises(ValueError) as mismatch:
                        store.save_research_trial(_trial(ResearchTrialStatus.SUCCEEDED))
                    self.assertEqual(str(mismatch.exception), "research_trial_result_mismatch")
                    self.assertFalse(_research_file(root, "us_equity", "global_etf_rotation", "trial-a", "terminal").exists())

    def test_terminal_keeps_known_started_identity(self) -> None:
        started = _trial(
            ResearchTrialStatus.STARTED,
            actual_params={"lookback": 20},
            param_set_id=None,
            source_revision=None,
            cost_source="synthetic_cost_v1",
            cost_inputs=dict(_COSTS),
        )
        replacements = {
            "candidate": {"candidate_config_id": "candidate-b"},
            "input": {"input_id": "input-b"},
            "window": {"window_end": date(2024, 1, 4)},
            "calendar": {"calendar_id": "XNAS"},
            "periods": {"periods_per_year": 365.25},
            "synthetic": {"synthetic": False},
            "actual_params": {"actual_params": {"lookback": 21}},
            "research_identity": {"research_identity": {"producer": "other"}},
            "cost_inputs": {"cost_inputs": {"commission_bps": 9.0}},
            "cost_source": {"cost_source": "other_cost"},
        }
        filled = _trial(
            ResearchTrialStatus.FAILED,
            reason_code="result_rejected",
            actual_params={"lookback": 20},
            param_set_id="set-a",
            source_revision="rev-a",
            cost_inputs=dict(_COSTS),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PerformanceStore(local_root=root)
            store.save_research_trial(started)
            started_path = _research_file(root, "us_equity", "global_etf_rotation", "trial-a", "started")
            started_bytes = started_path.read_text()
            for name, overrides in replacements.items():
                with self.subTest(name=name):
                    payload = {
                        "reason_code": "result_rejected",
                        "actual_params": {"lookback": 20},
                        "cost_inputs": dict(_COSTS),
                    }
                    payload.update(overrides)
                    with self.assertRaises(ValueError) as conflict:
                        store.save_research_trial(_trial(ResearchTrialStatus.FAILED, **payload))
                    self.assertEqual(str(conflict.exception), "research_trial_conflict")
                    self.assertFalse(_research_file(root, "us_equity", "global_etf_rotation", "trial-a", "terminal").exists())
            store.save_research_trial(filled)
            store.save_research_trial(filled)
            store.save_research_trial(started)
            self.assertEqual(store.load_research_trial("us_equity", "global_etf_rotation", "trial-a"), filled)
            self.assertEqual(started_path.read_text(), started_bytes)
            with self.assertRaises(ValueError) as rewritten:
                store.save_research_trial(_trial(
                    ResearchTrialStatus.STARTED,
                    candidate_config_id="candidate-b",
                    actual_params={"lookback": 20},
                    cost_inputs=dict(_COSTS),
                ))
            self.assertEqual(str(rewritten.exception), "research_trial_conflict")
            self.assertEqual(started_path.read_text(), started_bytes)
            self.assertEqual(store.load_research_trial("us_equity", "global_etf_rotation", "trial-a"), filled)
            planted = json.loads(_research_file(root, "us_equity", "global_etf_rotation", "trial-a", "terminal").read_text())
            planted["candidate_config_id"] = "candidate-b"
            terminal_path = _research_file(root, "us_equity", "global_etf_rotation", "trial-a", "terminal")
            terminal_path.write_text(json.dumps(planted))
            self.assertIsNone(store.load_research_trial("us_equity", "global_etf_rotation", "trial-a"))
            self.assertEqual(json.loads(terminal_path.read_text())["candidate_config_id"], "candidate-b")
        open_started = _trial(
            ResearchTrialStatus.STARTED,
            trial_id="trial-b",
            actual_params=None,
            param_set_id=None,
            source_revision=None,
            cost_source=None,
            cost_inputs={},
        )
        completed = _trial(
            ResearchTrialStatus.FAILED,
            trial_id="trial-b",
            reason_code="result_rejected",
            actual_params={"lookback": 20},
            param_set_id="set-a",
            source_revision="rev-a",
            cost_source="synthetic_cost_v1",
            cost_inputs=dict(_COSTS),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PerformanceStore(local_root=root)
            store.save_research_trial(completed)
            with self.assertRaises(ValueError) as late_started:
                store.save_research_trial(_trial(
                    ResearchTrialStatus.STARTED,
                    trial_id="trial-b",
                    candidate_config_id="candidate-b",
                    cost_inputs=dict(_COSTS),
                ))
            self.assertEqual(str(late_started.exception), "research_trial_conflict")
            self.assertFalse(_research_file(root, "us_equity", "global_etf_rotation", "trial-b", "started").exists())
            self.assertEqual(store.load_research_trial("us_equity", "global_etf_rotation", "trial-b"), completed)
            store.save_research_trial(open_started)
            store.save_research_trial(open_started)
            self.assertEqual(store.load_research_trial("us_equity", "global_etf_rotation", "trial-b"), completed)

    def test_cloud_faults_fail_closed_without_local_fallback(self) -> None:
        trial = _trial(ResearchTrialStatus.REJECTED, actual_params=None, cost_inputs=dict(_COSTS))
        digest = _identity_digest("us_equity", "global_etf_rotation", "trial-a")
        uri = f"gs://lifecycle-bucket/production/research_trial/{digest}/terminal.json"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local_path = _research_file(root, "us_equity", "global_etf_rotation", "trial-a", "terminal")
            local_path.parent.mkdir(parents=True)
            local_path.write_text('{"trial_id":"local-only"}')
            cloud = _ResearchCloud()
            store = PerformanceStore(cloud_bucket="lifecycle-bucket", cloud_prefix="production", local_root=root)
            with patch("quant_platform_kit.strategy_lifecycle.performance_store.get_object_store", return_value=cloud):
                cloud.fail_exists = True
                with self.assertRaises(ValueError) as exists_error:
                    store.save_research_trial(trial)
                self.assertEqual(str(exists_error.exception), "research_store_unavailable")
                self.assertEqual(cloud.create_calls, 0)
                with self.assertRaises(ValueError) as load_error:
                    store.load_research_trial("us_equity", "global_etf_rotation", "trial-a")
                self.assertEqual(str(load_error.exception), "research_store_unavailable")
                cloud.fail_exists = False
                cloud.objects[uri] = "{}"
                cloud.fail_read = True
                with self.assertRaises(ValueError) as read_error:
                    store.save_research_trial(trial)
                self.assertEqual(str(read_error.exception), "research_store_unavailable")
                self.assertEqual(cloud.create_calls, 0)
                self.assertEqual(cloud.objects[uri], "{}")
                cloud.fail_read = False
                cloud.objects.clear()
                self.assertIsNone(store.load_research_trial("us_equity", "global_etf_rotation", "trial-a"))
                cloud.fail_create = True
                with self.assertRaises(ValueError) as create_error:
                    store.save_research_trial(trial)
                self.assertEqual(str(create_error.exception), "research_store_unavailable")
                self.assertEqual(cloud.objects, {})
                cloud.fail_create = False
                store.save_research_trial(trial)
                self.assertEqual(local_path.read_text(), '{"trial_id":"local-only"}')
                local_path.write_text('{"reason_code":"local-copy"}')
                loaded = store.load_research_trial("us_equity", "global_etf_rotation", "trial-a")
                self.assertEqual(json.loads(cloud.objects[uri])["reason_code"], "config_unparsed")
            self.assertEqual(loaded, trial)
            self.assertEqual(local_path.read_text(), '{"reason_code":"local-copy"}')

    def test_cloud_success_uses_only_the_bucket(self) -> None:
        ledger = _ledger()
        trial = _trial(ResearchTrialStatus.SUCCEEDED)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cloud = _ResearchCloud()
            store = PerformanceStore(cloud_bucket="lifecycle-bucket", cloud_prefix="production", local_root=root)
            with patch("quant_platform_kit.strategy_lifecycle.performance_store.get_object_store", return_value=cloud):
                store.save_backtest_result(_result(ledger))
                store.save_research_ledger(ledger)
                store.save_research_trial(trial)
                loaded = store.load_research_trial("us_equity", "global_etf_rotation", "trial-a", run_id="run-a", param_version=1)
                loaded_ledger = store.load_research_ledger("us_equity", "global_etf_rotation", "trial-a", "run-a", 1)
            uris = list(cloud.objects)
            research = [uri for uri in uris if "/research_trial/" in uri]
            self.assertEqual(loaded, trial)
            self.assertEqual(loaded_ledger.total_fees, 1.0)
            self.assertTrue(research)
            self.assertTrue(any("/backtest/" in uri for uri in uris))
            self.assertTrue(all(uri.startswith("gs://lifecycle-bucket/production/") for uri in uris))
            self.assertTrue(all("/research_trial/" in uri or "/backtest/" in uri for uri in uris))
            self.assertFalse(any("research_trial" in path.parts for path in root.rglob("*")))


if __name__ == "__main__":
    unittest.main()
