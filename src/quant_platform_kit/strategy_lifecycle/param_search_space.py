"""Parameter search space definitions per strategy.

Each strategy declares which parameters are tunable, their types, and valid ranges.
"""

from __future__ import annotations

from collections.abc import Mapping

from quant_platform_kit.strategy_lifecycle.contracts import ParamDimension, ParamSearchSpace


# ── US Equity strategies ─────────────────────────────────────────────


GLOBAL_ETF_ROTATION_SPACE = ParamSearchSpace(
    strategy_profile="global_etf_rotation",
    domain="us_equity",
    dimensions={
        "rotation_top_n": ParamDimension(
            name="rotation_top_n",
            param_type="int",
            bounds=(2, 8),
            step=1,
            current_value=4,
        ),
        "momentum_window": ParamDimension(
            name="momentum_window",
            param_type="int",
            bounds=(20, 120),
            step=10,
            current_value=63,
        ),
        "volatility_window": ParamDimension(
            name="volatility_window",
            param_type="int",
            bounds=(10, 63),
            step=5,
            current_value=21,
        ),
        "weight_scheme": ParamDimension(
            name="weight_scheme",
            param_type="choice",
            choices=("equal", "inverse_vol", "momentum_scaled"),
            current_value="inverse_vol",
        ),
    },
)

TQQQ_GROWTH_INCOME_SPACE = ParamSearchSpace(
    strategy_profile="tqqq_growth_income",
    domain="us_equity",
    dimensions={
        "equity_portion": ParamDimension(
            name="equity_portion",
            param_type="float",
            bounds=(0.30, 0.80),
            step=0.05,
            current_value=0.60,
        ),
        "income_portion": ParamDimension(
            name="income_portion",
            param_type="float",
            bounds=(0.10, 0.50),
            step=0.05,
            current_value=0.30,
        ),
        "rebalance_threshold": ParamDimension(
            name="rebalance_threshold",
            param_type="float",
            bounds=(0.05, 0.20),
            step=0.025,
            current_value=0.10,
        ),
    },
)

SOXL_SOXX_TREND_SPACE = ParamSearchSpace(
    strategy_profile="soxl_soxx_trend_income",
    domain="us_equity",
    dimensions={
        "trend_signal_window": ParamDimension(
            name="trend_signal_window",
            param_type="int",
            bounds=(21, 126),
            step=5,
            current_value=63,
        ),
        "income_override_pct": ParamDimension(
            name="income_override_pct",
            param_type="float",
            bounds=(0.20, 0.60),
            step=0.05,
            current_value=0.40,
        ),
    },
)


# ── Crypto strategies ────────────────────────────────────────────────


CRYPTO_LIVE_POOL_ROTATION_SPACE = ParamSearchSpace(
    strategy_profile="crypto_live_pool_rotation",
    domain="crypto",
    dimensions={
        "trend_pool_size": ParamDimension(
            name="trend_pool_size",
            param_type="int",
            bounds=(3, 10),
            step=1,
            current_value=5,
        ),
        "rotation_top_n": ParamDimension(
            name="rotation_top_n",
            param_type="int",
            bounds=(1, 5),
            step=1,
            current_value=3,
        ),
        "weight_mode": ParamDimension(
            name="weight_mode",
            param_type="choice",
            choices=("inverse_vol", "equal"),
            current_value="inverse_vol",
        ),
        "rebalance_frequency_hours": ParamDimension(
            name="rebalance_frequency_hours",
            param_type="int",
            bounds=(4, 48),
            step=4,
            current_value=24,
        ),
    },
)

BTC_DCA_SPACE = ParamSearchSpace(
    strategy_profile="crypto_btc_dca",
    domain="crypto",
    dimensions={
        "dca_frequency_days": ParamDimension(
            name="dca_frequency_days",
            param_type="int",
            bounds=(1, 14),
            step=1,
            current_value=7,
        ),
        "dca_amount_pct": ParamDimension(
            name="dca_amount_pct",
            param_type="float",
            bounds=(0.01, 0.10),
            step=0.01,
            current_value=0.05,
        ),
    },
)


# ── HK Equity strategies ─────────────────────────────────────────────


HK_ETF_TACTICAL_ROTATION_SPACE = ParamSearchSpace(
    strategy_profile="hk_global_etf_tactical_rotation",
    domain="hk_equity",
    dimensions={
        "rotation_top_n": ParamDimension(
            name="rotation_top_n",
            param_type="int",
            bounds=(2, 6),
            step=1,
            current_value=3,
        ),
        "momentum_window": ParamDimension(
            name="momentum_window",
            param_type="int",
            bounds=(20, 120),
            step=10,
            current_value=63,
        ),
    },
)


# ── CN Equity strategies ─────────────────────────────────────────────


CN_INDUSTRY_ETF_ROTATION_SPACE = ParamSearchSpace(
    strategy_profile="cn_industry_etf_rotation",
    domain="cn_equity",
    dimensions={
        "rotation_top_n": ParamDimension(
            name="rotation_top_n",
            param_type="int",
            bounds=(2, 8),
            step=1,
            current_value=5,
        ),
        "momentum_window": ParamDimension(
            name="momentum_window",
            param_type="int",
            bounds=(10, 60),
            step=5,
            current_value=20,
        ),
    },
)

CN_STOCK_MOMENTUM_ROTATION_SPACE = ParamSearchSpace(
    strategy_profile="cn_stock_momentum_rotation",
    domain="cn_equity",
    dimensions={
        "selection_count": ParamDimension(
            name="selection_count",
            param_type="int",
            bounds=(5, 20),
            step=1,
            current_value=10,
        ),
        "momentum_window": ParamDimension(
            name="momentum_window",
            param_type="int",
            bounds=(10, 60),
            step=5,
            current_value=20,
        ),
    },
)


# ── Registry ─────────────────────────────────────────────────────────


_BUILTIN_SPACES: Mapping[str, ParamSearchSpace] = {
    "global_etf_rotation": GLOBAL_ETF_ROTATION_SPACE,
    "tqqq_growth_income": TQQQ_GROWTH_INCOME_SPACE,
    "soxl_soxx_trend_income": SOXL_SOXX_TREND_SPACE,
    "crypto_live_pool_rotation": CRYPTO_LIVE_POOL_ROTATION_SPACE,
    "crypto_btc_dca": BTC_DCA_SPACE,
    "hk_global_etf_tactical_rotation": HK_ETF_TACTICAL_ROTATION_SPACE,
    "cn_industry_etf_rotation": CN_INDUSTRY_ETF_ROTATION_SPACE,
    "cn_stock_momentum_rotation": CN_STOCK_MOMENTUM_ROTATION_SPACE,
}


def get_search_space(strategy_profile: str) -> ParamSearchSpace | None:
    """Look up the built-in parameter search space for a strategy."""
    return _BUILTIN_SPACES.get(strategy_profile)
