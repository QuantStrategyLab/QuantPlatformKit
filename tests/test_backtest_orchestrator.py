"""Tests for strategy_lifecycle.backtest_orchestrator."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
import json
import math
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping

from quant_platform_kit.strategy_lifecycle.backtest_orchestrator import (
    BacktestOrchestrator,
)
from quant_platform_kit.strategy_lifecycle.contracts import BacktestResult
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore


class _RecordingRunner:
    """Mock BacktestRunner that records calls and returns deterministic metrics."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def run(
        self,
        strategy_profile: str,
        params: Mapping[str, Any],
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> BacktestResult:
        self.calls.append(
            {
                "strategy_profile": strategy_profile,
                "params": dict(params),
                "start_date": start_date,
                "end_date": end_date,
            }
        )
        lookback = int(params.get("lookback", 20))
        sharpe = 1.0 + lookback * 0.01
        return BacktestResult(
            strategy_profile=strategy_profile,
            domain="us_equity",
            param_set_id="mock",
            params=dict(params),
            sharpe_ratio=sharpe,
            cagr=0.12,
            max_drawdown=-0.08,
            start_date=start_date,
            end_date=end_date,
            observation_count=252,
        )


class _PromotionRecordingRunner(_RecordingRunner):
    """Synthetic runner with the explicit promotion-only capability."""

    def __init__(self, **result_overrides: Any) -> None:
        super().__init__()
        self.result_overrides = result_overrides

    def _promotion_result(
        self,
        strategy_profile: str,
        params: Mapping[str, Any],
        *,
        start_date: date,
        end_date: date,
    ) -> BacktestResult:
        values: dict[str, Any] = {
            "strategy_profile": strategy_profile,
            "domain": "us_equity",
            "param_set_id": "runner_result",
            "params": dict(params),
            "sharpe_ratio": 1.2,
            "calmar_ratio": 1.1,
            "sortino_ratio": 1.4,
            "max_drawdown": -0.08,
            "cagr": 0.12,
            "volatility": 0.15,
            "win_rate": 0.55,
            "total_return": 0.18,
            "start_date": start_date,
            "end_date": end_date,
            "observation_count": 252,
        }
        values.update(self.result_overrides)
        return BacktestResult(**values)

    def run_purged_fold(
        self,
        strategy_profile: str,
        params: Mapping[str, Any],
        *,
        fold: Any,
        purge_days: int,
        embargo_days: int,
        cost_model: Any,
    ) -> BacktestResult:
        self.calls.append(
            {
                "kind": "fold",
                "fold": fold,
                "purge_days": purge_days,
                "embargo_days": embargo_days,
                "cost_model": cost_model,
            }
        )
        return self._promotion_result(
            strategy_profile,
            params,
            start_date=fold.test_start,
            end_date=fold.test_end,
        )

    def run_locked_oos(
        self,
        strategy_profile: str,
        params: Mapping[str, Any],
        *,
        start_date: date,
        end_date: date,
        cost_model: Any,
    ) -> BacktestResult:
        self.calls.append(
            {
                "kind": "locked_oos",
                "start_date": start_date,
                "end_date": end_date,
                "cost_model": cost_model,
            }
        )
        return self._promotion_result(
            strategy_profile,
            params,
            start_date=start_date,
            end_date=end_date,
        )


class BacktestOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = PerformanceStore(local_root=Path(self.tmp.name))
        self.orchestrator = BacktestOrchestrator(store=self.store)
        self.runner = _RecordingRunner()
        self.orchestrator.register_runner("us_equity", self.runner)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def _promotion_folds() -> list[Any]:
        from quant_platform_kit.strategy_lifecycle.contracts import (
            PurgedWalkForwardFold,
        )

        return [
            PurgedWalkForwardFold(
                date(2015, 1, 1),
                date(2015, 12, 31),
                date(2016, 1, 3),
                date(2016, 6, 30),
            ),
            PurgedWalkForwardFold(
                date(2016, 7, 3),
                date(2017, 6, 30),
                date(2017, 7, 3),
                date(2017, 12, 31),
            ),
            PurgedWalkForwardFold(
                date(2018, 1, 3),
                date(2018, 12, 31),
                date(2019, 1, 3),
                date(2019, 6, 30),
            ),
        ]

    @staticmethod
    def _cost_model(**overrides: Any) -> Any:
        from quant_platform_kit.strategy_lifecycle.contracts import PromotionCostModel

        values = {
            "model_id": "retail_us_equity_v1",
            "commission_bps": 1.0,
            "slippage_bps": 2.0,
            "market_impact_bps": 0.5,
        }
        values.update(overrides)
        return PromotionCostModel(**values)

    def _run_promotion(
        self,
        *,
        runner: _PromotionRecordingRunner | None = None,
        folds: list[Any] | None = None,
        locked_oos_start: date = date(2019, 7, 3),
        locked_oos_end: date = date(2020, 7, 3),
        purge_days: int = 1,
        embargo_days: int = 1,
        source_revision: str = "a" * 40,
        cost_model: Any = None,
    ) -> Any:
        promotion_runner = runner or _PromotionRecordingRunner()
        self.orchestrator.register_runner("us_equity", promotion_runner)
        return self.orchestrator.run_promotion(
            "test_strat",
            domain="us_equity",
            params={"lookback": 30},
            folds=self._promotion_folds() if folds is None else folds,
            locked_oos_start=locked_oos_start,
            locked_oos_end=locked_oos_end,
            purge_days=purge_days,
            embargo_days=embargo_days,
            source_revision=source_revision,
            cost_model=cost_model or self._cost_model(),
            param_set_id="promotion_test",
        )

    def test_run_enriches_and_persists(self) -> None:
        result = self.orchestrator.run(
            "test_strat",
            domain="us_equity",
            params={"lookback": 30},
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
        )
        self.assertEqual(result.strategy_profile, "test_strat")
        self.assertEqual(result.domain, "us_equity")
        self.assertEqual(result.params, {"lookback": 30})
        self.assertAlmostEqual(result.sharpe_ratio, 1.3)
        self.assertTrue(result.run_id)
        self.assertTrue(result.computed_at)
        self.assertEqual(result.source_script, "backtest_orchestrator")

    def test_persist_result_preserves_existing_param_version_by_default(self) -> None:
        result = BacktestResult(
            strategy_profile="test_strat",
            domain="us_equity",
            param_set_id="candidate",
            params={"lookback": 30},
            param_version=7,
            sharpe_ratio=1.3,
            cagr=0.12,
            max_drawdown=-0.08,
            observation_count=252,
        )

        persisted = self.orchestrator.persist_result(
            result,
            strategy_profile="test_strat",
            domain="us_equity",
            params={"lookback": 30},
            param_set_id="persisted",
        )

        self.assertEqual(persisted.param_version, 7)

    def test_persist_result_clamps_explicit_zero_param_version(self) -> None:
        result = BacktestResult(
            strategy_profile="test_strat",
            domain="us_equity",
            param_set_id="candidate",
            params={"lookback": 30},
            param_version=7,
            sharpe_ratio=1.3,
            cagr=0.12,
            max_drawdown=-0.08,
            observation_count=252,
        )

        persisted = self.orchestrator.persist_result(
            result,
            strategy_profile="test_strat",
            domain="us_equity",
            params={"lookback": 30},
            param_set_id="persisted",
            param_version=0,
        )

        self.assertEqual(persisted.param_version, 1)

    def test_persist_result_preserves_source_revision_and_cost_model(self) -> None:
        result = BacktestResult(
            strategy_profile="test_strat",
            domain="us_equity",
            param_set_id="candidate",
            params={"lookback": 30},
            source_revision="b" * 40,
            cost_model="retail_us_equity_v1",
        )

        persisted = self.orchestrator.persist_result(
            result,
            strategy_profile="test_strat",
            domain="us_equity",
            params={"lookback": 30},
        )

        self.assertEqual(persisted.source_revision, "b" * 40)
        self.assertEqual(persisted.cost_model, "retail_us_equity_v1")

    def test_backtest_result_keeps_legacy_positional_order(self) -> None:
        result = BacktestResult(
            "strat", "domain", "params-v1", {"lookback": 30}, 7, 1.25, 0.9
        )

        self.assertEqual(result.param_version, 7)
        self.assertEqual(result.sharpe_ratio, 1.25)
        self.assertEqual(result.calmar_ratio, 0.9)

    def test_run_raises_without_runner(self) -> None:
        with self.assertRaises(ValueError):
            self.orchestrator.run("test_strat", domain="cn_equity", params={})

    def test_walk_forward_runs_each_window(self) -> None:
        windows = [
            (date(2020, 1, 1), date(2021, 12, 31)),
            (date(2022, 1, 1), date(2023, 12, 31)),
            (date(2024, 1, 1), date(2024, 12, 31)),
        ]
        results = self.orchestrator.walk_forward(
            "test_strat",
            domain="us_equity",
            params={"lookback": 20},
            windows=windows,
            param_set_id="wf_test",
        )
        self.assertEqual(len(results), 3)
        self.assertEqual(len(self.runner.calls), 3)
        for idx, (result, window) in enumerate(zip(results, windows)):
            self.assertEqual(result.start_date, window[0])
            self.assertEqual(result.end_date, window[1])
            self.assertEqual(result.param_set_id, f"wf_test_wf{idx}")
        self.assertEqual(
            [self.runner.calls[i]["start_date"] for i in range(3)],
            [w[0] for w in windows],
        )

    def test_walk_forward_empty_windows_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.orchestrator.walk_forward(
                "test_strat",
                domain="us_equity",
                params={},
                windows=[],
            )

    def test_ordinary_walk_forward_accepts_raw_windows_but_is_non_promotion(
        self,
    ) -> None:
        results = self.orchestrator.walk_forward(
            "test_strat",
            domain="us_equity",
            params={},
            windows=[
                (date(2021, 1, 1), date(2021, 12, 31)),
                (date(2021, 6, 1), date(2021, 7, 1)),
                (None, None),
            ],
        )

        self.assertEqual(len(results), 3)
        self.assertTrue(
            all(
                getattr(result, "validation_identity", None) is None
                for result in results
            )
        )
        self.assertTrue(
            all("promotion_ready" not in result.to_dict() for result in results)
        )

    def test_promotion_run_requires_explicit_runner_capability(self) -> None:
        with self.assertRaises(TypeError):
            self.orchestrator.run_promotion(
                "test_strat",
                domain="us_equity",
                params={},
                folds=self._promotion_folds(),
                locked_oos_start=date(2019, 7, 3),
                locked_oos_end=date(2020, 7, 3),
                purge_days=1,
                embargo_days=1,
                source_revision="a" * 40,
                cost_model=self._cost_model(),
            )

    def test_promotion_run_enforces_and_persists_purged_wfa_identity(self) -> None:
        run = self._run_promotion()

        self.assertEqual(len(run.fold_results), 3)
        self.assertEqual(run.locked_oos_result.start_date, date(2019, 7, 3))
        self.assertEqual(run.locked_oos_result.end_date, date(2020, 7, 3))
        self.assertEqual(run.source_revision, "a" * 40)
        self.assertEqual(run.cost_model.model_id, "retail_us_equity_v1")
        results = (*run.fold_results, run.locked_oos_result)
        self.assertTrue(all(result.source_revision == "a" * 40 for result in results))
        self.assertTrue(
            all(result.cost_model == "retail_us_equity_v1" for result in results)
        )
        self.assertTrue(
            all(result.validation_identity is not None for result in results)
        )
        self.assertEqual(
            [result.validation_identity.fold_role for result in run.fold_results],
            ["test"] * 3,
        )
        self.assertEqual(
            run.locked_oos_result.validation_identity.fold_role, "locked_oos"
        )
        self.assertTrue(
            all(result.validation_identity.purge_days == 1 for result in results)
        )
        self.assertTrue(
            all(result.validation_identity.embargo_days == 1 for result in results)
        )
        self.assertTrue(
            all(result.cost_inputs["commission_bps"] == 1.0 for result in results)
        )

        payloads = [
            json.loads(path.read_text()) for path in Path(self.tmp.name).rglob("*.json")
        ]
        self.assertEqual(len(payloads), 4)
        self.assertTrue(
            all(payload["source_revision"] == "a" * 40 for payload in payloads)
        )
        self.assertTrue(
            all(payload["cost_model"] == "retail_us_equity_v1" for payload in payloads)
        )
        self.assertTrue(
            all(
                payload["validation_identity"]["purge_days"] == 1
                for payload in payloads
            )
        )
        self.assertTrue(
            all(
                payload["validation_identity"]["embargo_days"] == 1
                for payload in payloads
            )
        )

    def test_promotion_run_rejects_untyped_raw_windows(self) -> None:
        with self.assertRaises(TypeError):
            self._run_promotion(folds=[(date(2015, 1, 1), date(2016, 1, 1))])

    def test_promotion_run_rejects_fewer_than_three_folds(self) -> None:
        with self.assertRaises(ValueError):
            self._run_promotion(folds=self._promotion_folds()[:2])

    def test_promotion_run_rejects_zero_purge_or_embargo(self) -> None:
        with self.assertRaises(ValueError):
            self._run_promotion(purge_days=0)
        with self.assertRaises(ValueError):
            self._run_promotion(embargo_days=0)

    def test_promotion_run_requires_explicit_embargo(self) -> None:
        runner = _PromotionRecordingRunner()
        self.orchestrator.register_runner("us_equity", runner)
        with self.assertRaises(TypeError):
            self.orchestrator.run_promotion(
                "test_strat",
                domain="us_equity",
                params={},
                folds=self._promotion_folds(),
                locked_oos_start=date(2019, 7, 3),
                locked_oos_end=date(2020, 7, 3),
                purge_days=1,
                source_revision="a" * 40,
                cost_model=self._cost_model(),
            )

    def test_promotion_run_rejects_invalid_or_overlapping_folds(self) -> None:
        fold_type = type(self._promotion_folds()[0])
        invalid_sets = [
            [
                fold_type(
                    date(2015, 1, 2),
                    date(2015, 1, 1),
                    date(2015, 2, 1),
                    date(2015, 3, 1),
                ),
                *self._promotion_folds()[1:],
            ],
            [
                fold_type(
                    date(2015, 1, 1),
                    date(2015, 12, 31),
                    date(2015, 12, 31),
                    date(2016, 6, 30),
                ),
                *self._promotion_folds()[1:],
            ],
            [
                self._promotion_folds()[1],
                self._promotion_folds()[0],
                self._promotion_folds()[2],
            ],
            [
                self._promotion_folds()[0],
                fold_type(
                    date(2016, 6, 29),
                    date(2017, 6, 30),
                    date(2017, 7, 3),
                    date(2017, 12, 31),
                ),
                self._promotion_folds()[2],
            ],
        ]
        for folds in invalid_sets:
            with self.subTest(folds=folds), self.assertRaises(ValueError):
                self._run_promotion(folds=folds)

    def test_promotion_run_rejects_locked_oos_overlap_or_short_calendar_span(
        self,
    ) -> None:
        with self.assertRaises(ValueError):
            self._run_promotion(locked_oos_start=date(2019, 6, 30))
        with self.assertRaises(ValueError):
            self._run_promotion(locked_oos_end=date(2020, 7, 2))

    def test_promotion_run_uses_calendar_month_validation_for_leap_day(self) -> None:
        run = self._run_promotion(
            locked_oos_start=date(2020, 2, 29),
            locked_oos_end=date(2021, 2, 28),
        )

        self.assertEqual(run.locked_oos_result.end_date, date(2021, 2, 28))

    def test_promotion_run_rejects_undated_or_non_finite_results(self) -> None:
        with self.assertRaises(ValueError):
            self._run_promotion(runner=_PromotionRecordingRunner(start_date=None))
        with self.assertRaises(ValueError):
            self._run_promotion(runner=_PromotionRecordingRunner(sharpe_ratio=math.nan))
        with self.assertRaises(ValueError):
            self._run_promotion(runner=_PromotionRecordingRunner(cagr=math.inf))

    def test_promotion_run_rejects_non_finite_cost_inputs(self) -> None:
        with self.assertRaises(ValueError):
            self._run_promotion(cost_model=self._cost_model(slippage_bps=math.nan))
        with self.assertRaises(ValueError):
            self._run_promotion(cost_model=self._cost_model(commission_bps=math.inf))

    def test_promotion_run_rejects_invalid_source_revision(self) -> None:
        with self.assertRaises(ValueError):
            self._run_promotion(source_revision="caller-label")

    def test_public_persist_cannot_promote_a_caller_labeled_result(self) -> None:
        from quant_platform_kit.strategy_lifecycle.contracts import (
            BacktestValidationIdentity,
        )

        fold = self._promotion_folds()[0]
        identity = BacktestValidationIdentity(
            protocol="purged_walk_forward.v1",
            fold_id="caller",
            fold_role="locked_oos",
            train_start=None,
            train_end=None,
            test_start=date(2019, 7, 3),
            test_end=date(2020, 7, 3),
            locked_oos_start=date(2019, 7, 3),
            locked_oos_end=date(2020, 7, 3),
            purge_days=1,
            embargo_days=1,
        )
        caller_labeled = replace(
            self.runner.run(
                "test_strat", {}, start_date=fold.test_start, end_date=fold.test_end
            ),
            validation_identity=identity,
        )

        persisted = self.orchestrator.persist_result(
            caller_labeled,
            strategy_profile="test_strat",
            domain="us_equity",
            params={},
        )

        self.assertIsNone(persisted.validation_identity)

    def test_sensitivity_runs_param_grid(self) -> None:
        report = self.orchestrator.sensitivity(
            "test_strat",
            domain="us_equity",
            base_params={"top_n": 2},
            param_ranges={"lookback": [10, 20, 30]},
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
        )
        self.assertEqual(report.combination_count, 3)
        self.assertEqual(len(report.results), 3)
        self.assertEqual(report.strategy_profile, "test_strat")
        self.assertEqual(report.base_params, {"top_n": 2})
        sharpes = [r.sharpe_ratio for r in report.results]
        self.assertEqual(sharpes, [1.1, 1.2, 1.3])
        for call, result in zip(self.runner.calls, report.results):
            self.assertEqual(call["params"]["top_n"], 2)
            self.assertIn("lookback", call["params"])
            self.assertEqual(result.params["top_n"], 2)

    def test_sensitivity_two_dim_grid(self) -> None:
        report = self.orchestrator.sensitivity(
            "test_strat",
            domain="us_equity",
            base_params={},
            param_ranges={"lookback": [10, 20], "top_n": [2, 3]},
        )
        self.assertEqual(report.combination_count, 4)
        lookbacks = sorted({r.params["lookback"] for r in report.results})
        top_ns = sorted({r.params["top_n"] for r in report.results})
        self.assertEqual(lookbacks, [10, 20])
        self.assertEqual(top_ns, [2, 3])

    def test_sensitivity_empty_ranges_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.orchestrator.sensitivity(
                "test_strat",
                domain="us_equity",
                base_params={},
                param_ranges={},
            )


if __name__ == "__main__":
    unittest.main()
