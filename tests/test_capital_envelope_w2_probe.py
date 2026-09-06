"""W2 read-only capital envelope + gate probe."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

from quant_platform_kit.risk.account_new_risk_gate import NewRiskDisposition
from quant_platform_kit.risk.capital_envelope_w2_probe import (
    format_probe_report,
    main,
    probe_capital_envelope_w2,
)


class ProbeCapitalEnvelopeW2Tests(unittest.TestCase):
    def test_healthy_equity_allows_new_risk(self) -> None:
        result = probe_capital_envelope_w2(40_000.0)
        self.assertTrue(result["w2_probe"])
        self.assertFalse(result["live_wired"])
        self.assertEqual(result["gate"]["disposition"], NewRiskDisposition.ALLOW_NEW_RISK.value)
        self.assertEqual(result["gate"]["reason_codes"], [])
        self.assertTrue(result["envelope"]["new_risk_allowed"])

    def test_drawdown_brake_prohibits_new_risk(self) -> None:
        result = probe_capital_envelope_w2(85_000.0, peak_equity_usd=100_000.0)
        self.assertEqual(result["gate"]["disposition"], NewRiskDisposition.NEW_RISK_PROHIBITED.value)
        self.assertIn("DRAWDOWN_BRAKE_TRIPPED", result["gate"]["reason_codes"])
        self.assertFalse(result["envelope"]["new_risk_allowed"])

    def test_format_probe_report_contains_disposition(self) -> None:
        result = probe_capital_envelope_w2(40_000.0)
        report = format_probe_report(result)
        self.assertIn("ALLOW_NEW_RISK", report)
        self.assertIn("not live-wired", report)

    def test_cli_json_output(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--equity", "40000", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertTrue(payload["w2_probe"])
        self.assertEqual(payload["gate"]["disposition"], "ALLOW_NEW_RISK")

    def test_cli_text_output(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--equity", "100000", "--drawdown", "0.10"])
        self.assertEqual(code, 0)
        self.assertIn("NEW_RISK_PROHIBITED", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
