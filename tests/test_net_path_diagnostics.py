"""Hand-calculated, synthetic-only net-return path diagnostic acceptance."""

import json
import math
import os
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from quant_platform_kit.research_stats._validation import ResearchInputError
from quant_platform_kit.research_stats.net_path_diagnostics import (
    build_net_path_diagnostics,
)


UNDERWATER = "longest_underwater_run_observations"
RECOVERED = "longest_recovered_drawdown_duration_observations"
TERMINAL = "terminal_underwater_run_observations"
NEGATIVE = "longest_negative_net_return_run_observations"


class NetPathDiagnosticsTests(unittest.TestCase):
    def assert_counts(self, returns, underwater, recovered, terminal, negative):
        report = build_net_path_diagnostics(returns)
        self.assertEqual(report.observations, len(returns))
        for name, expected in ((UNDERWATER, underwater), (RECOVERED, recovered),
                               (TERMINAL, terminal), (NEGATIVE, negative)):
            result = report.metric(name)
            self.assertEqual(result.value, expected, name)
            if expected is not None:
                self.assertEqual(result.status, "COMPUTED", name)
                self.assertIs(type(result.value), int, name)
                self.assertIsNone(result.reason_code, name)
        return report

    def test_initial_nav_participates_without_adding_an_observation(self):
        # NAV: initial 1, .5, .5, 1; two below-peak observations, but
        # three return observations from peak to the recovered peak.
        report = self.assert_counts((-.5, 0., 1.), 2, 3, 0, 1)
        self.assertEqual(report.to_dict()["initial_nav"], 1.)
        self.assertFalse(report.metric(TERMINAL).details["right_censored"])

    def test_first_loss_is_underwater_even_without_a_prior_positive_return(self):
        report = self.assert_counts((-.5,), 1, None, 1, 1)
        self.assertTrue(report.metric(TERMINAL).details["right_censored"])

    def test_all_nonnegative_path_has_no_recovered_drawdown_sample(self):
        report = self.assert_counts((0., .25, 0., .5), 0, None, 0, 0)
        missing = report.metric(RECOVERED)
        self.assertEqual(missing.status, "UNCOMPUTABLE")
        self.assertEqual(missing.reason_code, "no_recovered_drawdown")
        self.assertFalse(report.metric(TERMINAL).details["right_censored"])

    def test_all_zero_path_does_not_invent_a_recovery(self):
        self.assert_counts((0., 0., 0.), 0, None, 0, 0)

    def test_zero_return_continues_an_underwater_run(self):
        self.assert_counts((-.5, 0., 0., 1.), 3, 4, 0, 1)

    def test_zero_return_at_peak_updates_the_latest_peak_index(self):
        # Tied high-water marks at indices 0, 1, 3, 4 and 6. Each drawdown
        # starts at the most recent tied peak, not an older plateau index.
        self.assert_counts((0., -.5, 1., 0., -.5, 1.), 1, 2, 0, 1)

    def test_recovered_duration_includes_the_recovery_observation(self):
        self.assert_counts((-.5, 1.), 1, 2, 0, 1)

    def test_recovery_can_overshoot_the_previous_peak(self):
        self.assert_counts((-.5, 2.), 1, 2, 0, 1)

    def test_new_high_then_repeated_completed_drawdowns(self):
        # NAV: 1, 1.5, .75, .75, 1.5, .75, 1.5.
        self.assert_counts((.5, -.5, 0., 1., -.5, 1.), 2, 3, 0, 1)

    def test_terminal_underwater_episode_is_right_censored(self):
        report = self.assert_counts((-.5, 0.), 2, None, 2, 1)
        self.assertTrue(report.metric(TERMINAL).details["right_censored"])

    def test_longest_run_and_recovered_duration_are_distinct(self):
        # NAV: 1, 1, .5, .25, 1, .5, .5, .375. The completed episode
        # lasts three return observations; the final three remain censored.
        report = self.assert_counts((0., -.5, -.5, 3., -.5, 0., -.25), 3, 3, 3, 2)
        self.assertTrue(report.metric(TERMINAL).details["right_censored"])

    def test_longer_terminal_episode_does_not_become_a_recovered_sample(self):
        self.assert_counts((-.5, 1., -.5, 0., 0., 0.), 4, 2, 4, 1)

    def test_negative_return_streak_is_not_a_drawdown_or_trade_streak(self):
        report = build_net_path_diagnostics((-.5, -.5, 0., -.25, .5, -.125, -.125, -.125))
        self.assertEqual(report.metric(NEGATIVE).value, 3)
        self.assertEqual(report.metric(UNDERWATER).value, 8)

    def test_zero_and_positive_returns_both_break_strict_negative_streaks(self):
        self.assert_counts((-.5, -.5, 0., -.25, 7., -.5, -.5), 4, 5, 2, 2)

    def test_positive_returns_can_leave_the_path_underwater(self):
        self.assert_counts((-.5, .25, .25), 3, None, 3, 1)

    def test_smallest_negative_float_is_not_rounded_into_a_peak(self):
        self.assert_counts((-math.ulp(0.), 0.), 2, None, 2, 1)

    def test_small_returns_after_a_large_gain_do_not_disappear(self):
        self.assert_counts((1e300, -1e-100, 2e-100), 1, 2, 0, 1)

    def test_extreme_positive_wealth_does_not_require_float_nav(self):
        self.assert_counts((1e300, 1e300, -.5, 1.), 1, 2, 0, 1)

    def test_extreme_drawdown_does_not_underflow_to_a_false_zero_nav(self):
        almost_ruin = math.nextafter(-1., 0.)
        self.assert_counts((almost_ruin,) * 24 + (0.,), 25, None, 25, 24)

    def test_supplied_binary_float_returns_are_not_rounded_to_force_recovery(self):
        # The exact supplied float -.2 is slightly less than -1/5. The
        # exact product (1 + -.2)*(1 + .25) is below 1, even though a
        # rounded float wealth product equals 1. No recovery tolerance.
        self.assert_counts((-.2, .25), 2, None, 2, 1)

    def test_window_truncation_never_claims_global_history_or_recovery(self):
        full = self.assert_counts((-.5, 1., -.5, 0., 0.), 3, 2, 3, 1)
        suffix = self.assert_counts((0., 0.), 0, None, 0, 0)
        for report in (full, suffix):
            payload = report.to_dict()
            self.assertEqual(payload["scope"], "window_only")
            self.assertEqual(payload["prior_history"], "unknown")
        # The standalone suffix is not evidence that the real earlier
        # underwater episode recovered; its normalized start is local only.
        self.assertIsNone(suffix.metric(RECOVERED).value)

    def test_repeated_calls_do_not_carry_an_earlier_peak_or_state(self):
        first = build_net_path_diagnostics((-.5, 0.)).to_dict()
        build_net_path_diagnostics((1e300, -.5, 1.))
        self.assertEqual(build_net_path_diagnostics((-.5, 0.)).to_dict(), first)

    def test_invalid_inputs_are_rejected_without_filling_or_dropping(self):
        for values in ((), None, 3, "0.1", (None,), (True,), (False,),
                       ("0.1",), (float("nan"),), (float("inf"),),
                       (-float("inf"),), (-1.,), (-1.01,), (.1, None, -.1)):
            with self.subTest(values=values), self.assertRaises(ResearchInputError):
                build_net_path_diagnostics(values)

    def test_generator_is_consumed_once_without_changing_input_order(self):
        seen = []

        def values():
            for value in (-.5, 0., 1.):
                seen.append(value)
                yield value

        report = build_net_path_diagnostics(values())
        self.assertEqual(seen, [-.5, 0., 1.])
        self.assertEqual(report.metric(RECOVERED).value, 3)

    def test_original_mutable_input_is_unchanged(self):
        values = [-.5, 0., 1.]
        original = list(values)
        build_net_path_diagnostics(values)
        self.assertEqual(values, original)

    def test_arithmetic_failure_preserves_unknown_path_metrics_and_negative_count(self):
        with patch("quant_platform_kit.research_stats.net_path_diagnostics.Fraction",
                   side_effect=OverflowError("synthetic arithmetic failure")):
            report = build_net_path_diagnostics((-.5, 0., -.25))
        for name in (UNDERWATER, RECOVERED, TERMINAL):
            result = report.metric(name)
            self.assertEqual(result.status, "UNCOMPUTABLE")
            self.assertIsNone(result.value)
            self.assertEqual(result.reason_code, "numerical_failure")
        self.assertIsNone(report.metric(TERMINAL).details["right_censored"])
        self.assertEqual(report.metric(NEGATIVE).value, 1)

    def test_envelope_is_report_only_and_cannot_grant_authority(self):
        report = build_net_path_diagnostics((-.5, 1.))
        payload = report.to_dict()
        self.assertEqual(payload["schema_version"], "qsl.net_path_diagnostics.v1")
        self.assertEqual(payload["status"], "DEVELOPMENT_ONLY")
        self.assertEqual(payload["purpose"], "REPORT_ONLY")
        self.assertTrue(payload["no_order"])
        self.assertFalse(payload["live_ready"])
        self.assertEqual(payload["unit"], "return_observations")
        self.assertEqual(len(payload["metrics"]), 4)
        for changes in ({"no_order": False}, {"live_ready": True}, {"status": "LIVE"},
                        {"purpose": "EXECUTE"}, {"scope": "global_history"},
                        {"prior_history": "verified"}, {"unit": "days"},
                        {"initial_nav": 2.}, {"initial_nav": True},
                        {"schema_version": "qsl.unified_net_report.v1"}):
            with self.subTest(changes=changes), self.assertRaises(ResearchInputError):
                replace(report, **changes)

    def test_serialization_contains_only_finite_values_and_integer_observation_counts(self):
        report = build_net_path_diagnostics((-.5, 0., 1., -.25))
        payload = report.to_dict()
        json.dumps(payload, allow_nan=False)
        for result in payload["metrics"]:
            self.assertIs(type(result["value"]), int)
            self.assertEqual(result["details"]["unit"], "return_observations")
            self.assertEqual(result["details"]["input_basis"], "same_period_net_returns")
            self.assertTrue(result["details"]["descriptive_only"])

    def test_import_and_calculation_need_no_numpy_pandas_or_io(self):
        root = Path(__file__).resolve().parents[1]
        probe = """
import sys, socket, subprocess, urllib.request, builtins, os
from pathlib import Path
sys.modules['numpy'] = None
sys.modules['pandas'] = None
def forbidden(*args, **kwargs):
    raise AssertionError('unexpected network or subprocess use')
socket.socket = forbidden
socket.getaddrinfo = forbidden
subprocess.run = forbidden
subprocess.Popen = forbidden
urllib.request.urlopen = forbidden
from quant_platform_kit.research_stats.net_path_diagnostics import build_net_path_diagnostics
builtins.open = forbidden
os.open = forbidden
Path.open = forbidden
report = build_net_path_diagnostics((-.5, 0., 1.))
assert report.metric('longest_recovered_drawdown_duration_observations').value == 3
assert report.no_order is True and report.live_ready is False
"""
        process = subprocess.run(
            [sys.executable, "-S", "-c", probe], cwd=root,
            env={"PYTHONPATH": str(root / "src"), "PATH": os.environ.get("PATH", "")},
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)


if __name__ == "__main__":
    unittest.main()
