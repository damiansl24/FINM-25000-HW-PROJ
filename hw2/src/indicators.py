from __future__ import annotations

import numpy as np
import pandas as pd


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def add_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """Add the homework indicator set to a copy of the input data."""
    df = data.copy()

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    df["sma_20"] = close.rolling(20).mean()
    df["sma_50"] = close.rolling(50).mean()
    df["sma_200"] = close.rolling(200).mean()
    df["ema_12"] = _ema(close, 12)
    df["ema_20"] = _ema(close, 20)
    df["ema_26"] = _ema(close, 26)

    df["macd"] = df["ema_12"] - df["ema_26"]
    df["macd_signal"] = _ema(df["macd"], 9)
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    df["rsi_14"] = 100 - (100 / (1 + rs))

    lowest_low = low.rolling(14).min()
    highest_high = high.rolling(14).max()
    range_14 = (highest_high - lowest_low).replace(0.0, np.nan)
    df["stoch_k"] = 100 * (close - lowest_low) / range_14
    df["stoch_d"] = df["stoch_k"].rolling(3).mean()
    df["williams_r"] = -100 * (highest_high - close) / range_14

    rolling_mean = close.rolling(20).mean()
    rolling_std = close.rolling(20).std()
    df["bb_mid"] = rolling_mean
    df["bb_upper"] = rolling_mean + (2 * rolling_std)
    df["bb_lower"] = rolling_mean - (2 * rolling_std)

    prev_close = close.shift(1)
    tr_components = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    )
    true_range = tr_components.max(axis=1)
    df["atr_14"] = true_range.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    df["atr_pct"] = df["atr_14"] / close

    direction = np.sign(close.diff()).fillna(0.0)
    df["obv"] = (direction * volume).cumsum()

    money_flow_multiplier = ((close - low) - (high - close)) / (high - low).replace(0.0, np.nan)
    money_flow_volume = money_flow_multiplier.fillna(0.0) * volume
    df["cmf_20"] = money_flow_volume.rolling(20).sum() / volume.rolling(20).sum()

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr_for_adx = true_range.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean() / atr_for_adx
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean() / atr_for_adx
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
    df["plus_di"] = plus_di
    df["minus_di"] = minus_di
    df["adx_14"] = dx.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()

    return df
