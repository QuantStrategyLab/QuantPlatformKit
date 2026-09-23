"""Tests for strategy_lifecycle.performance_store defaults."""

from __future__ import annotations

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
)
from quant_platform_kit.strategy_lifecycle.performance_store import (
    DEFAULT_LOCAL_ROOT,
    PerformanceStore,
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


if __name__ == "__main__":
    unittest.main()
