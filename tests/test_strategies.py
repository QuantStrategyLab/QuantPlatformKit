from __future__ import annotations

import unittest

from quant_platform_kit.common.strategies import (
    CRYPTO_DOMAIN,
    US_EQUITY_DOMAIN,
    StrategyDefinition,
    get_supported_profiles_for_platform,
    resolve_strategy_definition,
)


class StrategyContractsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy_definitions = {
            "global_etf_rotation": StrategyDefinition(
                profile="global_etf_rotation",
                domain=US_EQUITY_DOMAIN,
                supported_platforms=frozenset({"ibkr", "schwab", "longbridge"}),
            ),
            "crypto_leader_rotation": StrategyDefinition(
                profile="crypto_leader_rotation",
                domain=CRYPTO_DOMAIN,
                supported_platforms=frozenset({"binance"}),
            ),
        }
        self.platform_supported_domains = {
            "ibkr": frozenset({US_EQUITY_DOMAIN}),
            "binance": frozenset({CRYPTO_DOMAIN}),
        }

    def test_get_supported_profiles_for_platform_filters_by_domain_and_platform(self) -> None:
        supported = get_supported_profiles_for_platform(
            self.strategy_definitions,
            self.platform_supported_domains,
            platform_id="ibkr",
        )

        self.assertEqual(supported, frozenset({"global_etf_rotation"}))

    def test_resolve_strategy_definition_uses_default_profile_when_allowed(self) -> None:
        definition = resolve_strategy_definition(
            None,
            platform_id="binance",
            strategy_definitions=self.strategy_definitions,
            platform_supported_domains=self.platform_supported_domains,
            default_profile="crypto_leader_rotation",
        )

        self.assertEqual(definition.profile, "crypto_leader_rotation")
        self.assertEqual(definition.domain, CRYPTO_DOMAIN)

    def test_resolve_strategy_definition_requires_explicit_when_requested(self) -> None:
        with self.assertRaisesRegex(EnvironmentError, "STRATEGY_PROFILE is required"):
            resolve_strategy_definition(
                None,
                platform_id="ibkr",
                strategy_definitions=self.strategy_definitions,
                platform_supported_domains=self.platform_supported_domains,
                require_explicit=True,
            )

    def test_resolve_strategy_definition_rejects_profile_outside_platform_domain(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported STRATEGY_PROFILE"):
            resolve_strategy_definition(
                "crypto_leader_rotation",
                platform_id="ibkr",
                strategy_definitions=self.strategy_definitions,
                platform_supported_domains=self.platform_supported_domains,
            )
