"""
Historical daily OHLCV retrieval from the Alpaca Market Data API.

Extends the hw1 data-connector idea to *daily* bars over multi-year windows,
which is what the HW2 backtesting engine needs.
"""

from datetime import datetime, timedelta

import pandas as pd
from pandas import DataFrame

from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from src.get_keys import main

# Load + validate keys once at import time (mirrors hw1's data_connector_module).
api_key, secret_key = main()  # type: ignore


def load_daily_data(symbol: str,
                    years: float = 5.0,
                    start: str | None = None,
                    end: str | None = None) -> DataFrame:
    """
    Download daily OHLCV bars for a single ticker and return a clean DataFrame.

    Parameters
    ----------
    symbol : str
        Ticker to download, e.g. "AAPL", "SPY", "QQQ", "NVDA".
    years : float
        How many years of history to pull, counting back from today. Ignored if
        both ``start`` and ``end`` are provided. Defaults to 5 (HW2 minimum).
    start, end : str | None
        Optional explicit ``YYYY-MM-DD`` window. If omitted, the window is
        ``today - years`` … ``today``.

    Returns
    -------
    DataFrame
        Indexed by timezone-naive daily ``DatetimeIndex`` with columns
        ``open, high, low, close, volume`` (plus ``trade_count``/``vwap`` when
        Alpaca returns them). Sorted ascending, duplicates dropped.
    """
    symbol = symbol.upper().strip()

    if end is None:
        end_dt = datetime.now()
    else:
        end_dt = datetime.strptime(end, "%Y-%m-%d")

    if start is None:
        start_dt = end_dt - timedelta(days=int(round(years * 365.25)))
    else:
        start_dt = datetime.strptime(start, "%Y-%m-%d")

    client = StockHistoricalDataClient(api_key=api_key, secret_key=secret_key)
    request_params = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,  # type: ignore
        start=start_dt,
        end=end_dt,
    )
    bars = client.get_stock_bars(request_params=request_params)
    df: DataFrame = bars.df  # type: ignore

    if df is None or df.empty:
        raise ValueError(f"No data returned for '{symbol}'. Check the ticker/date range.")

    # bars.df comes back with a (symbol, timestamp) MultiIndex — flatten to just dates.
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(symbol, level="symbol")

    df.index = pd.to_datetime(df.index)
    # Drop intraday tz info so the index is plain calendar days.
    if df.index.tz is not None:
        df.index = df.index.tz_convert(None)
    df.index.name = "date"

    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df
