"""Download hourly crypto history, run the shared strategy, and report results."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd
from alpaca.data.historical import CryptoHistoricalDataClient

from backtest.backtester import run_backtest
from core.config import load_config, load_optional_alpaca_keys
from core.db import PROJECT_ROOT, get_conn
from core.logging_setup import setup_logging
from data import store
from data.history import backfill_timeframe

log = logging.getLogger(__name__)


def _parse_utc(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Northstar hourly crypto backtest")
    parser.add_argument("--days", type=int, default=180, help="history depth when --start is omitted")
    parser.add_argument("--start", default=None, help="first trading timestamp/date")
    parser.add_argument("--end", default=None, help="last timestamp/date (default: now)")
    parser.add_argument("--config", default=None, help="path to config.yaml")
    parser.add_argument("--offline", action="store_true", help="use only bars already in SQLite")
    parser.add_argument("--no-plot", action="store_true", help="skip backtest_equity.png")
    args = parser.parse_args()

    setup_logging("backtest.log")
    cfg = load_config(args.config)
    now = datetime.now(timezone.utc)
    end = _parse_utc(args.end, now)
    start = _parse_utc(args.start, end - timedelta(days=args.days))
    warmup_hours = max(
        cfg.strategy.slow_window,
        cfg.strategy.momentum_window + 1,
        cfg.strategy.volatility_window + 1,
        cfg.strategy.regime_window,
    ) + 4
    fetch_start = start - timedelta(hours=warmup_hours)

    conn = get_conn(cfg.data.db_path)
    if not args.offline:
        key, secret = load_optional_alpaca_keys()
        client = (
            CryptoHistoricalDataClient(key, secret)
            if key and secret
            else CryptoHistoricalDataClient()
        )
        log.info("downloading Alpaca crypto bars from %s to %s", fetch_start, end)
        backfill_timeframe(
            client,
            conn,
            cfg.universe,
            cfg.data.signal_timeframe,
            fetch_start,
            end,
            cfg.data.feed,
        )

    for table in ("signals", "orders", "equity_snapshots"):
        conn.execute(f"DELETE FROM {table} WHERE mode='backtest'")
    conn.commit()

    closes = store.get_closes(conn, cfg.universe, cfg.data.signal_timeframe, end)
    opens = store.get_opens(conn, cfg.universe, cfg.data.signal_timeframe, end)
    closes = closes[closes.index >= pd.Timestamp(fetch_start)]
    opens = opens.reindex(closes.index)
    if closes.empty:
        sys.exit("No hourly crypto bars available. Run scripts/backfill.py first.")

    result = run_backtest(closes, opens, cfg, conn=conn, trade_start=start)
    print(f"\n=== Crypto backtest ({result.equity.index[0]} to {result.equity.index[-1]}) ===")
    print(result.report.summary())
    if result.killed_on:
        print(f"NOTE: daily-loss kill switch halted the test at {result.killed_on}")
    if result.rejected_orders:
        print(f"Rejected/blocked orders: {len(result.rejected_orders)}")

    if not args.no_plot:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(11, 5.5))
        result.equity.plot(ax=ax, color="#0b6e69", linewidth=1.8)
        ax.set_title("Northstar Crypto - hourly trend strategy")
        ax.set_ylabel("Paper equity ($)")
        ax.grid(True, alpha=0.2)
        fig.tight_layout()
        output = PROJECT_ROOT / "backtest_equity.png"
        fig.savefig(output, dpi=150)
        print(f"Equity curve saved to {output}")


if __name__ == "__main__":
    main()
