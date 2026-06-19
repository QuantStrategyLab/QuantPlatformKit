from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

from quant_platform_kit.common.feature_snapshot import load_feature_snapshot_guarded


class FeatureSnapshotGuardAliasTests(unittest.TestCase):
    def test_guard_accepts_legacy_strategy_profile_alias_in_manifest(self) -> None:
        package = ModuleType("us_equity_strategies")
        catalog = ModuleType("us_equity_strategies.catalog")

        def resolve_canonical_profile(profile: str | None) -> str:
            mapping = {
                "tech_pullback_cash_buffer": "qqq_tech_enhancement",
                "qqq_tech_enhancement": "qqq_tech_enhancement",
            }
            return mapping.get(str(profile), str(profile))

        catalog.resolve_canonical_profile = resolve_canonical_profile
        sys.modules[package.__name__] = package
        sys.modules[catalog.__name__] = catalog
        self.addCleanup(sys.modules.pop, package.__name__, None)
        self.addCleanup(sys.modules.pop, catalog.__name__, None)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            snapshot_path = tmp_path / "snapshot.csv"
            manifest_path = tmp_path / "snapshot.csv.manifest.json"
            config_path = tmp_path / "tech_pullback_cash_buffer.json"
            snapshot_path.write_text(
                "as_of,symbol,close\n2026-04-01,QQQ,500\n",
                encoding="utf-8",
            )
            config_path.write_text('{"name": "tech_pullback_cash_buffer"}', encoding="utf-8")
            snapshot_sha256 = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
            config_sha256 = hashlib.sha256(config_path.read_bytes()).hexdigest()
            manifest_path.write_text(
                json.dumps(
                    {
                        "snapshot_as_of": "2026-04-01",
                        "strategy_profile": "tech_pullback_cash_buffer",
                        "config_name": "tech_pullback_cash_buffer",
                        "contract_version": "tech_pullback_cash_buffer.feature_snapshot.v1",
                        "snapshot_sha256": snapshot_sha256,
                        "config_sha256": config_sha256,
                        "price_as_of": "2026-04-01",
                        "universe_as_of": "2026-03-31",
                        "source_input_status": "fresh",
                        "source_input_fallback_used": False,
                        "source_refresh_run_id": "12345",
                    }
                ),
                encoding="utf-8",
            )

            result = load_feature_snapshot_guarded(
                str(snapshot_path),
                run_as_of="2026-04-02",
                required_columns=("as_of", "symbol", "close"),
                manifest_path=str(manifest_path),
                require_manifest=True,
                expected_strategy_profile="qqq_tech_enhancement",
                expected_config_name="qqq_tech_enhancement",
            )

            self.assertIsNotNone(result.frame)
            self.assertEqual(result.metadata["snapshot_guard_decision"], "proceed")
            self.assertEqual(result.metadata["snapshot_manifest_strategy_profile"], "tech_pullback_cash_buffer")
            self.assertEqual(result.metadata["snapshot_manifest_price_as_of"], "2026-04-01")
            self.assertEqual(result.metadata["snapshot_manifest_universe_as_of"], "2026-03-31")
            self.assertEqual(result.metadata["snapshot_manifest_source_input_status"], "fresh")
            self.assertEqual(result.metadata["snapshot_manifest_source_refresh_run_id"], "12345")

    def test_guard_includes_manifest_diagnostics_when_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            snapshot_path = tmp_path / "snapshot.csv"
            manifest_path = tmp_path / "snapshot.csv.manifest.json"
            snapshot_path.write_text(
                "as_of,symbol,close\n2026-04-01,QQQ,500\n",
                encoding="utf-8",
            )
            snapshot_sha256 = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
            manifest_path.write_text(
                json.dumps(
                    {
                        "snapshot_as_of": "2026-04-01",
                        "strategy_profile": "feature_snapshot_strategy",
                        "config_name": "feature_snapshot_strategy",
                        "contract_version": "feature_snapshot_strategy.feature_snapshot.v1",
                        "snapshot_sha256": snapshot_sha256,
                        "config_sha256": "abc",
                        "price_as_of": "2026-04-01",
                        "universe_as_of": "2026-03-31",
                        "source_input_status": "universe_fallback",
                        "source_input_fallback_used": True,
                        "source_input_fallback_reason": "RuntimeError: upstream returned HTML",
                        "source_input_fallback_streak": 1,
                    }
                ),
                encoding="utf-8",
            )

            result = load_feature_snapshot_guarded(
                str(snapshot_path),
                run_as_of="2026-06-01",
                required_columns=("as_of", "symbol", "close"),
                manifest_path=str(manifest_path),
                require_manifest=True,
                expected_strategy_profile="feature_snapshot_strategy",
                expected_config_name="feature_snapshot_strategy",
            )

            self.assertIsNone(result.frame)
            self.assertEqual(result.metadata["snapshot_guard_decision"], "fail_closed")
            self.assertEqual(result.metadata["snapshot_manifest_source_input_status"], "universe_fallback")
            self.assertIs(result.metadata["snapshot_manifest_source_input_fallback_used"], True)
            self.assertEqual(result.metadata["snapshot_manifest_source_input_fallback_streak"], 1)

    def test_guard_uses_last_valid_snapshot_when_current_source_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            cache_dir = tmp_path / "fallback-cache"
            snapshot_path = tmp_path / "snapshot.csv"
            manifest_path = tmp_path / "snapshot.csv.manifest.json"
            config_path = tmp_path / "config.json"
            snapshot_path.write_text(
                "as_of,symbol,close\n2026-04-01,QQQ,500\n",
                encoding="utf-8",
            )
            config_path.write_text('{"name": "feature_snapshot_strategy"}', encoding="utf-8")
            snapshot_sha256 = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
            config_sha256 = hashlib.sha256(config_path.read_bytes()).hexdigest()
            manifest_path.write_text(
                json.dumps(
                    {
                        "snapshot_as_of": "2026-04-01",
                        "strategy_profile": "feature_snapshot_strategy",
                        "config_name": "feature_snapshot_strategy",
                        "contract_version": "feature_snapshot_strategy.feature_snapshot.v1",
                        "snapshot_sha256": snapshot_sha256,
                        "config_sha256": config_sha256,
                    }
                ),
                encoding="utf-8",
            )

            first_result = load_feature_snapshot_guarded(
                str(snapshot_path),
                run_as_of="2026-04-02",
                required_columns=("as_of", "symbol", "close"),
                manifest_path=str(manifest_path),
                require_manifest=True,
                expected_strategy_profile="feature_snapshot_strategy",
                expected_config_name="feature_snapshot_strategy",
                expected_config_path=str(config_path),
                expected_contract_version="feature_snapshot_strategy.feature_snapshot.v1",
                fallback_mode="last_valid",
                fallback_cache_dir=cache_dir,
            )
            snapshot_path.unlink()
            manifest_path.unlink()

            fallback_result = load_feature_snapshot_guarded(
                str(snapshot_path),
                run_as_of="2026-04-02",
                required_columns=("as_of", "symbol", "close"),
                manifest_path=str(manifest_path),
                require_manifest=True,
                expected_strategy_profile="feature_snapshot_strategy",
                expected_config_name="feature_snapshot_strategy",
                expected_config_path=str(config_path),
                expected_contract_version="feature_snapshot_strategy.feature_snapshot.v1",
                fallback_mode="last_valid",
                fallback_cache_dir=cache_dir,
            )

            self.assertIsNotNone(first_result.frame)
            self.assertIsNotNone(fallback_result.frame)
            self.assertEqual(fallback_result.metadata["snapshot_guard_decision"], "proceed")
            self.assertIs(fallback_result.metadata["artifact_fallback_used"], True)
            self.assertEqual(fallback_result.metadata["artifact_fallback_mode"], "last_valid")
            self.assertIn("feature_snapshot_missing", fallback_result.metadata["artifact_fallback_reason"])


if __name__ == "__main__":
    unittest.main()
