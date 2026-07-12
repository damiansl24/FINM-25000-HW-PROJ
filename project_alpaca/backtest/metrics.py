"""Performance metrics for a continuously traded crypto equity curve."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

CRYPTO_HOURS_PER_YEAR = 24 * 365


@dataclass(frozen=True)
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


def compute_metrics(
    equity: pd.Series,
    realized_trades: list[float],
    n_fills: int,
    periods_per_year: int = CRYPTO_HOURS_PER_YEAR,
) -> PerformanceReport:
    initial = float(equity.iloc[0])
    final = float(equity.iloc[-1])
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    sharpe = 0.0
    if len(returns) > 1 and returns.std(ddof=1) > 0:
        sharpe = float(returns.mean() / returns.std(ddof=1) * np.sqrt(periods_per_year))
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_drawdown = abs(float(drawdown.min())) if len(drawdown) else 0.0
    wins = sum(pnl > 0 for pnl in realized_trades)
    return PerformanceReport(
        initial_equity=initial,
        final_equity=final,
        total_return=final / initial - 1 if initial else 0.0,
        cum_pnl=final - initial,
        max_drawdown=max_drawdown,
        sharpe=sharpe,
        n_fills=n_fills,
        n_round_trips=len(realized_trades),
        hit_rate=wins / len(realized_trades) if realized_trades else 0.0,
    )

