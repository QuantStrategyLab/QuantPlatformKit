from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from subprocess import CalledProcessError

from scripts.check_qpk_pin_consistency import (
    check_repo,
    extract_qpk_shas,
    extract_override_qpk_sha,
)
from scripts.open_downstream_qpk_pin_prs import (
    CONSUMER_REPOS,
    STRATEGY_REPOS,
    command_failure_summary,
    qpk_refs,
    update_aggregate_bundle,
    update_qsl_metadata_test_contract,
    update_qsl_strategy_requires,
    update_qsl_compat_qpk_pin,
    update_drift_workflow_test_contract,
    update_qpk_revision_contract,
    update_strategy_dependency_pins,
)


TARGET = "8378e939d9324ea63a0f45c9f21ba0e2eeb1cfff"
STALE = "37c81901160c5b31127a27dba1c63944933fb6bf"


class QpkPinConsistencyTests(unittest.TestCase):
    def test_command_failure_summary_omits_command_output(self) -> None:
        exc = CalledProcessError(
            2,
            ["uv", "pip", "install", "--python", "/tmp/resolver/bin/python", "."],
            output="do not log resolver output",
            stderr="do not log resolver stderr",
        )

        self.assertEqual("command=uv:exit=2", command_failure_summary(exc))

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

    def test_detect_reusable_workflow_qpk_pin_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = root / ".github" / "workflows" / "drift-check.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "jobs:\n"
                "  drift:\n"
                f"    uses: QuantStrategyLab/QuantPlatformKit/.github/workflows/reusable-drift-check.yml@{STALE}\n",
                encoding="utf-8",
            )

            _files, mismatches, errors = check_repo(root=root, target_sha=TARGET, fix_mode=False)

        self.assertGreater(mismatches, 0)
        self.assertTrue(any(".github/workflows/drift-check.yml" in err for err in errors))

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
            root.joinpath("tests").mkdir()
            root.joinpath("tests", "test_qsl_compat_metadata.py").write_text(
                f'QPK_REVISION = "{TARGET}"\n',
                encoding="utf-8",
            )
            workflow = root / ".github" / "workflows" / "drift-check.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                f"uses: QuantStrategyLab/QuantPlatformKit/.github/workflows/reusable-drift-check.yml@{TARGET}\n",
                encoding="utf-8",
            )

            self.assertEqual({TARGET}, qpk_refs(root))

    def test_qpk_revision_contract_tracks_staged_pin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("tests").mkdir()
            contract = root / "tests" / "test_qsl_compat_metadata.py"
            contract.write_text(
                f'QPK_REVISION = "{STALE}"\n',
                encoding="utf-8",
            )

            self.assertTrue(update_qpk_revision_contract(root, TARGET))
            self.assertEqual(
                f'QPK_REVISION = "{TARGET}"\n',
                contract.read_text(encoding="utf-8"),
            )

    def test_drift_workflow_test_contract_tracks_previously_observed_qpk_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("tests").mkdir()
            contract = root / "tests" / "test_drift_workflow_config.py"
            contract.write_text(
                f'QPK_REF = "{STALE}"\n'
                f'assert "reusable-drift-check.yml@{STALE}" in workflow\n'
                'assert "unrelated" in workflow\n',
                encoding="utf-8",
            )

            self.assertTrue(
                update_drift_workflow_test_contract(
                    root,
                    qpk_sha=TARGET,
                    previous_qpk_refs={STALE, "unrelated"},
                )
            )
            updated = contract.read_text(encoding="utf-8")

        self.assertEqual(2, updated.count(TARGET))
        self.assertNotIn(STALE, updated)
        self.assertIn("unrelated", updated)

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

    def test_qsl_strategy_map_and_test_contract_update_together(self) -> None:
        heads = {
            "CnEquityStrategies": "1" * 40,
            "HkEquityStrategies": "2" * 40,
            "UsEquityStrategies": "3" * 40,
            "CryptoStrategies": "4" * 40,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("qsl.toml").write_text(
                "[qsl.requires]\n"
                f'quant_platform_kit = "{STALE}"\n'
                f'cn_equity_strategies = "{STALE}"\n',
                encoding="utf-8",
            )
            root.joinpath("tests").mkdir()
            contract = root / "tests" / "test_qsl_metadata.py"
            contract.write_text(
                f'assert requires["quant_platform_kit"] == "{STALE}"\n'
                f'assert requires["cn_equity_strategies"] == "{STALE}"\n',
                encoding="utf-8",
            )

            self.assertTrue(update_qsl_strategy_requires(root, heads))
            self.assertTrue(
                update_qsl_metadata_test_contract(
                    root,
                    qpk_sha=TARGET,
                    strategy_heads=heads,
                )
            )
            qsl = root.joinpath("qsl.toml").read_text(encoding="utf-8")
            test_contract = contract.read_text(encoding="utf-8")

        self.assertIn(f'cn_equity_strategies = "{heads["CnEquityStrategies"]}"', qsl)
        self.assertIn(TARGET, test_contract)
        self.assertIn(heads["CnEquityStrategies"], test_contract)

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
