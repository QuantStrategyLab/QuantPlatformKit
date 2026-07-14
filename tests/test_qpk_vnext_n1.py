from __future__ import annotations

import copy
import unittest
from dataclasses import replace

from quant_platform_kit.strategy_lifecycle.qpk_vnext_n1 import (
    MAX_SAFE_JSON_INTEGER, ContractError, ResultContract, decode_wire,
)


def result(**overrides):
    values = dict(domain="us_equity", profile="SOXL", timing="next_open", identity_version=1,
                  persist_mode="durable", strategy_id="strategy", run_id="run-1",
                  param_set_id="baseline", param_version=1, source_revision="rev1",
                  computed_at="2026-07-15T00:00:00.000000Z", params={"x": 1, "seq": (True, ("a", 2))})
    values.update(overrides)
    return ResultContract(**values)


class QpkVNextN1Tests(unittest.TestCase):
    def test_profiles_roundtrip_and_identity_metadata_invariance(self):
        for profile in ("SOXL", "TQQQ", "UPRO"):
            item = result(profile=profile)
            self.assertEqual(decode_wire(item.to_wire()), item)
        changed = replace(result(), persist_mode="ephemeral", computed_at="2026-07-16T00:00:00.000000Z")
        self.assertEqual(result().key, changed.key)
        self.assertNotEqual(result().to_wire()["wire_digest"], changed.to_wire()["wire_digest"])

    def test_identity_changes_and_permutation(self):
        first = result(params={"b": 2, "a": 1})
        second = result(params={"a": 1, "b": 2})
        self.assertEqual(first.to_wire(), second.to_wire())
        for field, value in (("run_id", "run-2"), ("timing", "next_close"), ("source_revision", "rev2"), ("param_version", 2)):
            self.assertNotEqual(first.key, replace(first, **{field: value}).key)

    def test_safe_ints_bool_and_decimal_policy(self):
        self.assertEqual(result(params={"n": MAX_SAFE_JSON_INTEGER, "flag": True}).params["n"], MAX_SAFE_JSON_INTEGER)
        for value in (MAX_SAFE_JSON_INTEGER + 1, -(MAX_SAFE_JSON_INTEGER + 1)):
            with self.assertRaises(ContractError):
                result(params={"n": value})
        self.assertEqual(decode_wire(result(params={"decimal": "1.2500", "scaled": 12500}).to_wire()).params["scaled"], 12500)

    def test_sequence_freeze_and_nested_mapping_rejection(self):
        item = result()
        self.assertEqual(decode_wire(item.to_wire()), item)
        with self.assertRaises(AttributeError):
            item.params["seq"].append(1)
        with self.assertRaises(ContractError):
            result(params={"nested": {"x": 1}})
        wire = item.to_wire()
        wire["params"] = {"nested": {"x": 1}}
        with self.assertRaises(ContractError):
            decode_wire(wire)

    def test_strict_profile_timestamp_wire_and_values(self):
        for profile in ("soxl", "A/B", "..", "X" * 101, ""):
            with self.assertRaises(ContractError):
                result(profile=profile)
        for timestamp in ("2026-07-15T00:00:00Z", "2026-07-15T00:00:00.1Z", "2026-07-15T00:00:00.000000+00:00", "2026-02-30T00:00:00.000000Z"):
            with self.assertRaises(ContractError):
                result(computed_at=timestamp)
        for value in (1.0, -0.0, float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ContractError):
                result(params={"v": value})

    def test_unicode_safety_and_exact_wire_shape(self):
        for kwargs in ({"strategy_id": "bad\ud800"}, {"params": {"bad\ud800": 1}}, {"params": {"v": "bad\ud800"}}):
            with self.assertRaises(ContractError):
                result(**kwargs)
        wire = result().to_wire()
        for mutation in ({"unknown": 1}, {"namespace": "legacy"}, {"computed_at": None}, {"timing": None}):
            candidate = copy.deepcopy(wire)
            candidate.update(mutation)
            with self.assertRaises(ContractError):
                decode_wire(candidate)

    def test_key_bearing_ids_are_safe_segments(self):
        for value in ("Mixed_ID-1", "A.1"):
            item = result(strategy_id=value, run_id=value)
            self.assertEqual(decode_wire(item.to_wire()), item)
            self.assertEqual(len(item.key.split("/")), 11)
        for field in ("strategy_id", "run_id"):
            for value in ("", "/bad", "..", ".", "bad/control\n", "-bad", "X" * 101):
                with self.assertRaises(ContractError):
                    result(**{field: value})
                wire = result().to_wire()
                wire[field] = value
                with self.assertRaises(ContractError):
                    decode_wire(wire)


if __name__ == "__main__":
    unittest.main()
