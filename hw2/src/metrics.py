"""
metrics.py
──────────
Risk / performance metrics computed from a ``BacktestResult``.

All annualisation uses 252 trading days. The risk-free rate defaults to 0 but
can be supplied as an annual rate for the Sharpe/Sortino excess-return terms.
"""

import numpy as np
import pandas as pd
from pandas import DataFrame, Series

from src.backtest import BacktestResult

TRADING_DAYS = 252


def total_return(equity: Series) -> float:
    return float(equity.iloc[-1] / equity.iloc[0] - 1.0)


def cagr(equity: Series) -> float:
    """Compound annual growth rate based on calendar span of the equity curve."""
    n_days = (equity.index[-1] - equity.index[0]).days
    if n_days <= 0:
        return np.nan
    years = n_days / 365.25
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1.0)


def annual_volatility(returns: Series) -> float:
    return float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS))


def sharpe_ratio(returns: Series, risk_free: float = 0.0) -> float:
    """Annualised Sharpe ratio. ``risk_free`` is an annual rate."""
    rf_daily = risk_free / TRADING_DAYS
    excess = returns - rf_daily
    sd = excess.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return np.nan
    return float(excess.mean() / sd * np.sqrt(TRADING_DAYS))


def sortino_ratio(returns: Series, risk_free: float = 0.0) -> float:
    """Annualised Sortino ratio (downside deviation in the denominator)."""
    rf_daily = risk_free / TRADING_DAYS
    excess = returns - rf_daily
    downside = excess[excess < 0]
    dd = np.sqrt((downside ** 2).mean()) if len(downside) else np.nan
    if dd == 0 or np.isnan(dd):
        return np.nan
    return float(excess.mean() / dd * np.sqrt(TRADING_DAYS))


def drawdown_series(equity: Series) -> Series:
    """Running drawdown of the equity curve (0 at highs, negative below)."""
    running_max = equity.cummax()
    return equity / running_max - 1.0


def max_drawdown(equity: Series) -> float:
    return float(drawdown_series(equity).min())


def win_rate(trades: DataFrame) -> float:
    """Fraction of round-trip trades with a positive net return."""
    if trades is None or len(trades) == 0:
        return np.nan
    return float((trades["return"] > 0).mean())


def compute_metrics(result: BacktestResult, risk_free: float = 0.0) -> dict:
    """Bundle every HW2 metric for one strategy into a dict."""
    eq, ret = result.equity, result.returns
    return {
        "Total Return": total_return(eq),
        "CAGR": cagr(eq),
        "Volatility": annual_volatility(ret),
        "Sharpe": sharpe_ratio(ret, risk_free),
        "Sortino": sortino_ratio(ret, risk_free),
        "Max Drawdown": max_drawdown(eq),
        "Win Rate": win_rate(result.trades),
        "# Trades": int(len(result.trades)),
        "Final Value": result.final_value,
    }


def metrics_table(results: dict[str, BacktestResult], risk_free: float = 0.0) -> DataFrame:
    """
    Build a tidy comparison table: one row per strategy, one column per metric.
    ``results`` maps strategy name -> BacktestResult.
    """
    rows = {name: compute_metrics(res, risk_free) for name, res in results.items()}
    return pd.DataFrame(rows).T


def format_metrics_table(table: DataFrame) -> DataFrame:
    """Human-readable copy of ``metrics_table`` (percentages, rounded ratios)."""
    pct_cols = ["Total Return", "CAGR", "Volatility", "Max Drawdown", "Win Rate"]
    out = table.copy()
    for c in pct_cols:
        if c in out.columns:
            out[c] = out[c].map(lambda v: f"{v:.2%}" if pd.notna(v) else "—")
    for c in ["Sharpe", "Sortino"]:
        if c in out.columns:
            out[c] = out[c].map(lambda v: f"{v:.2f}" if pd.notna(v) else "—")
    if "Final Value" in out.columns:
        out["Final Value"] = out["Final Value"].map(lambda v: f"${v:,.0f}")
    if "# Trades" in out.columns:
        out["# Trades"] = out["# Trades"].map(lambda v: f"{int(v)}")
    return out
