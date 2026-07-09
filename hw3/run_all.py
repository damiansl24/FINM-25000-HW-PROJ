"""One-command entry point: run the full backtest pipeline, then the paper trade.

    python run_all.py                 # default ticker (AAPL), no live order
    python run_all.py NVDA            # backtest NVDA
    python run_all.py NVDA --trade    # backtest, then submit today's real signal
    python run_all.py NVDA --demo     # backtest, then force one BUY for the demo/video

*** PAPER TRADING ONLY — NO REAL MONEY IS USED. ***
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import config
from scripts.run_backtest import run_pipeline
from scripts.run_paper_trade import submit_paper_trade


def main():
    parser = argparse.ArgumentParser(description="Run backtest and (optionally) a paper trade.")
    parser.add_argument("ticker", nargs="?", default=config.DEFAULT_TICKER, help="Ticker symbol")
    parser.add_argument("--trade", action="store_true", help="Submit a paper order from today's signal")
    parser.add_argument("--demo", action="store_true", help="Force a small BUY (implies --trade)")
    parser.add_argument("--allocation", type=float, default=0.20, help="Fraction of buying power on a long")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    run_pipeline(ticker)

    if args.trade or args.demo:
        print("\n" + "=" * 60)
        submit_paper_trade(ticker=ticker, allocation=args.allocation, demo=args.demo)
    else:
        print("\nBacktest complete. Add --trade (or --demo) to submit a PAPER order.")


if __name__ == "__main__":
    main()
