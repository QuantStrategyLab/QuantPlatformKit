from __future__ import annotations

import unittest

from quant_platform_kit.common.strategy_release import (
    StrategyReleaseManifest,
    build_runtime_loaded_receipt,
    validate_runtime_loaded_receipt,
    validate_strategy_release_binding,
)


def _release_identity(*, release_id: str = "soxl-p2-v3.20260824") -> dict[str, str]:
    return {
        "release_id": release_id,
        "manifest_sha256": "a" * 64,
        "strategy_revision": "soxl-p2-v3",
        "config_sha256": "b" * 64,
        "risk_policy_sha256": "c" * 64,
        "evidence_sha256": "d" * 64,
        "plugin_bundle_sha256": "e" * 64,
        "effective_session": "2026-08-25",
    }


class StrategyReleaseTests(unittest.TestCase):
    def test_manifest_digest_is_deterministic_and_runtime_identity_is_complete(self) -> None:
        digest = "c" * 64
        manifest = StrategyReleaseManifest(
            release_id="soxl-p2-v3.20260824",
            strategy_profile="soxl_soxx_trend_income",
            strategy_revision="2e3bb51",
            config_sha256=digest,
            risk_policy_sha256=digest,
            evidence_sha256=digest,
            plugin_bundle_sha256=digest,
            effective_session="2026-08-25",
            target_set_id="us-equity-soxl-paper-v1",
            targets=("longbridge:SG", "interactive_brokers:US", "charles_schwab:US"),
        )

        identity = manifest.runtime_identity()

        self.assertEqual(identity.release_id, manifest.release_id)
        self.assertEqual(identity.manifest_sha256, manifest.manifest_sha256)
        self.assertEqual(len(manifest.manifest_sha256), 64)

    def test_legacy_runtime_receipt_is_explicit(self) -> None:
        receipt = build_runtime_loaded_receipt(strategy_release=None)

        self.assertEqual(receipt["attestation_state"], "legacy_unattested")
        self.assertEqual(receipt["missing"], ["strategy_release"])

    def test_release_manifest_rejects_duplicate_targets(self) -> None:
        digest = "c" * 64
        with self.assertRaisesRegex(ValueError, "duplicates"):
            StrategyReleaseManifest(
                release_id="soxl-p2-v3.20260824",
                strategy_profile="soxl_soxx_trend_income",
                strategy_revision="2e3bb51",
                config_sha256=digest,
                risk_policy_sha256=digest,
                evidence_sha256=digest,
                plugin_bundle_sha256=digest,
                effective_session="2026-08-25",
                target_set_id="us-equity-soxl-paper-v1",
                targets=("longbridge:SG", "longbridge:SG"),
            )

    def test_release_binding_rejects_missing_or_mismatched_identity(self) -> None:
        expected = _release_identity()

        missing = validate_strategy_release_binding(
            None,
            expected_strategy_release=expected,
        )
        mismatch = validate_strategy_release_binding(
            _release_identity(release_id="soxl-p2-v4.20260824"),
            expected_strategy_release=expected,
        )

        self.assertEqual(missing.findings, ("release_identity_mismatch",))
        self.assertEqual(mismatch.findings, ("release_identity_mismatch",))
        self.assertFalse(missing.is_valid)

    def test_runtime_receipt_validation_is_shared_and_fail_closed(self) -> None:
        expected = _release_identity()
        valid = validate_runtime_loaded_receipt(
            build_runtime_loaded_receipt(strategy_release=expected),
            expected_strategy_release=expected,
        )
        malformed = validate_runtime_loaded_receipt(
            {"attestation_state": "self_attested", "strategy_release": {"release_id": "incomplete"}},
            expected_strategy_release=expected,
        )

        self.assertTrue(valid.is_valid)
        self.assertEqual(valid.release_id, expected["release_id"])
        self.assertEqual(malformed.findings, ("release_identity_invalid",))


if __name__ == "__main__":
    unittest.main()
