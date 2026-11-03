"""B3 analytic and synthetic-only research report acceptance."""

import math
import hashlib
import json
import unittest
from dataclasses import replace
from statistics import NormalDist, stdev

from quant_platform_kit.research_stats._validation import ResearchInputError
from quant_platform_kit.research_stats.unified_report import (
    TrialEvidence,
    build_unified_net_report,
)


class UnifiedNetReportTests(unittest.TestCase):
    def test_recovery_opt_in_with_missing_rf_retains_censored_nulls(self):
        report = build_unified_net_report((-.5,), include_max_drawdown_recovery=True,
                                          sharpe_basis="net_wealth_excess_sharpe_v2",
                                          calendar_id="SYNTHETIC", periods_per_year=252)
        self.assertEqual(report.metric("sharpe_per_period").reason_code, "missing_risk_free_returns")
        self.assertEqual(report.metric("max_drawdown").value, -.5)
        for name in ("max_drawdown_peak_to_recovery_observations",
                     "max_drawdown_trough_to_recovery_observations"):
            metric = report.metric(name)
            self.assertIsNone(metric.value)
            self.assertEqual(metric.reason_code, "right_censored")
            self.assertEqual(metric.details["observed_trough_to_end_lower_bound"], 0)
        payload = report.to_dict()
        self.assertIsNone(next(m for m in payload["metrics"] if m["name"] ==
                              "max_drawdown_peak_to_recovery_observations")["value"])

    def test_recovery_observation_intervals_are_not_annualized(self):
        for periods in (252, 365):
            with self.subTest(periods=periods):
                report = build_unified_net_report((-.5, 0., 1.), periods_per_year=periods,
                                                  include_max_drawdown_recovery=True)
                self.assertEqual(report.metric("max_drawdown_peak_to_recovery_observations").value, 3)
        for flag in (0, 1, "yes", None):
            with self.subTest(flag=flag), self.assertRaises(ResearchInputError):
                build_unified_net_report((-.5, 1.), include_max_drawdown_recovery=flag)

    def test_recovery_opt_in_uses_net_wealth_never_excess(self):
        net = (-.5, 0., 1.)
        options = dict(periods_per_year=252, calendar_id="SYNTHETIC",
                       sharpe_basis="net_wealth_excess_sharpe_v2",
                       risk_free_returns=(.01,) * 3, risk_free_source="synthetic")
        base = build_unified_net_report(net, **options).to_dict()
        report = build_unified_net_report(net, include_max_drawdown_recovery=True, **options)
        self.assertEqual(report.to_dict()["metrics"][:-2], base["metrics"])
        self.assertEqual(report.metric("max_drawdown_peak_to_recovery_observations").value, 3)
        self.assertEqual(report.metric("max_drawdown_trough_to_recovery_observations").value, 2)
        self.assertEqual(report.metric("max_drawdown_peak_to_recovery_observations").details["unit"],
                         "return_observations")

    def test_c1_excess_below_minus_one_is_not_a_wealth_return(self):
        net = (.5, .7, -.995) * 12
        explicit = build_unified_net_report(
            net, periods_per_year=252, calendar_id="SYNTHETIC",
            sharpe_basis="net_wealth_excess_sharpe_v2", risk_free_returns=(.01,) * 36,
            risk_free_source="synthetic-c1", trials=TrialEvidence(3, .02, "a" * 64))
        self.assertAlmostEqual(explicit.metric("probabilistic_sharpe_ratio").value, .6695684362365747)
        for name in ("probabilistic_sharpe_ratio", "deflated_sharpe_ratio", "minimum_track_record_periods"):
            self.assertTrue(explicit.metric(name).computed, name)
        legacy = build_unified_net_report(net, periods_per_year=252)
        for name in ("net_log_growth_per_period", "net_cagr", "max_drawdown"):
            self.assertEqual(explicit.metric(name).value, legacy.metric(name).value)

    def test_c1_does_not_relax_raw_wealth_or_rf_bounds(self):
        options = dict(periods_per_year=252, calendar_id="SYNTHETIC",
                       sharpe_basis="net_wealth_excess_sharpe_v2", risk_free_source="synthetic-c1")
        for net, rf in (((.5, .7, -1.), (.01,)*3), ((.5, .7, -.995), (-1.,)*3)):
            with self.subTest(net=net, rf=rf), self.assertRaises(ResearchInputError):
                build_unified_net_report(net, risk_free_returns=rf, **options)

    def test_legacy_report_retains_frozen_base_digest(self):
        # Captured from QPK 187c429, before the explicit-basis implementation.
        report = build_unified_net_report((.01, -.01, .02), min_observations=3,
                                          periods_per_year=252).to_dict()
        digest = hashlib.sha256(json.dumps(report, sort_keys=True, separators=(",", ":"),
                                           allow_nan=False).encode()).hexdigest()
        self.assertEqual(digest, "60ef62cd382a5bf177b18b13d2cbe512fe4acd07b4f659e4f690869b31a1a015")

    def test_explicit_rf_contract_rejects_silent_assumptions(self):
        base = dict(sharpe_basis="net_wealth_excess_sharpe_v2", calendar_id="XNYS",
                    periods_per_year=252, risk_free_returns=(.001,) * 3,
                    risk_free_source="synthetic")
        for change in ({"risk_free_returns": (.001,)}, {"risk_free_source": None},
                       {"calendar_id": None}, {"periods_per_year": None},
                       {"sharpe_basis": "unknown"}, {"risk_free_returns": (float("nan"),) * 3},
                       {"sharpe_basis": "legacy_net_rf0_v1"}):
            with self.subTest(change=change), self.assertRaises(ResearchInputError):
                build_unified_net_report((.01, -.01, .02), **(base | change))

    def test_explicit_constant_excess_and_short_sample_stay_undefined(self):
        options = dict(sharpe_basis="net_wealth_excess_sharpe_v2", calendar_id="XNYS",
                       periods_per_year=252, risk_free_source="synthetic")
        constant = build_unified_net_report((.001,) * 30, risk_free_returns=(.001,) * 30, **options)
        self.assertIsNone(constant.metric("sharpe_per_period").value)
        self.assertEqual(constant.metric("sharpe_per_period").reason_code, "zero_variance")
        self.assertIsNone(constant.metric("net_calmar_ratio").value)
        short = build_unified_net_report((.01, -.01, .02), risk_free_returns=(0.,) * 3, **options)
        self.assertEqual(short.metric("sharpe_per_period").reason_code, "insufficient_observations")
        self.assertEqual(short.metric("deflated_sharpe_ratio").reason_code, "missing_trial_evidence")

    def test_explicit_excess_sharpe_does_not_change_net_wealth(self):
        net = (.01, -.01, .02)
        legacy = build_unified_net_report(net, min_observations=3, periods_per_year=252)
        report = build_unified_net_report(
            net, min_observations=3, periods_per_year=252,
            sharpe_basis="net_wealth_excess_sharpe_v2", calendar_id="XNYS",
            risk_free_returns=(.001,) * 3, risk_free_source="synthetic-period-rf")
        self.assertAlmostEqual(report.metric("sharpe_per_period").value, 1.7 / math.sqrt(21))
        for name in ("net_log_growth_per_period", "net_cagr", "max_drawdown"):
            self.assertEqual(report.metric(name).value, legacy.metric(name).value)
        self.assertNotEqual(report.to_dict(), legacy.to_dict())
        self.assertEqual(report.metric("sharpe_per_period").details["risk_free_source"],
                         "synthetic-period-rf")

    def test_explicit_missing_rf_only_disables_sharpe_inference(self):
        report = build_unified_net_report(
            (.01, -.01, .02), min_observations=3, periods_per_year=252,
            sharpe_basis="net_wealth_excess_sharpe_v2", calendar_id="XNYS")
        for name in ("sharpe_per_period", "probabilistic_sharpe_ratio", "deflated_sharpe_ratio",
                     "minimum_track_record_periods"):
            self.assertIsNone(report.metric(name).value)
            self.assertEqual(report.metric(name).reason_code, "missing_risk_free_returns")
        self.assertTrue(report.metric("net_cagr").computed)
        self.assertTrue(report.metric("max_drawdown").computed)

    def test_variable_rf_is_shared_by_all_sharpe_inference_only(self):
        net = (.01, -.01, .02) * 12
        rf = (.001, .002, -.001) * 12
        trials = TrialEvidence(3, .02, "a" * 64)
        explicit = build_unified_net_report(
            net, trials=trials, periods_per_year=252, calendar_id="synthetic",
            sharpe_basis="net_wealth_excess_sharpe_v2", risk_free_returns=rf,
            risk_free_source="synthetic-varying-rf")
        oracle = build_unified_net_report(tuple(r-f for r, f in zip(net, rf)), trials=trials)
        for name in ("sharpe_per_period", "probabilistic_sharpe_ratio", "deflated_sharpe_ratio",
                     "minimum_track_record_periods"):
            self.assertEqual(explicit.metric(name).value, oracle.metric(name).value)
            self.assertEqual(explicit.metric(name).status, oracle.metric(name).status)

    def test_analytic_growth_cost_drag_sharpe_and_drawdown(self):
        net = (.1, -.1, .05)
        gross = (.11, -.08, .05)
        report = build_unified_net_report(net, gross_returns=gross, min_observations=3)
        self.assertAlmostEqual(report.metric("net_log_growth_per_period").value,
                               math.log(1.1 * .9 * 1.05) / 3)
        self.assertAlmostEqual(report.metric("cost_log_drag_per_period").value,
                               math.log(1.11 * .92 / (1.1 * .9)) / 3)
        self.assertAlmostEqual(report.metric("sharpe_per_period").value,
                               (sum(net) / len(net)) / stdev(net))
        self.assertAlmostEqual(report.metric("max_drawdown").value, -.1)
        self.assertEqual(report.volatility_ddof, 1)
        self.assertFalse(report.live_ready)
        self.assertTrue(report.no_order)
        self.assertEqual(report.status, "DEVELOPMENT_ONLY")

    def test_initial_nav_is_in_drawdown(self):
        report = build_unified_net_report((-.1, .01))
        self.assertAlmostEqual(report.metric("max_drawdown").value, -.1)

    def test_compounding_growth_can_be_negative_despite_positive_mean(self):
        report = build_unified_net_report((.21, -.2))
        self.assertGreater((.21 - .2) / 2, 0)
        self.assertLess(report.metric("net_log_growth_per_period").value, 0)

    def test_cvar_has_exact_fractional_five_percent_mass(self):
        report = build_unified_net_report((-.2, -.1) + (.01,) * 19)
        result = report.metric("cvar95_return_per_period")
        self.assertAlmostEqual(result.value, (-.2 - .1 * .05) / 1.05)
        self.assertAlmostEqual(result.details["tail_observation_mass"], 1.05)
        self.assertEqual(result.details["fully_weighted_observations"], 1)

    def test_small_sample_and_tied_cvar_are_descriptive(self):
        small = build_unified_net_report((-.2, .1, .3)).metric("cvar95_return_per_period")
        self.assertAlmostEqual(small.value, -.2)
        tied = build_unified_net_report((-.2, -.2) + (.1,) * 38).metric("cvar95_return_per_period")
        self.assertAlmostEqual(tied.value, -.2)

    def test_missing_cost_and_trial_data_are_missing_not_zero(self):
        report = build_unified_net_report((.01, -.012, .01) * 20)
        for name, reason in (("deflated_sharpe_ratio", "missing_trial_evidence"),
                             ("cost_log_drag_per_period", "missing_gross_returns")):
            result = report.metric(name)
            self.assertEqual(result.status, "UNCOMPUTABLE")
            self.assertIsNone(result.value)
            self.assertEqual(result.reason_code, reason)

    def test_dsr_uses_the_cumulative_total_without_a_downward_override(self):
        returns = (.01, -.012, .01) * 20
        a = build_unified_net_report(returns, trials=TrialEvidence(48, .02, "a" * 64))
        b = build_unified_net_report(returns, trials=TrialEvidence(480, .02, "b" * 64))
        self.assertLess(b.metric("deflated_sharpe_ratio").value,
                        a.metric("deflated_sharpe_ratio").value)
        self.assertEqual(a.metric("deflated_sharpe_ratio").details["cumulative_trials"], 48)
        self.assertEqual(a.trial_ledger_sha256, "a" * 64)

    def test_trial_provenance_validation_and_zero_variance(self):
        for total, variance, digest in ((True, .01, "a" * 64), (48., .01, "a" * 64),
                                        (48, -.01, "a" * 64), (48, .01, "unverified")):
            with self.subTest(total=total, variance=variance, digest=digest), self.assertRaises(ResearchInputError):
                TrialEvidence(total, variance, digest)
        report = build_unified_net_report((.01, -.012, .01) * 20,
                                          trials=TrialEvidence(48, 0, "a" * 64))
        self.assertEqual(report.metric("deflated_sharpe_ratio").reason_code,
                         "zero_trial_sharpe_variance")

    def test_mintrl_inverts_the_same_psr_moments(self):
        report = build_unified_net_report((.01, -.012, .005) * 20)
        result = report.metric("minimum_track_record_periods")
        self.assertEqual(result.status, "COMPUTED")
        sr = report.metric("sharpe_per_period").value
        v = result.details["sharpe_variance_term"]
        n = result.value
        probability = NormalDist().cdf(sr * math.sqrt(n - 1) / math.sqrt(v))
        previous = NormalDist().cdf(sr * math.sqrt(n - 2) / math.sqrt(v))
        self.assertGreaterEqual(probability, .95)
        self.assertLess(previous, .95)
        self.assertIn("independent_stationary_observations", result.details["assumptions"])

    def test_unavailable_inference_never_becomes_zero(self):
        for returns, reason in (((.01,) * 40, "zero_variance"),
                                ((.01, -.01), "insufficient_observations"),
                                ((-.01, .002, -.003) * 20, "sharpe_not_above_benchmark")):
            result = build_unified_net_report(returns).metric("minimum_track_record_periods")
            self.assertEqual(result.reason_code, reason)
            self.assertIsNone(result.value)

    def test_invalid_or_misaligned_returns_reject_without_filling(self):
        for values in ((), (True,), (float("nan"),), (-1.,)):
            with self.subTest(values=values), self.assertRaises(ResearchInputError):
                build_unified_net_report(values)
        with self.assertRaises(ResearchInputError):
            build_unified_net_report((.1, -.1), gross_returns=(.1,))
        with self.assertRaises(ResearchInputError):
            build_unified_net_report((.1,), gross_returns=(.09,))
        for confidence in (.5, 1., True):
            with self.assertRaises(ResearchInputError):
                build_unified_net_report((.1,), confidence=confidence)

    def test_numeric_overflow_is_uncomputable_not_a_crash(self):
        report = build_unified_net_report((.01, -.012, .01) * 20,
                                          trials=TrialEvidence(10 ** 400, .02, "a" * 64))
        self.assertIsNone(report.metric("deflated_sharpe_ratio").value)
        self.assertEqual(report.metric("deflated_sharpe_ratio").reason_code, "numerical_failure")
        extreme = build_unified_net_report((1e300, -0.1, 1e300) * 20)
        self.assertIsNone(extreme.metric("probabilistic_sharpe_ratio").value)

    def test_entries_use_existing_v1_contract_and_serialization_is_finite(self):
        report = build_unified_net_report((.01, -.012, .01) * 20)
        entries = report.metric_entries(scenario_multiplier=1.)
        self.assertEqual(len(entries), 8)
        self.assertTrue(all(e.value is None or math.isfinite(e.value) for e in entries))
        self.assertEqual(report.to_dict()["status"], "DEVELOPMENT_ONLY")
        for change in ({"live_ready": True}, {"no_order": False}, {"status": "LIVE"},
                       {"volatility_ddof": 0}):
            with self.subTest(change=change), self.assertRaises(ResearchInputError):
                replace(report, **change)

    def test_zero_cost_compounding_roundoff_preserves_net_and_explains_drag(self):
        # CostModel/cost_stress retain this ordering for bitwise compatibility.
        gross = (.1, -1e-17, -.1)
        net = tuple((1 + r) - 1 for r in gross)
        self.assertGreater(net[0], gross[0])
        self.assertGreater(net[1], gross[1])
        report = build_unified_net_report(net, gross_returns=gross)
        unchanged = build_unified_net_report(net)
        self.assertEqual(report.metric("net_log_growth_per_period"),
                         unchanged.metric("net_log_growth_per_period"))
        self.assertEqual(report.metric("max_drawdown"), unchanged.metric("max_drawdown"))
        drag = report.metric("cost_log_drag_per_period")
        self.assertGreaterEqual(drag.value, 0)
        self.assertEqual(drag.details["roundoff_negative_cost_pairs_zeroed"], 3)
        self.assertEqual(drag.details["negative_cost_tolerance_ulps"], 4)

    def test_material_negative_cost_is_rejected_even_after_roundoff_allowance(self):
        with self.assertRaises(ResearchInputError):
            build_unified_net_report((.1 + 1e-12,), gross_returns=(.1,))
        with self.assertRaises(ResearchInputError):
            build_unified_net_report((1e-12,), gross_returns=(0.,))
        unit = math.ulp(1.1)
        allowed = build_unified_net_report((.1 + 4 * unit,), gross_returns=(.1,))
        self.assertEqual(allowed.metric("cost_log_drag_per_period").value, 0)
        with self.assertRaises(ResearchInputError):
            build_unified_net_report((.1 + 5 * unit,), gross_returns=(.1,))
        # One return-scale ULP doubles surviving wealth near -1; do not
        # forgive that as a tiny cost difference at the wrong scale.
        near_ruin = math.nextafter(-1., 0.)
        with self.assertRaises(ResearchInputError):
            build_unified_net_report((math.nextafter(near_ruin, 0.),), gross_returns=(near_ruin,))


if __name__ == "__main__":
    unittest.main()
