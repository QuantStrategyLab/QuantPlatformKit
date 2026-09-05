from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from quant_platform_kit.strategy_lifecycle.backtest_orchestrator import BacktestOrchestrator
from quant_platform_kit.strategy_lifecycle.contracts import BacktestResult, ParamDimension, ParamSearchSpace
from quant_platform_kit.strategy_lifecycle.param_optimizer import (
    _auto_register_runner,
    _build_optimization_proposal,
    _run_development_validation,
    run_grid_search,
)


class ParamOptimizerRecommendationTests(unittest.TestCase):
    def test_strong_ordinary_optimization_is_only_a_research_candidate(self) -> None:
        baseline = BacktestResult(
            strategy_profile="test_strategy",
            domain="us_equity",
            param_set_id="baseline",
            params={"window": 20},
            sharpe_ratio=0.5,
            calmar_ratio=0.5,
            sortino_ratio=0.5,
            max_drawdown=-0.2,
            cagr=0.1,
        )
        candidate = BacktestResult(
            strategy_profile="test_strategy",
            domain="us_equity",
            param_set_id="candidate",
            params={"window": 50},
            sharpe_ratio=1.0,
            calmar_ratio=1.0,
            sortino_ratio=1.0,
            max_drawdown=-0.1,
            cagr=0.2,
            walk_forward_stability=0.9,
        )

        proposal = _build_optimization_proposal(
            "test_strategy",
            "us_equity",
            baseline.params,
            candidate.params,
            baseline,
            candidate,
            improvement=0.38,
            search_count=10,
            development_stability=0.9,
        )

        self.assertEqual(proposal.recommendation, "research_candidate")
        self.assertNotEqual(proposal.recommendation, "promote")


class DevelopmentCompletenessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.start = date(2020, 1, 1)
        self.end = date(2023, 1, 1)
        self.baseline = BacktestResult(
            strategy_profile="synthetic", domain="us_equity", param_set_id="baseline",
            params={"window": 10}, sharpe_ratio=0.5, calmar_ratio=0.5,
            max_drawdown=-0.2, cagr=0.1, sortino_ratio=0.5,
            start_date=self.start, end_date=self.end, observation_count=252,
        )
        self.candidate = replace(self.baseline, param_set_id="candidate", params={"window": 20},
                                 sharpe_ratio=1.0, calmar_ratio=1.0, max_drawdown=-0.1)

    def orchestrator(self, outcomes):
        outcomes = iter(outcomes)

        def run(_profile, **kwargs):
            outcome = next(outcomes)
            if isinstance(outcome, Exception):
                raise outcome
            result = replace(self.candidate, start_date=kwargs["start_date"], end_date=kwargs["end_date"],
                             observation_count=63)
            return replace(result, **outcome)

        return Mock(spec=BacktestOrchestrator, run=Mock(side_effect=run))

    def proposal(self, candidate, improvement=1.0, development_stability=None):
        return _build_optimization_proposal(
            "synthetic", "us_equity", self.baseline.params, candidate.params,
            self.baseline, candidate, improvement=improvement, search_count=3,
            development_stability=development_stability,
        )

    def validate(self, orchestrator):
        return _run_development_validation(
            "synthetic", domain="us_equity", params=self.candidate.params,
            orchestrator=orchestrator, start_date=self.start, end_date=self.end,
        )

    def assert_incomplete(self, diagnostics):
        self.assertEqual(diagnostics, (None,) * 4)
        proposal = self.proposal(self.candidate, development_stability=diagnostics[0])
        self.assertFalse(proposal.walk_forward_passed)
        self.assertNotEqual(proposal.recommendation, "research_candidate")
        self.assertTrue(np.isfinite(proposal.confidence))
        self.assertEqual(proposal.confidence, 0.0)

    def test_one_success_two_failures_cannot_become_perfectly_stable(self):
        orchestrator = self.orchestrator([{}, RuntimeError("synthetic fold failure"), RuntimeError("synthetic fold failure")])
        result = _run_development_validation(
            "synthetic", domain="us_equity", params={}, orchestrator=orchestrator,
            start_date=self.start, end_date=self.end,
        )
        self.assertEqual(result, (None,) * 4)
        orchestrator = self.orchestrator([{}, RuntimeError("synthetic fold failure"), RuntimeError("synthetic fold failure")])
        self.assert_incomplete(self.validate(orchestrator))
        self.assertEqual(orchestrator.run.call_count, 2)

    def test_first_middle_last_or_all_fold_failures_stop_without_survivor_averaging(self):
        for failed_index in (0, 1, 2):
            with self.subTest(failed_index=failed_index):
                outcomes = [{} for _ in range(3)]
                outcomes[failed_index] = RuntimeError("synthetic fold failure")
                orchestrator = self.orchestrator(outcomes)
                self.assert_incomplete(self.validate(orchestrator))
                self.assertEqual(orchestrator.run.call_count, failed_index + 1)
        orchestrator = self.orchestrator([RuntimeError("synthetic fold failure")] * 3)
        self.assert_incomplete(self.validate(orchestrator))
        self.assertEqual(orchestrator.run.call_count, 1)

    def test_required_metrics_must_be_present_and_finite_in_every_fold(self):
        for metric in ("sharpe_ratio", "calmar_ratio", "max_drawdown"):
            for invalid in (None, float("nan"), float("inf"), float("-inf")):
                with self.subTest(metric=metric, invalid=invalid):
                    orchestrator = self.orchestrator([{}, {metric: invalid}, {}])
                    self.assert_incomplete(self.validate(orchestrator))
                    self.assertEqual(orchestrator.run.call_count, 2)

    def test_empty_missing_reversed_or_outside_result_window_is_incomplete(self):
        for invalid in (
            {"observation_count": 0}, {"observation_count": -1},
            {"observation_count": float("nan")}, {"start_date": None}, {"end_date": None},
            {"start_date": self.end, "end_date": self.start},
            {"start_date": self.start - timedelta(days=1)},
        ):
            with self.subTest(invalid=invalid):
                self.assert_incomplete(self.validate(self.orchestrator([invalid, {}, {}])))

    def test_short_or_invalid_requested_windows_never_run(self):
        for start, end, folds in ((None, self.end, 3), (self.start, None, 3),
                                  (self.end, self.start, 3), (self.start, self.start + timedelta(days=90), 3),
                                  (self.start, self.start + timedelta(days=252), 10), (self.start, self.end, 1)):
            with self.subTest(start=start, end=end, folds=folds):
                orchestrator = self.orchestrator([])
                result = _run_development_validation(
                    "synthetic", domain="us_equity", params={}, orchestrator=orchestrator,
                    start_date=start, end_date=end, folds=folds,
                )
                self.assertEqual(result, (None,) * 4)
                orchestrator.run.assert_not_called()

    def test_complete_valid_folds_keep_original_stability_and_research_only_recommendation(self):
        orchestrator = self.orchestrator([
            {"sharpe_ratio": 1.0, "calmar_ratio": 1.0, "max_drawdown": -0.1},
            {"sharpe_ratio": 2.0, "calmar_ratio": 2.0, "max_drawdown": -0.3},
            {"sharpe_ratio": 3.0, "calmar_ratio": 3.0, "max_drawdown": -0.2},
        ])
        diagnostics = self.validate(orchestrator)
        expected_stability = 1.0 - np.sqrt(2.0 / 3.0) / 2.0
        self.assertAlmostEqual(diagnostics[0], expected_stability)
        self.assertEqual(diagnostics[1:], (2.0, 2.0, -0.3))
        self.assertEqual(orchestrator.run.call_count, 3)
        proposal = self.proposal(self.candidate, development_stability=diagnostics[0])
        self.assertIs(proposal.walk_forward_passed, False)
        self.assertEqual(proposal.recommendation, "research_candidate")
        self.assertAlmostEqual(proposal.confidence, round(expected_stability, 4))

    def test_invalid_stability_or_improvement_cannot_create_pass_or_confidence(self):
        for invalid in (float("nan"), float("inf"), float("-inf")):
            for field in ("stability", "improvement"):
                with self.subTest(invalid=invalid, field=field):
                    proposal = self.proposal(
                        self.candidate, improvement=invalid if field == "improvement" else 1.0,
                        development_stability=invalid if field == "stability" else 1.0,
                    )
                    self.assertIs(proposal.walk_forward_passed, False)
                    self.assertEqual(proposal.confidence, 0.0)
                    self.assertNotEqual(proposal.recommendation, "research_candidate")

    def test_finite_fold_inputs_with_overflowing_aggregates_are_incomplete(self):
        orchestrator = self.orchestrator([{"sharpe_ratio": 1e308}] * 3)
        with np.errstate(over="ignore", invalid="ignore"):
            self.assert_incomplete(self.validate(orchestrator))

    def test_missing_or_out_of_range_stability_has_no_confidence_fallback(self):
        for stability in (None, -0.1, 1.1):
            with self.subTest(stability=stability):
                proposal = self.proposal(self.candidate, development_stability=stability)
                self.assertIs(proposal.walk_forward_passed, False)
                self.assertEqual(proposal.confidence, 0.0)

    def test_grid_search_can_follow_seen_returns_but_never_exports_oos_or_pass(self):
        space = ParamSearchSpace(
            strategy_profile="synthetic", domain="us_equity",
            dimensions={"mode": ParamDimension(name="mode", param_type="choice", choices=("left", "right"), current_value="baseline")},
        )
        for seen_winner, failed_segment in (("left", False), ("right", False), ("left", True)):
            with self.subTest(seen_winner=seen_winner, failed_segment=failed_segment):
                segments = []
                original_results = []

                def run(_profile, **kwargs):
                    run_id = kwargs["param_set_id"]
                    if run_id.endswith("_current"):
                        sharpe = 0.5
                    elif "_grid_" in run_id:
                        sharpe = 2.0 if kwargs["params"]["mode"] == seen_winner else 0.6
                    else:
                        segments.append(run_id)
                        if failed_segment and len(segments) == 2:
                            raise RuntimeError("synthetic segment failure")
                        sharpe = 1.0
                    result = replace(
                        self.candidate, params=kwargs["params"], param_set_id=run_id,
                        start_date=kwargs["start_date"], end_date=kwargs["end_date"],
                        sharpe_ratio=sharpe, observation_count=63,
                        oos_sharpe=999.0, oos_calmar=999.0, oos_max_drawdown=-0.01,
                        walk_forward_stability=1.0,
                    )
                    original_results.append(result)
                    return result

                orchestrator = Mock(spec=BacktestOrchestrator, run=Mock(side_effect=run))
                proposal = run_grid_search(
                    "synthetic", domain="us_equity", orchestrator=orchestrator,
                    search_space=space, current_params={"mode": "baseline"},
                    start_date=self.start, end_date=self.end,
                )
                self.assertEqual(proposal.proposed_params, {"mode": seen_winner})
                payload = proposal.to_dict()
                self.assertEqual(payload["optimization_method"], "grid_search_seen_development")
                self.assertIs(payload["walk_forward_passed"], False)
                for metrics in (payload["current_metrics"], payload["proposed_metrics"]):
                    for field in ("oos_sharpe", "oos_calmar", "oos_max_drawdown", "walk_forward_stability"):
                        self.assertIsNone(metrics[field])
                for result in original_results:
                    self.assertEqual((result.oos_sharpe, result.oos_calmar,
                                      result.oos_max_drawdown, result.walk_forward_stability),
                                     (999.0, 999.0, -0.01, 1.0))
                self.assertEqual(len(segments), 2 if failed_segment else 3)
                self.assertEqual(proposal.confidence, 0.0 if failed_segment else 1.0)
                self.assertEqual(proposal.recommendation, "needs_review" if failed_segment else "research_candidate")


class ParamOptimizerRunnerRegistrationTests(unittest.TestCase):
    def test_auto_register_runner_requires_exact_real_marker(self) -> None:
        missing = object()
        for marker in (missing, None, "", " ", "placeholder", "REAL", " real "):
            with self.subTest(marker=marker):
                orchestrator = BacktestOrchestrator()
                runner = SimpleNamespace()
                if marker is not missing:
                    runner.runner_kind = marker
                fake_module = SimpleNamespace(build_backtest_runner=lambda: runner)

                with (
                    patch("importlib.import_module", return_value=fake_module),
                    self.assertRaisesRegex(RuntimeError, "explicit runner_kind='real'"),
                ):
                    _auto_register_runner(orchestrator, "us_equity")

    def test_auto_register_runner_raises_when_all_candidates_fail(self) -> None:
        orchestrator = BacktestOrchestrator()

        def _raise(name: str) -> None:
            raise ImportError(f"missing {name}")

        with patch("importlib.import_module", side_effect=_raise):
            with self.assertRaisesRegex(RuntimeError, "Unable to register BacktestRunner"):
                _auto_register_runner(orchestrator, "crypto")

    def test_auto_register_runner_falls_back_to_legacy_us_equity_module(self) -> None:
        orchestrator = BacktestOrchestrator()

        class RealRunner:
            runner_kind = "real"

        fake_module = SimpleNamespace(build_backtest_runner=lambda: RealRunner())

        def _import(name: str) -> SimpleNamespace:
            if name == "us_equity_snapshot_pipelines.strategy_lifecycle.backtest_wrapper":
                return fake_module
            raise ImportError(f"missing {name}")

        with patch("importlib.import_module", side_effect=_import):
            _auto_register_runner(orchestrator, "us_equity")

        self.assertIsNotNone(orchestrator.get_runner("us_equity"))


if __name__ == "__main__":
    unittest.main()
