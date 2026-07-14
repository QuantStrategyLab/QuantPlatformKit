from __future__ import annotations

import copy
import unittest
from dataclasses import replace

from quant_platform_kit.strategy_lifecycle.capabilities import ExecutionTiming, PersistMode
from quant_platform_kit.strategy_lifecycle.vnext_result_store_contract import (
    VNEXT_NAMESPACE,
    VNextContractError,
    VNextResultContract,
    decode_vnext_wire,
)


def _contract(**overrides):
    values = {
        "domain": "us_equity",
        "canonical_profile": "SOXL",
        "execution_timing": ExecutionTiming.NEXT_OPEN,
        "result_identity_version": 1,
        "persist_mode": PersistMode.DURABLE,
        "strategy_id": "soxl_trend",
        "run_id": "run-001",
        "param_set_id": "baseline",
        "param_version": 1,
        "computed_at": "2026-07-15T00:00:00Z",
        "source_revision": "abc123",
        "params": {"lookback": 20, "threshold": 0.5},
    }
    values.update(overrides)
    return VNextResultContract(**values)


class VNextResultStoreContractTests(unittest.TestCase):
    def test_round_trip_and_namespace_isolation(self) -> None:
        contract = _contract()
        wire = contract.to_wire()
        self.assertEqual(wire["namespace"], VNEXT_NAMESPACE)
        self.assertEqual(decode_vnext_wire(wire), contract)
        self.assertTrue(contract.key.startswith("qpk-vnext/result/v1/"))

    def test_order_independence_and_identity_changes(self) -> None:
        first = _contract(params={"b": 2, "a": 1})
        second = _contract(params={"a": 1, "b": 2})
        self.assertEqual(first.to_wire(), second.to_wire())
        self.assertEqual(first.key, second.key)
        self.assertNotEqual(first.key, replace(first, run_id="run-002").key)

    def test_required_none_legacy_any_alias_and_unknown_values_reject(self) -> None:
        for field in ("execution_timing", "canonical_profile", "strategy_id", "run_id", "source_revision"):
            with self.assertRaises(VNextContractError):
                _contract(**{field: None})
        with self.assertRaises(VNextContractError):
            _contract(execution_timing=None)
        with self.assertRaises(VNextContractError):
            _contract(canonical_profile="soxl_soxx_trend_income")
        with self.assertRaises(VNextContractError):
            _contract(execution_timing="ANY")

    def test_persist_modes_are_explicit_without_io(self) -> None:
        self.assertEqual(_contract(persist_mode=PersistMode.EPHEMERAL).to_wire()["persist_mode"], "ephemeral")
        self.assertEqual(_contract(persist_mode=PersistMode.DURABLE).to_wire()["persist_mode"], "durable")

    def test_adversarial_wire_values_reject(self) -> None:
        wire = _contract().to_wire()
        for mutation in (
            {"namespace": "strategy_lifecycle"},
            {"execution_timing": None},
            {"canonical_profile": "SOXL_SOXX_TREND_INCOME"},
            {"result_identity_version": True},
            {"params": {"bad": []}},
            {"unknown": "field"},
        ):
            candidate = copy.deepcopy(wire)
            candidate.update(mutation)
            with self.assertRaises(VNextContractError):
                decode_vnext_wire(candidate)
        missing = copy.deepcopy(wire)
        del missing["run_id"]
        with self.assertRaises(VNextContractError):
            decode_vnext_wire(missing)

    def test_unsafe_and_overlong_identity_segments_reject(self) -> None:
        for field in ("domain", "strategy_id", "run_id", "param_set_id", "source_revision"):
            with self.assertRaises(VNextContractError):
                _contract(**{field: "../unsafe"})
            with self.assertRaises(VNextContractError):
                _contract(**{field: "x" * 101})
        with self.assertRaises(VNextContractError):
            _contract(param_version=True)


if __name__ == "__main__":
    unittest.main()
