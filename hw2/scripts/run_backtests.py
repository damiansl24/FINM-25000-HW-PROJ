from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backtester import build_buy_and_hold, run_long_only_backtest
from src.data_loader import load_daily_ohlcv
from src.indicators import add_indicators
from src.metrics import build_metrics_table, calculate_metrics
from src.reporting import (
    generate_report_pdf,
    save_drawdown_chart,
    save_equity_curve_chart,
    save_strategy_chart,
)
from src.strategies import (
    build_custom_signals,
    build_mean_reversion_signals,
    build_trend_following_signals,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run HW2 Alpaca backtests and generate deliverables.")
    parser.add_argument("--ticker", default="SPY", help="Ticker symbol to analyze. Default: SPY")
    parser.add_argument("--capital", type=float, default=100_000.0, help="Initial capital. Default: 100000")
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parents[1] / "output"),
        help="Directory where charts, CSVs, and the PDF report will be written.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ticker = args.ticker.upper().strip()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    end_date = datetime.today()
    start_date = end_date - timedelta(days=365 * 5 + 10)

    prices = load_daily_ohlcv(ticker, start=start_date, end=end_date)
    enriched = add_indicators(prices).dropna().copy()

    trend_signals = build_trend_following_signals(enriched)
    mean_rev_signals = build_mean_reversion_signals(enriched)
    custom_signals = build_custom_signals(enriched)

    trend_result = run_long_only_backtest(enriched, trend_signals, "Trend Following", args.capital)
    mean_result = run_long_only_backtest(enriched, mean_rev_signals, "Mean Reversion", args.capital)
    custom_result = run_long_only_backtest(enriched, custom_signals, "Custom Strategy", args.capital)
    benchmark = build_buy_and_hold(enriched, args.capital)

    metrics_map = {
        "Buy & Hold": calculate_metrics(benchmark, pd.DataFrame(), args.capital),
        "Trend Following": calculate_metrics(trend_result.history, trend_result.trades, args.capital),
        "Mean Reversion": calculate_metrics(mean_result.history, mean_result.trades, args.capital),
        "Custom Strategy": calculate_metrics(custom_result.history, custom_result.trades, args.capital),
    }
    metrics_table = build_metrics_table(metrics_map)

    trend_chart = output_dir / "trend_following_price_chart.png"
    mean_chart = output_dir / "mean_reversion_price_chart.png"
    custom_chart = output_dir / "custom_strategy_price_chart.png"
    equity_chart = output_dir / "equity_curve_comparison.png"
    drawdown_chart = output_dir / "drawdown_comparison.png"
    report_pdf = output_dir / "final_report.pdf"

    save_strategy_chart(
        enriched,
        trend_result.history,
        "Trend Following",
        ["sma_50", "sma_200", "macd", "macd_signal"],
        trend_chart,
    )
    save_strategy_chart(
        enriched,
        mean_result.history,
        "Mean Reversion",
        ["bb_upper", "bb_mid", "bb_lower"],
        mean_chart,
    )
    save_strategy_chart(
        enriched,
        custom_result.history,
        "Custom Strategy",
        ["ema_20", "sma_50"],
        custom_chart,
    )
    save_equity_curve_chart(
        {
            "Buy & Hold": benchmark["portfolio_value"],
            "Trend Following": trend_result.history["portfolio_value"],
            "Mean Reversion": mean_result.history["portfolio_value"],
            "Custom Strategy": custom_result.history["portfolio_value"],
        },
        equity_chart,
    )
    save_drawdown_chart(
        {
            "Buy & Hold": benchmark["drawdown"],
            "Trend Following": trend_result.history["drawdown"],
            "Mean Reversion": mean_result.history["drawdown"],
            "Custom Strategy": custom_result.history["drawdown"],
        },
        drawdown_chart,
    )
    generate_report_pdf(
        ticker=ticker,
        output_path=report_pdf,
        metrics_table=metrics_table,
        chart_paths=[trend_chart, mean_chart, custom_chart, equity_chart, drawdown_chart],
    )

    metrics_table.to_csv(output_dir / "performance_summary.csv")
    trend_result.history.to_csv(output_dir / "trend_following_history.csv")
    mean_result.history.to_csv(output_dir / "mean_reversion_history.csv")
    custom_result.history.to_csv(output_dir / "custom_strategy_history.csv")
    benchmark.to_csv(output_dir / "buy_and_hold_history.csv")
    trend_result.trades.to_csv(output_dir / "trend_following_trades.csv", index=False)
    mean_result.trades.to_csv(output_dir / "mean_reversion_trades.csv", index=False)
    custom_result.trades.to_csv(output_dir / "custom_strategy_trades.csv", index=False)

    print(f"HW2 deliverables generated in: {output_dir}")
    print(f"Performance summary saved to: {output_dir / 'performance_summary.csv'}")
    print(f"Final report saved to: {report_pdf}")


if __name__ == "__main__":
    main()
