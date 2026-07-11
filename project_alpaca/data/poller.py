"""Live data pipeline: polls Alpaca for the latest minute bars (one
multi-symbol REST request per cycle) and appends them to SQLite.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from alpaca.data.historical import StockHistoricalDataClient

from data import store
from data.history import _fetch_bars

log = logging.getLogger(__name__)

# On the first poll (empty db) look back this far for minute bars.
INITIAL_LOOKBACK = timedelta(minutes=30)


class Poller:
    def __init__(self, client: StockHistoricalDataClient, conn, symbols: list[str],
                 feed: str = "iex"):
        self.client = client
        self.conn = conn
        self.symbols = symbols
        self.feed = feed

    def poll_once(self) -> int:
        """Fetch minute bars since the last stored bar; returns new row count."""
        last_seen = [
            ts for s in self.symbols
            if (ts := store.last_bar_ts(self.conn, s, "1Min")) is not None
        ]
        if last_seen:
            # Overlap one minute so a partially-delivered bar gets re-fetched;
            # INSERT OR IGNORE dedupes.
            start = min(last_seen) - timedelta(minutes=1)
        else:
            start = datetime.now(timezone.utc) - INITIAL_LOOKBACK
        try:
            bars = _fetch_bars(self.client, self.symbols, "1Min", start, None, self.feed)
        except Exception as exc:  # transient failures self-heal next cycle
            log.error("poll failed, will retry next cycle: %s", exc)
            return 0
        n = store.insert_bars(self.conn, bars)
        if n:
            latest = max(b.ts for b in bars)
            log.info("poll: %d new minute bars (latest %s)", n, latest.isoformat())
        return n
