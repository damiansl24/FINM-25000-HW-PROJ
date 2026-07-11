"""Historical bar backfill from Alpaca into SQLite (daily for signals/backtest,
minute for recent context). Idempotent: re-running only inserts missing rows.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from core.models import Bar
from core.retry import with_retry
from data import store

log = logging.getLogger(__name__)

_TIMEFRAMES = {"1Day": TimeFrame.Day, "1Min": TimeFrame.Minute}


def _fetch_bars(client: StockHistoricalDataClient, symbols: list[str], timeframe: str,
                start: datetime, end: datetime | None, feed: str) -> list[Bar]:
    request = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=_TIMEFRAMES[timeframe],
        start=start,
        end=end,
        feed=feed,
    )
    barset = with_retry(lambda: client.get_stock_bars(request),
                        what=f"get_stock_bars {timeframe}")
    out: list[Bar] = []
    for symbol, bars in barset.data.items():
        for b in bars:
            out.append(Bar(symbol, timeframe, b.timestamp, b.open, b.high, b.low,
                           b.close, b.volume))
    return out


def backfill_daily(client, conn, symbols: list[str], start: datetime,
                   end: datetime | None = None, feed: str = "iex") -> int:
    bars = _fetch_bars(client, symbols, "1Day", start, end, feed)
    n = store.insert_bars(conn, bars)
    log.info("daily backfill: %d bars fetched, %d new rows", len(bars), n)
    return n


def backfill_minute(client, conn, symbols: list[str], days: int = 3,
                    feed: str = "iex") -> int:
    start = datetime.now(timezone.utc) - timedelta(days=days)
    bars = _fetch_bars(client, symbols, "1Min", start, None, feed)
    n = store.insert_bars(conn, bars)
    log.info("minute backfill: %d bars fetched, %d new rows", len(bars), n)
    return n


def ensure_daily_history(client, conn, symbols: list[str], min_days: int,
                         feed: str = "iex") -> None:
    """Backfill enough daily history for the momentum lookback if missing."""
    closes = store.get_daily_closes(conn, symbols)
    if len(closes) >= min_days and not closes.tail(min_days).isna().any().any():
        return
    start = datetime.now(timezone.utc) - timedelta(days=int(min_days * 2) + 30)
    backfill_daily(client, conn, symbols, start, feed=feed)
