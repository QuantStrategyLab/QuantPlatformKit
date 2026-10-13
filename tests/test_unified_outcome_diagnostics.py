"""Analytic, synthetic-only outcome diagnostics; no trade or policy inference."""

import json
import math
import unittest

from quant_platform_kit.research_stats._validation import ResearchInputError
from quant_platform_kit.research_stats.unified_report import build_unified_net_report


NAMES = (
    "net_win_rate_ex_zero_per_period",
    "net_payoff_ratio_per_period",
    "net_profit_factor_per_period",
    "mean_net_return_per_period",
)


class OutcomeDiagnosticsTests(unittest.TestCase):
    def report(self, values):
        return build_unified_net_report(values, include_outcome_diagnostics=True)

    def test_payoff_is_not_profit_factor_and_zero_days_are_explicit(self):
        report = self.report((.02, .02, -.01, 0.))
        self.assertAlmostEqual(report.metric(NAMES[0]).value, 2 / 3)
        self.assertAlmostEqual(report.metric(NAMES[1]).value, 2.)
        self.assertAlmostEqual(report.metric(NAMES[2]).value, 4.)
        self.assertAlmostEqual(report.metric(NAMES[3]).value, .0075)
        for name in NAMES:
            details = report.metric(name).details
            self.assertEqual(details["positive_observations"], 2)
            self.assertEqual(details["negative_observations"], 1)
            self.assertEqual(details["zero_observations"], 1)
            self.assertEqual(details["aggregation_level"], "return_observations_not_trades")

    def test_expected_mean_includes_zero_periods(self):
        a = self.report((.02, -.01))
        b = self.report((.02, -.01, 0., 0.))
        self.assertEqual(a.metric(NAMES[0]).value, .5)
        self.assertEqual(b.metric(NAMES[0]).value, .5)
        self.assertEqual(a.metric(NAMES[0]).details["zero_observations"], 0)
        self.assertEqual(b.metric(NAMES[0]).details["zero_observations"], 2)
        for name in NAMES[:3]:
            self.assertEqual(a.metric(name).value, b.metric(name).value)
        self.assertAlmostEqual(a.metric(NAMES[3]).value, .005)
        self.assertAlmostEqual(b.metric(NAMES[3]).value, .0025)

    def test_high_win_rate_can_have_negative_net_expectation(self):
        report = self.report((.01,) * 9 + (-.2,))
        self.assertAlmostEqual(report.metric(NAMES[0]).value, .9)
        self.assertAlmostEqual(report.metric(NAMES[1]).value, .05)
        self.assertAlmostEqual(report.metric(NAMES[2]).value, .45)
        self.assertAlmostEqual(report.metric(NAMES[3]).value, -.011)

    def test_all_positive_periods_do_not_invent_a_loss_distribution(self):
        report = self.report((.01, .02, 0.))
        self.assertEqual(report.metric(NAMES[0]).value, 1.)
        for name in NAMES[1:3]:
            metric = report.metric(name)
            self.assertEqual(metric.status, "UNCOMPUTABLE")
            self.assertIsNone(metric.value)
            self.assertEqual(metric.reason_code, "no_loss_observations")

    def test_all_negative_periods_have_zero_profit_factor_but_no_average_win(self):
        report = self.report((-.01, -.02, 0.))
        self.assertEqual(report.metric(NAMES[0]).value, 0.)
        self.assertEqual(report.metric(NAMES[2]).value, 0.)
        self.assertEqual(report.metric(NAMES[1]).reason_code, "no_win_observations")
        self.assertIsNone(report.metric(NAMES[1]).value)
        self.assertAlmostEqual(report.metric(NAMES[3]).value, -.01)

    def test_all_zero_periods_have_known_zero_mean_and_undefined_ratios(self):
        report = self.report((0., 0., 0.))
        self.assertEqual(report.metric(NAMES[3]).value, 0.)
        for name in NAMES[:3]:
            self.assertEqual(report.metric(name).status, "UNCOMPUTABLE")
            self.assertIsNone(report.metric(name).value)
        self.assertEqual(report.metric(NAMES[0]).reason_code, "no_nonzero_observations")

    def test_enabling_diagnostics_preserves_all_original_metric_results(self):
        values = (.01, -.012, .005) * 20
        baseline = build_unified_net_report(values)
        enabled = self.report(values)
        self.assertEqual(len(baseline.metrics), 8)
        self.assertEqual(enabled.metrics[:8], baseline.metrics)
        self.assertEqual(len(enabled.metrics), 12)
        self.assertFalse(enabled.live_ready)
        self.assertTrue(enabled.no_order)
        self.assertEqual(enabled.status, "DEVELOPMENT_ONLY")
        self.assertEqual(baseline, build_unified_net_report(values, include_outcome_diagnostics=False))

    def test_flag_must_be_boolean(self):
        for flag in (1, 0, "true", None):
            with self.subTest(flag=flag), self.assertRaises(ResearchInputError):
                build_unified_net_report((.01, -.01), include_outcome_diagnostics=flag)

    def test_invalid_returns_keep_existing_rejection(self):
        for values in ((), (True,), (float("nan"),), (float("inf"),), (-1.,)):
            with self.subTest(values=values), self.assertRaises(ResearchInputError):
                self.report(values)

    def test_unrepresentable_ratio_is_missing_and_serialization_is_finite(self):
        report = self.report((1e300, -1e-300, 0.))
        for name in NAMES[1:3]:
            self.assertEqual(report.metric(name).reason_code, "numerical_failure")
            self.assertIsNone(report.metric(name).value)
        self.assertTrue(all(x.value is None or math.isfinite(x.value) for x in report.metrics))
        json.dumps(report.to_dict(), allow_nan=False)

    def test_generator_input_is_consumed_once(self):
        report = self.report(x for x in (.02, .02, -.01, 0.))
        self.assertEqual(report.observations, 4)
        self.assertAlmostEqual(report.metric(NAMES[2]).value, 4.)

    def test_nonzero_mean_underflow_is_not_a_fabricated_zero(self):
        report = self.report((math.nextafter(0., 1.), 0.))
        result = report.metric(NAMES[3])
        self.assertEqual(result.status, "UNCOMPUTABLE")
        self.assertIsNone(result.value)
        self.assertEqual(result.reason_code, "numerical_failure")

    def test_exact_cancellation_has_a_known_zero_mean(self):
        result = self.report((.01, -.01)).metric(NAMES[3])
        self.assertEqual(result.status, "COMPUTED")
        self.assertEqual(result.value, 0.)


if __name__ == "__main__":
    unittest.main()
