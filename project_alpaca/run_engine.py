"""Start the 24/7 Alpaca crypto paper-trading engine."""
from __future__ import annotations

import argparse
import logging

from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.trading.client import TradingClient

from core.config import load_alpaca_keys, load_config
from core.db import get_conn
from core.logging_setup import setup_logging
from data.history import ensure_signal_history
from data.poller import Poller
from engine.engine import Engine
from execution.alpaca_exec import AlpacaExecutionClient

log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Northstar Crypto on Alpaca paper")
    parser.add_argument("--once", action="store_true", help="run one engine cycle and exit")
    args = parser.parse_args()

    setup_logging("engine.log")
    cfg = load_config()
    key, secret = load_alpaca_keys()
    trading = TradingClient(key, secret, paper=True)
    account = trading.get_account()
    if bool(account.trading_blocked):
        raise RuntimeError("Alpaca paper account is trading-blocked")
    log.info("connected to Alpaca PAPER account with equity %s", account.equity)

    data_client = CryptoHistoricalDataClient(key, secret)
    conn = get_conn(cfg.data.db_path)
    minimum_bars = max(
        cfg.strategy.slow_window,
        cfg.strategy.momentum_window + 1,
        cfg.strategy.volatility_window + 1,
        cfg.strategy.regime_window,
    ) + 2
    ensure_signal_history(
        data_client,
        conn,
        cfg.universe,
        min_bars=minimum_bars,
        history_days=cfg.data.history_days,
        timeframe=cfg.data.signal_timeframe,
        feed=cfg.data.feed,
    )

    executor = AlpacaExecutionClient(trading, cfg.universe)
    poller = Poller(
        data_client,
        conn,
        cfg.universe,
        live_timeframe=cfg.data.live_timeframe,
        signal_timeframe=cfg.data.signal_timeframe,
        feed=cfg.data.feed,
    )
    Engine(cfg, conn, executor, poller).run(once=args.once)


if __name__ == "__main__":
    main()
