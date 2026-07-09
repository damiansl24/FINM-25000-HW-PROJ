"""Simple long-only, no-leverage backtest comparing ML signal vs Buy & Hold."""
import pandas as pd

from . import config


def run_backtest(prices: pd.Series, signal: pd.Series, initial_capital=config.INITIAL_CAPITAL):
    """Long-only backtest.

    prices : close prices aligned to `signal`'s index.
    signal : 1 (long) / 0 (flat) from the model probability threshold.

    The position held on day t is decided by day t-1's signal (signal.shift(1)),
    so there is no look-ahead: we can only act on the bar AFTER a signal appears.
    """
    df = pd.DataFrame({"price": prices, "signal": signal}).dropna()
    df["asset_return"] = df["price"].pct_change().fillna(0.0)

    df["position"] = df["signal"].shift(1).fillna(0).astype(int)
    df["strategy_return"] = df["position"] * df["asset_return"]
    df["trade"] = df["position"].diff().fillna(df["position"]).astype(int)

    df["ml_equity"] = initial_capital * (1 + df["strategy_return"]).cumprod()
    df["bh_equity"] = initial_capital * (1 + df["asset_return"]).cumprod()

    return df, _trade_log(df)


def _trade_log(df: pd.DataFrame) -> pd.DataFrame:
    """One row per completed long trade (enter when position -> 1, exit when -> 0)."""
    records = []
    in_pos = False
    entry_date = entry_price = None
    for date, row in df.iterrows():
        if row["position"] == 1 and not in_pos:
            in_pos, entry_date, entry_price = True, date, row["price"]
        elif row["position"] == 0 and in_pos:
            in_pos = False
            records.append({
                "entry_date": entry_date, "exit_date": date,
                "entry_price": entry_price, "exit_price": row["price"],
                "return_pct": row["price"] / entry_price - 1.0,
            })
    if in_pos:  # still holding at the end of the window
        last = df.iloc[-1]
        records.append({
            "entry_date": entry_date, "exit_date": df.index[-1],
            "entry_price": entry_price, "exit_price": last["price"],
            "return_pct": last["price"] / entry_price - 1.0,
        })
    return pd.DataFrame(records)
