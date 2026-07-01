"""
A small, reusable, long-only backtesting engine.

Assumptions (per HW2):
Initial capital: $100,000
Long-only, no leverage, no short selling  (positions are clamped to {0, 1})
A position decided from bar *t*'s indicators is entered at bar *t+1*'s
close, so there is no look-ahead. This is done by shifting the target
position forward one bar.
Optional proportional transaction cost charged on every change in position.

The engine is strategy-agnostic: it takes a price DataFrame and a target
position Series and returns a ``BacktestResult`` holding the equity curve, daily
returns, and the list of round-trip trades.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from pandas import DataFrame, Series


@dataclass
class BacktestResult:
    """Container for everything a strategy run produces."""
    name: str
    equity: Series          # portfolio value over time ($)
    returns: Series         # daily portfolio returns
    position: Series        # position actually held each day (0/1, post-shift)
    trades: DataFrame       # one row per round-trip trade
    initial_capital: float

    @property
    def final_value(self) -> float:
        return float(self.equity.iloc[-1])


def run_backtest(price: DataFrame,
                 position: Series,
                 name: str = "Strategy",
                 initial_capital: float = 100_000.0,
                 cost_per_trade: float = 0.0005) -> BacktestResult:
    """
    Vectorised long-only backtest.

    Parameters
    ----------
    price : DataFrame
        Must contain a ``close`` column, indexed by date.
    position : Series
        Target position in {0, 1} aligned to ``price`` (as produced by the
        strategy functions). Shifted forward one bar internally.
    name : str
        Label carried through to the result / charts.
    initial_capital : float
        Starting portfolio value.
    cost_per_trade : float
        Proportional cost applied to the traded notional whenever the position
        changes (e.g. 0.0005 = 5 bps). Set to 0 to disable.
    """
    close = price["close"].astype(float)
    market_ret = close.pct_change().fillna(0.0)

    # Decide today, trade tomorrow: hold yesterday's target today.
    held = position.reindex(close.index).fillna(0.0).clip(0, 1).shift(1).fillna(0.0)

    # Transaction cost on the bar where the held position changes.
    turnover = held.diff().abs().fillna(held.abs())
    cost = turnover * cost_per_trade

    strat_ret = held * market_ret - cost
    equity = initial_capital * (1.0 + strat_ret).cumprod()
    equity.name = name

    trades = _extract_trades(close, held, initial_capital, cost_per_trade)

    return BacktestResult(
        name=name,
        equity=equity,
        returns=strat_ret,
        position=held,
        trades=trades,
        initial_capital=initial_capital,
    )


def _extract_trades(close: Series,
                    held: Series,
                    initial_capital: float,
                    cost_per_trade: float) -> DataFrame:
    """
    Reconstruct round-trip trades from the held-position series.

    A trade opens when position goes 0 -> 1 and closes when it goes 1 -> 0 (or
    at the final bar if still open). Return per trade is close-to-close over the
    holding window, net of entry+exit costs.
    """
    pos = held.to_numpy()
    prices = close.to_numpy()
    dates = close.index

    records = []
    entry_i = None
    for i in range(len(pos)):
        if pos[i] == 1 and (i == 0 or pos[i - 1] == 0):
            entry_i = i
        is_last = i == len(pos) - 1
        exiting = pos[i] == 1 and (is_last or pos[i + 1] == 0)
        if exiting and entry_i is not None:
            entry_px = prices[entry_i]
            exit_px = prices[i]
            gross = exit_px / entry_px - 1.0
            net = gross - 2 * cost_per_trade  # entry + exit
            records.append({
                "entry_date": dates[entry_i],
                "exit_date": dates[i],
                "entry_price": entry_px,
                "exit_price": exit_px,
                "return": net,
                "bars_held": i - entry_i,
            })
            entry_i = None

    return pd.DataFrame(records, columns=[
        "entry_date", "exit_date", "entry_price", "exit_price", "return", "bars_held",
    ])
