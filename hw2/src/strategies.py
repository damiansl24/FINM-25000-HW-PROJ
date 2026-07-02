from __future__ import annotations

import numpy as np
import pandas as pd


def _signal_frame(index: pd.Index) -> pd.DataFrame:
    return pd.DataFrame(index=index, data={"entry": False, "exit": False, "signal": 0})


def build_trend_following_signals(data: pd.DataFrame) -> pd.DataFrame:
    signals = _signal_frame(data.index)
    entry_rule = (
        (data["macd"] > data["macd_signal"])
        & (data["sma_50"] > data["sma_200"])
        & (data["adx_14"] > 25)
    )
    exit_rule = (data["macd"] < data["macd_signal"]) | (data["sma_50"] < data["sma_200"])

    signals["entry"] = entry_rule.fillna(False)
    signals["exit"] = exit_rule.fillna(False)
    signals["signal"] = np.where(signals["entry"], 1, np.where(signals["exit"], -1, 0))
    return signals


def build_mean_reversion_signals(data: pd.DataFrame) -> pd.DataFrame:
    signals = _signal_frame(data.index)
    entry_rule = (data["rsi_14"] < 30) & (data["close"] < data["bb_lower"])
    exit_rule = (data["rsi_14"] > 70) | (data["close"] > data["bb_upper"])

    signals["entry"] = entry_rule.fillna(False)
    signals["exit"] = exit_rule.fillna(False)
    signals["signal"] = np.where(signals["entry"], 1, np.where(signals["exit"], -1, 0))
    return signals


def build_custom_signals(data: pd.DataFrame) -> pd.DataFrame:
    signals = _signal_frame(data.index)
    obv_slope = data["obv"].diff(5)

    entry_rule = (
        (data["ema_20"] > data["sma_50"])
        & (data["cmf_20"] > 0)
        & (data["rsi_14"].between(50, 70))
        & (obv_slope > 0)
    )
    exit_rule = (
        (data["ema_20"] < data["sma_50"])
        | (data["cmf_20"] < 0)
        | (data["rsi_14"] < 45)
    )

    signals["entry"] = entry_rule.fillna(False)
    signals["exit"] = exit_rule.fillna(False)
    signals["signal"] = np.where(signals["entry"], 1, np.where(signals["exit"], -1, 0))
    return signals
