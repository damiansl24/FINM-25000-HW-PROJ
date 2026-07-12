"""Backfill hourly strategy bars and recent minute bars from Alpaca crypto data."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alpaca.data.historical import CryptoHistoricalDataClient

from core.config import load_config, load_optional_alpaca_keys
from core.db import get_conn
from core.logging_setup import setup_logging
from data.history import backfill_recent_minutes, backfill_timeframe


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Alpaca crypto bars")
    parser.add_argument("--days", type=int, default=180, help="hourly history depth")
    parser.add_argument("--minute-days", type=int, default=1, help="minute history depth")
    parser.add_argument("--config", default=None, help="path to config.yaml")
    args = parser.parse_args()

    setup_logging("backfill.log")
    cfg = load_config(args.config)
    key, secret = load_optional_alpaca_keys()
    client = (
        CryptoHistoricalDataClient(key, secret)
        if key and secret
        else CryptoHistoricalDataClient()
    )
    conn = get_conn(cfg.data.db_path)
    start = datetime.now(timezone.utc) - timedelta(days=args.days)
    hourly = backfill_timeframe(
        client,
        conn,
        cfg.universe,
        cfg.data.signal_timeframe,
        start,
        feed=cfg.data.feed,
    )
    minutes = backfill_recent_minutes(
        client,
        conn,
        cfg.universe,
        days=args.minute_days,
        feed=cfg.data.feed,
    )
    print(f"Backfill complete: {hourly:,} hourly bars and {minutes:,} minute bars stored.")


if __name__ == "__main__":
    main()

