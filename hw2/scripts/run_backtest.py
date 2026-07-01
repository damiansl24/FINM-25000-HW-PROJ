"""
End-to-end HW2 driver: pull daily data from Alpaca, run every strategy through
the backtesting engine, print the performance table, and write all charts +
the final PDF report to hw2/charts/ and hw2/report/.

Run from hw2/scripts/:

    python run_backtest.py                 # defaults: SPY, 6 years
    python run_backtest.py --ticker AAPL --years 7
    python run_backtest.py --ticker QQQ --start 2018-01-01 --end 2024-12-31

Requires a .env with ALPACA_API_KEY / ALPACA_SECRET_KEY (see repo README).
"""

import argparse
import os
import sys

sys.path.insert(0, "..") 

from src.data_loader import load_daily_data
from src.indicators import add_all_indicators
from src import strategies as strat
from src.backtest import run_backtest
from src.metrics import metrics_table, format_metrics_table
from src import visualize as viz
from src.report import build_report, CHART_CONFIG

HERE = os.path.dirname(os.path.abspath(__file__))
HW2 = os.path.dirname(HERE)
CHARTS_DIR = os.path.join(HW2, "charts")
REPORT_DIR = os.path.join(HW2, "report")


def parse_args():
    p = argparse.ArgumentParser(description="HW2 strategy backtester")
    p.add_argument("--ticker", default="SPY", help="Ticker symbol (default SPY)")
    p.add_argument("--years", type=float, default=6.0,
                   help="Years of history if start/end not given (default 6)")
    p.add_argument("--start", default=None, help="Start date YYYY-MM-DD")
    p.add_argument("--end", default=None, help="End date YYYY-MM-DD")
    p.add_argument("--capital", type=float, default=100_000.0,
                   help="Initial capital (default 100000)")
    p.add_argument("--cost", type=float, default=0.0005,
                   help="Proportional cost per trade (default 5 bps)")
    p.add_argument("--risk-free", type=float, default=0.0,
                   help="Annual risk-free rate for Sharpe/Sortino (default 0)")
    return p.parse_args()


def main():
    args = parse_args()
    ticker = args.ticker.upper().strip()
    os.makedirs(CHARTS_DIR, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)

    print(f"► Downloading daily data for {ticker} …")
    df = load_daily_data(ticker, years=args.years, start=args.start, end=args.end)
    print(f"  {len(df)} bars  {df.index[0].date()} → {df.index[-1].date()}")

    print("► Computing indicators …")
    ind = add_all_indicators(df)

    print("► Running strategies …")
    results = {}
    for name, fn in strat.STRATEGIES.items():
        pos = fn(ind)
        results[name] = run_backtest(
            df, pos, name=name,
            initial_capital=args.capital, cost_per_trade=args.cost)
        print(f"    {name:16s} trades={len(results[name].trades):3d} "
              f"final=${results[name].final_value:,.0f}")

    table = metrics_table(results, risk_free=args.risk_free)
    print("\n=== Performance Comparison ===")
    print(format_metrics_table(table).to_string())

    print("\n► Saving charts …")
    viz.plot_equity_curves(
        results, title=f"Equity Curve Comparison — {ticker}",
        save_path=os.path.join(CHARTS_DIR, "equity_curves.png"))
    viz.plot_drawdowns(
        results, title=f"Drawdown Comparison — {ticker}",
        save_path=os.path.join(CHARTS_DIR, "drawdowns.png"))
    for name in ["Trend Following", "Mean Reversion", "Custom"]:
        cfg = CHART_CONFIG[name]
        fname = f"price_{name.lower().replace(' ', '_')}.png"
        viz.plot_price_signals(
            ind, results[name], title=f"{name} — {ticker}",
            overlays=cfg["overlays"], lower=cfg["lower"],
            save_path=os.path.join(CHARTS_DIR, fname))
    print(f"  charts → {CHARTS_DIR}")

    print("► Building PDF report …")
    pdf_path = os.path.join(REPORT_DIR, f"HW2_Report_{ticker}.pdf")
    build_report(pdf_path, ticker, ind, results, risk_free=args.risk_free)
    print(f"  report → {pdf_path}")

    table.to_csv(os.path.join(REPORT_DIR, f"metrics_{ticker}.csv"))
    print("✓ Done.")


if __name__ == "__main__":
    main()
