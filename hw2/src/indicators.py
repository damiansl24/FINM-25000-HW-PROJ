"""
indicators.py
─────────────
Pure pandas/numpy implementations of the technical indicators used in HW2.
No TA-Lib dependency — everything is vectorised on the OHLCV DataFrame.

All functions take a DataFrame with lowercase columns
``open, high, low, close, volume`` (the shape returned by ``data_loader``)
and return either a Series or a small DataFrame of component columns.

Categories implemented (10 total, HW2 asks for >= 6):
    Trend      : SMA, EMA, MACD, ADX
    Momentum   : RSI, Stochastic Oscillator, Williams %R
    Volatility : Bollinger Bands, ATR
    Volume     : OBV, Chaikin Money Flow (CMF)
"""

import numpy as np
import pandas as pd
from pandas import DataFrame, Series


# ── Trend ─────────────────────────────────────────────────────────────────
def sma(close: Series, period: int = 20) -> Series:
    """Simple Moving Average."""
    return close.rolling(window=period, min_periods=period).mean()


def ema(close: Series, period: int = 20) -> Series:
    """Exponential Moving Average."""
    return close.ewm(span=period, adjust=False).mean()


def macd(close: Series, fast: int = 12, slow: int = 26, signal: int = 9) -> DataFrame:
    """
    Moving Average Convergence Divergence.

    Returns columns: ``macd`` (fast EMA - slow EMA), ``signal`` (EMA of macd),
    and ``hist`` (macd - signal).
    """
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": hist})


def adx(df: DataFrame, period: int = 14) -> DataFrame:
    """
    Average Directional Index (Wilder). Measures trend *strength*.

    Returns columns: ``plus_di``, ``minus_di``, ``adx``.
    """
    high, low, close = df["high"], df["low"], df["close"]

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    tr = _true_range(high, low, close)

    # Wilder smoothing == EMA with alpha = 1/period.
    atr_ = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_ = dx.ewm(alpha=1 / period, adjust=False).mean()

    return pd.DataFrame({"plus_di": plus_di, "minus_di": minus_di, "adx": adx_})


# ── Momentum ──────────────────────────────────────────────────────────────
def rsi(close: Series, period: int = 14) -> Series:
    """Relative Strength Index (Wilder smoothing)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_ = 100 - (100 / (1 + rs))
    # When there are no losses at all, RSI is 100.
    rsi_ = rsi_.where(avg_loss != 0, 100.0)
    return rsi_


def stochastic(df: DataFrame, k_period: int = 14, d_period: int = 3) -> DataFrame:
    """
    Stochastic Oscillator. Returns ``%K`` and ``%D`` (SMA of %K).
    """
    low_min = df["low"].rolling(window=k_period, min_periods=k_period).min()
    high_max = df["high"].rolling(window=k_period, min_periods=k_period).max()

    percent_k = 100 * (df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)
    percent_d = percent_k.rolling(window=d_period, min_periods=d_period).mean()
    return pd.DataFrame({"percent_k": percent_k, "percent_d": percent_d})


def williams_r(df: DataFrame, period: int = 14) -> Series:
    """Williams %R — oscillates between 0 (overbought) and -100 (oversold)."""
    high_max = df["high"].rolling(window=period, min_periods=period).max()
    low_min = df["low"].rolling(window=period, min_periods=period).min()
    return -100 * (high_max - df["close"]) / (high_max - low_min).replace(0, np.nan)


# ── Volatility ────────────────────────────────────────────────────────────
def bollinger_bands(close: Series, period: int = 20, num_std: float = 2.0) -> DataFrame:
    """
    Bollinger Bands. Returns ``mid`` (SMA), ``upper``, ``lower`` and the
    ``pct_b`` position of price within the bands (0 = lower, 1 = upper).
    """
    mid = sma(close, period)
    std = close.rolling(window=period, min_periods=period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    pct_b = (close - lower) / (upper - lower).replace(0, np.nan)
    return pd.DataFrame({"mid": mid, "upper": upper, "lower": lower, "pct_b": pct_b})


def atr(df: DataFrame, period: int = 14) -> Series:
    """Average True Range (Wilder smoothing)."""
    tr = _true_range(df["high"], df["low"], df["close"])
    return tr.ewm(alpha=1 / period, adjust=False).mean()


# ── Volume ────────────────────────────────────────────────────────────────
def obv(df: DataFrame) -> Series:
    """On-Balance Volume."""
    direction = np.sign(df["close"].diff().fillna(0.0))
    return (direction * df["volume"]).cumsum()


def cmf(df: DataFrame, period: int = 20) -> Series:
    """Chaikin Money Flow — volume-weighted accumulation/distribution."""
    high, low, close, volume = df["high"], df["low"], df["close"], df["volume"]
    hl_range = (high - low).replace(0, np.nan)
    mf_multiplier = ((close - low) - (high - close)) / hl_range
    mf_volume = mf_multiplier * volume
    return (mf_volume.rolling(period, min_periods=period).sum()
            / volume.rolling(period, min_periods=period).sum().replace(0, np.nan))


# ── shared helper ─────────────────────────────────────────────────────────
def _true_range(high: Series, low: Series, close: Series) -> Series:
    prev_close = close.shift(1)
    ranges = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1)
    return ranges.max(axis=1)


def add_all_indicators(df: DataFrame) -> DataFrame:
    """
    Convenience: attach every indicator (with default parameters) as columns to
    a copy of ``df``. Column names are namespaced so downstream code / strategies
    and charts can reference them directly.
    """
    out = df.copy()

    out["sma_20"] = sma(df["close"], 20)
    out["sma_50"] = sma(df["close"], 50)
    out["sma_200"] = sma(df["close"], 200)
    out["ema_20"] = ema(df["close"], 20)

    macd_df = macd(df["close"])
    out["macd"] = macd_df["macd"]
    out["macd_signal"] = macd_df["signal"]
    out["macd_hist"] = macd_df["hist"]

    adx_df = adx(df)
    out["plus_di"] = adx_df["plus_di"]
    out["minus_di"] = adx_df["minus_di"]
    out["adx"] = adx_df["adx"]

    out["rsi"] = rsi(df["close"])

    stoch_df = stochastic(df)
    out["stoch_k"] = stoch_df["percent_k"]
    out["stoch_d"] = stoch_df["percent_d"]

    out["williams_r"] = williams_r(df)

    bb = bollinger_bands(df["close"])
    out["bb_mid"] = bb["mid"]
    out["bb_upper"] = bb["upper"]
    out["bb_lower"] = bb["lower"]
    out["bb_pct_b"] = bb["pct_b"]

    out["atr"] = atr(df)
    out["obv"] = obv(df)
    out["cmf"] = cmf(df)

    return out
