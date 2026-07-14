from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from quant_platform_kit.strategy_lifecycle.legacy_profile_index import (
    IndexValidationError,
    build_index_from_keys,
    build_index_from_local_fixture,
    index_from_dict,
)


class LegacyProfileIndexTests(unittest.TestCase):
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
        for prefix in ("", ".", "..", "a/b", "a\\b", "/absolute", "a" * 101, "a!b"):
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


if __name__ == "__main__":
    unittest.main()
