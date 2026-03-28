from __future__ import annotations

import numpy as np
import pandas as pd


def _daily_interval():
    try:
        from binance.client import Client  # type: ignore

        return Client.KLINE_INTERVAL_1DAY
    except Exception:
        return "1d"


def fetch_daily_indicators(client, symbol, lookback_days=420):
    klines = client.get_historical_klines(symbol, _daily_interval(), f"{lookback_days} days ago UTC")
    if not klines:
        return None

    df = pd.DataFrame(klines).iloc[:, :6]
    df.columns = ["time", "open", "high", "low", "close", "vol"]
    df[["high", "low", "close", "vol"]] = df[["high", "low", "close", "vol"]].astype(float)
    df["quote_vol"] = df["close"] * df["vol"]

    df["sma20"] = df["close"].rolling(20).mean()
    df["sma60"] = df["close"].rolling(60).mean()
    df["sma200"] = df["close"].rolling(200).mean()
    df["roc20"] = df["close"].pct_change(20)
    df["roc60"] = df["close"].pct_change(60)
    df["roc120"] = df["close"].pct_change(120)
    df["vol20"] = df["close"].pct_change().rolling(20).std()
    df["tr"] = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift(1)).abs(),
            (df["low"] - df["close"].shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["atr14"] = df["tr"].rolling(14).mean()
    df["avg_quote_vol_30"] = df["quote_vol"].rolling(30).mean()
    df["avg_quote_vol_90"] = df["quote_vol"].rolling(90).mean()
    df["avg_quote_vol_180"] = df["quote_vol"].rolling(180).mean()
    df["trend_persist_90"] = (df["close"] > df["sma200"]).rolling(90).mean()
    df["age_days"] = np.arange(1, len(df) + 1)

    latest = df.iloc[-1]
    required_fields = [
        "close",
        "sma20",
        "sma60",
        "sma200",
        "roc20",
        "roc60",
        "roc120",
        "vol20",
        "atr14",
        "avg_quote_vol_30",
        "avg_quote_vol_90",
        "avg_quote_vol_180",
        "trend_persist_90",
    ]
    if any(pd.isna(latest[field]) for field in required_fields):
        return None

    return {
        "close": float(latest["close"]),
        "sma20": float(latest["sma20"]),
        "sma60": float(latest["sma60"]),
        "sma200": float(latest["sma200"]),
        "roc20": float(latest["roc20"]),
        "roc60": float(latest["roc60"]),
        "roc120": float(latest["roc120"]),
        "vol20": float(latest["vol20"]),
        "atr14": float(latest["atr14"]),
        "avg_quote_vol_30": float(latest["avg_quote_vol_30"]),
        "avg_quote_vol_90": float(latest["avg_quote_vol_90"]),
        "avg_quote_vol_180": float(latest["avg_quote_vol_180"]),
        "trend_persist_90": float(latest["trend_persist_90"]),
        "age_days": int(latest["age_days"]),
    }


def fetch_btc_market_snapshot(
    client,
    btc_price,
    lookback_days=700,
    *,
    on_fetch_error=None,
    on_empty=None,
    on_insufficient=None,
):
    try:
        klines = client.get_historical_klines("BTCUSDT", _daily_interval(), f"{lookback_days} days ago UTC")
    except Exception as exc:
        if on_fetch_error is not None:
            on_fetch_error(exc)
        return None
    if not klines:
        if on_empty is not None:
            on_empty()
        return None

    df = pd.DataFrame(klines).iloc[:, :6]
    df.columns = ["time", "open", "high", "low", "close", "vol"]
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df["close"] = df["close"].astype(float)
    df["ma200"] = df["close"].rolling(200).mean()
    df["std200"] = df["close"].rolling(200).std()
    df["zscore"] = (df["close"] - df["ma200"]) / df["std200"]
    df["geom200"] = np.exp(np.log(df["close"]).rolling(200).mean())
    df["sell_trigger"] = df["zscore"].rolling(365).quantile(0.95).clip(lower=2.5)
    df["ma200_slope"] = df["ma200"].pct_change(20)
    df["btc_roc20"] = df["close"].pct_change(20)
    df["btc_roc60"] = df["close"].pct_change(60)
    df["btc_roc120"] = df["close"].pct_change(120)

    required_fields = ["ma200", "zscore", "geom200", "sell_trigger", "ma200_slope", "btc_roc20", "btc_roc60", "btc_roc120"]
    valid = df.dropna(subset=required_fields)
    if valid.empty:
        if on_insufficient is not None:
            last_time = df["time"].iloc[-1] if not df.empty else None
            on_insufficient(len(df), last_time)
        return None

    latest = valid.iloc[-1]
    regime_on = btc_price > float(latest["ma200"]) and float(latest["ma200_slope"]) > 0
    return {
        "ma200": float(latest["ma200"]),
        "zscore": float(latest["zscore"]),
        "geom200": float(latest["geom200"]),
        "sell_trigger": float(latest["sell_trigger"]),
        "ma200_slope": float(latest["ma200_slope"]),
        "ahr999": float(btc_price / latest["geom200"]),
        "btc_roc20": float(latest["btc_roc20"]),
        "btc_roc60": float(latest["btc_roc60"]),
        "btc_roc120": float(latest["btc_roc120"]),
        "regime_on": regime_on,
    }
