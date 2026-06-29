from __future__ import annotations

import unittest

from quant_platform_kit.common.execution_capabilities import (
    FRACTIONAL_SHARE_EXECUTION_CAPABILITY,
    FRACTIONAL_SHARE_EXECUTION_SKIP_REASON,
    fractional_share_execution_unsupported_reason,
)
from quant_platform_kit.common.strategies import (
    PlatformCapabilityMatrix,
    StrategyCatalog,
    StrategyDefinition,
    US_EQUITY_DOMAIN,
    derive_eligible_profiles_for_platform,
)
from quant_platform_kit.common.strategy_contracts import StrategyRuntimeAdapter


class ExecutionCapabilitiesTests(unittest.TestCase):
    def test_fractional_share_execution_unsupported_reason(self) -> None:
        catalog = StrategyCatalog(
            definitions={
                "ibit_smart_dca": StrategyDefinition(
                    profile="ibit_smart_dca",
                    domain=US_EQUITY_DOMAIN,
                    supported_platforms=frozenset({"schwab"}),
                    required_inputs=frozenset({"portfolio_snapshot"}),
                    target_mode="value",
                    compatible_capabilities=frozenset({FRACTIONAL_SHARE_EXECUTION_CAPABILITY}),
                ),
                "tqqq_growth_income": StrategyDefinition(
                    profile="tqqq_growth_income",
                    domain=US_EQUITY_DOMAIN,
                    supported_platforms=frozenset({"schwab"}),
                    required_inputs=frozenset({"portfolio_snapshot"}),
                    target_mode="value",
                ),
            }
        )
        whole_share_matrix = PlatformCapabilityMatrix(
            platform_id="schwab",
            supported_domains=frozenset({US_EQUITY_DOMAIN}),
            supported_target_modes=frozenset({"value"}),
            supported_inputs=frozenset({"portfolio_snapshot"}),
            supported_capabilities=frozenset(),
        )
        fractional_matrix = PlatformCapabilityMatrix(
            platform_id="schwab",
            supported_domains=frozenset({US_EQUITY_DOMAIN}),
            supported_target_modes=frozenset({"value"}),
            supported_inputs=frozenset({"portfolio_snapshot"}),
            supported_capabilities=frozenset({FRACTIONAL_SHARE_EXECUTION_CAPABILITY}),
        )

        self.assertEqual(
            fractional_share_execution_unsupported_reason(
                "ibit_smart_dca",
                strategy_catalog=catalog,
                capability_matrix=whole_share_matrix,
            ),
            FRACTIONAL_SHARE_EXECUTION_SKIP_REASON,
        )
        self.assertIsNone(
            fractional_share_execution_unsupported_reason(
                "ibit_smart_dca",
                strategy_catalog=catalog,
                capability_matrix=fractional_matrix,
            )
        )
        self.assertIsNone(
            fractional_share_execution_unsupported_reason(
                "tqqq_growth_income",
                strategy_catalog=catalog,
                capability_matrix=whole_share_matrix,
            )
        )

    def test_capability_matrix_excludes_fractional_dca_profiles(self) -> None:
        catalog = StrategyCatalog(
            definitions={
                "ibit_smart_dca": StrategyDefinition(
                    profile="ibit_smart_dca",
                    domain=US_EQUITY_DOMAIN,
                    supported_platforms=frozenset({"schwab"}),
                    required_inputs=frozenset({"portfolio_snapshot"}),
                    target_mode="value",
                    compatible_capabilities=frozenset({FRACTIONAL_SHARE_EXECUTION_CAPABILITY}),
                ),
            }
        )
        matrix = PlatformCapabilityMatrix(
            platform_id="schwab",
            supported_domains=frozenset({US_EQUITY_DOMAIN}),
            supported_target_modes=frozenset({"value"}),
            supported_inputs=frozenset({"portfolio_snapshot"}),
            supported_capabilities=frozenset(),
        )
        adapters = {
            "ibit_smart_dca": StrategyRuntimeAdapter(
                available_inputs=frozenset({"portfolio_snapshot"}),
                available_capabilities=frozenset({FRACTIONAL_SHARE_EXECUTION_CAPABILITY}),
            ),
        }

        eligible = derive_eligible_profiles_for_platform(
            catalog,
            capability_matrix=matrix,
            runtime_adapter_loader=lambda profile: adapters[profile],
        )

        # ``fractional_share_execution`` is a soft capability — profiles that
        # require it are still eligible even when the platform lacks native
        # support (compat mode converts notional → whole-share orders).
        self.assertEqual(eligible, frozenset({"ibit_smart_dca"}))


if __name__ == "__main__":
    unittest.main()
