"""Performance metrics computed from a daily-returns series."""
import numpy as np
import pandas as pd

from . import config

TD = config.TRADING_DAYS_PER_YEAR
RF = config.RISK_FREE_RATE


def performance_metrics(daily_returns: pd.Series, equity: pd.Series) -> dict:
    """Total Return, CAGR, Volatility, Sharpe, Sortino, Max Drawdown, Win Rate."""
    r = daily_returns.dropna()
    n = len(r)
    if n == 0:
        return {}

    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    years = n / TD
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1.0 if years > 0 else np.nan

    std = r.std(ddof=0)
    vol = std * np.sqrt(TD)
    excess = r - RF / TD
    sharpe = (excess.mean() / std * np.sqrt(TD)) if std > 0 else np.nan

    downside_std = r[r < 0].std(ddof=0)
    sortino = (excess.mean() / downside_std * np.sqrt(TD)) if downside_std > 0 else np.nan

    drawdown = equity / equity.cummax() - 1.0
    max_dd = drawdown.min()

    active = r[r != 0]
    win_rate = (active > 0).mean() if len(active) else np.nan

    return {
        "Total Return": total_return,
        "CAGR": cagr,
        "Volatility (ann.)": vol,
        "Sharpe Ratio": sharpe,
        "Sortino Ratio": sortino,
        "Max Drawdown": max_dd,
        "Win Rate": win_rate,
    }


def format_metrics_table(name_to_metrics: dict) -> str:
    """Pretty side-by-side table of {strategy_name: metrics_dict}."""
    strategies = list(name_to_metrics.keys())
    rows = list(next(iter(name_to_metrics.values())).keys())
    pct_rows = {"Total Return", "CAGR", "Volatility (ann.)", "Max Drawdown", "Win Rate"}
    width = 20

    header = f"{'Metric':<20}" + "".join(f"{s:>{width}}" for s in strategies)
    lines = [header, "-" * len(header)]
    for row in rows:
        cells = ""
        for s in strategies:
            v = name_to_metrics[s].get(row, float("nan"))
            cells += (f"{v:>{width}.2%}" if row in pct_rows else f"{v:>{width}.2f}")
        lines.append(f"{row:<20}{cells}")
    return "\n".join(lines)
