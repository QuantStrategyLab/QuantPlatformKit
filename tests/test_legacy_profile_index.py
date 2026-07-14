from __future__ import annotations

import tempfile
import unittest
import copy
import hashlib
import json
from pathlib import Path

from quant_platform_kit.strategy_lifecycle.legacy_profile_index import (
    IndexValidationError,
    build_index_from_keys,
    build_index_from_local_fixture,
    index_from_dict,
)


class LegacyProfileIndexTests(unittest.TestCase):
    @staticmethod
    def _redigest(index: dict) -> dict:
        result = copy.deepcopy(index)
        result["inventory"].pop("digest", None)
        result["inventory"]["digest"] = hashlib.sha256(
            json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return result

    def test_deterministic_index_and_digest_are_input_order_independent(self) -> None:
        keys = [
            "backtest/us_equity/soxl_soxx_trend_income/a.json",
            "backtest/us_equity/SOXL/b.json",
            "backtest/us_equity/soxl_soxx_trend_income/a.json",
        ]
        first = build_index_from_keys(keys, backend="local_fixture", complete=True, source_label="fixture")
        second = build_index_from_keys(reversed(keys), backend="local_fixture", complete=True, source_label="fixture")
        self.assertEqual(first, second)
        self.assertEqual(index_from_dict(first), first)
        self.assertEqual(first["entries"]["us_equity"]["SOXL"]["prefixes"], ["SOXL", "soxl_soxx_trend_income"])

    def test_remote_pagination_and_collision_metadata(self) -> None:
        result = build_index_from_keys(
            [
                "backtest/us_equity/SOXL/a.json",
                "backtest/us_equity/soxl_soxx_trend_income/b.json",
            ],
            backend="object_store_fixture",
            complete=False,
            source_label="exported-page-1",
        )
        self.assertFalse(result["inventory"]["complete"])
        self.assertEqual(result["collisions"][0]["canonical_profile"], "SOXL")
        self.assertEqual(len(result["collisions"][0]["prefixes"]), 2)

    def test_malformed_schema_and_unsafe_prefixes_fail_closed(self) -> None:
        with self.assertRaises(IndexValidationError):
            index_from_dict({"schema_version": "wrong"})
        for prefix in ("", ".", "..", "a\\b", "/absolute", "a" * 101, "a!b"):
            with self.assertRaises(IndexValidationError):
                build_index_from_keys([f"backtest/us_equity/{prefix}/a.json"], backend="fixture", complete=True, source_label="x")

    def test_local_fixture_requires_explicit_root_and_does_not_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "synthetic"
            (root / "backtest" / "us_equity" / "TQQQ").mkdir(parents=True)
            (root / "backtest" / "us_equity" / "TQQQ" / "record.json").write_text("{}")
            result = build_index_from_local_fixture(root, source_label="synthetic")
        self.assertEqual(result["entries"]["us_equity"]["TQQQ"]["prefixes"], ["TQQQ"])

    def test_diagnostics_do_not_echo_raw_payload(self) -> None:
        with self.assertRaises(IndexValidationError) as ctx:
            index_from_dict({"schema_version": "bad-secret-value"})
        self.assertEqual(str(ctx.exception), "invalid legacy profile index")

    def test_forged_collision_report_is_rejected_even_with_recomputed_digest(self) -> None:
        valid = build_index_from_keys(
            ["backtest/us_equity/SOXL/a.json", "backtest/us_equity/soxl_soxx_trend_income/b.json"],
            backend="fixture", complete=True, source_label="x",
        )
        for forged in ([], [{"domain": "us_equity", "canonical_profile": "SOXL", "prefixes": ["SOXL"]}]):
            candidate = copy.deepcopy(valid)
            candidate["collisions"] = forged
            with self.assertRaises(IndexValidationError):
                index_from_dict(self._redigest(candidate))

    def test_backend_union_and_declared_backend_are_consistent(self) -> None:
        valid = build_index_from_keys(["backtest/us_equity/SOXL/a.json"], backend="local", complete=True, source_label="x")
        missing = copy.deepcopy(valid)
        missing["entries"]["us_equity"]["SOXL"]["backend_prefixes"] = {}
        with self.assertRaises(IndexValidationError):
            index_from_dict(self._redigest(missing))
        mismatch = copy.deepcopy(valid)
        mismatch["entries"]["us_equity"]["SOXL"]["prefixes"] = []
        with self.assertRaises(IndexValidationError):
            index_from_dict(self._redigest(mismatch))

    def test_duplicate_or_unsorted_union_rejected_and_multiple_backends_valid(self) -> None:
        valid = build_index_from_keys(["backtest/us_equity/SOXL/a.json"], backend="local", complete=True, source_label="x")
        duplicate = copy.deepcopy(valid)
        entry = duplicate["entries"]["us_equity"]["SOXL"]
        entry["prefixes"] = ["SOXL", "SOXL"]
        with self.assertRaises(IndexValidationError):
            index_from_dict(self._redigest(duplicate))
        multi = copy.deepcopy(valid)
        multi["inventory"]["backends"] = ["local", "remote"]
        entry = multi["entries"]["us_equity"]["SOXL"]
        entry["backend_prefixes"]["remote"] = ["SOXL"]
        self.assertEqual(index_from_dict(self._redigest(multi)), self._redigest(multi))

    def test_nested_artifacts_are_supported_but_short_or_unsafe_keys_rejected(self) -> None:
        result = build_index_from_keys(
            ["backtest/us_equity/SOXL/nested/artifact.json"],
            backend="fixture", complete=True, source_label="x",
        )
        self.assertEqual(result["entries"]["us_equity"]["SOXL"]["prefixes"], ["SOXL"])
        for key in (
            "backtest/us_equity/SOXL",
            "backtest/us_equity/SOXL/",
            "backtest/us_equity/SOXL/../artifact.json",
            "backtest/us_equity/SOXL//artifact.json",
            "backtest/us_equity/SOXL/a/../../artifact.json",
        ):
            with self.assertRaises(IndexValidationError):
                build_index_from_keys([key], backend="fixture", complete=True, source_label="x")

    def test_input_collection_and_completion_flag_are_strict(self) -> None:
        for keys in ("backtest/us_equity/SOXL/a.json", b"backtest/us_equity/SOXL/a.json"):
            with self.assertRaises(IndexValidationError):
                build_index_from_keys(keys, backend="fixture", complete=True, source_label="x")
        with self.assertRaises(IndexValidationError):
            build_index_from_keys([], backend="fixture", complete=1, source_label="x")

    def test_cross_profile_mapping_with_recomputed_digest_is_rejected(self) -> None:
        candidate = build_index_from_keys(["backtest/us_equity/SOXL/a.json"], backend="fixture", complete=True, source_label="x")
        entry = candidate["entries"]["us_equity"]["SOXL"]
        entry["prefixes"] = ["TQQQ"]
        entry["backend_prefixes"]["fixture"] = ["TQQQ"]
        with self.assertRaises(IndexValidationError):
            index_from_dict(self._redigest(candidate))


if __name__ == "__main__":
    unittest.main()
