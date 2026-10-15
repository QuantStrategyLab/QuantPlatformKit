from __future__ import annotations

import io
import traceback
import unittest
from contextlib import redirect_stderr, redirect_stdout
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


class GridFailureAccountingTests(unittest.TestCase):
    """Offline synthetic attempts must not become a survivor-only proposal."""

    def setUp(self) -> None:
        self.start = date(2020, 1, 1)
        self.end = date(2023, 1, 1)
        self.profile = "synthetic_grid"
        self.space = ParamSearchSpace(
            strategy_profile=self.profile, domain="us_equity",
            dimensions={"mode": ParamDimension(
                name="mode", param_type="choice", choices=("first", "middle", "last"),
                current_value="baseline",
            )},
        )
        self.result = BacktestResult(
            strategy_profile=self.profile, domain="us_equity", param_set_id="",
            params={}, sharpe_ratio=2.0, calmar_ratio=1.0, cagr=0.2,
            max_drawdown=-0.1, sortino_ratio=1.0,
            start_date=self.start, end_date=self.end, observation_count=252,
        )
        self.store = Mock()
        self.runner = Mock()
        self.attempts = []

    def orchestrator(self, failed_index=None, baseline_error=None):
        def run(_profile, params, *, start_date=None, end_date=None):
            mode = params["mode"]
            self.attempts.append(mode)
            if mode == "baseline" and baseline_error is not None:
                raise baseline_error
            if failed_index is not None and mode == self.space.dimensions["mode"].choices[failed_index]:
                raise RuntimeError("SYNTHETIC_SECRET_TOKEN https://invalid.example/private")
            return replace(
                self.result, params=dict(params), start_date=start_date, end_date=end_date,
                sharpe_ratio=0.5 if mode == "baseline" else 2.0,
            )

        self.runner.run.side_effect = run
        orchestrator = BacktestOrchestrator(store=self.store)
        orchestrator.register_runner("us_equity", self.runner)
        return orchestrator

    def search(self, orchestrator):
        return run_grid_search(
            self.profile, domain="us_equity", orchestrator=orchestrator,
            search_space=self.space, current_params={"mode": "baseline"},
            start_date=self.start, end_date=self.end, max_combinations=3,
        )

    def assert_sanitized_incomplete(self, error, index, phase):
        self.assertEqual(
            str(error), f"research_history_incomplete: candidate_index={index} phase={phase}",
        )
        self.assertTrue(error.__suppress_context__)
        self.assertIsNone(error.__cause__)
        self.assertNotIn("SYNTHETIC_SECRET_TOKEN", "".join(traceback.format_exception(error)))
        self.assertNotIn("invalid.example", "".join(traceback.format_exception(error)))
        self.store.save_proposal.assert_not_called()
        self.store.save_research_trial.assert_not_called()
        self.store.save_research_ledger.assert_not_called()

    def test_first_middle_or_last_runner_failure_stops_without_a_survivor_proposal(self):
        for index in range(3):
            with self.subTest(index=index):
                self.setUp()
                with self.assertRaises(RuntimeError) as caught:
                    self.search(self.orchestrator(failed_index=index))
                self.assert_sanitized_incomplete(caught.exception, index, "backtest")
                self.assertEqual(self.attempts, ["baseline", "first", "middle", "last"][:index + 2])
                self.assertEqual(self.store.save_backtest_result.call_count, index + 1)

    def test_candidate_persistence_failure_is_incomplete_and_does_not_retry_or_continue(self):
        def save(result):
            if result.param_set_id.endswith("_grid_1"):
                raise OSError("SYNTHETIC_SECRET_TOKEN https://invalid.example/private")

        self.store.save_backtest_result.side_effect = save
        with self.assertRaises(RuntimeError) as caught:
            self.search(self.orchestrator())
        self.assert_sanitized_incomplete(caught.exception, 1, "backtest")
        self.assertEqual(self.attempts, ["baseline", "first", "middle"])
        self.assertEqual(self.store.save_backtest_result.call_count, 3)

    def test_failure_output_does_not_include_strategy_or_parameter_values(self):
        self.profile = "SYNTHETIC_SECRET_TOKEN"
        self.space = replace(self.space, strategy_profile=self.profile, dimensions={
            **self.space.dimensions,
            "api_token": ParamDimension(
                name="api_token", param_type="choice", choices=("SYNTHETIC_SECRET_TOKEN",),
                current_value="SYNTHETIC_SECRET_TOKEN",
            ),
        })
        with self.assertRaises(RuntimeError) as caught:
            self.search(self.orchestrator(failed_index=1))
        self.assert_sanitized_incomplete(caught.exception, 1, "backtest")
        self.assertEqual(vars(caught.exception), {})
        self.assertEqual(self.attempts, ["baseline", "first", "middle"])

    def test_candidate_score_failure_is_incomplete_after_result_persistence(self):
        from quant_platform_kit.strategy_lifecycle import param_optimizer

        score = param_optimizer._score_backtest_result

        def fail_score(result):
            if result.param_set_id.endswith("_grid_1"):
                raise ValueError("SYNTHETIC_SECRET_TOKEN https://invalid.example/private")
            return score(result)

        with patch.object(param_optimizer, "_score_backtest_result", side_effect=fail_score):
            with self.assertRaises(RuntimeError) as caught:
                self.search(self.orchestrator())
        self.assert_sanitized_incomplete(caught.exception, 1, "score")
        self.assertEqual(self.attempts, ["baseline", "first", "middle"])
        self.assertEqual(self.store.save_backtest_result.call_count, 3)

    def test_baseline_failure_retains_existing_exception_and_never_starts_grid(self):
        original = ValueError("synthetic baseline failure")
        with self.assertRaises(ValueError) as caught:
            self.search(self.orchestrator(baseline_error=original))
        self.assertIs(caught.exception, original)
        self.assertEqual(self.attempts, ["baseline"])
        self.store.save_backtest_result.assert_not_called()
        self.store.save_proposal.assert_not_called()

    def test_failed_grid_cannot_reach_promotion_gates_shadow_or_console(self):
        from quant_platform_kit.strategy_lifecycle.contracts import DriftResult, DriftStatus
        from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import run_research_promotion_cycle

        drift = DriftResult(
            strategy_profile=self.profile, domain="us_equity", as_of=self.end,
            drift_score=0.8, status=DriftStatus.REVIEW,
        )
        gates, shadow, console = Mock(), Mock(), Mock()
        orchestrator = self.orchestrator(failed_index=1)
        with self.assertRaises(RuntimeError) as caught:
            run_research_promotion_cycle(
                drift, optimize=lambda *_: self.search(orchestrator),
                enforce_backtest_gates=gates, record_shadow=shadow, sync_console=console,
            )
        self.assert_sanitized_incomplete(caught.exception, 1, "backtest")
        gates.assert_not_called()
        shadow.assert_not_called()
        console.assert_not_called()

    def test_successful_search_retains_development_only_proposal_without_fabricated_trials(self):
        proposal = self.search(self.orchestrator())
        self.assertEqual(proposal.search_iterations, 3)
        self.assertEqual(proposal.recommendation, "research_candidate")
        self.assertEqual(proposal.optimization_method, "grid_search_seen_development")
        self.assertIs(proposal.walk_forward_passed, False)
        for result in (proposal.current_metrics, proposal.proposed_metrics):
            self.assertIsNone(result.oos_sharpe)
            self.assertIsNone(result.oos_calmar)
            self.assertIsNone(result.oos_max_drawdown)
            self.assertIsNone(result.walk_forward_stability)
        self.store.save_research_trial.assert_not_called()
        self.store.save_research_ledger.assert_not_called()

    def test_cli_reports_sanitized_nonzero_exit_and_entry_point_saves_no_proposal(self):
        from quant_platform_kit.strategy_lifecycle import cli, param_optimizer

        orchestrator = self.orchestrator(failed_index=1)

        def register(target, domain):
            target.register_runner(domain, orchestrator.get_runner(domain))

        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch.object(param_optimizer, "get_search_space", return_value=self.space),
            patch.object(param_optimizer, "_auto_register_runner", side_effect=register),
            patch.object(param_optimizer.PerformanceStore, "from_env", return_value=self.store),
            redirect_stdout(stdout), redirect_stderr(stderr),
        ):
            exit_code = cli.main(["optimize", "--strategy", self.profile])
        self.assertEqual(exit_code, 1)
        self.assertEqual(stderr.getvalue(), "[optimize] Error: research_history_incomplete: candidate_index=1 phase=backtest\n")
        self.assertNotIn("Recommendation:", stdout.getvalue())
        self.assertNotIn("SYNTHETIC_SECRET_TOKEN", stdout.getvalue() + stderr.getvalue())
        self.assertEqual(self.attempts, ["baseline", "first", "middle"])
        self.store.save_proposal.assert_not_called()


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
