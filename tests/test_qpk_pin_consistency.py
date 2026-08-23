from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.check_qpk_pin_consistency import (
    check_repo,
    extract_qpk_shas,
    extract_override_qpk_sha,
)
from scripts.open_downstream_qpk_pin_prs import (
    CONSUMER_REPOS,
    STRATEGY_REPOS,
    qpk_refs,
    update_aggregate_bundle,
    update_qsl_compat_qpk_pin,
    update_strategy_dependency_pins,
)


TARGET = "8378e939d9324ea63a0f45c9f21ba0e2eeb1cfff"
STALE = "37c81901160c5b31127a27dba1c63944933fb6bf"


class QpkPinConsistencyTests(unittest.TestCase):
    def test_rollout_tiers_keep_qmt_after_strategies(self) -> None:
        self.assertEqual(
            {
                "CnEquityStrategies",
                "HkEquityStrategies",
                "UsEquityStrategies",
                "CryptoStrategies",
            },
            {repo.name for repo in STRATEGY_REPOS},
        )
        consumer_names = {repo.name for repo in CONSUMER_REPOS}
        self.assertIn("QmtPlatform", consumer_names)
        self.assertNotIn("BinancePlatform", consumer_names)

    def test_extract_uv_lock_rev(self) -> None:
        text = (
            'source = { git = "https://github.com/QuantStrategyLab/QuantPlatformKit.git'
            f'?rev={STALE}#{STALE}" }}'
        )
        refs = extract_qpk_shas(Path("uv.lock"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "uv.lock"
            path.write_text(text, encoding="utf-8")
            refs = extract_qpk_shas(path)
        self.assertEqual([STALE], [sha for _ln, _raw, sha in refs])

    def test_detect_pyproject_uv_lock_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("pyproject.toml").write_text(
                "\n".join(
                    [
                        "[project]",
                        "dependencies = [",
                        f'  "quant-platform-kit @ git+https://github.com/QuantStrategyLab/QuantPlatformKit.git@{TARGET}",',
                        "]",
                    ]
                ),
                encoding="utf-8",
            )
            root.joinpath("uv.lock").write_text(
                f'name = "quant-platform-kit"\n'
                f'source = {{ git = "https://github.com/QuantStrategyLab/QuantPlatformKit.git?rev={STALE}#{STALE}" }}',
                encoding="utf-8",
            )
            _files, mismatches, errors = check_repo(root=root, target_sha=TARGET, fix_mode=False)
            self.assertGreater(mismatches, 0)
            self.assertTrue(any("uv.lock" in err for err in errors))

    def test_override_must_match_pin(self) -> None:
        pyproject = """
[tool.uv]
override-dependencies = [
  "quant-platform-kit @ git+https://github.com/QuantStrategyLab/QuantPlatformKit.git@1111111111111111111111111111111111111111",
]
"""
        override = extract_override_qpk_sha(pyproject)
        self.assertEqual("1111111111111111111111111111111111111111", override)

    def test_update_qsl_compat_qpk_pin_rewrites_only_qpk_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            qsl_path = Path(tmp) / "qsl.toml"
            qsl_path.write_text(
                "[compat]\n"
                "requires = [\n"
                f'  "pandas>=2.0",\n'
                f'  "quant-platform-kit @ git+https://github.com/QuantStrategyLab/QuantPlatformKit.git@{STALE}",\n'
                f'  "us-equity-strategies @ git+https://github.com/QuantStrategyLab/UsEquityStrategies.git@{STALE}",\n'
                "]\n",
                encoding="utf-8",
            )

            self.assertTrue(update_qsl_compat_qpk_pin(Path(tmp), TARGET))
            updated = qsl_path.read_text(encoding="utf-8")

        self.assertIn(f"QuantPlatformKit.git@{TARGET}", updated)
        self.assertIn(f"UsEquityStrategies.git@{STALE}", updated)

    def test_update_qsl_compat_qpk_pin_rewrites_qsl_requires_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            qsl_path = Path(tmp) / "qsl.toml"
            qsl_path.write_text(
                "[qsl.requires]\n"
                f'quant_platform_kit = "{STALE}"\n'
                f'quant-platform-kit = "{STALE}"\n'
                f'crypto_strategies = "{STALE}"\n'
                "\n[runtime]\n"
                f'quant_platform_kit = "{STALE}"\n',
                encoding="utf-8",
            )

            self.assertTrue(update_qsl_compat_qpk_pin(Path(tmp), TARGET))
            updated = qsl_path.read_text(encoding="utf-8")

        self.assertIn(f'quant_platform_kit = "{TARGET}"', updated)
        self.assertIn(f'quant-platform-kit = "{TARGET}"', updated)
        self.assertIn(f'crypto_strategies = "{STALE}"', updated)
        self.assertIn(f'[runtime]\nquant_platform_kit = "{STALE}"', updated)

    def test_update_qsl_compat_qpk_pin_rewrites_single_quoted_qsl_requires_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            qsl_path = Path(tmp) / "qsl.toml"
            qsl_path.write_text(
                "[qsl.requires]\n"
                f"quant_platform_kit = '{STALE}'\n"
                f"'quant-platform-kit' = '{STALE}'\n",
                encoding="utf-8",
            )

            self.assertTrue(update_qsl_compat_qpk_pin(Path(tmp), TARGET))
            updated = qsl_path.read_text(encoding="utf-8")

        self.assertIn(f"quant_platform_kit = '{TARGET}'", updated)
        self.assertIn(f"'quant-platform-kit' = '{TARGET}'", updated)

    def test_qpk_refs_reads_consumer_pin_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("pyproject.toml").write_text(
                "[project]\n"
                "dependencies = [\n"
                f'  "quant-platform-kit @ git+https://github.com/QuantStrategyLab/QuantPlatformKit.git@{TARGET}",\n'
                "]\n",
                encoding="utf-8",
            )
            root.joinpath("qsl.toml").write_text(
                "[qsl.requires]\n"
                f'quant_platform_kit = "{TARGET}"\n',
                encoding="utf-8",
            )

            self.assertEqual({TARGET}, qpk_refs(root))

    def test_consumer_strategy_pins_update_as_one_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("pyproject.toml").write_text(
                "[project]\n"
                "dependencies = [\n"
                f'  "us-equity-strategies @ git+https://github.com/QuantStrategyLab/UsEquityStrategies.git@{STALE}",\n'
                f'  "cn-equity-strategies @ git+https://github.com/QuantStrategyLab/CnEquityStrategies.git@{STALE}",\n'
                "]\n",
                encoding="utf-8",
            )

            self.assertTrue(
                update_strategy_dependency_pins(
                    root,
                    {
                        "UsEquityStrategies": TARGET,
                        "CnEquityStrategies": TARGET,
                        "HkEquityStrategies": TARGET,
                        "CryptoStrategies": TARGET,
                    },
                )
            )
            updated = root.joinpath("pyproject.toml").read_text(encoding="utf-8")

        self.assertEqual(2, updated.count(TARGET))
        self.assertNotIn(STALE, updated)

    def test_aggregate_bundle_updates_qpk_and_all_strategy_heads(self) -> None:
        strategy_heads = {
            "CnEquityStrategies": "1" * 40,
            "HkEquityStrategies": "2" * 40,
            "UsEquityStrategies": "3" * 40,
            "CryptoStrategies": "4" * 40,
        }
        manifest = "\n".join(
            [
                "# source of truth",
                f"quant-platform-kit @ git+https://github.com/QuantStrategyLab/QuantPlatformKit.git@{STALE}",
                f"cn-equity-strategies @ git+https://github.com/QuantStrategyLab/CnEquityStrategies.git@{STALE}",
                f"hk-equity-strategies @ git+https://github.com/QuantStrategyLab/HkEquityStrategies.git@{STALE}",
                f"us-equity-strategies @ git+https://github.com/QuantStrategyLab/UsEquityStrategies.git@{STALE}",
                f"crypto-strategies @ git+https://github.com/QuantStrategyLab/CryptoStrategies.git@{STALE}",
                "",
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for filename in ("qsl-pins.txt", "constraints.txt"):
                root.joinpath(filename).write_text(manifest, encoding="utf-8")

            self.assertTrue(
                update_aggregate_bundle(
                    root,
                    qpk_sha=TARGET,
                    strategy_heads=strategy_heads,
                )
            )
            pins = root.joinpath("qsl-pins.txt").read_text(encoding="utf-8")
            constraints = root.joinpath("constraints.txt").read_text(encoding="utf-8")

        self.assertEqual(pins, constraints)
        self.assertIn(TARGET, pins)
        for sha in strategy_heads.values():
            self.assertIn(sha, pins)
        self.assertNotIn(STALE, pins)


if __name__ == "__main__":
    unittest.main()
