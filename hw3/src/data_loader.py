"""Alpaca market-data retrieval: daily OHLCV into a pandas DataFrame."""
from datetime import datetime, timedelta

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed

from . import config
from .get_keys import get_alpaca_keys, DATA_FEED
from .exceptions import NoDataError


def _feed():
    return DataFeed.SIP if DATA_FEED == "sip" else DataFeed.IEX


def get_daily_ohlcv(ticker: str, years: int = config.YEARS_OF_DATA) -> pd.DataFrame:
    """Download `years` of daily OHLCV bars for `ticker` from Alpaca.

    Returns a DataFrame indexed by date with columns:
    open, high, low, close, volume (and trade_count / vwap when provided).
    """
    key, secret = get_alpaca_keys()
    client = StockHistoricalDataClient(key, secret)

    # Alpaca free (IEX) data cannot include the most recent ~15 minutes; a small
    # end buffer avoids "subscription does not permit" errors when run intraday.
    end = datetime.now() - timedelta(minutes=20)
    start = end - timedelta(days=int(years * 365.25) + 5)

    request = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        feed=_feed(),
    )
    df = client.get_stock_bars(request).df

    if df is None or df.empty:
        raise NoDataError(f"No data returned for {ticker}. Check the ticker and data feed.")

    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(ticker, level="symbol")

    df = df.copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "date"
    df = df[~df.index.duplicated(keep="last")].sort_index()

    keep = [c for c in ["open", "high", "low", "close", "volume", "trade_count", "vwap"] if c in df.columns]
    return df[keep]
