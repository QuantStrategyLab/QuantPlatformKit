import copy
import unittest
from quant_platform_kit.common.pending_order_evidence import validate_pending_order_evidence


class EvidenceTest(unittest.TestCase):
    def setUp(self):
        self.observation = {"account_domain_key": "d", "account_binding": "a", "currency": "USD", "source_digest": "s", "valuation_at": "2026-10-30T03:00:00Z", "pending_3x_exposure": 3000}
        self.attempts = {"a" * 64: {"certainty": "KNOWN_PENDING", "observation": {"broker_order_id": "one"}, "observation_recorded_at": "2026-10-30T02:00:00Z", "observation_event_sha256": "b" * 64, "order_sha256": "c", "quantity": 2, "filled_quantity": 1}}
        self.reservations = {"c": {"reconciled_filled": 1}}
        self.evidence = {**{k: self.observation[k] for k in ("account_domain_key", "account_binding", "currency", "source_digest", "valuation_at")}, "schema_version": "pending_order_evidence.v1", "source_version": "synthetic", "observed_through": "2026-10-30T02:30:00Z", "orders": [{"attempt_id": "a" * 64, "broker_order_id": "one", "journal_observation_sha256": "b" * 64, "remaining_quantity": 1, "remaining_fee": 0, "pending_3x_exposure": 3000}]}

    def check(self, evidence):
        validate_pending_order_evidence(evidence, observation=self.observation, attempts=self.attempts, reservations=self.reservations)

    def test_valid(self):
        self.check(self.evidence)

    def test_identity_quantity_and_coverage(self):
        for field, value in [("broker_order_id", "other"), ("remaining_quantity", 2), ("journal_observation_sha256", "0" * 64), ("pending_3x_exposure", 3001)]:
            evidence = copy.deepcopy(self.evidence)
            evidence["orders"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check(evidence)
        for field, value in [("observed_through", "2026-10-30T01:00:00Z"), ("account_binding", "wrong"), ("source_digest", "wrong")]:
            evidence = copy.deepcopy(self.evidence)
            evidence[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check(evidence)
        evidence = copy.deepcopy(self.evidence)
        evidence["orders"].append(evidence["orders"][0])
        with self.assertRaises(ValueError):
            self.check(evidence)
        self.attempts["a" * 64]["certainty"] = "UNKNOWN"
        with self.assertRaises(ValueError):
            self.check(self.evidence)

    def test_invalid_numeric_amounts(self):
        for value in (True, -1, float("nan"), float("inf"), 10 ** 400):
            evidence = copy.deepcopy(self.evidence)
            evidence["orders"][0]["remaining_fee"] = value
            with self.subTest(value=str(value)[:20]), self.assertRaises(ValueError):
                self.check(evidence)
