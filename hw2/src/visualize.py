"""
visualize.py
────────────
Matplotlib charts for HW2. Every function returns a Figure and optionally saves
a PNG, so the same code powers both the notebook and the PDF report.

Charts:
    * plot_price_signals  — price + indicator overlays + buy/sell markers
    * plot_equity_curves  — equity-curve comparison across strategies
    * plot_drawdowns      — drawdown comparison across strategies
"""

from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
from pandas import DataFrame

from src.backtest import BacktestResult
from src.metrics import drawdown_series

matplotlib.rcParams.update({
    "figure.dpi": 110,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.size": 10,
})

_PALETTE = {
    "Buy & Hold": "#6b7280",
    "Trend Following": "#2563eb",
    "Mean Reversion": "#16a34a",
    "Custom": "#d946ef",
}


def _color(name: str, i: int = 0) -> str:
    return _PALETTE.get(name, plt.cm.tab10(i % 10))


def plot_price_signals(df: DataFrame,
                       result: BacktestResult,
                       title: str,
                       overlays: list[tuple[str, str]] | None = None,
                       lower: dict | None = None,
                       save_path: str | None = None):
    """
    Price chart with indicator overlays and buy/sell markers.

    Parameters
    ----------
    df : DataFrame
        Indicator-enriched frame (must include ``close`` and any overlay cols).
    result : BacktestResult
        Provides the round-trip trades used to place ▲ buy / ▼ sell markers.
    overlays : list of (column, label)
        Series plotted on the price axis (e.g. SMAs, Bollinger Bands).
    lower : dict or None
        Optional lower panel, e.g.
        ``{"series": [("rsi", "RSI")], "hlines": [30, 70], "ylabel": "RSI"}``.
    """
    overlays = overlays or []
    has_lower = lower is not None

    if has_lower:
        fig, (ax, ax2) = plt.subplots(
            2, 1, figsize=(12, 7), sharex=True,
            gridspec_kw={"height_ratios": [3, 1]},
        )
    else:
        fig, ax = plt.subplots(figsize=(12, 6))
        ax2 = None

    ax.plot(df.index, df["close"], color="#111827", lw=1.1, label="Close")
    for col, label in overlays:
        if col in df.columns:
            ax.plot(df.index, df[col], lw=1.0, alpha=0.85, label=label)

    trades = result.trades
    if trades is not None and len(trades):
        ax.scatter(trades["entry_date"], trades["entry_price"],
                   marker="^", s=70, color="#16a34a", zorder=5,
                   label="Buy", edgecolors="white", linewidths=0.5)
        ax.scatter(trades["exit_date"], trades["exit_price"],
                   marker="v", s=70, color="#dc2626", zorder=5,
                   label="Sell", edgecolors="white", linewidths=0.5)

    ax.set_ylabel("Price (USD)")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.legend(loc="upper left", ncol=2, fontsize=8, framealpha=0.9)

    if has_lower:
        for col, label in lower.get("series", []):
            if col in df.columns:
                ax2.plot(df.index, df[col], lw=1.0, label=label)
        for y in lower.get("hlines", []):
            ax2.axhline(y, color="#9ca3af", ls="--", lw=0.8)
        ax2.set_ylabel(lower.get("ylabel", ""))
        ax2.legend(loc="upper left", fontsize=8, framealpha=0.9)

    (ax2 or ax).set_xlabel("Date")
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, bbox_inches="tight")
    return fig


def plot_equity_curves(results: dict[str, BacktestResult],
                       title: str = "Equity Curve Comparison",
                       save_path: str | None = None):
    """Overlay every strategy's portfolio value on a single axis."""
    fig, ax = plt.subplots(figsize=(12, 6))
    for i, (name, res) in enumerate(results.items()):
        ax.plot(res.equity.index, res.equity, lw=1.4,
                color=_color(name, i), label=name)
    ax.axhline(next(iter(results.values())).initial_capital,
               color="#9ca3af", ls=":", lw=0.9)
    ax.set_ylabel("Portfolio Value (USD)")
    ax.set_xlabel("Date")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.legend(loc="upper left", fontsize=9)
    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, bbox_inches="tight")
    return fig


def plot_drawdowns(results: dict[str, BacktestResult],
                   title: str = "Drawdown Comparison",
                   save_path: str | None = None):
    """Overlay each strategy's drawdown curve (as a percentage)."""
    fig, ax = plt.subplots(figsize=(12, 6))
    for i, (name, res) in enumerate(results.items()):
        dd = drawdown_series(res.equity) * 100
        ax.plot(dd.index, dd, lw=1.2, color=_color(name, i), label=name)
        ax.fill_between(dd.index, dd, 0, color=_color(name, i), alpha=0.08)
    ax.set_ylabel("Drawdown (%)")
    ax.set_xlabel("Date")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.legend(loc="lower left", fontsize=9)
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, bbox_inches="tight")
    return fig
