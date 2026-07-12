"""24/7 Alpaca crypto polling for live minute prices and hourly signal bars."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from alpaca.data.historical import CryptoHistoricalDataClient

from data import store
from data.history import _fetch_bars

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PollResult:
    minute_bars: int = 0
    hourly_bars: int = 0
    latest_ts: datetime | None = None
    errors: tuple[str, ...] = ()
    live_ok: bool = False


class Poller:
    def __init__(
        self,
        client: CryptoHistoricalDataClient,
        conn,
        symbols: list[str],
        live_timeframe: str = "1Min",
        signal_timeframe: str = "1Hour",
        feed: str = "us",
    ):
        self.client = client
        self.conn = conn
        self.symbols = symbols
        self.live_timeframe = live_timeframe
        self.signal_timeframe = signal_timeframe
        self.feed = feed

    def poll_once(self) -> PollResult:
        minute_count, minute_latest, minute_error = self._poll_timeframe(
            self.live_timeframe, timedelta(minutes=10), timedelta(minutes=2)
        )
        hour_count, hour_latest, hour_error = self._poll_timeframe(
            self.signal_timeframe, timedelta(hours=3), timedelta(hours=2)
        )
        latest = max(
            (value for value in (minute_latest, hour_latest) if value is not None),
            default=None,
        )
        errors = tuple(error for error in (minute_error, hour_error) if error)
        if minute_count or hour_count:
            log.info(
                "poll stored %d minute and %d hourly bars (latest %s)",
                minute_count,
                hour_count,
                latest.isoformat() if latest else "n/a",
            )
        return PollResult(
            minute_bars=minute_count,
            hourly_bars=hour_count,
            latest_ts=latest,
            errors=errors,
            live_ok=minute_error is None,
        )

    def _poll_timeframe(
        self, timeframe: str, initial_lookback: timedelta, overlap: timedelta
    ) -> tuple[int, datetime | None, str | None]:
        last_seen = [
            timestamp
            for symbol in self.symbols
            if (timestamp := store.last_bar_ts(self.conn, symbol, timeframe)) is not None
        ]
        start = (
            min(last_seen) - overlap
            if last_seen
            else datetime.now(timezone.utc) - initial_lookback
        )
        try:
            bars = _fetch_bars(
                self.client,
                self.symbols,
                timeframe,
                start,
                feed=self.feed,
            )
        except Exception as exc:  # transient gaps are handled by the stale-data gate
            message = f"{timeframe} poll failed: {exc}"
            log.error(message)
            return 0, None, message
        count = store.insert_bars(self.conn, bars)
        latest = max((bar.ts for bar in bars), default=None)
        return count, latest, None
