"""Live PAPER-TRADING demo.

Pipeline: fetch latest data -> compute features -> apply saved PCA -> ML signal
-> submit a PAPER order.

    Long  (P(up) > 0.60)  -> BUY  (open/keep a long position)
    Flat  (P(up) <= 0.60) -> SELL (close the position)

    python scripts/run_paper_trade.py                # act on today's real signal
    python scripts/run_paper_trade.py --ticker NVDA  # override ticker
    python scripts/run_paper_trade.py --demo         # force a small BUY for the demo/video

*** PAPER TRADING ONLY — NO REAL MONEY IS USED. ***
"""
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import joblib
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

from src import config
from src.get_keys import get_alpaca_keys
from src.data_loader import get_daily_ohlcv
from src.indicators import make_dataset
from src.strategies import train_signal_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(config.OUTPUT_DIR, "paper_trade.log")),
    ],
)
log = logging.getLogger("paper_trade")


def load_model(ticker_override=None):
    """Load the saved model; if a different ticker is requested, refit on the fly."""
    if os.path.exists(config.MODEL_PATH):
        bundle = joblib.load(config.MODEL_PATH)
        if ticker_override is None or ticker_override == bundle["ticker"]:
            return bundle["ticker"], bundle["trading_model"]

    ticker = ticker_override or config.DEFAULT_TICKER
    log.info("No saved model for %s — training a fresh pipeline...", ticker)
    X, y, _ = make_dataset(get_daily_ohlcv(ticker))
    return ticker, train_signal_model(X, y)


def latest_signal(ticker, tm):
    """Return (proba_up, signal_str, last_close, as_of_date) using the most recent bar."""
    X, _, feats = make_dataset(get_daily_ohlcv(ticker, years=2))
    proba = float(tm.predict_proba_up(X.iloc[[-1]])[0])
    signal = "LONG" if proba > config.SIGNAL_THRESHOLD else "FLAT"
    return proba, signal, float(feats["close"].iloc[-1]), feats.index[-1]


def submit_paper_trade(ticker=None, allocation=0.20, demo=False):
    get_alpaca_keys()  # fail fast with a clear message if keys are missing
    log.info("=== ALPACA PAPER TRADING — NO REAL MONEY IS USED ===")

    ticker, tm = load_model(ticker)
    proba, signal, last_close, asof = latest_signal(ticker, tm)
    log.info("Ticker=%s  as-of=%s  last_close=$%.2f", ticker, asof.date(), last_close)
    log.info("Model P(next-day up) = %.3f  ->  signal = %s (threshold %.2f)",
             proba, signal, config.SIGNAL_THRESHOLD)

    key, secret = get_alpaca_keys()
    trading = TradingClient(key, secret, paper=True)
    acct = trading.get_account()
    log.info("Account: status=%s  equity=$%s  buying_power=$%s  (PAPER)",
             acct.status, acct.equity, acct.buying_power)

    position_qty = 0.0
    try:
        pos = trading.get_open_position(ticker)
        position_qty = float(pos.qty)
        log.info("Current position: %s shares of %s (market value $%s)", pos.qty, ticker, pos.market_value)
    except Exception:
        log.info("Current position: none in %s", ticker)

    want_long = (signal == "LONG") or demo
    if demo and signal != "LONG":
        log.info("--demo set: forcing a BUY for demonstration despite a FLAT signal.")

    if want_long and position_qty == 0:
        notional = round(max(1.0, float(acct.buying_power) * allocation), 2)
        order = MarketOrderRequest(symbol=ticker, notional=notional,
                                   side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
        submitted = trading.submit_order(order)
        log.info("SUBMITTED BUY  %s  ~$%.2f notional  (order id %s, status %s)",
                 ticker, notional, submitted.id, submitted.status)
    elif not want_long and position_qty > 0:
        submitted = trading.close_position(ticker)
        log.info("SUBMITTED SELL (close position) %s  (order id %s, status %s)",
                 ticker, submitted.id, submitted.status)
    elif want_long and position_qty > 0:
        log.info("Signal LONG and already holding %s shares — no action (hold).", position_qty)
    else:
        log.info("Signal FLAT and no open position — no action.")

    log.info("Done. Dashboard: https://app.alpaca.markets/paper/dashboard/overview")
    log.info("*** This is PAPER TRADING ONLY — no real money is used. ***")


def main():
    parser = argparse.ArgumentParser(description="Alpaca paper-trading demo.")
    parser.add_argument("--ticker", help="Override ticker symbol")
    parser.add_argument("--allocation", type=float, default=0.20,
                        help="Fraction of buying power to deploy on a long (default 0.20)")
    parser.add_argument("--demo", action="store_true",
                        help="Force a small BUY so a paper trade executes for the demo/video")
    args = parser.parse_args()
    submit_paper_trade(ticker=args.ticker, allocation=args.allocation, demo=args.demo)


if __name__ == "__main__":
    main()
