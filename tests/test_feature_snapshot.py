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


if __name__ == "__main__":
    unittest.main()
