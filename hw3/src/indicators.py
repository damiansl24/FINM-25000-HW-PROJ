"""Technical indicators — exactly the set listed in the assignment.

Pure pandas/numpy (no TA-Lib) so it installs cleanly on Windows.

The 11 indicators the assignment names, plus the 3 required extras
(log returns, rolling mean, rolling std) = 14 feature columns, one per item:

  Trend      : SMA, EMA, MACD, ADX
  Momentum   : RSI, Stochastic, Williams %R
  Volatility : Bollinger Bands, ATR
  Volume     : OBV, CMF
  Extras     : log returns, rolling mean, rolling std
"""
import numpy as np
import pandas as pd

# One feature column per indicator the assignment lists (+ the 3 extras).
FEATURE_COLUMNS = [
    "sma_20",        # Trend: Simple Moving Average
    "ema_20",        # Trend: Exponential Moving Average
    "macd",          # Trend: MACD line (EMA12 - EMA26)
    "adx_14",        # Trend: Average Directional Index
    "rsi_14",        # Momentum: Relative Strength Index
    "stoch_k",       # Momentum: Stochastic %K
    "williams_r",    # Momentum: Williams %R
    "bb_pctb",       # Volatility: Bollinger Bands %B (position within the bands)
    "atr_14",        # Volatility: Average True Range
    "obv",           # Volume: On-Balance Volume
    "cmf_20",        # Volume: Chaikin Money Flow
    "log_return",    # Extra: log return
    "roll_mean_20",  # Extra: rolling mean of log returns
    "roll_std_20",   # Extra: rolling std of log returns
]


def _true_range(high, low, close):
    prev_close = close.shift(1)
    ranges = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    )
    return ranges.max(axis=1)


def _rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _adx(high, low, close, period=14):
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=high.index)

    atr = _true_range(high, low, close).ewm(alpha=1 / period, min_periods=period).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, min_periods=period).mean()


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return the 14 feature columns aligned to `df`'s index (NaNs not yet dropped)."""
    high, low, close, volume = df["high"], df["low"], df["close"], df["volume"]
    out = pd.DataFrame(index=df.index)

    # --- Trend ---
    out["sma_20"] = close.rolling(20).mean()
    out["ema_20"] = close.ewm(span=20, adjust=False).mean()
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    out["adx_14"] = _adx(high, low, close, 14)

    # --- Momentum ---
    out["rsi_14"] = _rsi(close, 14)
    low_14 = low.rolling(14).min()
    high_14 = high.rolling(14).max()
    out["stoch_k"] = 100 * (close - low_14) / (high_14 - low_14).replace(0, np.nan)
    out["williams_r"] = -100 * (high_14 - close) / (high_14 - low_14).replace(0, np.nan)

    # --- Volatility ---
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    out["bb_pctb"] = (close - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)
    out["atr_14"] = _true_range(high, low, close).ewm(alpha=1 / 14, min_periods=14).mean()

    # --- Volume ---
    out["obv"] = (np.sign(close.diff()).fillna(0) * volume).cumsum()
    mfm = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
    out["cmf_20"] = (mfm * volume).rolling(20).sum() / volume.rolling(20).sum().replace(0, np.nan)

    # --- Extras ---
    log_ret = np.log(close / close.shift(1))
    out["log_return"] = log_ret
    out["roll_mean_20"] = log_ret.rolling(20).mean()
    out["roll_std_20"] = log_ret.rolling(20).std()

    return out


def make_dataset(df: pd.DataFrame):
    """Build features + binary target (next-day return > 0), dropping NaN rows.

    Returns (X, y, feats) where `feats` keeps the aligned 'close' column so the
    backtest can compute realized returns.
    """
    feats = build_features(df)
    feats["close"] = df["close"]
    # Target: 1 if the NEXT day's close is higher than today's, else 0.
    feats["target"] = (df["close"].shift(-1) > df["close"]).astype(int)

    feats = feats.dropna(subset=FEATURE_COLUMNS + ["close"])
    feats = feats.iloc[:-1] if len(feats) else feats  # last row has no next-day target

    X = feats[FEATURE_COLUMNS].copy()
    y = feats["target"].astype(int).copy()
    return X, y, feats
