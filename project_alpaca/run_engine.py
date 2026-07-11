"""Live paper-trading engine entrypoint.

Usage (from project_alpaca/, with .env configured):
    python run_engine.py

Run the dashboard alongside it in another terminal:
    python -m streamlit run ui/app.py
"""
from __future__ import annotations

import logging

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.trading.client import TradingClient

from core.config import load_alpaca_keys, load_config
from core.db import get_conn
from core.logging_setup import setup_logging
from data.history import ensure_daily_history
from data.poller import Poller
from engine.engine import Engine
from execution.alpaca_exec import AlpacaExecutionClient

log = logging.getLogger(__name__)


def main() -> None:
    setup_logging("engine.log")
    cfg = load_config()
    key, secret = load_alpaca_keys()

    trading = TradingClient(key, secret, paper=True)  # paper trading ONLY
    account = trading.get_account()
    log.info("connected to paper account %s -- equity %s, shorting_enabled=%s",
             account.account_number, account.equity, account.shorting_enabled)

    data_client = StockHistoricalDataClient(key, secret)
    conn = get_conn(cfg.data.db_path)
    ensure_daily_history(
        data_client, conn, cfg.universe,
        min_days=cfg.strategy.lookback_days + cfg.strategy.skip_days + 5,
        feed=cfg.data.feed,
    )

    engine = Engine(
        base_cfg=cfg,
        conn=conn,
        executor=AlpacaExecutionClient(trading),
        poller=Poller(data_client, conn, cfg.universe, feed=cfg.data.feed),
        trading_client=trading,
    )
    engine.run()


if __name__ == "__main__":
    main()
