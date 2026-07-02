from __future__ import annotations

from datetime import datetime

import pandas as pd
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from src.get_keys import load_alpaca_keys


def load_daily_ohlcv(symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
    """Download daily OHLCV bars from Alpaca and return a clean DataFrame."""
    api_key, secret_key = load_alpaca_keys()
    client = StockHistoricalDataClient(api_key=api_key, secret_key=secret_key)

    request = StockBarsRequest(
        symbol_or_symbols=symbol.upper(),
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
    )
    bars = client.get_stock_bars(request).df

    if bars.empty:
        raise ValueError(f"No daily bars were returned for ticker {symbol.upper()}.")

    if isinstance(bars.index, pd.MultiIndex):
        bars = bars.xs(symbol.upper(), level="symbol")

    data = bars.copy()
    data.index = pd.to_datetime(data.index).tz_localize(None)
    data = data.sort_index()
    data.index.name = "date"
    return data
