from __future__ import annotations

import unittest

from quant_platform_kit.strategy_contracts import StrategyManifest, StrategyRuntimeAdapter
from quant_platform_kit.ibkr.runtime_inputs import (
    build_ibkr_strategy_context,
    build_market_history_inputs,
    build_semiconductor_rotation_indicators,
    build_semiconductor_rotation_inputs,
)


class IbkrRuntimeInputsTests(unittest.TestCase):
    def test_build_market_history_inputs_wraps_loader(self) -> None:
        def loader(*_args, **_kwargs):
            return None

        payload = build_market_history_inputs(loader)

        self.assertEqual(set(payload), {"market_history"})
        self.assertIs(payload["market_history"], loader)

    def test_build_ibkr_strategy_context_uses_required_inputs_and_portfolio(self) -> None:
        entrypoint = type(
            "Entrypoint",
            (),
            {
                "manifest": StrategyManifest(
                    profile="semiconductor_rotation_income",
                    domain="us_equity",
                    display_name="SOXL/SOXX Semiconductor Trend Income",
                    description="test",
                    required_inputs=frozenset({"derived_indicators", "portfolio_snapshot"}),
                )
            },
        )()
        runtime_adapter = StrategyRuntimeAdapter(portfolio_input_name="portfolio_snapshot")
        portfolio_snapshot = object()

        ctx = build_ibkr_strategy_context(
            entrypoint=entrypoint,
            runtime_adapter=runtime_adapter,
            as_of="2026-04-09",
            market_inputs={"derived_indicators": {"soxl": {"price": 1.0}}},
            portfolio_snapshot=portfolio_snapshot,
            runtime_config={"translator": "noop"},
            current_holdings={"SOXL"},
            ib="fake-ib",
        )

        self.assertEqual(ctx.as_of, "2026-04-09")
        self.assertEqual(ctx.market_data["derived_indicators"]["soxl"]["price"], 1.0)
        self.assertIs(ctx.portfolio, portfolio_snapshot)
        self.assertEqual(ctx.state["current_holdings"], ("SOXL",))
        self.assertEqual(ctx.capabilities["broker_client"], "fake-ib")
        self.assertEqual(ctx.runtime_config["translator"], "noop")

    def test_build_semiconductor_rotation_indicators_uses_soxl_and_soxx_history(self) -> None:
        observed = []

        def fake_loader(_ib, symbol, duration="2 Y", bar_size="1 day"):
            observed.append((symbol, duration, bar_size))
            if symbol == "SOXL":
                return [100.0 + idx for idx in range(170)]
            if symbol == "SOXX":
                return [200.0 + idx for idx in range(20)]
            raise AssertionError(symbol)

        indicators = build_semiconductor_rotation_indicators(
            "fake-ib",
            fake_loader,
            trend_ma_window=150,
        )

        self.assertEqual(observed[0], ("SOXL", "220 D", "1 day"))
        self.assertEqual(observed[1], ("SOXX", "20 D", "1 day"))
        self.assertEqual(indicators["soxl"]["price"], 269.0)
        self.assertAlmostEqual(
            indicators["soxl"]["ma_trend"],
            sum(100.0 + idx for idx in range(20, 170)) / 150,
        )
        self.assertEqual(indicators["soxx"]["price"], 219.0)

    def test_build_semiconductor_rotation_inputs_wraps_derived_indicators(self) -> None:
        def fake_loader(_ib, symbol, duration="2 Y", bar_size="1 day"):
            if symbol == "SOXL":
                return [100.0] * 170
            if symbol == "SOXX":
                return [200.0] * 20
            raise AssertionError(symbol)

        payload = build_semiconductor_rotation_inputs(
            "fake-ib",
            fake_loader,
            trend_ma_window=150,
        )

        self.assertEqual(set(payload), {"derived_indicators"})
        self.assertEqual(payload["derived_indicators"]["soxl"]["price"], 100.0)
        self.assertEqual(payload["derived_indicators"]["soxx"]["price"], 200.0)

    def test_build_semiconductor_rotation_indicators_requires_sufficient_history(self) -> None:
        def fake_loader(_ib, symbol, duration="2 Y", bar_size="1 day"):
            if symbol == "SOXL":
                return [100.0] * 100
            if symbol == "SOXX":
                return [200.0] * 20
            raise AssertionError(symbol)

        with self.assertRaisesRegex(ValueError, "sufficient SOXL/SOXX history"):
            build_semiconductor_rotation_indicators(
                "fake-ib",
                fake_loader,
                trend_ma_window=150,
            )


if __name__ == "__main__":
    unittest.main()
