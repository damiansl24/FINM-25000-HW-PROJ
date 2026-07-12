"""Historical crypto bar retrieval from Alpaca into SQLite."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from alpaca.data.enums import CryptoFeed
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame

from core.models import Bar
from core.retry import with_retry
from core.symbols import canonical_pair
from data import store

log = logging.getLogger(__name__)

TIMEFRAMES = {
    "1Min": TimeFrame.Minute,
    "1Hour": TimeFrame.Hour,
    "1Day": TimeFrame.Day,
}


def _crypto_feed(feed: str) -> CryptoFeed:
    try:
        return CryptoFeed(feed.lower())
    except ValueError as exc:
        raise ValueError(f"unsupported Alpaca crypto feed {feed!r}") from exc


def _fetch_bars(
    client: CryptoHistoricalDataClient,
    symbols: list[str],
    timeframe: str,
    start: datetime,
    end: datetime | None = None,
    feed: str = "us",
) -> list[Bar]:
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"unsupported timeframe {timeframe}")
    request = CryptoBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TIMEFRAMES[timeframe],
        start=start,
        end=end,
    )
    barset = with_retry(
        lambda: client.get_crypto_bars(request, feed=_crypto_feed(feed)),
        what=f"get_crypto_bars {timeframe}",
    )
    output: list[Bar] = []
    for symbol, bars in barset.data.items():
        pair = canonical_pair(symbol, symbols)
        for bar in bars:
            output.append(
                Bar(
                    symbol=pair,
                    timeframe=timeframe,
                    ts=bar.timestamp,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=float(bar.volume),
                )
            )
    return output


def backfill_timeframe(
    client,
    conn,
    symbols: list[str],
    timeframe: str,
    start: datetime,
    end: datetime | None = None,
    feed: str = "us",
) -> int:
    bars = _fetch_bars(client, symbols, timeframe, start, end, feed)
    processed = store.insert_bars(conn, bars)
    log.info("%s backfill: %d bars stored", timeframe, processed)
    return processed


def ensure_signal_history(
    client,
    conn,
    symbols: list[str],
    min_bars: int,
    history_days: int,
    timeframe: str = "1Hour",
    feed: str = "us",
) -> None:
    closes = store.get_closes(conn, symbols, timeframe)
    enough = all(closes[symbol].count() >= min_bars for symbol in symbols) if not closes.empty else False
    if enough:
        return
    minimum_days = int(min_bars / 24) + 3
    start = datetime.now(timezone.utc) - timedelta(days=max(history_days, minimum_days))
    backfill_timeframe(client, conn, symbols, timeframe, start, feed=feed)


def backfill_recent_minutes(
    client,
    conn,
    symbols: list[str],
    days: int = 1,
    feed: str = "us",
) -> int:
    start = datetime.now(timezone.utc) - timedelta(days=days)
    return backfill_timeframe(client, conn, symbols, "1Min", start, feed=feed)

