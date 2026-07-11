"""Backtest entrypoint.

Usage (from project_alpaca/):
    python run_backtest.py --start 2025-01-01 --end 2026-06-30

Requires daily bars in the database (run scripts/backfill.py first; this
script backfills automatically if Alpaca keys are available in .env).
Results print to the console, an equity-curve PNG is saved, and signals/
orders/equity land in SQLite with mode='backtest' so the UI can show them.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

from backtest.backtester import run_backtest
from core.config import load_config
from core.db import PROJECT_ROOT, get_conn
from core.logging_setup import setup_logging
from data import store

log = logging.getLogger(__name__)


def _ensure_history(conn, cfg, start: str) -> None:
    closes = store.get_daily_closes(conn, cfg.universe)
    warmup_days = cfg.strategy.lookback_days + cfg.strategy.skip_days + 5
    if not closes.empty and closes.index[0] <= start and len(closes) > warmup_days:
        return
    log.info("daily history missing or too short -- backfilling from Alpaca")
    from alpaca.data.historical import StockHistoricalDataClient

    from core.config import load_alpaca_keys
    from data.history import backfill_daily

    key, secret = load_alpaca_keys()
    client = StockHistoricalDataClient(key, secret)
    fetch_start = (datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
                   - timedelta(days=warmup_days * 2 + 30))
    backfill_daily(client, conn, cfg.universe, fetch_start, feed=cfg.data.feed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the momentum backtest")
    parser.add_argument("--start", default="2025-01-01", help="first trading date")
    parser.add_argument("--end", default=None, help="last trading date (default: today)")
    parser.add_argument("--config", default=None, help="path to config.yaml")
    parser.add_argument("--no-plot", action="store_true", help="skip the equity PNG")
    args = parser.parse_args()

    setup_logging("backtest.log")
    cfg = load_config(args.config)
    conn = get_conn(cfg.data.db_path)
    _ensure_history(conn, cfg, args.start)

    # Fresh slate for this run's backtest rows (live rows are untouched).
    for table in ("signals", "orders", "equity_snapshots"):
        conn.execute(f"DELETE FROM {table} WHERE mode='backtest'")
    conn.commit()

    closes = store.get_daily_closes(conn, cfg.universe, end_date=args.end)
    opens = store.get_daily_opens(conn, cfg.universe, end_date=args.end)
    if closes.empty:
        sys.exit("No daily bars in the database -- run scripts/backfill.py first.")

    result = run_backtest(closes, opens, cfg, conn=conn, trade_start=args.start)

    print("\n=== Backtest results "
          f"({result.equity.index[0]} to {result.equity.index[-1]}) ===")
    print(result.report.summary())
    if result.killed_on:
        print(f"NOTE: daily-loss kill switch halted the backtest on {result.killed_on}")
    if result.rejected_orders:
        print(f"Rejected/blocked orders: {len(result.rejected_orders)} "
              "(see orders table for reasons)")

    if not args.no_plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 5))
        result.equity.plot(ax=ax, color="tab:blue")
        ax.set_title("Momentum long-short backtest -- equity curve")
        ax.set_ylabel("Equity ($)")
        ax.grid(True, alpha=0.3)
        step = max(1, len(result.equity) // 8)
        ax.set_xticks(range(0, len(result.equity), step))
        fig.autofmt_xdate()
        out = PROJECT_ROOT / "backtest_equity.png"
        fig.tight_layout()
        fig.savefig(out, dpi=120)
        print(f"Equity curve saved to {out}")


if __name__ == "__main__":
    main()
