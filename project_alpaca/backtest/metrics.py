"""Performance metrics for a backtest (or live) equity curve and trade log."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 252


@dataclass
class PerformanceReport:
    initial_equity: float
    final_equity: float
    total_return: float
    cum_pnl: float
    max_drawdown: float
    sharpe: float
    n_fills: int
    n_round_trips: int
    hit_rate: float

    def summary(self) -> str:
        return (
            f"Initial equity   : {self.initial_equity:>12,.2f}\n"
            f"Final equity     : {self.final_equity:>12,.2f}\n"
            f"Cumulative P&L   : {self.cum_pnl:>12,.2f}\n"
            f"Total return     : {self.total_return:>12.2%}\n"
            f"Max drawdown     : {self.max_drawdown:>12.2%}\n"
            f"Sharpe (ann.)    : {self.sharpe:>12.2f}\n"
            f"Fills            : {self.n_fills:>12d}\n"
            f"Closed trades    : {self.n_round_trips:>12d}\n"
            f"Hit rate         : {self.hit_rate:>12.2%}"
        )


def compute_metrics(equity: pd.Series, realized_trades: list[float],
                    n_fills: int) -> PerformanceReport:
    """equity: daily equity indexed by date, first value = starting equity."""
    initial, final = float(equity.iloc[0]), float(equity.iloc[-1])
    returns = equity.pct_change().dropna()
    sharpe = 0.0
    if len(returns) > 1 and returns.std() > 0:
        sharpe = float(returns.mean() / returns.std() * np.sqrt(TRADING_DAYS))
    running_max = equity.cummax()
    max_dd = float(((equity - running_max) / running_max).min()) if len(equity) else 0.0
    wins = sum(1 for pnl in realized_trades if pnl > 0)
    return PerformanceReport(
        initial_equity=initial,
        final_equity=final,
        total_return=final / initial - 1 if initial else 0.0,
        cum_pnl=final - initial,
        max_drawdown=abs(max_dd),
        sharpe=sharpe,
        n_fills=n_fills,
        n_round_trips=len(realized_trades),
        hit_rate=wins / len(realized_trades) if realized_trades else 0.0,
    )
