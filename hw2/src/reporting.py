from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages


def save_strategy_chart(
    price_data: pd.DataFrame,
    backtest_history: pd.DataFrame,
    strategy_name: str,
    indicator_columns: list[str],
    output_path: Path,
) -> None:
    """Save a price chart with indicators and buy/sell markers."""
    fig, axes = plt.subplots(
        2,
        1,
        figsize=(14, 9),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    axes[0].plot(price_data.index, price_data["close"], label="Close", linewidth=1.6, color="black")
    for column in indicator_columns:
        if column in price_data.columns:
            axes[0].plot(price_data.index, price_data[column], label=column, linewidth=1.1)

    buys = backtest_history[backtest_history["action"] == "BUY"]
    sells = backtest_history[backtest_history["action"] == "SELL"]
    axes[0].scatter(buys.index, buys["close"], marker="^", color="green", s=70, label="Buy")
    axes[0].scatter(sells.index, sells["close"], marker="v", color="red", s=70, label="Sell")
    axes[0].set_title(f"{strategy_name} Price Chart")
    axes[0].set_ylabel("Price (USD)")
    axes[0].legend(loc="upper left", ncol=2)
    axes[0].grid(alpha=0.25)

    axes[1].plot(backtest_history.index, backtest_history["portfolio_value"], color="tab:blue", linewidth=1.4)
    axes[1].set_title(f"{strategy_name} Portfolio Value")
    axes[1].set_ylabel("Portfolio Value")
    axes[1].grid(alpha=0.25)

    axes[1].xaxis.set_major_locator(mdates.AutoDateLocator())
    axes[1].xaxis.set_major_formatter(mdates.ConciseDateFormatter(axes[1].xaxis.get_major_locator()))
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def save_equity_curve_chart(curves: dict[str, pd.Series], output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(14, 7))
    for label, series in curves.items():
        ax.plot(series.index, series.values, linewidth=1.6, label=label)
    ax.set_title("Equity Curve Comparison")
    ax.set_ylabel("Portfolio Value")
    ax.grid(alpha=0.25)
    ax.legend()
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def save_drawdown_chart(drawdowns: dict[str, pd.Series], output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(14, 7))
    for label, series in drawdowns.items():
        ax.plot(series.index, series.values, linewidth=1.6, label=label)
    ax.set_title("Drawdown Comparison")
    ax.set_ylabel("Drawdown")
    ax.grid(alpha=0.25)
    ax.legend()
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _format_metrics_for_display(metrics_table: pd.DataFrame) -> pd.DataFrame:
    display = metrics_table.copy()
    percent_columns = ["Total Return", "CAGR", "Volatility", "Maximum Drawdown", "Win Rate"]
    for column in percent_columns:
        if column in display.columns:
            display[column] = display[column].map(lambda value: "N/A" if pd.isna(value) else f"{value:.2%}")
    for column in ["Sharpe Ratio", "Sortino Ratio"]:
        if column in display.columns:
            display[column] = display[column].map(lambda value: "N/A" if pd.isna(value) else f"{value:.2f}")
    if "Trades Executed" in display.columns:
        display["Trades Executed"] = display["Trades Executed"].map(lambda value: f"{int(value)}")
    return display


def generate_report_pdf(
    ticker: str,
    output_path: Path,
    metrics_table: pd.DataFrame,
    chart_paths: list[Path],
) -> None:
    """Create the final PDF report required by the homework."""
    formatted_table = _format_metrics_for_display(metrics_table)

    summary_lines = [
        "Homework 2 Final Report",
        f"Ticker: {ticker}",
        "",
        "Strategy descriptions",
        "Trend Following: MACD, ADX, and moving average confirmation for directional trades.",
        "Mean Reversion: RSI and Bollinger Bands to buy oversold pullbacks and exit rebounds.",
        "Custom Strategy: EMA vs. SMA trend filter plus CMF, OBV slope, and RSI confirmation.",
        "",
        "Entry and exit rules",
        "Trend Following enters when MACD is above signal, SMA50 is above SMA200, and ADX exceeds 25.",
        "Trend Following exits when MACD falls below signal or SMA50 falls below SMA200.",
        "Mean Reversion enters when RSI is below 30 and price is below the lower Bollinger Band.",
        "Mean Reversion exits when RSI is above 70 or price rises above the upper Bollinger Band.",
        "Custom Strategy enters when EMA20 is above SMA50, CMF is positive, OBV is rising, and RSI is between 50 and 70.",
        "Custom Strategy exits when EMA20 drops below SMA50, CMF turns negative, or RSI falls below 45.",
        "",
        "Discussion of results",
        "Use the table and charts in this report to compare total return, risk-adjusted performance,",
        "drawdowns, and trade behavior against buy-and-hold.",
    ]

    with PdfPages(output_path) as pdf:
        fig = plt.figure(figsize=(11, 8.5))
        fig.text(0.05, 0.95, "Technical Indicators & Strategy Backtesting with Alpaca", fontsize=20, weight="bold")
        fig.text(0.05, 0.91, f"Ticker analyzed: {ticker}", fontsize=12)
        fig.text(0.05, 0.06, "\n".join(summary_lines), fontsize=10, va="bottom")
        plt.axis("off")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(11, 8.5))
        ax.axis("off")
        ax.set_title("Performance Comparison Table", fontsize=16, pad=18)
        table = ax.table(
            cellText=formatted_table.reset_index().values,
            colLabels=["Strategy", *formatted_table.columns.tolist()],
            loc="center",
            cellLoc="center",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 1.6)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        for chart_path in chart_paths:
            image = mpimg.imread(chart_path)
            fig, ax = plt.subplots(figsize=(11, 8.5))
            ax.imshow(image)
            ax.axis("off")
            ax.set_title(chart_path.stem.replace("_", " ").title(), fontsize=14, pad=10)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
