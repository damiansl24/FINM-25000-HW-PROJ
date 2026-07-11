"""One-shot backfill CLI: load historical bars into SQLite.

Usage (from project_alpaca/):
    python scripts/backfill.py                 # ~1.5y daily + 3d minute bars
    python scripts/backfill.py --days 900      # more daily history
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alpaca.data.historical import StockHistoricalDataClient

from core.config import load_alpaca_keys, load_config
from core.db import get_conn
from core.logging_setup import setup_logging
from data.history import backfill_daily, backfill_minute


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Alpaca bars into SQLite")
    parser.add_argument("--days", type=int, default=550, help="daily-bar history depth")
    parser.add_argument("--minute-days", type=int, default=3, help="minute-bar history depth")
    parser.add_argument("--config", default=None, help="path to config.yaml")
    args = parser.parse_args()

    setup_logging("backfill.log")
    cfg = load_config(args.config)
    key, secret = load_alpaca_keys()
    client = StockHistoricalDataClient(key, secret)
    conn = get_conn(cfg.data.db_path)

    start = datetime.now(timezone.utc) - timedelta(days=args.days)
    n_daily = backfill_daily(client, conn, cfg.universe, start, feed=cfg.data.feed)
    n_min = backfill_minute(client, conn, cfg.universe, days=args.minute_days, feed=cfg.data.feed)
    print(f"Backfill complete: {n_daily} new daily rows, {n_min} new minute rows.")


if __name__ == "__main__":
    main()
