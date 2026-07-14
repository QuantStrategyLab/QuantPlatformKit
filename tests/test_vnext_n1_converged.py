from __future__ import annotations

import copy
import unittest
from dataclasses import replace

from quant_platform_kit.strategy_lifecycle.vnext_n1_contract import (
    MAX_SAFE_JSON_INTEGER,
    VNextContractError,
    VNextResult,
    decode_wire,
)


def result(**overrides):
    values = dict(
        domain="us_equity", canonical_profile="SOXL", execution_timing="next_open",
        result_identity_version=1, persist_mode="durable", strategy_id="soxl_trend",
        run_id="run-1", param_set_id="baseline", param_version=1,
        source_revision="rev1", computed_at="2026-07-15T00:00:00.000000Z",
        params={"x": 1, "nested": (True, ("a", 2))},
    )
    values.update(overrides)
    return VNextResult(**values)


class ConvergedN1Tests(unittest.TestCase):
    def test_profiles_timing_and_round_trip(self):
        for profile in ("SOXL", "TQQQ", "UPRO"):
            item = result(canonical_profile=profile)
            self.assertEqual(decode_wire(item.to_wire()), item)

    def test_identity_subset_and_metadata(self):
        base = result()
        changed = replace(base, persist_mode="ephemeral", computed_at="2026-07-16T00:00:00.000000Z")
        self.assertEqual(base.key, changed.key)
        self.assertEqual(base.to_wire()["identity_digest"], changed.to_wire()["identity_digest"])
        self.assertNotEqual(base.to_wire()["wire_digest"], changed.to_wire()["wire_digest"])
        for field, value in (("run_id", "run-2"), ("source_revision", "rev2"), ("execution_timing", "next_close"), ("param_version", 2)):
            self.assertNotEqual(base.key, replace(base, **{field: value}).key)

    def test_safe_integer_all_positions_and_bool(self):
        self.assertEqual(result(params={"n": MAX_SAFE_JSON_INTEGER}).params["n"], MAX_SAFE_JSON_INTEGER)
        self.assertTrue(result(params={"flag": True}).params["flag"])
        for field in ("result_identity_version", "param_version"):
            with self.assertRaises(VNextContractError):
                result(**{field: MAX_SAFE_JSON_INTEGER + 1})
        with self.assertRaises(VNextContractError):
            result(params={"n": MAX_SAFE_JSON_INTEGER + 1})

    def test_deep_immutable_and_wire_lists(self):
        item = result()
        with self.assertRaises(AttributeError):
            item.params["nested"].append(3)
        with self.assertRaises(VNextContractError):
            result(params={"x": [1]})
        wire = item.to_wire()
        self.assertEqual(decode_wire(wire), item)

    def test_timestamp_and_profile_strictness(self):
        for timestamp in ("2026-07-15T00:00:00Z", "2026-07-15T00:00:00.1Z", "2026-07-15T00:00:00.000000+00:00", "2026-02-30T00:00:00.000000Z", " 2026-07-15T00:00:00.000000Z"):
            with self.assertRaises(VNextContractError):
                result(computed_at=timestamp)
        for profile in ("soxl", "A/B", "..", "X" * 101, ""):
            with self.assertRaises(VNextContractError):
                result(canonical_profile=profile)

    def test_wire_shape_namespace_and_adversarial_values(self):
        wire = result().to_wire()
        for mutation in ({"unknown": 1}, {"namespace": "legacy"}, {"computed_at": None}, {"params": {"x": [MAX_SAFE_JSON_INTEGER + 1]}}):
            candidate = copy.deepcopy(wire)
            candidate.update(mutation)
            with self.assertRaises(VNextContractError):
                decode_wire(candidate)
        self.assertTrue(result().key.startswith("qpk-vnext/result/v2/"))


if __name__ == "__main__":
    unittest.main()
