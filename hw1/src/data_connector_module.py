from src import exceptions as ex
import pandas as pd
from pandas import DataFrame
from src.get_keys import main
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from datetime import datetime


# Import keys for testing
api_key, secret_key = main() # type: ignore

# Connect to alpaca market data API

def load_historical_data(sym: str | list[str], min_rez: int, start: str, end: str) -> DataFrame:
    '''
    Connects to Alpaca market data API and loads historical data.

    Parameters:
    sym: a string or list of strings, for tickers that data will be gathered for.
    min_rez: either 1 or 5 minute resolution for historical data frames. 
    start: start date
    end: end date
    '''
    start_dt = datetime.strptime(start, '%Y-%m-%d')
    end_dt = datetime.strptime(end, '%Y-%m-%d')
    client = StockHistoricalDataClient(api_key=api_key, secret_key=secret_key)
    request_params = StockBarsRequest(symbol_or_symbols=sym,
                                      timeframe=TimeFrame(min_rez, TimeFrameUnit.Minute), # type: ignore
                                      start=start_dt,
                                      end=end_dt
                                      )
    bars = client.get_stock_bars(request_params=request_params)

    return bars.df # type: ignore