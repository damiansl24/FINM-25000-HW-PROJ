"""
report.py
─────────
Assemble the final PDF report from a completed backtest run using matplotlib's
``PdfPages`` — no extra dependencies beyond matplotlib.

The report contains:
    1. Title page (ticker, period, capital)
    2. Strategy descriptions + entry/exit rules
    3. Performance comparison table
    4. Price/signal chart for each active strategy
    5. Equity-curve comparison
    6. Drawdown comparison
    7. Discussion of results (auto-generated from the metrics)
"""

from __future__ import annotations

import textwrap
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

from src.backtest import BacktestResult
from src.metrics import metrics_table, format_metrics_table
from src import visualize as viz


STRATEGY_DOCS = {
    "Trend Following": {
        "category": "Trend (MACD + ADX)",
        "buy": "MACD line crosses above its signal line AND ADX > 25",
        "sell": "MACD line falls below its signal line",
        "idea": "Ride established up-trends only when they are strong enough "
                "(ADX filter) and exit as soon as momentum turns.",
    },
    "Mean Reversion": {
        "category": "Momentum + Volatility (RSI + Bollinger Bands)",
        "buy": "RSI < 30 AND close below the lower Bollinger Band (oversold)",
        "sell": "RSI > 70 AND close above the upper Bollinger Band (overbought)",
        "idea": "Fade extremes: buy panic, sell euphoria, betting price snaps "
                "back to its 20-day mean.",
    },
    "Custom": {
        "category": "Trend + Momentum + Volume (SMA-50 + RSI + CMF)",
        "buy": "close > SMA(50) AND RSI > 50 AND CMF > 0",
        "sell": "close < SMA(50) OR RSI < 50",
        "idea": "Triple confirmation across three indicator families; requires "
                "trend, momentum, and money-flow to agree before committing.",
    },
    "Buy & Hold": {
        "category": "Benchmark",
        "buy": "Invest 100% on day one",
        "sell": "Never — hold to the end",
        "idea": "Passive benchmark every active strategy must beat on a "
                "risk-adjusted basis.",
    },
}

# Per-strategy chart configuration (overlays + optional lower oscillator panel).
CHART_CONFIG = {
    "Trend Following": dict(
        overlays=[("ema_20", "EMA 20"), ("sma_50", "SMA 50")],
        lower={"series": [("macd", "MACD"), ("macd_signal", "Signal")],
               "hlines": [0], "ylabel": "MACD"},
    ),
    "Mean Reversion": dict(
        overlays=[("bb_upper", "BB upper"), ("bb_mid", "BB mid"), ("bb_lower", "BB lower")],
        lower={"series": [("rsi", "RSI")], "hlines": [30, 70], "ylabel": "RSI"},
    ),
    "Custom": dict(
        overlays=[("sma_50", "SMA 50")],
        lower={"series": [("cmf", "CMF")], "hlines": [0], "ylabel": "CMF"},
    ),
}


def _text_page(pdf: PdfPages, title: str, body_lines: list[str], subtitle: str = ""):
    """Render a plain text page into the PDF."""
    fig = plt.figure(figsize=(8.5, 11))
    fig.subplots_adjust(left=0.08, right=0.92, top=0.92, bottom=0.06)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")

    y = 0.94
    ax.text(0.08, y, title, fontsize=18, fontweight="bold", va="top")
    y -= 0.045
    if subtitle:
        ax.text(0.08, y, subtitle, fontsize=11, color="#555", va="top")
        y -= 0.035

    for line in body_lines:
        style = {}
        text = line
        if line.startswith("## "):
            text = line[3:]
            style = dict(fontsize=13, fontweight="bold")
            y -= 0.012
        elif line.startswith("**") and line.endswith("**"):
            text = line.strip("*")
            style = dict(fontsize=11, fontweight="bold")
        else:
            style = dict(fontsize=10)
        for wrapped in textwrap.wrap(text, width=95) or [""]:
            ax.text(0.08, y, wrapped, va="top", **style)
            y -= 0.024
        y -= 0.006
    pdf.savefig(fig)
    plt.close(fig)


def _table_page(pdf: PdfPages, table: pd.DataFrame, title: str):
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.axis("off")
    ax.set_title(title, fontsize=15, fontweight="bold", pad=20)

    disp = format_metrics_table(table)
    tbl = ax.table(cellText=disp.values,
                   rowLabels=disp.index,
                   colLabels=disp.columns,
                   cellLoc="center", rowLoc="center", loc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1.0, 1.6)
    for (r, c), cell in tbl.get_celld().items():
        if r == 0 or c == -1:
            cell.set_text_props(fontweight="bold")
            cell.set_facecolor("#eef2ff")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _discussion(table: pd.DataFrame) -> list[str]:
    """Auto-generate a short results discussion from the metrics table."""
    lines = []
    active = table.drop(index=[i for i in ["Buy & Hold"] if i in table.index])
    best_sharpe = table["Sharpe"].idxmax()
    best_return = table["Total Return"].idxmax()
    best_dd = table["Max Drawdown"].idxmax()  # closest to 0 = smallest loss

    lines.append(
        f"On a risk-adjusted basis, **{best_sharpe}** delivered the highest "
        f"Sharpe ratio ({table.loc[best_sharpe, 'Sharpe']:.2f}), making it the "
        f"best performer by the assignment's primary criterion.")
    lines.append("")
    lines.append(
        f"By raw total return, **{best_return}** led with "
        f"{table.loc[best_return, 'Total Return']:.2%}. The smallest maximum "
        f"drawdown belonged to **{best_dd}** at "
        f"{table.loc[best_dd, 'Max Drawdown']:.2%}, indicating the gentlest "
        f"equity declines.")
    lines.append("")
    if "Buy & Hold" in table.index:
        bh = table.loc["Buy & Hold"]
        beat = [n for n in active.index if table.loc[n, "Sharpe"] > bh["Sharpe"]]
        if beat:
            lines.append(
                "Strategies that beat Buy & Hold on Sharpe: "
                + ", ".join(beat) + ".")
        else:
            lines.append(
                "No active strategy beat Buy & Hold on Sharpe over this window — "
                "a reminder that timing overhead and whipsaws often erode the "
                "edge of active rules in a trending market.")
    lines.append("")
    lines.append(
        "Trade counts and win rates highlight the style differences: trend "
        "following and the custom strategy trade more frequently and depend on "
        "a few large winners, while mean reversion trades sparingly with a high "
        "hit rate but limited exposure. Results are sensitive to the chosen "
        "ticker and sample period and should not be read as forward-looking.")
    return lines


def build_report(pdf_path: str,
                 ticker: str,
                 df_ind: pd.DataFrame,
                 results: dict[str, BacktestResult],
                 risk_free: float = 0.0):
    """Write the full multi-page PDF report to ``pdf_path``."""
    table = metrics_table(results, risk_free)
    start = df_ind.index[0].strftime("%Y-%m-%d")
    end = df_ind.index[-1].strftime("%Y-%m-%d")
    cap = next(iter(results.values())).initial_capital

    with PdfPages(pdf_path) as pdf:
        # 1. Title page
        _text_page(
            pdf,
            "HW2 — Technical Indicators & Strategy Backtesting",
            [
                "",
                f"**Ticker:** {ticker}",
                f"**Period:** {start} to {end}  ({len(df_ind)} trading days)",
                f"**Initial capital:** ${cap:,.0f}",
                "**Constraints:** long-only, no leverage, no short selling",
                f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "",
                "## Objective",
                "Build a reusable backtesting platform on Alpaca historical data "
                "and compare a Trend-Following, a Mean-Reversion, and a Custom "
                "multi-indicator strategy against a Buy & Hold benchmark to "
                "determine which performs best on a risk-adjusted basis.",
            ],
            subtitle="FINM 25000 · Algorithmic Trading",
        )

        # 2. Strategy descriptions
        body = ["## Strategy Descriptions & Rules", ""]
        for name in ["Trend Following", "Mean Reversion", "Custom", "Buy & Hold"]:
            d = STRATEGY_DOCS[name]
            body += [
                f"**{name}  —  {d['category']}**",
                f"Idea: {d['idea']}",
                f"Buy rule:  {d['buy']}",
                f"Sell rule: {d['sell']}",
                "",
            ]
        _text_page(pdf, "Strategies", body)

        # 3. Performance table
        _table_page(pdf, table, f"Performance Comparison — {ticker}")

        # 4. Price/signal chart per active strategy
        for name in ["Trend Following", "Mean Reversion", "Custom"]:
            cfg = CHART_CONFIG[name]
            fig = viz.plot_price_signals(
                df_ind, results[name],
                title=f"{name} — {ticker}",
                overlays=cfg["overlays"], lower=cfg["lower"])
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

        # 5. Equity curves
        fig = viz.plot_equity_curves(results, title=f"Equity Curve Comparison — {ticker}")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # 6. Drawdowns
        fig = viz.plot_drawdowns(results, title=f"Drawdown Comparison — {ticker}")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # 7. Discussion
        _text_page(pdf, "Discussion of Results", ["## Discussion", ""] + _discussion(table))

    return pdf_path
