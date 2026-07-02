from __future__ import annotations

import numpy as np
import pandas as pd


TRADING_DAYS = 252


def calculate_metrics(history: pd.DataFrame, trades: pd.DataFrame, initial_capital: float) -> dict[str, float]:
    """Calculate the homework performance metrics for a strategy history."""
    portfolio = history["portfolio_value"].dropna()
    daily_returns = history["daily_returns"].dropna()

    total_return = (portfolio.iloc[-1] / initial_capital) - 1
    years = max(len(portfolio) / TRADING_DAYS, 1 / TRADING_DAYS)
    cagr = (portfolio.iloc[-1] / initial_capital) ** (1 / years) - 1
    volatility = daily_returns.std(ddof=0) * np.sqrt(TRADING_DAYS)

    mean_daily = daily_returns.mean()
    downside = daily_returns[daily_returns < 0]
    downside_std = downside.std(ddof=0) * np.sqrt(TRADING_DAYS) if not downside.empty else np.nan
    sharpe = (mean_daily / daily_returns.std(ddof=0)) * np.sqrt(TRADING_DAYS) if daily_returns.std(ddof=0) > 0 else np.nan
    sortino = (mean_daily * TRADING_DAYS) / downside_std if downside_std and downside_std > 0 else np.nan
    max_drawdown = history["drawdown"].min()

    if trades.empty:
        win_rate = np.nan
        trades_executed = 0
    else:
        win_rate = float((trades["pnl"] > 0).mean())
        trades_executed = int(len(trades))

    return {
        "Total Return": total_return,
        "CAGR": cagr,
        "Volatility": volatility,
        "Sharpe Ratio": sharpe,
        "Sortino Ratio": sortino,
        "Maximum Drawdown": max_drawdown,
        "Win Rate": win_rate,
        "Trades Executed": float(trades_executed),
    }


def build_metrics_table(metrics_map: dict[str, dict[str, float]]) -> pd.DataFrame:
    table = pd.DataFrame(metrics_map).T
    table.index.name = "Strategy"
    return table
